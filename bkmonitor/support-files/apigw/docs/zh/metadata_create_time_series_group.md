### 功能描述

创建自定义时序分组

### 请求参数

| 字段                     | 类型     | 必选 | 描述                                               |
|------------------------|--------|----|--------------------------------------------------|
| bk_data_id             | string | 是  | 数据源ID                                            |
| bk_biz_id              | string | 是  | 业务ID                                             |
| time_series_group_name | string | 是  | 自定义时序分组名                                         |
| label                  | string | 是  | 自定义时序分组标签，用于表示监控对象，应复用【result_table_label】类型下的标签 |
| operator               | string | 是  | 操作者                                              |
| metric_info_list       | list   | 否  | 自定义时序 metric 列表，默认为空                             |
| table_id               | string | 否  | 结果表ID                                            |
| is_split_measurement   | bool   | 否  | 是否启动自动分表逻辑，默认为 false                             |
| default_storage_config | dict   | 否  | 默认存储参数                                           |
| additional_options     | dict   | 否  | 附带创建的 ResultTableOption                          |
| data_label             | string | 否  | 数据标签，默认为空                                        |

#### metric_info_list 元素字段说明

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| field_name | string | 自定义时序名 |
| tag_list   | list   | 维度列表   |

### 请求参数示例

```json
{
    "bk_data_id": "123",
    "bk_biz_id": "123",
    "time_series_group_name": "自定义时序分组名",
    "label": "application",
    "operator": "system",
    "metric_info_list": [
        {
            "field_name": "usage for update",
            "tag_list": ["dimension_name"]
        },
        {
            "field_name": "usage for create",
            "tag_list": ["dimension_name"]
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
| data    | dict   | 数据     |

#### data 字段说明

| 字段                     | 类型     | 描述        |
|------------------------|--------|-----------|
| time_series_group_id   | int    | 新建的时序分组ID |
| bk_tenant_id           | string | 租户ID      |
| time_series_group_name | string | 时序分组名称    |
| bk_data_id             | int    | 数据源ID     |
| bk_biz_id              | int    | 业务ID      |
| table_id               | string | 结果表ID     |
| label                  | string | 分组标签      |
| is_enable              | bool   | 是否启用      |
| creator                | string | 创建人       |
| create_time            | string | 创建时间      |
| last_modify_user       | string | 最后更新人     |
| last_modify_time       | string | 最后更新时间    |
| metric_info_list       | list   | 自定义时序列表   |
| data_label             | string | 数据标签      |

#### data.metric_info_list 元素字段说明

| 字段                  | 类型     | 描述      |
|---------------------|--------|---------|
| field_name          | string | 字段名     |
| metric_display_name | string | 指标显示名称  |
| description         | string | 字段描述    |
| unit                | string | 单位      |
| type                | string | 字段类型    |
| table_id            | string | 所属结果表ID |
| is_disabled         | bool   | 是否禁用    |
| tag_list            | list   | 维度列表    |

#### data.metric_info_list.tag_list 元素字段说明

| 字段          | 类型     | 描述                 |
|-------------|--------|--------------------|
| field_name  | string | 字段名                |
| description | string | 字段描述（字段存在时返回，否则为空） |
| unit        | string | 单位（字段存在时返回）        |
| type        | string | 字段类型（字段存在时返回）      |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "bk_data_id": 123,
        "bk_biz_id": 123,
        "time_series_group_id": 1,
        "time_series_group_name": "自定义时序分组名",
        "label": "application",
        "is_enable": true,
        "creator": "admin",
        "create_time": "2019-10-10 10:10:10",
        "last_modify_user": "admin",
        "last_modify_time": "2020-10-10 10:10:10",
        "metric_info_list": [
            {
                "field_name": "mem_usage",
                "metric_display_name": "",
                "description": "mem_usage_2",
                "unit": "M",
                "type": "double",
                "table_id": "2_bkmonitor_time_series_123.base",
                "is_disabled": false,
                "tag_list": [
                    {
                        "field_name": "test_name",
                        "description": "test_name_2",
                        "unit": "M",
                        "type": "double"
                    }
                ]
            }
        ],
        "data_label": ""
    },
    "result": true
}
```