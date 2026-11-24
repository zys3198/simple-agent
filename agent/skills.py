"""skill 加载与提示词注入，照 pi 的 dist/core/skills.js。

pi 的规矩（docs/skills.md 与 Agent Skills 规范）：
- 目录里有 SKILL.md 就是一个 skill，递归发现
- 启动时只把 name / description / location 注入系统提示词，正文由 read 工具按需读
- name 小写字母数字连字符、不超 64 字；description 不超 1024 字；不合规的跳过并给诊断，不中断启动
- disable-model-invocation 为真时不进提示词，只能由人显式调用
"""

import xml.sax.saxutils as sax
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    file_path: Path
    disable_model_invocation: bool = False


@dataclass
class SkillLoad:
    skills: list[Skill] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


def load_skills(directory: Path = SKILLS_DIR) -> SkillLoad:
    out = SkillLoad()
    for file in sorted(directory.rglob("SKILL.md")):
        try:
            meta = _frontmatter(file)
        except (ValueError, yaml.YAMLError) as exc:
            out.diagnostics.append(f"{file}: frontmatter 解析失败（{exc}）")
            continue
        name, description = meta.get("name"), meta.get("description")
        problems = _validate(name, description)
        if problems:
            out.diagnostics.append(f"{file}: {'; '.join(problems)}")
            continue
        out.skills.append(
            Skill(
                name=name,
                description=description,
                file_path=file,
                disable_model_invocation=bool(meta.get("disable-model-invocation", False)),
            )
        )
    return out


def _frontmatter(file: Path) -> dict:
    text = file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("没有以 --- 开头的 frontmatter")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end]) or {}


def _validate(name, description) -> list[str]:
    problems = []
    if not name or not isinstance(name, str):
        return ["缺 name"]
    if len(name) > MAX_NAME_LENGTH:
        problems.append(f"name 超过 {MAX_NAME_LENGTH} 字符（{len(name)}）")
    if not all(c.islower() or c.isdigit() or c == "-" for c in name):
        problems.append("name 只能用 a-z、0-9、连字符")
    if name.startswith("-") or name.endswith("-") or "--" in name:
        problems.append("name 不能以连字符开头结尾，也不能连续出现")
    if not description or not isinstance(description, str):
        return problems + ["缺 description"]
    if len(description) > MAX_DESCRIPTION_LENGTH:
        problems.append(f"description 超过 {MAX_DESCRIPTION_LENGTH} 字符（{len(description)}）")
    return problems


def format_skills_for_prompt(skills: list[Skill], file_read_tool: str = "read") -> str:
    """与 pi 的 formatSkillsForPrompt 输出同形。"""
    visible = [s for s in skills if not s.disable_model_invocation]
    if not visible:
        return ""
    lines = [
        "\n\nThe following skills provide specialized instructions for specific tasks.",
        "Use the read tool to load a skill's file when the task matches its description."
        if file_read_tool == "read"
        else f"Use {file_read_tool} to load a skill's file when the task matches its description.",
        "Resolve relative paths against the skill's directory (parent of SKILL.md). Use absolute paths in tool calls.",
        "",
        "<available_skills>",
    ]
    for skill in visible:
        lines.append("  <skill>")
        lines.append(f"    <name>{_escape(skill.name)}</name>")
        lines.append(f"    <description>{_escape(skill.description)}</description>")
        lines.append(f"    <location>{_escape(str(skill.file_path))}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def _escape(s: str) -> str:
    return sax.escape(s, {'"': "&quot;", "'": "&apos;"})
