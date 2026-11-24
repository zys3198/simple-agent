"""pi 的内置工具四件套：read / write / edit / bash，即 pi 的 DEFAULT_TOOL_NAMES。

pi 一共八个（另有 grep / find / ls / powershell），那四个是搜索与 Windows 专用，本任务用 bash 里的 grep、ls 代替。
契约照 pi dist/core/tools/：
- read  : path、offset、limit；按行取，超 2000 行或 50KB 截断
- write : path、content；自动建目录、覆盖写
- edit  : path、edits[]（oldText / newText）；每段 oldText 必须在原文里唯一出现、互不重叠
- bash  : command、timeout；stdout 与 stderr 合并返回，超限只留末尾，全文落盘
"""

import subprocess
from itertools import pairwise
from pathlib import Path

from .tools import AgentTool, ToolResult

DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024
BASH_TIMEOUT = 300  # pi 里这个参数可选、无默认值；本实现给上限，防命令挂死


def truncate_tail(text: str, max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[str, bool]:
    """保留末尾：超限时从前面删，因为命令输出最关心的在最后。"""
    lines = text.split("\n")
    truncated = False
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
        truncated = True
    out = "\n".join(lines)
    if len(out.encode()) > max_bytes:
        out = out.encode()[-max_bytes:].decode(errors="replace")
        truncated = True
    return out, truncated


def truncate_head(text: str, max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[str, bool]:
    lines = text.split("\n")
    truncated = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True
    out = "\n".join(lines)
    if len(out.encode()) > max_bytes:
        out = out.encode()[:max_bytes].decode(errors="replace")
        truncated = True
    return out, truncated


class BuiltinTools:
    def __init__(self, root: Path):
        self.root = root
        self.full_output_dir = root / ".tmp" / "bash"

    def read(self, args: dict) -> ToolResult:
        path = self._path(args["path"])
        lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        start = max(int(args.get("offset", 1)) - 1, 0)
        limit = args.get("limit")
        selected = lines[start : start + int(limit)] if limit else lines[start:]
        text, truncated = truncate_head("\n".join(selected))
        notice = f"\n\n[已截断，原文共 {len(lines)} 行]" if truncated else ""
        return ToolResult(content=text + notice, details={"lines": len(lines)})

    def write(self, args: dict) -> ToolResult:
        path = self._path(args["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return ToolResult(content=f"已写入 {path}（{len(args['content'])} 字）")

    def edit(self, args: dict) -> ToolResult:
        path = self._path(args["path"])
        if not path.is_file():
            raise FileNotFoundError(f"要改的文件不存在：{args['path']}")
        edits = args["edits"]
        content = path.read_text(encoding="utf-8")
        # shortcut: 只按纯文本匹配，不做 pi 的空白容错与 CRLF 回填；文件带 CRLF 或缩进不一致时改用 write
        for i, edit in enumerate(edits):
            old = edit["oldText"]
            if not old:
                raise ValueError(f"edits[{i}].oldText 为空")
            count = content.count(old)
            if count == 0:
                raise ValueError(f"edits[{i}].oldText 在 {args['path']} 里找不到")
            if count > 1:
                raise ValueError(f"edits[{i}].oldText 在 {args['path']} 里出现 {count} 次，不够唯一")
        spans = sorted(
            (content.index(e["oldText"]), len(e["oldText"])) for e in edits
        )
        for (start, length), (next_start, _) in pairwise(spans):
            if start + length > next_start:
                raise ValueError("多个 edits 的目标区域重叠，合并成一段再发")
        for edit in edits:
            content = content.replace(edit["oldText"], edit["newText"], 1)
        path.write_text(content, encoding="utf-8")
        return ToolResult(content=f"Successfully replaced {len(edits)} block(s) in {args['path']}.")

    def bash(self, args: dict) -> ToolResult:
        completed = subprocess.run(
            ["bash", "-lc", args["command"]],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=args.get("timeout", BASH_TIMEOUT),
            check=False,
        )
        combined = completed.stdout + completed.stderr
        text, truncated = truncate_tail(combined)
        details = {"exit": completed.returncode}
        if truncated:
            self.full_output_dir.mkdir(parents=True, exist_ok=True)
            full = self.full_output_dir / f"{len(list(self.full_output_dir.glob('*.txt'))) + 1:03d}.txt"
            full.write_text(combined, encoding="utf-8")
            details["full_output_path"] = str(full)
            text += f"\n\n[只显示末尾 {DEFAULT_MAX_LINES} 行 / {DEFAULT_MAX_BYTES // 1024}KB，全文：{full.relative_to(self.root)}]"
        return ToolResult(content=text or "（无输出）", is_error=completed.returncode != 0, details=details)

    def _path(self, raw: str) -> Path:
        path = Path(raw)
        return path if path.is_absolute() else (self.root / path)

    def as_tools(self) -> list[AgentTool]:
        return [
            AgentTool(
                name="read",
                description=(
                    "读取文件内容。默认全读，超 2000 行或 50KB 头部截断；用 offset / limit 读长文件的后半部分。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to read (relative or absolute)"},
                        "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
                        "limit": {"type": "integer", "description": "Maximum number of lines to read"},
                    },
                    "required": ["path"],
                },
                execute=self.read,
            ),
            AgentTool(
                name="write",
                description="写入文件。文件不存在就新建，存在就覆盖；目录不存在会自动创建。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to write (relative or absolute)"},
                        "content": {"type": "string", "description": "Content to write to the file"},
                    },
                    "required": ["path", "content"],
                },
                execute=self.write,
            ),
            AgentTool(
                name="edit",
                description=(
                    "按原文精确替换来改文件。每段 edits[].oldText 必须在原文件里唯一出现，且多段之间不能重叠；"
                    "两处改动靠得很近时合并成一段。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file to edit (relative or absolute)"},
                        "edits": {
                            "type": "array",
                            "description": "One or more targeted replacements, matched against the original file",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "oldText": {"type": "string", "description": "Exact text for one targeted replacement; must be unique"},
                                    "newText": {"type": "string", "description": "Replacement text for this targeted edit"},
                                },
                                "required": ["oldText", "newText"],
                            },
                        },
                    },
                    "required": ["path", "edits"],
                },
                execute=self.edit,
            ),
            AgentTool(
                name="bash",
                description=(
                    "在当前目录执行 bash 命令，返回 stdout 与 stderr 合并后的结果；超限只留末尾，全文另存。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to execute"},
                        "timeout": {"type": "integer", "description": "Timeout in seconds (default 300)"},
                    },
                    "required": ["command"],
                },
                execute=self.bash,
            ),
        ]
