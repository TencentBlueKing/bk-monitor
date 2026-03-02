### 功能描述

批量获取结果表快照状态

### 请求参数

| 字段        | 类型           | 必选 | 描述      |
|-----------|--------------|----|---------|
| table_ids | list[string] | 是  | 结果表ID列表 |

### 请求参数示例

```json
{
    "table_ids": ["2_bklog.test_index", "2_bklog.another_index"]
}
```

### 响应参数

| 字段      | 类型     | 描述                   |
|---------|--------|----------------------|
| result  | bool   | 请求是否成功               |
| code    | int    | 返回的状态码               |
| message | string | 描述信息                 |
| data    | list   | 返回数据，每条记录对应一个快照的状态信息 |

#### data 元素字段说明

| 字段            | 类型     | 描述                                              |
|---------------|--------|-------------------------------------------------|
| table_id      | string | 结果表ID                                           |
| snapshot_name | string | 快照名称（来自ES）                                      |
| state         | string | 快照状态（来自ES，如 `SUCCESS`、`IN_PROGRESS`、`FAILED` 等） |
| duration      | int    | 快照执行耗时（毫秒，来自ES的 `duration_in_millis` 字段）        |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "table_id": "2_bklog.test_index",
            "snapshot_name": "2_bklog.test_index_20240101000000",
            "state": "SUCCESS",
            "duration": 12345
        },
        {
            "table_id": "2_bklog.another_index",
            "snapshot_name": "2_bklog.another_index_20240101000000",
            "state": "IN_PROGRESS",
            "duration": null
        }
    ]
}
```