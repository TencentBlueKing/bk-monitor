### 功能描述

【告警V2】告警关联Trace查询

### 请求参数

| 字段       | 类型  | 必选 | 描述               |
|----------|-----|----|------------------|
| alert_id | str | 是  | 告警ID             |
| limit    | int | 否  | 返回调用链的最大数量，默认为10 |
| offset   | int | 否  | 分页偏移量，默认为0       |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2",
    "limit": 10,
    "offset": 0
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段           | 类型   | 描述          |
|--------------|------|-------------|
| list         | list | 调用链列表       |
| query_config | dict | 查询配置，用于前端跳转 |

#### list 元素字段说明

| 字段                     | 类型     | 描述        |
|------------------------|--------|-----------|
| app_name               | string | 应用名称      |
| trace_id               | string | 调用链ID     |
| root_service           | string | 根服务名称     |
| root_span_name         | string | 根Span名称   |
| root_service_span_name | string | 根服务Span名称 |
| error                  | bool   | 是否有错误     |
| error_msg              | string | 错误信息      |

#### query_config 字段说明

| 字段 | 类型 | 描述 |
|-----------|------------|--------------------------||
| app_name | string | 应用名称 |
| sceneMode | string | 场景模式（固定值："span"） |
| where | string/list| 查询条件（JSON字符串或列表） |
| start_time| int | 开始时间（毫秒时间戳） |
| end_time | int | 结束时间（毫秒时间戳） |
| sortBy | string | 排序字段（如：status.code） |
| descending| string | 是否降序（"true"/"false"） |

#### where 元素字段说明（当 where 为列表时）

| 字段       | 类型     | 必选 | 描述                                |
|----------|--------|----|-----------------------------------|
| key      | string | 是  | 过滤字段                              |
| operator | string | 是  | 操作符（equal/not_equal/like/exists等） |
| value    | any    | 是  | 过滤值（通常为列表）                        |
| options  | dict   | 否  | 额外选项（如：{"group_relation": "OR"}）  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "list": [
            {
                "app_name": "my-app",
                "trace_id": "abc123def456",
                "root_service": "api-gateway",
                "root_span_name": "GET /api/users",
                "root_service_span_name": "api-gateway: GET /api/users",
                "error": true,
                "error_msg": "Connection timeout"
            },
            {
                "app_name": "my-app",
                "trace_id": "xyz789uvw012",
                "root_service": "user-service",
                "root_span_name": "POST /users",
                "root_service_span_name": "user-service: POST /users",
                "error": true,
                "error_msg": "Database connection failed"
            }
        ],
        "query_config": {
            "app_name": "my-app",
            "sceneMode": "span",
            "where": [
                {
                    "key": "status.code",
                    "operator": "equal",
                    "value": 2
                }
            ],
            "start_time": 1763553000000,
            "end_time": 1763557000000,
            "sortBy": "status.code",
            "descending": "true"
        }
    }
}
```
