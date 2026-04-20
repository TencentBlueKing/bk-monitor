### 功能描述

修改快照回溯配置

### 请求参数

| 字段           | 类型     | 必选 | 描述                              |
|--------------|--------|----|---------------------------------|
| restore_id   | int    | 是  | 回溯任务ID                          |
| expired_time | string | 是  | 新的过期时间，格式：`YYYY-MM-DD HH:MM:SS` |
| operator     | string | 是  | 操作者                             |

### 请求参数示例

```json
{
    "restore_id": 1,
    "expired_time": "2024-03-01 00:00:00",
    "operator": "admin"
}
```

### 响应参数

| 字段      | 类型     | 描述                      |
|---------|--------|-------------------------|
| result  | bool   | 请求是否成功                  |
| code    | int    | 返回的状态码                  |
| message | string | 描述信息                    |
| data    | dict   | 返回数据，为请求参数加自动获取的租户ID的回显 |

#### data 字段说明

| 字段           | 类型     | 描述                               |
|--------------|--------|----------------------------------|
| restore_id   | int    | 回溯任务ID                           |
| expired_time | string | 新的过期时间（`YYYY-MM-DD HH:MM:SS` 格式） |
| operator     | string | 操作者                              |
| bk_tenant_id | string | 租户ID                             |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "restore_id": 1,
        "expired_time": "2024-03-01 00:00:00",
        "operator": "admin",
        "bk_tenant_id": "system"
    }
}
```
