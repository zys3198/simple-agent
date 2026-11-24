---
name: open-targets-graphql
description: 查 Open Targets（疾病-靶点关联打分与逐条证据）时读。含可直接跑的查询脚本与字段说明，覆盖名称转 id、疾病→靶点、靶点→疾病、一对关联的逐条证据。
---

# Open Targets Platform

端点 `https://api.platform.opentargets.org/api/v4/graphql`，POST GraphQL，免密钥。

## 怎么用

先跑脚本，别手写 GraphQL：

```bash
python3 skills/open-targets-graphql/scripts/ot.py search-disease "Alzheimer disease"
python3 skills/open-targets-graphql/scripts/ot.py search-target APOE
python3 skills/open-targets-graphql/scripts/ot.py disease-targets MONDO_0004975 10
python3 skills/open-targets-graphql/scripts/ot.py target-diseases ENSG00000130203 10
python3 skills/open-targets-graphql/scripts/ot.py evidence MONDO_0004975 ENSG00000130203 8
```

脚本会把原始响应存进 `.tmp/responses/`，路径打印在输出末尾。要在输出之外再算点什么（交集、重排序、拼表），用 `bash` 跑 Python 读那个 JSON 文件。

需要改字段或加参数时，读 `references/queries.md` 里的完整模板照着改，不要臆造字段名。

## 读结果时要记住

- 名称检索必须先做：疾病要 MONDO/EFO id，靶点要 ENSG，脚本不会替你猜。
- 缩写会撞到多条（TB、AD、MS），看命中全名再选，答案里写出选了哪条 id。
- `score` 是整体关联强度（0–1），`datatypeScores` 是分项证据；跨疾病比分数没有意义。
- `literature` 里的数字是 PMID，写答案时加 `PMID ` 前缀。
- 接口报错也会返回 HTTP 200，脚本已经拦下 `errors` 并退出非零，直接看 stderr。
