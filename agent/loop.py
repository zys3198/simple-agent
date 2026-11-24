import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from .messages import (
    AgentMessage,
    AssistantMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    default_convert_to_llm,
    to_openai_messages,
)
from .tools import AgentTool, ToolResult, find_tool, validate_tool_arguments

# Agent Loop。对应 pi packages/agent/src/agent-loop.ts 的 runLoop 与 streamAssistantResponse。
# 保留：内层「调模型 -> 执行工具 -> 再调模型」循环、stopReason 硬停止、截断保护、
#       串行/并行工具执行、before/afterToolCall 钩子、turn 级事件、shouldStopAfterTurn 出口。
# 去掉：steering / follow-up 两级消息队列、上下文压缩、扩展系统（生医场景不需要）。


StreamFn = Callable[[str, list[dict], list[AgentTool], Callable], Awaitable[AssistantMessage]]


@dataclass
class AgentContext:
    system_prompt: str
    messages: list[AgentMessage] = field(default_factory=list)
    tools: list[AgentTool] = field(default_factory=list)


@dataclass
class TurnContext:
    message: AssistantMessage
    tool_results: list[ToolResultMessage]
    new_messages: list[AgentMessage]


@dataclass
class AfterToolCallContext:
    """对应 pi types.d.ts 的 AfterToolCallContext。"""

    tool_call: ToolCall
    args: dict
    result: ToolResult


@dataclass
class AgentLoopConfig:
    model: str
    stream_fn: StreamFn
    tool_execution: str = "parallel"
    should_stop_after_turn: Callable[[TurnContext], str | None] | None = None
    # 中止信号：每轮开始前、每次工具调用前都查一次，置位后尽快停
    cancelled: Callable[[], bool] | None = None
    before_tool_call: Callable[[AgentTool, dict], ToolResult | None] | None = None
    # 对应 pi 的 afterToolCall：执行完、发 tool_execution_end 之前调用，可覆盖 content / details / is_error / terminate
    after_tool_call: Callable[[AfterToolCallContext], dict | None] | None = None


async def emit_event(emit: Callable, event: dict) -> None:
    out = emit(event)
    if inspect.isawaitable(out):
        await out


async def agent_loop(
    prompt: UserMessage,
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[dict], object] = lambda event: None,
) -> list[AgentMessage]:
    prompt.timestamp = prompt.timestamp or time.time()
    context.messages.append(prompt)
    new_messages: list[AgentMessage] = [prompt]

    await emit_event(emit, {"type": "agent_start"})
    await emit_event(emit, {"type": "turn_start"})
    await emit_event(emit, {"type": "message_start", "message": prompt})
    await emit_event(emit, {"type": "message_end", "message": prompt})

    await run_loop(context, new_messages, config, emit)
    await emit_event(emit, {"type": "agent_end", "messages": new_messages})
    return new_messages


async def run_loop(context: AgentContext, new_messages: list[AgentMessage], config: AgentLoopConfig, emit: Callable) -> None:
    has_more_tool_calls = True
    first_turn = True

    while has_more_tool_calls:
        if config.cancelled and config.cancelled():
            await emit_event(emit, {"type": "loop_stop", "reason": "用户中止"})
            return
        if not first_turn:
            await emit_event(emit, {"type": "turn_start"})
        first_turn = False

        message = await stream_assistant_response(context, config, emit)
        new_messages.append(message)

        # 硬停止：模型调用失败或中止，不再进入下一轮
        if message.stop_reason in ("error", "aborted"):
            await emit_event(emit, {"type": "turn_end", "message": message, "tool_results": []})
            return

        tool_calls = message.tool_calls
        tool_results: list[ToolResultMessage] = []
        if tool_calls:
            # stop_reason == "length" 说明输出被截断，参数可能不完整，一律不执行
            if message.stop_reason == "length":
                tool_results = [_error_result(c, "输出被长度上限截断，参数可能不完整，请重新发起调用") for c in tool_calls]
            else:
                tool_results = await execute_tool_calls(context, message, config, emit)
            for result in tool_results:
                context.messages.append(result)
                new_messages.append(result)

        turn = TurnContext(message=message, tool_results=tool_results, new_messages=new_messages)
        await emit_event(emit, {"type": "turn_end", "message": message, "tool_results": tool_results})

        if config.should_stop_after_turn:
            reason = config.should_stop_after_turn(turn)
            if reason:
                await emit_event(emit, {"type": "loop_stop", "reason": reason})
                return

        # 上一轮有工具调用才有下一轮；没有工具调用就是自然结束
        has_more_tool_calls = bool(tool_calls)


