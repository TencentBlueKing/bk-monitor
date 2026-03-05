### 功能描述

获取结果表 ID 与其 DataLabel 的映射关系

### 请求参数

| 字段              | 类型        | 必选 | 描述                             |
|-----------------|-----------|----|--------------------------------|
| bk_biz_id       | str       | 是  | 业务 ID                          |
| table_or_labels | list[str] | 是  | 结果表 ID 或 DataLabel 列表，至少包含一个元素 |

### 请求参数示例

```json
{
    "bk_biz_id": "2",
    "table_or_labels": ["system.cpu_detail", "my_data_label"]
}
```

### 响应参数

| 字段      | 类型     | 描述                                                |
|---------|--------|---------------------------------------------------|
| result  | bool   | 请求是否成功                                            |
| code    | int    | 返回的状态码                                            |
| message | string | 描述信息                                              |
| data    | dict   | 返回数据，key 为结果表 ID 或 DataLabel，value 为对应的 DataLabel |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "system.cpu_detail": "my_data_label",
        "my_data_label_1": "my_data_label_1"
    }
}
```
