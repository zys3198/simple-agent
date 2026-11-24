#!/usr/bin/env python3
"""Open Targets GraphQL 查询助手。只用标准库，任何 python3 都能跑。

用法：
  python3 skills/open-targets-graphql/scripts/ot.py search-disease "Alzheimer disease"
  python3 skills/open-targets-graphql/scripts/ot.py search-target APOE
  python3 skills/open-targets-graphql/scripts/ot.py disease-targets MONDO_0004975 10
  python3 skills/open-targets-graphql/scripts/ot.py target-diseases ENSG00000130203 10
  python3 skills/open-targets-graphql/scripts/ot.py evidence MONDO_0004975 ENSG00000130203 8

原始响应存进 .tmp/responses/，文件名打印在输出末尾，供后续用代码二次处理。
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://api.platform.opentargets.org/api/v4/graphql"
OUT = Path(__file__).resolve().parents[3] / ".tmp" / "responses"
# 最近一次响应的落盘路径：渲染成表格的输出要另存 .txt，台账才扫得到 PMID
LAST_PATH: Path | None = None

SEARCH = 'query($s:String!){ search(queryString:$s, entityNames:%s){ hits{ id name entity } } }'
DISEASE_TARGETS = """query($id:String!,$n:Int!){ disease(efoId:$id){ id name
  associatedTargets(page:{index:0,size:$n}){ count rows{ target{ id approvedSymbol approvedName }
  score datatypeScores{ id score } } } } }"""
TARGET_DISEASES = """query($id:String!,$n:Int!){ target(ensemblId:$id){ approvedSymbol approvedName
  associatedDiseases(page:{index:0,size:$n}){ count rows{ disease{ id name } score } } } }"""
EVIDENCE = """query($d:String!,$g:[String!]!){ disease(efoId:$d){ name evidences(ensemblIds:$g, size:%d){
  count rows{ datatypeId datasourceId score literature publicationYear } } } }"""


def run(query: str, variables: dict, name: str) -> dict:
    request = urllib.request.Request(
        URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read())
    OUT.mkdir(parents=True, exist_ok=True)
    # 文件名带时间戳：同名查询多次执行不互相覆盖，台账才能只增不减
    path = OUT / f"ot-{name}-{int(time.time() * 1000)}.json"
    global LAST_PATH
    LAST_PATH = path
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    if "errors" in payload:
        sys.exit(f"接口报错：{payload['errors'][0]['message']}\n原始响应：{path}")
    print(f"原始响应：{path}")
    return payload["data"]


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, args = argv[1], argv[2:]

    if cmd == "search-disease":
        data = run(SEARCH % '["disease"]', {"s": args[0]}, "search-disease")
        for hit in data["search"]["hits"][:10]:
            print(f"{hit['id']}\t{hit['name']}")

    elif cmd == "search-target":
        data = run(SEARCH % '["target"]', {"s": args[0]}, "search-target")
        for hit in data["search"]["hits"][:10]:
            print(f"{hit['id']}\t{hit['name']}")

    elif cmd == "disease-targets":
        data = run(DISEASE_TARGETS, {"id": args[0], "n": int(args[1]) if len(args) > 1 else 10}, "disease-targets")
        disease = data["disease"]
        print(f"{disease['name']} ({disease['id']}) 关联靶点共 {disease['associatedTargets']['count']} 条")
        for row in disease["associatedTargets"]["rows"]:
            top = sorted(row["datatypeScores"], key=lambda x: -x["score"])[:3]
            print(
                f"{row['target']['approvedSymbol']}\t{row['target']['id']}\tscore={row['score']:.4f}\t"
                + ", ".join(f"{t['id']}={t['score']:.2f}" for t in top)
            )

    elif cmd == "target-diseases":
        data = run(TARGET_DISEASES, {"id": args[0], "n": int(args[1]) if len(args) > 1 else 10}, "target-diseases")
        target = data["target"]
        print(f"{target['approvedSymbol']} ({target['approvedName']}) 关联疾病共 {target['associatedDiseases']['count']} 条")
        for row in target["associatedDiseases"]["rows"]:
            print(f"{row['disease']['id']}\t{row['disease']['name']}\tscore={row['score']:.4f}")

    elif cmd == "evidence":
        query = EVIDENCE % (int(args[2]) if len(args) > 2 else 8)
        data = run(query, {"d": args[0], "g": [args[1]]}, "evidence")
        rows = data["disease"]["evidences"]
        print(f"{data['disease']['name']} 与 {args[1]} 的逐条证据共 {rows['count']} 条")
        lines = []
        for row in rows["rows"]:
            pmids = row.get("literature") or []
            lines.append(
                f"{row['datatypeId']}\t来源={row['datasourceId']}\tscore={row['score']:.4f}\t"
                f"年份={row.get('publicationYear')}\t"
                + ("PMID: " + ", ".join(str(p) for p in pmids) if pmids else "无文献标识")
            )
        print("\n".join(lines))
        if LAST_PATH:
            LAST_PATH.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
