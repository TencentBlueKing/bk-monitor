### 功能描述

查询ES快照仓库列表，支持按集群ID列表过滤

### 请求参数

| 字段          | 类型        | 必选 | 描述                 |
|-------------|-----------|----|--------------------| 
| cluster_ids | list[int] | 否  | ES存储集群ID列表，不传则返回所有 |

### 请求参数示例

```json
{
    "cluster_ids": [1, 2]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段               | 类型     | 描述                                 |
|------------------|--------|------------------------------------|
| repository_name  | string | 快照仓库名称                             |
| cluster_id       | int    | ES存储集群ID                           |
| alias            | string | 快照仓库别名                             |
| creator          | string | 创建者                                |
| create_time      | float  | 创建时间（Unix 时间戳）                     |
| last_modify_user | string | 最后修改者                              |
| last_modify_time | float  | 最后修改时间（Unix 时间戳）                   |
| bk_tenant_id     | string | 租户ID                               |
| type             | string | 仓库类型（来自 ES，如 `fs`、`s3` 等，获取失败时不返回） |
| settings         | dict   | 仓库配置（来自 ES，具体字段取决于仓库类型，获取失败时不返回）   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "repository_name": "my_snapshot_repo",
            "cluster_id": 1,
            "alias": "my_repo_alias",
            "creator": "admin",
            "create_time": 1704038400.0,
            "last_modify_user": "admin",
            "last_modify_time": 1704038400.0,
            "bk_tenant_id": "system",
            "type": "fs",
            "settings": {
                "location": "/mnt/snapshot"
            }
        },
        {
            "repository_name": "another_alias",
            "cluster_id": 2,
            "alias": "another_alias",
            "creator": "admin",
            "create_time": 1704038400.0,
            "last_modify_user": "admin",
            "last_modify_time": 1704038400.0,
            "bk_tenant_id": "system",
            "type": "s3",
            "settings": {
                "bucket": "my-bucket"
            }
        }
    ]
}
```
