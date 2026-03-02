### 功能描述

查询结果表 MQ（Kafka）的最新数据

### 请求参数

| 字段         | 类型  | 必选 | 描述                                    |
|------------|-----|----|---------------------------------------|
| table_id   | str | 否  | 结果表 ID，与 bk_data_id 二选一               |
| bk_data_id | int | 否  | 数据源 ID，与 table_id 二选一                 |
| size       | int | 否  | 拉取条数，默认为 10                           |
| namespace  | str | 否  | 命名空间，默认为 `bkmonitor`，V4 链路调用计算平台接口时使用 |

> 注意：`table_id` 和 `bk_data_id` 至少提供一个。

### 请求参数示例

```json
{
    "table_id": "2_bkmonitor_time_series_123456.__default__",
    "size": 5
}
```

### 响应参数

| 字段      | 类型         | 描述                                         |
|---------|------------|--------------------------------------------|
| result  | bool       | 请求是否成功                                     |
| code    | int        | 返回的状态码                                     |
| message | string     | 描述信息                                       |
| data    | list[dict] | Kafka 消息数据列表，每条为消息体 JSON 解析后的原始内容，结构取决于数据源 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "data": "{\"dimensions\":{\"bk_target_ip\":\"127.0.0.1\"},\"metrics\":{\"cpu_usage\":0.5},\"time\":1704067200}",
            "dataid": 1500001,
            "time": 1704067200
        }
    ]
}
```
