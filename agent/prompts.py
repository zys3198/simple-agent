"""系统提示词：照 pi 的 buildSystemPromptSections 分段拼装。

pi 的形状：preamble / tools / rules 用 <section> 包起来，末尾附加 <skills> 与 <cwd>；
工具摘要与规则由被选中的工具决定，技能清单只给 name / description / location。
领域角色、输出格式与判据不写在这里，写进对应技能的正文。
"""

from .skills import Skill, format_skills_for_prompt, load_skills

PREAMBLE = "你是一个 helpful agent，可以帮用户查资料、跑命令、读写文件。"

TOOL_SNIPPETS = {
    "read": "读取文件内容，可按行取，超长自动截断",
    "write": "写入文件，不存在就新建，存在就覆盖，自动建目录",
    "edit": "按原文精确替换改文件，支持一次发多段互不重叠的替换",
    "bash": "执行 bash 命令，返回合并后的输出，超长只留末尾并保存全文",
}

TOOL_GUIDELINES = {
    "read": ["读大文件用 offset / limit 分段读，不要一次拉全文"],
    "write": ["新建文件用 write；改已有文件用 edit，不要整篇重写"],
    "edit": ["每段 oldText 必须在原文里唯一出现且互不重叠，匹配不上就换更长的上下文"],
    "bash": [
        "发网络请求、跑脚本、解析 JSON 都用 bash",
        "命令报错先读错误信息再改参数重试一次，不要重复发同一条命令",
    ],
}

PROMPT_GUIDELINES = [
    "大数目的排行、交集、统计用代码算，不要手推",
    "够答复就停手，不要为了凑数继续查",
    "技能里带 scripts/ 时，按 SKILL.md 给的示例命令直接用 bash 跑；不要 cat 整个脚本或自己重写一遍",
    "当前目录已在 <cwd> 里给出，不要用 ls / pwd / date 探测环境",
    "回答简洁，涉及文件时写出路径",
]


def _tools_section(tools: list[str]) -> str:
    lines = "\n".join(f"- {name}: {TOOL_SNIPPETS[name]}" for name in tools if name in TOOL_SNIPPETS)
    return f"{lines}\n\n还有别的工具可能可用。"


def _rules_section(tools: list[str]) -> str:
    rules: list[str] = []
    if "bash" in tools and not {"grep", "find", "ls"} & set(tools):
        rules.append("列目录、搜文件、找文件都用 bash")
    for name in tools:
        rules.extend(TOOL_GUIDELINES.get(name, []))
    rules.extend(PROMPT_GUIDELINES)
    return "\n".join(f"- {rule}" for rule in rules)


def build_system_prompt(
    skills: list[Skill] | None = None,
    tools: list[str] | None = None,
    cwd: str = ".",
) -> str:
    skills = load_skills().skills if skills is None else skills
    tools = ["read", "bash", "edit", "write"] if tools is None else tools
    blocks = [PREAMBLE, f"<tools>\n{_tools_section(tools)}\n</tools>", f"<rules>\n{_rules_section(tools)}\n</rules>"]
    if skills:
        blocks.append(format_skills_for_prompt(skills, "read").strip())
    blocks.append(f"<cwd>\n{cwd}\n</cwd>")
    return "\n\n".join(block for block in blocks if block)


BASELINE_SYSTEM_PROMPT = "你是一个通用 agent。请直接回答用户的问题。"
