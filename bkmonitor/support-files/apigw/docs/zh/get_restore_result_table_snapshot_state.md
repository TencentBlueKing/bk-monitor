### 功能描述

查询快照回溯任务状态

### 请求参数

| 字段          | 类型        | 必选 | 描述         |
|-------------|-----------|----|------------|
| restore_ids | list[int] | 是  | 快照回溯任务ID列表 |

### 请求参数示例

```json
{
    "restore_ids": [1, 2]
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

| 字段                 | 类型  | 描述       |
|--------------------|-----|----------|
| table_id           | str | 结果表ID    |
| restore_id         | int | 快照回溯任务ID |
| total_doc_count    | int | 总文档数     |
| complete_doc_count | int | 已完成文档数   |
| duration           | int | 耗时（秒）    |
| bk_tenant_id       | str | 租户ID     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "table_id": "2_bklog.test_index",
            "restore_id": 1,
            "total_doc_count": 1000,
            "complete_doc_count": 800,
            "duration": 120,
            "bk_tenant_id": "default"
        }
    ]
}
```
