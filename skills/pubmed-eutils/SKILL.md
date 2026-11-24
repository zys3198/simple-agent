---
name: pubmed-eutils
description: 查 PubMed 文献（检索式 → PMID → 标题摘要）时读。含可直接跑的检索与摘要脚本，以及 E-utilities 的参数与返回结构。
---

# PubMed E-utilities

基址 `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`，全部 GET，免密钥，无密钥时限速 3 次/秒。

## 怎么用

```bash
python3 skills/pubmed-eutils/scripts/pubmed.py search "GZMA AND tuberculosis" 5
python3 skills/pubmed-eutils/scripts/pubmed.py abstract 39641275
```

脚本把原始响应存进 `.tmp/responses/` 并打印路径。要拿更多字段（作者、MeSH、DOI）就 `bash` 跑 Python 读那个 JSON。

参数与返回结构见 `references/endpoints.md`。

## 读结果时要记住

- `search` 输出里的 PMID 才是可以引用的文献标识，写答案时形式是 `PMID 39641275`。
- 检索式支持 `AND` `OR`、字段标签 `GZMA[Title]`、日期区间 `2020:2024[dp]`。
- 摘要只对单篇取，一次一个 PMID；要读多篇就分别调。
- 摘要里的数字（样本量、效应值）属于该篇文献，不要跨文献混算。
