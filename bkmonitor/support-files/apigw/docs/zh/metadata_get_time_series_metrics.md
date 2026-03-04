### 功能描述

获取自定义时序结果表的 metrics 信息

### 请求参数

| 字段       | 类型     | 必选 | 描述    |
|----------|--------|----|-------|
| table_id | string | 是  | 结果表ID |

### 请求参数示例

```json
{
    "table_id": "2_bkmonitor_time_series_1001.base"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段               | 类型   | 描述   |
|------------------|------|------|
| metric_info_list | list | 指标列表 |

#### data.metric_info_list 元素字段说明

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

#### data.metric_info_list[].tag_list 元素字段说明

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
    "data": {
        "metric_info_list": [
            {
                "field_name": "mem_usage",
                "metric_display_name": "mem_usage",
                "description": "内存使用率",
                "unit": "percent",
                "type": "double",
                "is_disabled": false,
                "table_id": "2_bkmonitor_time_series_1001.base",
                "tag_list": [
                    {
                        "field_name": "target",
                        "description": "目标",
                        "unit": "",
                        "type": "string"
                    }
                ]
            },
            {
                "field_name": "cpu_usage",
                "metric_display_name": "cpu_usage",
                "description": "CPU使用率",
                "unit": "percent",
                "type": "double",
                "is_disabled": false,
                "table_id": "2_bkmonitor_time_series_1001.base",
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
    },
    "result": true
}
```
