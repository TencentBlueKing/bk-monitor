### 功能描述

获取扁平化后的Trace列表数据，将嵌套的Trace数据结构转换为扁平化的键值对形式。

#### 接口参数

| 字段名        | 类型      | 必选 | 描述      |
|------------| --------- | ---- |---------|
| bk_biz_id  | Integer   | 是   | 业务ID    |
| app_name   | String    | 是   | 应用名称    |
| start_time | Integer   | 是   | 查询开始时间戳 |
| end_time   | Integer   | 是   | 查询结束时间戳 |
| offset     | Integer   | 否   | 分页偏移量   |
| limit      | Integer   | 否   | 每页数量    |
| filters    | List      | 否   | 过滤条件列表  |
| query      | String    | 否   | 查询字符串   |
| sort       | List    | 否   | 排序      |
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

| 字段名  | 类型   | 描述                     |
| ------- | ------ | ------------------------ |
| result  | Bool   | 请求是否成功             |
| code    | Int    | 返回的状态码             |
| message | String | 描述信息                 |
| data    | List   | 扁平化后的Trace数据列表   |

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