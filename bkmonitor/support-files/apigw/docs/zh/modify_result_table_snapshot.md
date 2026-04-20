### 功能描述

修改结果表快照配置

### 请求参数

| 字段            | 类型     | 必选 | 描述                          |
|---------------|--------|----|-----------------------------|
| table_id      | string | 是  | 结果表ID                       |
| snapshot_days | int    | 是  | 快照存储时间（天），最小值为0             |
| operator      | string | 是  | 操作者                         |
| status        | string | 否  | 快照状态（如 `running`、`stopped`） |

### 请求参数示例

```json
{
    "table_id": "2_bklog.test_index",
    "snapshot_days": 14,
    "operator": "admin",
    "status": "running"
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

| 字段            | 类型     | 描述               |
|---------------|--------|------------------|
| bk_tenant_id  | string | 租户ID             |
| table_id      | string | 结果表ID            |
| snapshot_days | int    | 快照存储时间（天）        |
| operator      | string | 操作者              |
| status        | string | 快照状态（仅在请求中传入时返回） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_tenant_id": "system",
        "table_id": "2_bklog.test_index",
        "snapshot_days": 14,
        "operator": "admin"
    }
}
```
