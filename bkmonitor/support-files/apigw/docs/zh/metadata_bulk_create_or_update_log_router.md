### 功能描述

批量创建或更新日志路由配置

### 请求参数

| 字段         | 类型         | 必选 | 描述               |
|------------|------------|----|------------------|
| space_type | str        | 是  | 空间类型             |
| space_id   | str        | 是  | 空间ID             |
| data_label | str        | 是  | 数据标签（允许为空字符串）    |
| table_info | list[dict] | 是  | 结果表信息列表，至少包含1个元素 |

#### table_info 元素字段说明

| 字段                   | 类型         | 必选 | 描述                                                   |
|----------------------|------------|----|------------------------------------------------------|
| table_id             | str        | 是  | 结果表ID                                                |
| cluster_id           | int        | 否  | 存储集群ID                                               |
| index_set            | str        | 否  | 索引集规则                                                |
| source_type          | str        | 否  | 数据源类型                                                |
| bkbase_table_id      | str        | 否  | 计算平台结果表ID（Doris存储时使用）                                |
| origin_table_id      | str        | 否  | 原始结果表ID                                              |
| need_create_index    | bool       | 否  | 是否创建索引（ES存储时使用）                                      |
| storage_type         | str        | 否  | 存储类型，可选值：`elasticsearch`、`doris`，默认为 `elasticsearch` |
| is_enable            | bool       | 否  | 是否启用                                                 |
| query_alias_settings | list[dict] | 否  | 查询别名设置列表                                             |

#### table_info.options 元素字段说明

| 字段         | 类型  | 必选 | 描述               |
|------------|-----|----|------------------|
| name       | str | 是  | 选项名称             |
| value      | str | 是  | 选项值              |
| value_type | str | 否  | 值类型，默认为 `dict`   |
| creator    | str | 否  | 创建者，默认为 `system` |

#### table_info.query_alias_settings 元素字段说明

| 字段          | 类型  | 必选 | 描述           |
|-------------|-----|----|--------------|
| field_name  | str | 是  | 需要设置查询别名的字段名 |
| query_alias | str | 是  | 字段的查询别名      |

### 请求参数示例

```json
{
    "bk_tenant_id": "default",
    "space_type": "bkcc",
    "space_id": "2",
    "data_label": "test_label",
    "table_info": [
        {
            "table_id": "2_bklog.test_index_01",
            "cluster_id": 1,
            "index_set": "2_bklog.test_index_01*",
            "source_type": "log",
            "storage_type": "elasticsearch",
            "need_create_index": true,
            "is_enable": true,
            "query_alias_settings": [
                {
                    "field_name": "log",
                    "query_alias": "message"
                }
            ]
        },
        {
            "table_id": "2_bklog.test_index_02",
            "cluster_id": 1,
            "index_set": "2_bklog.test_index_02*",
            "source_type": "log",
            "storage_type": "elasticsearch",
            "need_create_index": true,
            "is_enable": true
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
| data    | null   | 无返回数据  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
