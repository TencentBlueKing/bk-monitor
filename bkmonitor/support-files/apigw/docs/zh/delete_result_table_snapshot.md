### 功能描述

删除结果表快照配置

### 请求参数

| 字段       | 类型     | 必选 | 描述                     |
|----------|--------|----|------------------------|
| table_id | string | 是  | 结果表ID                  |
| is_sync  | bool   | 否  | 是否同步执行，默认为 false（异步执行） |

### 请求参数示例

```json
{
    "table_id": "2_bklog.test_index",
    "is_sync": false
}
```

### 响应参数

| 字段      | 类型     | 描述            |
|---------|--------|---------------|
| result  | bool   | 请求是否成功        |
| code    | int    | 返回的状态码        |
| message | string | 描述信息          |
| data    | dict   | 返回数据，为请求参数的回显 |

#### data 字段说明

| 字段           | 类型     | 描述     |
|--------------|--------|--------|
| bk_tenant_id | string | 租户ID   |
| table_id     | string | 结果表ID  |
| is_sync      | bool   | 是否同步执行 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_tenant_id": "system",
        "table_id": "2_bklog.test_index",
        "is_sync": false
    }
}
```
