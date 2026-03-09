### 功能描述

拉取单业务的计算平台RT元信息

### 请求参数

| 字段           | 类型  | 必选 | 描述                |
|--------------|-----|----|-------------------|
| bk_biz_id    | str | 是  | 业务ID              |
| page         | int | 否  | 页码，默认为1，最小值为1     |
| page_size    | int | 否  | 每页数量，默认为0（0表示不分页） |

### 请求参数示例

```json
{
    "bk_biz_id": "2",
    "page": 1,
    "page_size": 10
}
```

### 响应参数

| 字段      | 类型          | 描述               |
|---------|-------------|------------------|
| result  | bool        | 请求是否成功           |
| code    | int         | 返回的状态码           |
| message | string      | 描述信息             |
| data    | object/list | 分页时返回对象，不分页时返回列表 |

#### data 字段说明（分页模式，page_size > 0）

| 字段    | 类型   | 描述      |
|-------|------|---------|
| count | int  | 总记录数    |
| info  | list | 结果表信息列表 |

#### info 元素字段说明

| 字段               | 类型         | 描述                              |
|------------------|------------|---------------------------------|
| table_id         | str        | 结果表ID                           |
| bk_tenant_id     | str        | 租户ID                            |
| table_name_zh    | str        | 结果表中文名                          |
| is_custom_table  | bool       | 是否自定义结果表                        |
| scheme_type      | str        | Schema类型                        |
| default_storage  | str        | 默认存储类型，计算平台结果表固定为 `bkdata`      |
| storage_list     | list[str]  | 存储类型列表                          |
| creator          | str        | 创建者                             |
| create_time      | str        | 创建时间，格式：`YYYY-MM-DD HH:MM:SS`   |
| last_modify_user | str        | 最后修改者                           |
| last_modify_time | str        | 最后修改时间，格式：`YYYY-MM-DD HH:MM:SS` |
| field_list       | list[dict] | 字段列表                            |
| bk_biz_id        | int        | 业务ID                            |
| option           | dict       | 结果表选项                           |
| label            | str        | 标签                              |
| bk_data_id       | int/null   | 数据源ID，计算平台类型结果表时为 `null`        |
| is_enable        | bool       | 是否启用                            |
| data_label       | str        | 数据标签                            |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "count": 1,
        "info": [
            {
                "table_id": "2_bkbase_rt_001",
                "bk_tenant_id": "default",
                "table_name_zh": "计算平台结果表001",
                "is_custom_table": false,
                "scheme_type": "free",
                "default_storage": "bkdata",
                "storage_list": ["bkdata"],
                "creator": "admin",
                "create_time": "2024-01-01 00:00:00",
                "last_modify_user": "admin",
                "last_modify_time": "2024-01-01 00:00:00",
                "field_list": [],
                "bk_biz_id": 2,
                "option": {},
                "label": "other_rt",
                "bk_data_id": null,
                "is_enable": true,
                "data_label": ""
            }
        ]
    }
}
```
