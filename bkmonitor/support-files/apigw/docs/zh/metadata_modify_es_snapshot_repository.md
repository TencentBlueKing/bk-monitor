### 功能描述

修改 ES 快照仓库

### 请求参数

| 字段                       | 类型     | 必选 | 描述        |
|--------------------------|--------|----|-----------|
| cluster_id               | int    | 是  | ES 存储集群ID |
| snapshot_repository_name | string | 是  | 快照仓库名称    |
| alias                    | string | 是  | 仓库别名      |
| operator                 | string | 是  | 操作者       |

### 请求参数示例

```json
{
    "cluster_id": 1,
    "snapshot_repository_name": "my_snapshot_repo",
    "alias": "新的仓库别名",
    "operator": "admin"
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

| 字段                       | 类型     | 描述     |
|--------------------------|--------|--------|
| bk_tenant_id             | string | 租户ID   |
| cluster_id               | int    | 集群ID   |
| snapshot_repository_name | string | 快照仓库名称 |
| alias                    | string | 仓库别名   |
| operator                 | string | 操作者    |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "bk_tenant_id": "system",
        "cluster_id": 1,
        "snapshot_repository_name": "my_snapshot_repo",
        "alias": "新的仓库别名",
        "operator": "admin"
    },
    "result": true
}
```
