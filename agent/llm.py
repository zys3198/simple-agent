import asyncio
import json
import time
from collections.abc import Awaitable, Callable

import requests

from .messages import AssistantMessage, TextContent, ToolCall
from .tools import AgentTool, to_tool_declarations

# 模型接入层。对应 pi packages/ai 的 provider adapter 与 packages/agent/src/stream-fn.ts。
# 流式读 SSE：正文走 text_delta，模型的思考过程走 reasoning_delta，工具调用按 index 拼装。

RETRYABLE = (429, 500, 502, 503, 504)
DeltaFn = Callable[[dict], Awaitable[None]]


def make_stream_fn(base_url: str, api_key: str, timeout: int = 300, max_retries: int = 2, temperature: float = 0.2):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def stream_fn(
        model: str, wire_messages: list[dict], tools: list[AgentTool], on_delta: DeltaFn | None = None
    ) -> AssistantMessage:
        body = {
            "model": model,
            "messages": wire_messages,
            "temperature": temperature,
            "tools": to_tool_declarations(tools),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        last_error = ""
        for attempt in range(max_retries + 1):
            response = await asyncio.to_thread(
                lambda: requests.post(url, json=body, headers=headers, timeout=timeout, stream=True)
            )
            if response.status_code == 200:
                return await read_stream(response, on_delta)
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            if response.status_code not in RETRYABLE:
                break
            await asyncio.sleep(2**attempt)
        return AssistantMessage(
            content=[TextContent(text="")], stop_reason="error", error_message=last_error, timestamp=time.time()
        )

    return stream_fn


async def read_stream(response: requests.Response, on_delta: DeltaFn | None) -> AssistantMessage:
    """在传输边界解析一次，后面全部信任这里的结果。"""
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    calls: dict[int, dict] = {}
    finish: str | None = None
    error: str | None = None
    usage: dict | None = None

    while True:
        line = await asyncio.to_thread(response.raw.readline)
        if not line:
            break
        line = line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        chunk = json.loads(payload)
        if chunk.get("error"):
            error = json.dumps(chunk["error"], ensure_ascii=False)[:300]
            break
        if chunk.get("usage"):
            usage = chunk["usage"]
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        if delta.get("reasoning_content"):
            reasoning_parts.append(delta["reasoning_content"])
            if on_delta:
                await on_delta({"type": "reasoning_delta", "text": delta["reasoning_content"]})
        if delta.get("content"):
            text_parts.append(delta["content"])
            if on_delta:
                await on_delta({"type": "text_delta", "text": delta["content"]})
        for fragment in delta.get("tool_calls") or []:
            slot = calls.setdefault(fragment["index"], {"id": "", "name": "", "arguments": ""})
            slot["id"] = fragment.get("id") or slot["id"]
            function = fragment.get("function") or {}
            slot["name"] = function.get("name") or slot["name"]
            slot["arguments"] += function.get("arguments") or ""
        if choice.get("finish_reason"):
            finish = choice["finish_reason"]

    content: list[TextContent | ToolCall] = []
    text = "".join(text_parts)
    if text:
        content.append(TextContent(text=text))
    for index in sorted(calls):
        slot = calls[index]
        arguments, arguments_error = parse_arguments(slot["arguments"])
        content.append(
            ToolCall(
                id=slot["id"] or f"call_{index}",
                name=slot["name"],
                arguments=arguments,
                arguments_error=arguments_error,
            )
        )

    stop_reason = {"tool_calls": "toolUse", "length": "length", "content_filter": "error"}.get(finish or "", "end")
    if error:
        stop_reason = "error"
    return AssistantMessage(
        content=content or [TextContent(text="")],
        stop_reason=stop_reason,
        error_message=error or (None if stop_reason != "error" else f"finish_reason={finish}"),
        reasoning="".join(reasoning_parts) or None,
        usage=usage,
        timestamp=time.time(),
    )


def parse_arguments(raw: str) -> tuple[dict, str | None]:
    if not raw:
        return {}, None
    try:
        arguments = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, str(exc)
    if not isinstance(arguments, dict):
        return {}, f"参数应为 JSON 对象，实际是 {type(arguments).__name__}"
    return arguments, None
