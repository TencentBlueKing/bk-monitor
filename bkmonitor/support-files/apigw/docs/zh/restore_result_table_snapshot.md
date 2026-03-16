### 功能描述

创建快照回溯任务

### 请求参数

| 字段           | 类型     | 必选 | 描述                                |
|--------------|--------|----|-----------------------------------|
| table_id     | string | 是  | 结果表ID                             |
| start_time   | string | 是  | 数据开始时间，格式：`YYYY-MM-DD HH:MM:SS`   |
| end_time     | string | 是  | 数据结束时间，格式：`YYYY-MM-DD HH:MM:SS`   |
| expired_time | string | 是  | 回溯数据过期时间，格式：`YYYY-MM-DD HH:MM:SS` |
| operator     | string | 是  | 操作者                               |
| is_sync      | bool   | 否  | 是否同步执行，默认为 false（异步执行）            |

### 请求参数示例

```json
{
    "table_id": "2_bklog.test_index",
    "start_time": "2024-01-01 00:00:00",
    "end_time": "2024-01-07 23:59:59",
    "expired_time": "2024-02-01 00:00:00",
    "operator": "admin",
    "is_sync": false
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

| 字段               | 类型  | 描述             |
|------------------|-----|----------------|
| restore_id       | int | 快照回溯任务ID       |
| total_store_size | int | 回溯索引的总存储大小（字节） |
| total_doc_count  | int | 回溯索引的总文档数量     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "restore_id": 1,
        "total_store_size": 1048576,
        "total_doc_count": 10000
    }
}
```
