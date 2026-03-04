### 功能描述

获取监控链路时序数据

### 请求参数

| 字段                   | 类型   | 必选 | 描述                                                 |
|----------------------|------|----|----------------------------------------------------|
| bk_tenant_id         | str  | 是  | 租户ID                                               |
| table_id             | str  | 是  | 结果表ID                                              |
| query_body           | dict | 是  | 查询内容（Elasticsearch查询DSL）                           |
| use_full_index_names | bool | 否  | 是否使用索引全名进行检索，默认为`false`。设置为`true`时会使用完整的索引名称列表进行查询 |

#### query_body 字段说明

query_body是标准的Elasticsearch查询DSL（Domain Specific Language），支持Elasticsearch的所有查询语法。常用字段包括：

| 字段    | 类型   | 必选 | 描述                                    |
|-------|------|----|---------------------------------------|
| query | dict | 否  | 查询条件，支持bool、match、term、range等各种ES查询类型 |
| size  | int  | 否  | 返回结果数量，默认为10                          |
| from  | int  | 否  | 分页起始位置，默认为0                           |
| sort  | list | 否  | 排序规则                                  |
| aggs  | dict | 否  | 聚合查询配置                                |

### 请求参数示例

```json
{
    "bk_tenant_id": "bk_tenant_001",
    "table_id": "2_bkapm_trace_testapp",
    "query_body": {
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "time": {
                                "gte": 1704067200000,
                                "lte": 1704153600000
                            }
                        }
                    },
                    {
                        "term": {
                            "status_code": "0"
                        }
                    }
                ],
                "filter": [
                    {
                        "term": {
                            "kind": "1"
                        }
                    }
                ]
            }
        },
        "size": 100,
        "sort": [
            {
                "time": {
                    "order": "desc"
                }
            }
        ]
    },
    "use_full_index_names": false
}
```

### 响应参数

| 字段      | 类型     | 描述                |
|---------|--------|-------------------|
| result  | bool   | 请求是否成功            |
| code    | int    | 返回的状态码            |
| message | string | 描述信息              |
| data    | dict   | Elasticsearch查询结果 |

#### data 字段说明

data字段为标准的Elasticsearch查询响应结果，主要包含以下字段：

| 字段           | 类型   | 描述              |
|--------------|------|-----------------|
| hits         | dict | 查询命中结果          |
| took         | int  | 查询耗时（毫秒）        |
| timed_out    | bool | 是否超时            |
| _shards      | dict | 分片信息            |
| aggregations | dict | 聚合结果（如果查询中包含聚合） |

#### data.hits 字段说明

| 字段 | 类型 | 描述 |
|---------|------|--------------||
| total | int/dict | 命中总数 |
| max_score | float | 最大相关性分数 |
| hits | list | 命中的文档列表 |

#### data.hits.hits 元素字段说明

| 字段      | 类型     | 描述    |
|---------|--------|-------|
| _index  | string | 索引名称  |
| _type   | string | 文档类型  |
| _id     | string | 文档ID  |
| _score  | float  | 相关性分数 |
| _source | dict   | 文档源数据 |

#### data._shards 字段说明

| 字段         | 类型  | 描述     |
|------------|-----|--------|
| total      | int | 总分片数   |
| successful | int | 成功的分片数 |
| skipped    | int | 跳过的分片数 |
| failed     | int | 失败的分片数 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "took": 5,
        "timed_out": false,
        "_shards": {
            "total": 5,
            "successful": 5,
            "skipped": 0,
            "failed": 0
        },
        "hits": {
            "total": 1523,
            "max_score": null,
            "hits": [
                {
                    "_index": "2_bkapm_trace_testapp_20240120_0",
                    "_type": "_doc",
                    "_id": "abc123def456",
                    "_score": null,
                    "_source": {
                        "time": 1704153500000,
                        "trace_id": "1a2b3c4d5e6f7g8h",
                        "span_id": "9i0j1k2l",
                        "parent_span_id": "",
                        "span_name": "GET /api/users",
                        "kind": 1,
                        "status_code": "0",
                        "elapsed_time": 125,
                        "resource": {
                            "service.name": "user-service",
                            "telemetry.sdk.language": "python",
                            "telemetry.sdk.version": "1.20.0"
                        },
                        "attributes": {
                            "http.method": "GET",
                            "http.url": "/api/users",
                            "http.status_code": 200
                        }
                    },
                    "sort": [
                        1704153500000
                    ]
                },
                {
                    "_index": "2_bkapm_trace_testapp_20240120_0",
                    "_type": "_doc",
                    "_id": "xyz789uvw012",
                    "_score": null,
                    "_source": {
                        "time": 1704153480000,
                        "trace_id": "2b3c4d5e6f7g8h9i",
                        "span_id": "0j1k2l3m",
                        "parent_span_id": "",
                        "span_name": "POST /api/orders",
                        "kind": 1,
                        "status_code": "0",
                        "elapsed_time": 256,
                        "resource": {
                            "service.name": "order-service",
                            "telemetry.sdk.language": "java",
                            "telemetry.sdk.version": "1.19.0"
                        },
                        "attributes": {
                            "http.method": "POST",
                            "http.url": "/api/orders",
                            "http.status_code": 201
                        }
                    },
                    "sort": [
                        1704153480000
                    ]
                }
            ]
        }
    }
}
```
