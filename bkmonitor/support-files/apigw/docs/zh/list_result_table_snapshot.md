### 功能描述

查询结果表快照配置列表

### 请求参数

| 字段        | 类型           | 必选 | 描述                  |
|-----------|--------------|----|---------------------|
| table_ids | list[string] | 否  | 结果表ID列表，不传则返回所有快照配置 |

### 请求参数示例

```json
{
    "table_ids": ["2_bklog.test_index", "2_bklog.another_index"]
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

| 字段                              | 类型     | 描述                  |
|---------------------------------|--------|---------------------|
| table_id                        | string | 结果表ID               |
| target_snapshot_repository_name | string | 目标ES集群快照仓库名称        |
| snapshot_days                   | int    | 快照存储时间（天），0表示永久保存   |
| creator                         | string | 创建者                 |
| create_time                     | float  | 创建时间（Unix 时间戳）      |
| last_modify_user                | string | 最后修改者               |
| last_modify_time                | float  | 最后修改时间（Unix 时间戳）    |
| bk_tenant_id                    | string | 租户ID                |
| doc_count                       | int    | 快照文档总数（来自物理索引统计）    |
| store_size                      | int    | 快照存储大小（字节，来自物理索引统计） |
| index_count                     | int    | 快照物理索引数量（来自物理索引统计）  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "table_id": "2_bklog.test_index",
            "target_snapshot_repository_name": "my_snapshot_repo",
            "snapshot_days": 7,
            "creator": "admin",
            "create_time": 1704038400.0,
            "last_modify_user": "admin",
            "last_modify_time": 1704038400.0,
            "bk_tenant_id": "system",
            "doc_count": 10000,
            "store_size": 1048576,
            "index_count": 3
        }
    ]
}
```
