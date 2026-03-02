### 功能描述

创建或更新日志路由配置

### 请求参数

| 字段                   | 类型         | 必选 | 描述                             |
|----------------------|------------|----|--------------------------------|
| space_type           | str        | 否  | 空间类型（创建时必填）                    |
| space_id             | str        | 否  | 空间 ID（创建时必填）                   |
| table_id             | str        | 是  | 结果表 ID                         |
| data_label           | str        | 否  | 数据标签                           |
| cluster_id           | int        | 否  | 存储集群 ID                        |
| index_set            | str        | 否  | 索引集规则                          |
| source_type          | str        | 否  | 数据源类型                          |
| bkbase_table_id      | str        | 否  | 计算平台结果表 ID                     |
| need_create_index    | bool       | 否  | 是否需要创建索引                       |
| storage_type         | str        | 否  | 存储类型，可选值：`es`、`doris`，默认为 `es` |
| origin_table_id      | str        | 否  | 原始结果表 ID                       |
| options              | list[dict] | 否  | 结果表 option 列表，默认为空列表           |
| query_alias_settings | list[dict] | 否  | 查询别名设置列表                       |

#### options 元素字段说明

| 字段         | 类型  | 必选 | 描述               |
|------------|-----|----|------------------|
| name       | str | 是  | option 名称        |
| value      | str | 是  | option 值         |
| value_type | str | 否  | 值类型，默认为 `dict`   |
| creator    | str | 否  | 创建者，默认为 `system` |

#### query_alias_settings 元素字段说明

| 字段          | 类型  | 必选 | 描述           |
|-------------|-----|----|--------------|
| field_name  | str | 是  | 需要设置查询别名的字段名 |
| query_alias | str | 是  | 字段的查询别名      |

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
    "storage_type": "es",
    "origin_table_id": "",
    "options": [
        {
            "name": "retention",
            "value": "7",
            "value_type": "int",
            "creator": "admin"
        }
    ],
    "query_alias_settings": [
        {
            "field_name": "log",
            "query_alias": "message"
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
