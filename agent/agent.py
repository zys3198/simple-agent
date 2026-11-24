import asyncio
import threading
from dataclasses import dataclass, field

from .config import gateway_config
from .llm import make_stream_fn
from .loop import AgentContext, AgentLoopConfig, TurnContext, agent_loop
from .messages import AssistantMessage, UserMessage, to_openai_messages
from .prompts import BASELINE_SYSTEM_PROMPT, build_system_prompt
from .skills import ROOT, Skill, load_skills
from .tools_builtin import BuiltinTools


@dataclass
class RunResult:
    question: str
    answer: str
    messages: list
    events: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    turns: int = 0
    # 留给调用方填，agent 不读也不认这里面的字段
    verification: dict = field(default_factory=dict)


class Agent:
    """通用 agent：循环、工具、技能。

    领域知识全在 skills 目录里，这一类只认工具与消息，不含任何具体领域的判断。
    """

    def __init__(
        self,
        model: str,
        max_turns: int = 12,
        tool_execution: str = "parallel",
        force_final_answer: bool = False,
    ):
        base_url, api_key = gateway_config()
        self.model = model
        self.max_turns = max_turns
        self.tool_execution = tool_execution
        self.force_final_answer = force_final_answer
        self.stream_fn = make_stream_fn(base_url, api_key)
        loaded = load_skills()
        self.skills: list[Skill] = loaded.skills
        self.skill_diagnostics = loaded.diagnostics
        # 同一个 context 反复用 → 多轮对话：上一轮的工具结果留在 messages 里，下一轮能接着问。
        self.context: AgentContext | None = None
        # 置位后，下一轮开始前停下来（中止只在轮次边界生效，不会切断正在跑的请求）
        self.cancelled: threading.Event | None = None
        self.turns_done = 0

    def reset(self) -> None:
        """开一轮新会话：清掉消息，工具重新按新上下文构建。"""
        self.context = None

    def _build(self) -> tuple[AgentContext, AgentLoopConfig]:
        self.turns_done = 0
        if self.context is None:
            tools = BuiltinTools(ROOT).as_tools()
            self.context = AgentContext(
                system_prompt=build_system_prompt(self.skills, [t.name for t in tools], str(ROOT)),
                tools=tools,
            )
        context = self.context
        config = AgentLoopConfig(
            model=self.model,
            stream_fn=self.stream_fn,
            tool_execution=self.tool_execution,
            should_stop_after_turn=self._turn_budget,
            cancelled=self._is_cancelled,
        )
        return context, config

    def _is_cancelled(self) -> bool:
        return self.cancelled is not None and self.cancelled.is_set()

    def _turn_budget(self, turn: TurnContext) -> str | None:
        """对应 pi 配置里的 shouldStopAfterTurn：轮次预算用完就停，避免无界循环。

        turn.new_messages 只是本圈新增的消息，拿它算不出总轮次，所以自己累加。
        """
        if self._is_cancelled():
            return "用户中止"
        self.turns_done += 1
        return f"达到轮次上限 {self.max_turns}" if self.turns_done >= self.max_turns else None

    async def ask(self, question: str, on_event=None) -> RunResult:
        context, config = self._build()
        events: list[dict] = []

        def sink(event: dict) -> None:
            events.append(event)
            if on_event:
                on_event(event)

        messages = await agent_loop(UserMessage(content=question), context, config, emit=sink)
        finished = messages[-1].role == "assistant" and bool(messages[-1].text)
        if self.force_final_answer and not finished and not self._is_cancelled():
            messages.append(await self._final_answer(context, events))
        answer = next((m.text for m in reversed(messages) if m.role == "assistant" and m.text), "")
        return RunResult(
            question=question,
            answer=answer,
            messages=messages,
            events=events,
            tool_calls=[
                {"tool": e["tool_name"], "args": e.get("args", {})}
                for e in events
                if e.get("type") == "tool_execution_start"
            ],
            turns=sum(1 for m in messages if m.role == "assistant"),
        )

    async def _final_answer(self, context: AgentContext, events: list[dict]) -> AssistantMessage:
        """轮次预算耗尽时收束：再要一次回复，但不给工具，逼它基于已有工具结果作答。"""
        context.messages.append(
            UserMessage(content="轮次预算已用完。不要调用工具，立刻按输出格式，用已有工具结果作答；拿不到的部分写进「缺口」。")
        )
        messages = [m for m in context.messages if m.role in ("user", "assistant", "toolResult")]
        message = await self.stream_fn(self.model, to_openai_messages(context.system_prompt, messages), [])
        context.messages.append(message)
        events.append({"type": "forced_final_answer"})
        return message

    async def ask_without_tools(self, question: str) -> RunResult:
        """对照组：同一个模型、同样的问题，但没有工具。"""
        wire = [{"role": "system", "content": BASELINE_SYSTEM_PROMPT}, {"role": "user", "content": question}]
        message: AssistantMessage = await self.stream_fn(self.model, wire, [])
        return RunResult(question=question, answer=message.text, messages=[message], turns=1)


def run(coro):
    """notebook 里直接跑协程。"""
    return asyncio.run(coro)
