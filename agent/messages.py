from dataclasses import dataclass, field
from typing import Literal

# AgentMessage：agent 内部的消息类型。对应 pi packages/agent/src/types.ts 的 AgentMessage。
# 与教材第 6 章「两层消息」一致：内部消息 -> LLM 消息的转换只在调用模型前做一次。


@dataclass
class TextContent:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolCall:
    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict = field(default_factory=dict)
    arguments_error: str | None = None


@dataclass
class UserMessage:
    content: str
    role: Literal["user"] = "user"
    timestamp: float = 0.0


@dataclass
class AssistantMessage:
    content: list[TextContent | ToolCall]
    # pi 的 stopReason：end / toolUse / length / error / aborted
    stop_reason: Literal["end", "toolUse", "length", "error"] = "end"
    error_message: str | None = None
    role: Literal["assistant"] = "assistant"
    timestamp: float = 0.0
    # 模型的思考过程（网关的 reasoning_content 字段），不参与工具协议，只用于展示
    reasoning: str | None = None
    # 网关回的 usage（prompt_tokens / completion_tokens 等），没开 include_usage 就是 None
    usage: dict | None = None

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.content if c.type == "text")

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [c for c in self.content if c.type == "toolCall"]


@dataclass
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    role: Literal["toolResult"] = "toolResult"
    timestamp: float = 0.0


AgentMessage = UserMessage | AssistantMessage | ToolResultMessage


def default_convert_to_llm(messages: list[AgentMessage]) -> list[AgentMessage]:
    """只保留模型认识的三类消息，丢掉 agent 内部状态消息。对应 pi 的 defaultConvertToLlm。"""
    return [m for m in messages if m.role in ("user", "assistant", "toolResult")]


def to_openai_messages(system_prompt: str, messages: list[AgentMessage]) -> list[dict]:
    """把内部消息翻译成 OpenAI chat/completions 的线格式。
    pi 里这一步拆成 convertToLlm + provider adapter，这里合成一个函数，因为只有一个 provider。"""
    wire: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m.role == "user":
            wire.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            entry: dict = {"role": "assistant", "content": m.text or None}
            if m.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {
                            "name": c.name,
                            "arguments": c.arguments_error or _dumps(c.arguments),
                        },
                    }
                    for c in m.tool_calls
                ]
            wire.append(entry)
        elif m.role == "toolResult":
            wire.append(
                {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
            )
    return wire


def _dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)
