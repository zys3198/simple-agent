# E-utilities 三段调用

## 1. 检索式 → PMID 列表

```
esearch.fcgi?db=pubmed&term=<检索式>&retmax=5&retmode=json&sort=relevance
```

| 参数 | 说明 |
|---|---|
| `term` | 检索式，支持 `AND`/`OR`、`[Title]`/`[Abstract]` 标签、`2020:2024[dp]` 日期区间 |
| `retmax` | 最多返回几条，默认 5 足够 |
| `retmode` | 用 `json`，返回结构在 `esearchresult` |
| `sort` | `relevance` 或 `pub_date` |

返回：`esearchresult.count` 是命中总数，`esearchresult.idlist` 是 PMID 字符串数组。

## 2. PMID → 标题与出处

```
esummary.fcgi?db=pubmed&id=39641275,41924266&retmode=json
```

返回的 `result` 以 PMID 为键，常用字段：`title`、`pubdate`、`source`（期刊名）、`authors`。`result.uids` 是本次请求的 PMID 列表。

## 3. PMID → 摘要原文

```
efetch.fcgi?db=pubmed&id=<PMID>&retmode=text&rettype=abstract
```

返回纯文本，直接截前 2500 字给模型看即可，不需要解析。

## 限速与错误

- 无 API key：每秒最多 3 次，别并发打。
- 网络错误或缺参数会返回 HTTP 400 与一段文本，不是 JSON。
- `idlist` 为空数组表示检索无命中，改检索式重试一次，不要重复发同一条。
