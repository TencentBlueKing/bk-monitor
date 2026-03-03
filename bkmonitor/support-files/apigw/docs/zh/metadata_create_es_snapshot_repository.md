### 功能描述

创建 ES 快照仓库

### 请求参数

| 字段                       | 类型     | 必选 | 描述              |
|--------------------------|--------|----|-----------------|
| cluster_id               | int    | 是  | ES 存储集群ID       |
| snapshot_repository_name | string | 是  | 快照仓库名称          |
| es_config                | dict   | 是  | 快照仓库配置          |
| alias                    | string | 是  | 仓库别名            |
| operator                 | string | 是  | 操作者             |

#### es_config 字段说明

`es_config` 为 ES 原生快照仓库配置，其结构由 Elasticsearch 官方定义，常用字段如下：

| 字段       | 类型     | 必选 | 描述                                                 |
|----------|--------|----|----------------------------------------------------|
| type     | string | 是  | 仓库类型，如 `fs`（共享文件系统）、`s3`（AWS S3）、`hdfs` 等          |
| settings | dict   | 是  | 仓库具体配置，内容随 `type` 不同而不同，例如 `fs` 类型需要 `location` 字段 |

### 请求参数示例

```json
{
    "cluster_id": 1,
    "snapshot_repository_name": "my_snapshot_repo",
    "es_config": {
        "type": "fs",
        "settings": {
            "location": "/mnt/es_snapshots"
        }
    },
    "alias": "我的快照仓库",
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

基础字段来自数据库记录，`type` 和 `settings` 字段来自 ES `snapshot.get_repository` 接口的返回，会合并到结果中。

| 字段               | 类型     | 描述                                         |
|------------------|--------|--------------------------------------------|
| repository_name  | string | 仓库名称                                       |
| cluster_id       | int    | 集群ID                                       |
| alias            | string | 仓库别名                                       |
| creator          | string | 创建者                                        |
| create_time      | float  | 创建时间（Unix 时间戳）                             |
| last_modify_user | string | 最后修改者                                      |
| last_modify_time | float  | 最后修改时间（Unix 时间戳）                           |
| bk_tenant_id     | string | 租户ID                                       |
| type             | string | 仓库类型（来自 ES，如 `fs`、`s3` 等），获取 ES 仓库信息失败时不返回 |
| settings         | dict   | 仓库具体配置（来自 ES），获取 ES 仓库信息失败时不返回             |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "repository_name": "my_snapshot_repo",
        "cluster_id": 1,
        "alias": "我的快照仓库",
        "creator": "admin",
        "create_time": 1704067200.0,
        "last_modify_user": "admin",
        "last_modify_time": 1704067200.0,
        "bk_tenant_id": "system",
        "type": "fs",
        "settings": {
            "location": "/mnt/es_snapshots"
        }
    },
    "result": true
}
```
