### 功能描述

转发 ES GET 请求

### 请求参数

| 字段                 | 类型  | 必选 | 描述           |
|--------------------|-----|----|--------------|
| es_storage_cluster | int | 是  | ES 存储集群 ID   |
| url                | str | 是  | ES 请求 URL 路径 |

> 注意：`url` 仅允许特定前缀的路径("_cat", "_cluster", "_nodes", "_stats")，非法路径将返回错误。

### 请求参数示例

```json
{
    "es_storage_cluster": 1,
    "url": "_cat/indices"
}
```

### 响应参数

| 字段      | 类型     | 描述             |
|---------|--------|----------------|
| result  | bool   | 请求是否成功         |
| code    | int    | 返回的状态码         |
| message | string | 描述信息           |
| data    | object | ES 接口返回的原始响应数据 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "health": "green",
        "status": "open",
        "index": "my_index",
        "uuid": "abc123",
        "pri": "1",
        "rep": "1",
        "docs.count": "100",
        "docs.deleted": "0",
        "store.size": "10mb",
        "pri.store.size": "5mb"
    }
}
```
