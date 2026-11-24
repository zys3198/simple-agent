"""核验答案里的标识符是不是本次运行中工具真正返回过的。

台账来源是技能脚本落盘的原始响应目录（默认 .tmp/responses/）：查询脚本每次把原始 JSON
写在那里，文件名打印在输出末尾，所以扫这个目录等于扫「工具真实返回过的内容」。用 --since
限定只算本轮之后写入的文件，避免历史会话的标识符混进台账。

用法：
    python3 skills/evidence-discipline/scripts/verify.py --answer-file answer.md --since 1795000000
输出一段 JSON：cited / unverified / verified_count / coverage / ledger_size / ledger。
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSES = ROOT / ".tmp" / "responses"

ID_PATTERNS = {
    # Open Targets 的文献字段渲染成「PMID: a, b, c」，后面的编号没有前缀，所以整串一次性抓住再拆
    "PMID": re.compile(r"PMID[:\s]*(\d{7,8}(?:[,\s]+\d{7,8})*)"),
    "Ensembl": re.compile(r"(ENSG\d{11})"),
    "OpenTargets": re.compile(r"\b((?:MONDO|EFO|Orphanet|HP)_?\d{4,7})\b"),
}


def _identifiers_in(match: re.Match, label: str) -> list[str]:
    """从一处命中里拆出全部标识符；PMID 是逗号列表，其余是一个。"""
    if label == "PMID":
        return [f"PMID {raw}" for raw in re.findall(r"\d{7,8}", match.group(0))]
    return [match.group(0)]


@dataclass
class EvidenceRecord:
    source: str        # 登记来源：原始响应文件路径
    identifier: str    # ENSG00000130203 / MONDO_0004975 / PMID 12345678
    snippet: str = ""  # 标识符所在的那一行，人看一眼就知道是哪个基因 / 哪篇文章


@dataclass
class EvidenceLedger:
    records: list[EvidenceRecord] = field(default_factory=list)

    def scan(self, source: str, text: str) -> int:
        """把文本里出现的标识符登记进台账，返回新登记条数。

        同一标识符只留一行，但优先留带 tab 的结果行：技能文档里的示例命令、bash 回显
        只有编号，换成结果行才能在页面上读出是哪个基因 / 哪篇文章。
        """
        by_id = {r.identifier: r for r in self.records}
        added = 0
        for label, pattern in ID_PATTERNS.items():
            for match in pattern.finditer(text):
                for identifier in _identifiers_in(match, label):
                    raw = identifier.split()[-1]
                    snippet = _snippet_for(text, raw, match.start())
                    record = by_id.get(identifier)
                    if record is None:
                        record = EvidenceRecord(source=source, identifier=identifier, snippet=snippet)
                        self.records.append(record)
                        by_id[identifier] = record
                        added += 1
                    elif "\t" not in record.snippet and "\t" in snippet:
                        record.snippet, record.source = snippet, source
        return added

    @property
    def identifiers(self) -> set[str]:
        return {r.identifier for r in self.records}


def _line_at(text: str, at: int) -> str:
    """取标识符所在的整行（工具输出是 tab 分隔的表），最长 300 字。"""
    start = text.rfind("\n", 0, at) + 1
    end = text.find("\n", at)
    line = text[start:] if end == -1 else text[start:end]
    return line.strip()[:300]


def _snippet_for(text: str, needle: str, at: int) -> str:
    """命令回显那一行只有命令本身，取下一处出现的一行（带 tab 的结果行）。"""
    first = ""
    pos = at
    while pos != -1:
        line = _line_at(text, pos)
        if not first:
            first = line
        if "\t" in line:
            return line
        pos = text.find(needle, pos + len(needle))
    return first


def ledger_from_responses(responses: Path = DEFAULT_RESPONSES, since: float = 0.0) -> EvidenceLedger:
    ledger = EvidenceLedger()
    if not responses.is_dir():
        return ledger
    for path in sorted(responses.iterdir()):
        if not path.is_file() or path.stat().st_mtime < since:
            continue
        try:
            source = str(path.relative_to(ROOT))
        except ValueError:
            source = str(path)
        ledger.scan(source, path.read_text(encoding="utf-8", errors="replace"))
    return ledger


def verify_answer(answer: str, ledger: EvidenceLedger) -> dict:
    """检查答案里的每个标识符是否都是本次运行中工具返回过的。"""
    cited: list[str] = []
    for label, pattern in ID_PATTERNS.items():
        for match in pattern.finditer(answer):
            for identifier in _identifiers_in(match, label):
                if identifier not in cited:
                    cited.append(identifier)
    known = ledger.identifiers
    unverified = [c for c in cited if c not in known]
    return {
        "cited": cited,
        "unverified": unverified,
        "verified_count": len(cited) - len(unverified),
        "coverage": round((len(cited) - len(unverified)) / len(cited), 3) if cited else 0.0,
        "ledger_size": len(ledger.records),
        "ledger": [{"identifier": r.identifier, "source": r.source, "snippet": r.snippet} for r in ledger.records],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="核验答案里的标识符是否来自本轮工具输出")
    parser.add_argument("--answer-file", required=True, help="答案文本文件")
    parser.add_argument("--since", type=float, default=0.0, help="只算这个 epoch 之后写入的原始响应")
    parser.add_argument("--responses", type=Path, default=DEFAULT_RESPONSES, help="原始响应目录")
    args = parser.parse_args()

    answer = Path(args.answer_file).read_text(encoding="utf-8")
    result = verify_answer(answer, ledger_from_responses(args.responses, args.since))
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
