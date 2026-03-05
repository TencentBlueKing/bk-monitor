### 功能描述

批量查询自定义时序分组信息

### 请求参数

| 字段                     | 类型     | 必选 | 描述              |
|------------------------|--------|----|-----------------|
| label                  | string | 否  | 自定义时序分组标签（监控对象） |
| time_series_group_name | string | 否  | 自定义时序分组名称       |
| bk_biz_id              | string | 否  | 业务ID            |
| page                   | int    | 否  | 页码，默认为 1        |
| page_size              | int    | 否  | 每页数量，默认为 0（不分页） |

### 请求参数示例

```json
{
    "label": "application",
    "time_series_group_name": "自定义时序分组名",
    "bk_biz_id": "2",
    "page": 1,
    "page_size": 10
}
```

### 响应参数

| 字段      | 类型          | 描述                              |
|---------|-------------|---------------------------------|
| result  | bool        | 请求是否成功                          |
| code    | int         | 返回的状态码                          |
| message | string      | 描述信息                            |
| data    | list 或 dict | 不分页时为列表，分页时为包含 count 和 info 的字典 |

#### data 分页时字段说明（page_size > 0）

| 字段    | 类型   | 描述     |
|-------|------|--------|
| count | int  | 总记录数   |
| info  | list | 分组信息列表 |

#### data 元素字段说明（不分页时为 data 列表元素，分页时为 data.info 列表元素）

| 字段                     | 类型     | 描述                                           |
|------------------------|--------|----------------------------------------------|
| time_series_group_id   | int    | 自定义时序分组ID                                    |
| time_series_group_name | string | 时序分组名称                                       |
| bk_data_id             | int    | 数据源ID                                        |
| bk_biz_id              | int    | 业务ID                                         |
| table_id               | string | 结果表ID                                        |
| label                  | string | 自定义时序标签                                      |
| is_enable              | bool   | 是否启用                                         |
| creator                | string | 创建者                                          |
| create_time            | string | 创建时间                                         |
| last_modify_user       | string | 最后修改者                                        |
| last_modify_time       | string | 最后修改时间                                       |
| metric_info_list       | list   | 指标列表                                         |
| data_label             | string | 数据标签                                         |
| shipper_list           | list   | 结果表存储配置列表（仅 with_result_table_info=true 时返回） |

#### data[].metric_info_list 元素字段说明

| 字段                  | 类型     | 描述             |
|---------------------|--------|----------------|
| field_name          | string | 指标字段名          |
| metric_display_name | str    | 指标展示名称         |
| description         | string | 描述             |
| unit                | string | 单位             |
| type                | string | 字段类型           |
| is_disabled         | bool   | 是否禁用           |
| table_id            | string | 结果表ID（分表模式下有值） |
| tag_list            | list   | 维度列表           |

#### data[].metric_info_list[].tag_list 元素字段说明

| 字段          | 类型     | 描述    |
|-------------|--------|-------|
| field_name  | string | 维度字段名 |
| description | string | 描述    |
| unit        | string | 单位    |
| type        | string | 字段类型  |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": [
        {
            "time_series_group_id": 1,
            "time_series_group_name": "bkunifylogbeat common metrics",
            "bk_data_id": 1100006,
            "bk_biz_id": 0,
            "table_id": "bkunifylogbeat_common.base",
            "label": "service_process",
            "is_enable": true,
            "creator": "system",
            "create_time": "2021-12-07 03:29:51",
            "last_modify_user": "system",
            "last_modify_time": "2021-12-07 03:29:51",
            "data_label": "bkunifylogbeat_common",
            "metric_info_list": [
                {
                    "field_name": "mem_usage",
                    "metric_display_name": "mem_usage",
                    "description": "内存使用率",
                    "unit": "percent",
                    "type": "double",
                    "is_disabled": false,
                    "table_id": "bkunifylogbeat_common.base",
                    "tag_list": [
                        {
                            "field_name": "target",
                            "description": "目标",
                            "unit": "",
                            "type": "string"
                        }
                    ]
                }
            ]
        }
    ],
    "result": true
}
```