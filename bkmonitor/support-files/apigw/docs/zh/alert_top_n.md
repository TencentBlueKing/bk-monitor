### 功能描述

获取告警TopN统计信息，支持按指定字段进行聚合统计，返回告警数量排名前N的结果。

### 请求参数

| 字段                | 类型           | 必选 | 描述                                                         |
| ------------------- | -------------- | ---- | ------------------------------------------------------------ |
| bk_biz_ids          | List[int]      | 否   | 业务ID列表，为空时查询所有有权限的业务                       |
| status              | List[string]   | 否   | 状态，可选 `ABNORMAL`, `CLOSED`, `RECOVERED`                 |
| conditions          | List[Condition] | 否   | 过滤条件                                                     |
| query_string        | string         | 否   | 查询字符串，语法：https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html#query-string-query-notes |
| start_time          | int            | 是   | 开始时间（时间戳）                                           |
| end_time            | int            | 是   | 结束时间（时间戳）                                           |
| username            | string         | 否   | 负责人                                                       |
| fields              | List[string]   | 否   | 查询字段列表，支持的字段包括：`bk_biz_id`, `severity`, `status`, `strategy_id`, `assignee`, `category`, `plugin_id`, `target_type`, `ip`, `bk_cloud_id` 等 |
| size                | int            | 否   | 获取的桶数量，默认10                                         |
| need_time_partition | bool           | 否   | 是否需要按时间分片，默认true                                 |

#### 过滤条件（conditions）

| 字段      | 类型   | 必须 | 描述                                                         |
| :-------- | :----- | :--- | :----------------------------------------------------------- |
| key       | string | 是   | 字段名                                                       |
| value     | List   | 是   | 可取值的列表。当 `method = eq`，则满足其一即可；当`method = neq`，则全都不满足 |
| method    | string | 是   | 匹配方式，可选 `eq`, `neq`, `include`, `exclude`, `gt`, `gte`, `lt`, `lte`，默认 `eq` |
| condition | string | 否   | 可选 `and`, `or`, `""`                                       |

### 请求参数示例

```json
{
    "bk_biz_ids": [5000140, 5000141],
    "status": ["ABNORMAL"],
    "conditions": [
        {
            "key": "severity",
            "value": [1, 2],
            "method": "eq",
            "condition": "and"
        }
    ],
    "query_string": "",
    "start_time": 1645665785,
    "end_time": 1645669385,
    "username": "",
    "fields": ["bk_biz_id", "severity", "strategy_id"],
    "size": 10,
    "need_time_partition": true
}
```

### 响应参数

| 字段    | 类型   | 描述               |
| ------- | ------ | ------------------ |
| result  | bool   | 请求是否成功       |
| code    | int    | 返回的状态码       |
| message | string | 描述信息           |
| data    | dict   | TopN统计数据       |

#### data字段说明

| 字段      | 类型        | 描述                   |
| --------- | ----------- | ---------------------- |
| doc_count | int         | 总文档数量             |
| fields    | List[Field] | 各字段的TopN统计结果   |

#### data.fields字段说明

| 字段         | 类型         | 描述                     |
| ------------ | ------------ | ------------------------ |
| field        | string       | 字段名                   |
| is_char      | bool         | 是否为字符类型字段       |
| bucket_count | int          | 该字段的桶总数           |
| buckets      | List[Bucket] | TopN桶列表               |

#### data.fields.buckets字段说明

| 字段  | 类型   | 描述           |
| ----- | ------ | -------------- |
| id    | string | 桶ID           |
| name  | string | 桶显示名称     |
| count | int    | 该桶的文档数量 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "doc_count": 1250,
        "fields": [
            {
                "field": "bk_biz_id",
                "is_char": false,
                "bucket_count": 15,
                "buckets": [
                    {
                        "id": "5000140",
                        "name": "5000140",
                        "count": 450
                    },
                    {
                        "id": "5000141",
                        "name": "5000141",
                        "count": 320
                    },
                    {
                        "id": "5000142",
                        "name": "5000142",
                        "count": 280
                    },
                    {
                        "id": "5000143",
                        "name": "5000143",
                        "count": 200
                    }
                ]
            },
            {
                "field": "severity",
                "is_char": false,
                "bucket_count": 3,
                "buckets": [
                    {
                        "id": "3",
                        "name": "3",
                        "count": 600
                    },
                    {
                        "id": "2",
                        "name": "2",
                        "count": 400
                    },
                    {
                        "id": "1",
                        "name": "1",
                        "count": 250
                    }
                ]
            },
            {
                "field": "strategy_id",
                "is_char": false,
                "bucket_count": 25,
                "buckets": [
                    {
                        "id": "41868",
                        "name": "41868",
                        "count": 180
                    },
                    {
                        "id": "41869",
                        "name": "41869",
                        "count": 150
                    },
                    {
                        "id": "41870",
                        "name": "41870",
                        "count": 120
                    }
                ]
            }
        ]
    }
}
```
