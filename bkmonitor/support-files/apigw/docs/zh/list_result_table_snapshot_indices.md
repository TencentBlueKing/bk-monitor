### 功能描述

查询结果表快照配置列表，包含物理索引详情信息

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

| 字段      | 类型     | 描述                                               |
|---------|--------|--------------------------------------------------|
| result  | bool   | 请求是否成功                                           |
| code    | int    | 返回的状态码                                           |
| message | string | 描述信息                                             |
| data    | list   | 返回数据，二维列表，外层每个元素对应一个结果表的快照列表（从ES实时获取，若获取失败则为空列表） |

#### data 元素说明

`data` 中每个元素是一个 list，对应一个结果表的所有快照记录。

#### data[][] 快照记录字段说明

| 字段            | 类型     | 描述                                              |
|---------------|--------|-------------------------------------------------|
| snapshot_name | string | 快照名称（来自ES）                                      |
| state         | string | 快照状态（来自ES，如 `SUCCESS`、`IN_PROGRESS`、`FAILED` 等） |
| table_id      | string | 结果表ID                                           |
| expired_time  | float  | 快照过期时间（Unix 时间戳），永久保存时为 `null`                  |
| indices       | list   | 快照包含的物理索引列表                                     |

#### data[][][] indices 元素字段说明

| 字段              | 类型     | 描述                    |
|-----------------|--------|-----------------------|
| table_id        | string | 结果表ID                 |
| cluster_id      | int    | ES存储集群ID              |
| repository_name | string | 快照仓库名称                |
| snapshot_name   | string | 快照名称                  |
| index_name      | string | 物理索引名称                |
| start_time      | float  | 索引开始时间（Unix 时间戳）      |
| end_time        | float  | 索引结束时间（Unix 时间戳）      |
| doc_count       | int    | 文档数量                  |
| store_size      | int    | 索引大小（字节）              |
| is_stored       | bool   | 该索引是否已被回溯（restore）到集群 |
| bk_tenant_id    | string | 租户ID                  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        [
            {
                "snapshot_name": "2_bklog.test_index_20240101000000",
                "state": "SUCCESS",
                "table_id": "2_bklog.test_index",
                "expired_time": 1704643200.0,
                "indices": [
                    {
                        "table_id": "2_bklog.test_index",
                        "cluster_id": 1,
                        "repository_name": "my_snapshot_repo",
                        "snapshot_name": "2_bklog.test_index_20240101000000",
                        "index_name": "v2_2_bklog.test_index_20240101_0",
                        "start_time": 1704038400.0,
                        "end_time": 1704124800.0,
                        "doc_count": 10000,
                        "store_size": 1048576,
                        "is_stored": false,
                        "bk_tenant_id": "system"
                    }
                ]
            }
        ],
        [
            {
                "snapshot_name": "2_bklog.another_index_20240101000000",
                "state": "SUCCESS",
                "table_id": "2_bklog.another_index",
                "expired_time": null,
                "indices": []
            }
        ]
    ]
}
```