async def stream_assistant_response(context: AgentContext, config: AgentLoopConfig, emit: Callable) -> AssistantMessage:
    llm_messages = default_convert_to_llm(context.messages)
    wire = to_openai_messages(context.system_prompt, llm_messages)
    await emit_event(
        emit,
        {
            "type": "request_start",
            "ts": time.time(),
            "model": config.model,
            "message_count": len(wire),
            # 给界面的上下文清单：每条只用角色、字数与开头一行，不把全文再传一遍
            "messages": [
                {
                    "role": m.get("role", "?"),
                    "chars": len(m.get("content") or ""),
                    "preview": " ".join(str(m.get("content") or "").split())[:60],
                }
                for m in wire
            ],
        },
    )

    async def forward(delta: dict) -> None:
        await emit_event(emit, delta)

    message = await config.stream_fn(config.model, wire, context.tools, forward)
    message.timestamp = time.time()
    await emit_event(emit, {"type": "message_start", "message": message})
    await emit_event(
        emit,
        {
            "type": "message_end",
            "ts": message.timestamp,
            "message": message,
            # 轨迹面板要的：字数、token、工具名、停因
            "summary": {
                "role": "assistant",
                "chars": len(message.text),
                "reasoning_chars": len(message.reasoning or ""),
                "tool_calls": [c.name for c in message.tool_calls],
                "stop_reason": message.stop_reason,
                "usage": message.usage,
            },
        },
    )
    return message


async def execute_tool_calls(
    context: AgentContext, message: AssistantMessage, config: AgentLoopConfig, emit: Callable
) -> list[ToolResultMessage]:
    calls = message.tool_calls
    sequential = config.tool_execution == "sequential" or any(
        (t := find_tool(context.tools, c.name)) is not None and t.execution_mode == "sequential" for c in calls
    )
    if sequential:
        return [await execute_one(context, c, config, emit) for c in calls]
    return list(await asyncio.gather(*(execute_one(context, c, config, emit) for c in calls)))


async def execute_one(context: AgentContext, call: ToolCall, config: AgentLoopConfig, emit: Callable) -> ToolResultMessage:
    started = time.time()
    if config.cancelled and config.cancelled():
        return ToolResultMessage(tool_call_id=call.id, tool_name=call.name, content="用户已中止，本次调用未执行", is_error=True)
    await emit_event(
        emit,
        {"type": "tool_execution_start", "ts": started, "tool_call_id": call.id, "tool_name": call.name, "args": call.arguments},
    )

    tool = find_tool(context.tools, call.name)
    result: ToolResult
    if call.arguments_error:
        result = ToolResult(content=f"参数不是合法 JSON：{call.arguments_error}", is_error=True)
    elif tool is None:
        result = ToolResult(content=f"没有名为 {call.name} 的工具，可用工具：{', '.join(t.name for t in context.tools)}", is_error=True)
    else:
        invalid = validate_tool_arguments(tool, call.arguments)
        if invalid:
            result = ToolResult(content=f"参数不合法：{invalid}", is_error=True)
        else:
            blocked = config.before_tool_call(tool, call.arguments) if config.before_tool_call else None
            if blocked is not None:
                result = blocked
            else:
                # 对应 pi agent-loop.js 的 catch：工具抛异常变成一条错误结果，循环继续，模型能改参数重试
                try:
                    result = await tool.execute_safely(call.arguments)
                except Exception as exc:  # noqa: BLE001 —— 工具抛任何异常都转成错误结果，循环不能因此中断
                    result = ToolResult(content=f"{type(exc).__name__}: {exc}", is_error=True)

    if config.after_tool_call:
        override = config.after_tool_call(AfterToolCallContext(tool_call=call, args=call.arguments, result=result))
        if override:
            result = replace(result, **override)

    await emit_event(
        emit,
        {"type": "tool_execution_end", "ts": time.time(), "ms": int((time.time() - started) * 1000),
         "tool_call_id": call.id, "tool_name": call.name,
         "is_error": result.is_error, "content": result.content},
    )
    return ToolResultMessage(tool_call_id=call.id, tool_name=call.name, content=result.content, is_error=result.is_error)


def _error_result(call: ToolCall, reason: str) -> ToolResultMessage:
    return ToolResultMessage(tool_call_id=call.id, tool_name=call.name, content=reason, is_error=True)
