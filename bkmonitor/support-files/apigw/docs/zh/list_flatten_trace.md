### 功能描述

获取 Trace 列表数据

#### 接口参数

| 字段名        | 类型      | 必选 | 描述      |
|------------| --------- | ---- |---------|
| bk_biz_id  | int       | 是   | 业务 ID   |
| app_name   | str       | 是   | 应用名称    |
| start_time | int       | 是   | 查询开始时间戳 |
| end_time   | int       | 是   | 查询结束时间戳 |
| offset     | int       | 否   | 分页偏移量   |
| limit      | int       | 否   | 每页数量    |
| filters    | list      | 否   | 过滤条件列表  |
| query      | str       | 否   | 查询字符串   |
| sort       | list      | 否   | 排序      |

#### 示例数据

```json
{
    "app_name": "app_name",
    "filters": [],
    "start_time": 1755048571,
    "end_time": 1755052171,
    "query": "",
    "sort": [],
    "limit": 30,
    "offset": 0,
    "bk_biz_id": 1
}
```

### 响应参数

| 字段名  | 类型   | 描述         |
| ------- | ------ |------------|
| result  | bool   | 请求是否成功     |
| code    | int    | 返回的状态码     |
| message | str    | 描述信息       |
| data    | object | Trace 数据对象 |

#### data 对象字段

| 字段名 | 类型 | 描述 |
|-------|------|------|
| total | int | 总记录数 |
| data | array | Trace 数据列表 |
| type | str | 数据类型 |

#### data 列表中的 Trace 对象字段

| 字段名 | 类型 | 描述           |
|-------|------|--------------|
| bk_tenant_id | int | 租户 ID        |
| bk_biz_id | int | 业务 ID        |
| bk_app_code | int | 应用代码         |
| app_name | str | 应用名称         |
| trace_id | str | Trace ID     |
| hierarchy_count | int | Span 层数      |
| service_count | int | 服务数量         |
| span_count | int | Span 数量      |
| min_start_time | int | 开始时间         |
| max_end_time | int | 结束时间         |
| trace_duration | int | 总耗时          |
| span_max_duration | int | 最大 Span 耗时   |
| span_min_duration | int | 最小 Span 耗时   |
| root_service | str | 入口服务         |
| root_service_span_id | str | 入口服务 Span ID |
| root_service_span_name | str | 入口服务接口       |
| root_service_status_code | int | 入口服务状态码      |
| root_service_category | str | 入口服务分类       |
| root_service_kind | int | 入口服务类型       |
| root_span_name | str | 根 Span 接口    |
| root_span_service | str | 根 Span 服务    |
| root_span_kind | int | 根 Span 类型    |
| error | bool | 是否错误         |
| error_count | int | 错误数量         |
| time | int | 时间戳          |
| category_statistics.http | int | HTTP 数量      |
| category_statistics.rpc | int | RPC 数量       |
| category_statistics.db | int | DB 数量        |
| category_statistics.messaging | int | 消息数量         |
| category_statistics.async_backend | int | 异步后台数量       |
| category_statistics.other | int | 其他数量         |
| kind_statistics.async | int | 异步调用数量       |
| kind_statistics.sync | int | 同步调用数量       |
| kind_statistics.interval | int | 内部调用数量       |
| kind_statistics.unspecified | int | 未知调用数量       |


#### 示例响应

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 0,
        "data": [
            {
                "bk_tenant_id": 1,
                "bk_biz_id": 1,
                "bk_app_code": 1,
                "app_name": "app_name",
                "trace_id": "",
                "hierarchy_count": 9,
                "service_count": 1,
                "span_count": 1,
                "min_start_time": 1755052139249044,
                "max_end_time": 1755052139249634,
                "trace_duration": 590,
                "span_max_duration": 590,
                "span_min_duration": 1,
                "root_service": "root_service",
                "root_service_span_id": "",
                "root_service_span_name": "root_service_span_name",
                "root_service_status_code": 200,
                "root_service_category": "http",
                "root_service_kind": 2,
                "root_span_name": "root_span_name",
                "root_span_service": "root_span_service",
                "root_span_kind": 2,
                "error": false,
                "error_count": 0,
                "time": 1755067610963659,
                "category_statistics.http": 1,
                "category_statistics.rpc": 0,
                "category_statistics.db": 0,
                "category_statistics.messaging": 0,
                "category_statistics.async_backend": 0,
                "category_statistics.other": 17,
                "kind_statistics.async": 0,
                "kind_statistics.sync": 1,
                "kind_statistics.interval": 17,
                "kind_statistics.unspecified": 0
            }
        ],
        "type": "origin"
    }
}
```