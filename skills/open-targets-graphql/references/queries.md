# Open Targets GraphQL 查询模板

脚本里没有的查询照着这些改。变量通过 `variables` 传，`size` 这类分页参数要么当变量传（`Int`），要么直接写进查询字符串。

## 名称 → id

```graphql
query($s:String!){ search(queryString:$s, entityNames:["disease"]){ hits{ id name entity } } }
```

`entityNames` 只能是 `["disease"]` 或 `["target"]`，疾病与靶点必须分两次查。疾病命中返回 `MONDO_*` / `EFO_*`，靶点返回 `ENSG*`。

## 疾病 → 靶点排行

```graphql
query($id:String!,$n:Int!){ disease(efoId:$id){ id name
  associatedTargets(page:{index:0,size:$n}){ count rows{
    target{ id approvedSymbol approvedName } score datatypeScores{ id score } } } } }
```

## 靶点 → 疾病排行

```graphql
query($id:String!,$n:Int!){ target(ensemblId:$id){ approvedSymbol approvedName
  associatedDiseases(page:{index:0,size:$n}){ count rows{ disease{ id name } score } } } }
```

参数名是 `ensemblId`，不是 `id`。

## 一对关联的逐条证据

```graphql
query($d:String!,$g:[String!]!){ disease(efoId:$d){ name evidences(ensemblIds:$g, size:8){
  count rows{ datatypeId datasourceId score literature publicationYear } } } }
```

- `ensemblIds` 类型是 `[String!]!`，必须传数组。
- `size` 是查询里的字面量，不能当变量传。
- 字段是 `datasourceId`，写成 `datasource` 会报字段不存在。
- `publicationYear` 可能为空。

## 常见错误

| 现象 | 原因 |
|---|---|
| `Cannot query field "datasource"` | 字段名是 `datasourceId` |
| `Field "search" argument "entityNames" of type "[String!]!" is required` | 漏了 `entityNames` |
| `Expected type [String!]!, found String` | `ensemblIds` 传了字符串 |
| `Unknown argument "size"` | `size` 只能写在查询字符串里 |
