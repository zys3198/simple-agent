import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

# 工具系统。对应 pi packages/agent/src/types.ts 的 AgentTool 与 pi-ai 的 toToolDeclaration。
# 关键点：工具的对外描述（JSON Schema）与执行体放在同一个对象上，模型看到的就是运行时可执行的。


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    # pi 的 terminate：为真时本批次工具执行完就结束 agent loop
    terminate: bool = False
    details: dict = field(default_factory=dict)


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    execute: Callable[[dict], ToolResult | Awaitable[ToolResult]]
    execution_mode: str = "parallel"  # sequential | parallel

    def execute_safely(self, args: dict) -> Awaitable[ToolResult]:
        return self._run(args)

    async def _run(self, args: dict) -> ToolResult:
        out = self.execute(args)
        if inspect.isawaitable(out):
            out = await out
        return out


def to_tool_declarations(tools: list[AgentTool]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def validate_tool_arguments(tool: AgentTool, args: dict) -> str | None:
    """按 JSON Schema 的必填项与顶层类型校验。返回错误描述，合法返回 None。
    对应 pi-ai 的 validateToolArguments：参数不合法的工具调用不执行，改成一条错误结果回给模型。"""
    props = tool.parameters.get("properties", {})
    for key in tool.parameters.get("required", []):
        if key not in args:
            return f"缺少必填参数 {key}"
    expected = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list}
    for key, value in args.items():
        if key not in props:
            return f"未知参数 {key}，允许的参数：{', '.join(props) or '无'}"
        want = props[key].get("type")
        if want in expected and not isinstance(value, expected[want]):
            return f"参数 {key} 应为 {want}，实际是 {type(value).__name__}"
    return None


def find_tool(tools: list[AgentTool], name: str) -> AgentTool | None:
    return next((t for t in tools if t.name == name), None)
