### 功能描述

创建 ES 路由配置

### 请求参数

| 字段                | 类型         | 必选 | 描述                   |
|-------------------|------------|----|----------------------|
| space_type        | str        | 是  | 空间类型                 |
| space_id          | str        | 是  | 空间 ID                |
| table_id          | str        | 是  | 结果表 ID               |
| data_label        | str        | 否  | 数据标签                 |
| cluster_id        | int        | 否  | ES 集群 ID             |
| index_set         | str        | 否  | 索引集规则                |
| source_type       | str        | 否  | 数据源类型                |
| need_create_index | bool       | 否  | 是否创建索引               |
| origin_table_id   | str        | 否  | 原始结果表 ID             |
| options           | list[dict] | 否  | 结果表 option 列表，默认为空列表 |

#### options 元素字段说明

| 字段         | 类型  | 必选 | 描述               |
|------------|-----|----|------------------|
| name       | str | 是  | option 名称        |
| value      | str | 是  | option 值         |
| value_type | str | 否  | 值类型，默认为 `dict`   |
| creator    | str | 否  | 创建者，默认为 `system` |

### 请求参数示例

```json
{
    "space_type": "bklog",
    "space_id": "my_space",
    "table_id": "my_index_set.base",
    "data_label": "my_data_label",
    "cluster_id": 1,
    "index_set": "my_index_set_*",
    "source_type": "log",
    "need_create_index": true,
    "origin_table_id": "",
    "options": [
        {
            "name": "retention",
            "value": "7",
            "value_type": "int",
            "creator": "admin"
        }
    ]
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 返回数据   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
