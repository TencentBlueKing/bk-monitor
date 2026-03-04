### 功能描述

查询快照回溯任务列表

### 请求参数

| 字段        | 类型        | 必选 | 描述                  |
|-----------|-----------|----|---------------------|
| table_ids | list[str] | 否  | 结果表ID列表，为空时返回所有回溯任务 |

### 请求参数示例

```json
{
    "table_ids": ["2_bklog.test_index"]
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

| 字段                 | 类型    | 描述          |
|--------------------|-------|-------------|
| restore_id         | int   | 快照恢复任务ID    |
| table_id           | str   | 结果表ID       |
| is_expired         | bool  | 是否已过期       |
| start_time         | float | 回溯开始时间（时间戳） |
| end_time           | float | 回溯结束时间（时间戳） |
| expired_time       | float | 过期时间（时间戳）   |
| indices            | str   | 回溯索引列表      |
| complete_doc_count | int   | 已完成文档数      |
| total_doc_count    | int   | 总文档数        |
| total_store_size   | int   | 总存储大小（字节）   |
| creator            | str   | 创建者         |
| create_time        | float | 创建时间（时间戳）   |
| last_modify_user   | str   | 最后修改者       |
| last_modify_time   | float | 最后修改时间（时间戳） |
| bk_tenant_id       | str   | 租户ID        |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "restore_id": 1,
            "table_id": "2_bklog.test_index",
            "is_expired": false,
            "start_time": 1704067200.0,
            "end_time": 1704153600.0,
            "expired_time": 1704240000.0,
            "indices": "restore_1_2_bklog.test_index_20240101",
            "complete_doc_count": 1000,
            "total_doc_count": 1000,
            "total_store_size": 1048576,
            "creator": "admin",
            "create_time": 1704067200.0,
            "last_modify_user": "admin",
            "last_modify_time": 1704067200.0,
            "bk_tenant_id": "default"
        }
    ]
}
```
