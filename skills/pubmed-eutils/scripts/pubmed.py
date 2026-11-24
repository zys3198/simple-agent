#!/usr/bin/env python3
"""PubMed E-utilities 查询助手。只用标准库。

用法：
  python3 skills/pubmed-eutils/scripts/pubmed.py search "GZMA AND tuberculosis" 5
  python3 skills/pubmed-eutils/scripts/pubmed.py abstract 35900000

原始响应存进 .tmp/responses/，路径打印在输出末尾。
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OUT = Path(__file__).resolve().parents[3] / ".tmp" / "responses"


def get(endpoint: str, params: dict) -> str:
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def save(name: str, text: str) -> Path:
    """文件名带时间戳：同名查询多次执行不互相覆盖，台账才能只增不减。"""
    OUT.mkdir(parents=True, exist_ok=True)
    stem, _, suffix = name.rpartition(".")
    path = OUT / f"pubmed-{stem}-{int(time.time() * 1000)}.{suffix}"
    path.write_text(text, encoding="utf-8")
    return path


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1]

    if cmd == "search":
        term = argv[2]
        retmax = int(argv[3]) if len(argv) > 3 else 5
        raw = get("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": retmax, "retmode": "json", "sort": "relevance"})
        save("esearch.json", raw)
        result = json.loads(raw)["esearchresult"]
        ids = result["idlist"]
        print(f"检索「{term}」命中 {result.get('count')} 条，本次取 {len(ids)} 条：{', '.join(ids)}")
        if not ids:
            return
        raw = get("esummary.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        summary_path = save("esummary.json", raw)
        print(f"原始响应：{summary_path}")
        summary = json.loads(raw)["result"]
        lines = []
        for pmid in ids:
            item = summary[pmid]
            lines.append(f"PMID {pmid}\t{item.get('pubdate')}\t{item.get('source')}\t{item.get('title')}")
        print("\n".join(lines))
        # 渲染出的行另存一份：台账扫的是文本里的 PMID，JSON 里的裸数字扫不到
        summary_path.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    elif cmd == "abstract":
        pmid = argv[2]
        text = get("efetch.fcgi", {"db": "pubmed", "id": pmid, "retmode": "text", "rettype": "abstract"})
        print(f"原始响应：{save(f'abstract-{pmid}.txt', text)}")
        print(text[:2500])

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
