### 功能描述

验证 ES 快照仓库是否可访问

### 请求参数

| 字段                       | 类型     | 必选 | 描述        |
|--------------------------|--------|----|-----------|
| cluster_id               | int    | 是  | ES 存储集群ID |
| snapshot_repository_name | string | 是  | 快照仓库名称    |

### 请求参数示例

```json
{
    "cluster_id": 1,
    "snapshot_repository_name": "my_snapshot_repo"
}
```

### 响应参数

| 字段      | 类型     | 描述                               |
|---------|--------|----------------------------------|
| result  | bool   | 请求是否成功                           |
| code    | int    | 返回的状态码                           |
| message | string | 描述信息                             |
| data    | dict   | 返回数据，为 ES 快照仓库验证结果，包含可访问该仓库的节点信息 |

#### data 字段说明

| 字段    | 类型   | 描述                                      |
|-------|------|-----------------------------------------|
| nodes | dict | 可访问该快照仓库的 ES 节点信息，key 为节点ID，value 为节点详情 |

#### data.nodes[节点ID] 字段说明

| 字段   | 类型     | 描述   |
|------|--------|------|
| name | string | 节点名称 |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "nodes": {
            "YMFSs1r7QWCbIjOt_L_ZfA": {
                "name": "es-node-1"
            },
            "1xYjpOC4Th6NwPgQt6b3zQ": {
                "name": "es-node-2"
            }
        }
    },
    "result": true
}
```
