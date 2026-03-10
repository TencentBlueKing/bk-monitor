### 功能描述

查询自定义时序指标列表，支持分页、搜索和排序

### 请求参数

| 字段                              | 类型     | 必选 | 描述                                                       |
|---------------------------------|--------|----|----------------------------------------------------------|
| group_id                        | int    | 是  | 自定义时序数据源 ID                                              |
| page                            | int    | 否  | 页数，从1开始，默认为1                                             |
| page_size                       | int    | 否  | 每页数量，默认为10, 最小为 1，最大为 1000                               |
| conditions                      | list   | 否  | 搜索条件列表，同一字段的多个值用OR，不同字段之间用AND                            |
| order_by                        | string | 否  | 排序字段：name、update_time、-name、-update_time，默认为-update_time |

#### conditions列表项字段说明

| 字段                              | 类型     | 必选 | 描述                                                                                    |
|---------------------------------|--------|----|---------------------------------------------------------------------------------------|
| key                           | string | 是  | 搜索字段：name、field_config_alias、field_config_unit、field_config_aggregate_method、field_config_hidden、field_config_disabled、scope_id、field_id |
| values                           | list | 是  | 搜索值列表，多个值用OR连接                                                                          |
| search_type                     | string | 否  | 搜索类型：regex-正则表达式，fuzzy-模糊搜索，exact-精确匹配（仅对name字段有效，其他字段默认为exact），默认为fuzzy |

### 请求参数示例

```json
{
  "group_id": 123,
  "conditions": [
    {
      "key": "name",
      "values": ["cpu", "memory"],
      "search_type": "fuzzy"
    },
    {
      "key": "field_config_unit",
      "values": ["ms", "percent"]
    },
    {
      "key": "scope_id",
      "values": ["1", "2"]
    }
  ],
  "page": 1,
  "page_size": 10,
  "order_by": "-update_time"
}
```

### 响应参数

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | object | 数据对象   |
| request_id | string | 请求 ID  |

#### data字段说明

| 字段     | 类型     | 描述                    |
|--------|--------|-----------------------|
| metrics | list   | 指标列表                  |
| total   | int    | 指标总的数量 |

#### metrics列表项字段说明

| 字段          | 类型     | 描述                                      |
|-------------|--------|-----------------------------------------|
| field_id    | int    | 字段ID                                    |
| scope       | dict | 指标分组信息，包含id和name字段              |
| name        | string | 指标名称                                    |
| tag_list    | list   | 指标的维度名称列表                           |
| field_config | dict   | 字段配置对象（包含alias、unit、hidden、aggregate_method、function、interval、disabled等）                        |
| field_scope | string | 字段所属分组                                  |
| create_time | float  | 创建时间（Unix时间戳，秒级浮点数）               |
| update_time | float  | 更新时间（Unix时间戳，秒级浮点数）               |

### 响应参数示例

```json
{
  "message": "OK",
  "code": 200,
  "data": {
    "metrics": [
      {
        "field_id": 1001,
        "scope": {
          "id": 1,
          "name": "指标分组名1"
        },
        "name": "cpu_usage",
        "tag_list": ["dimension1", "dimension2"],
        "field_config": {
          "alias": "CPU使用率",
          "unit": "percent",
          "hidden": false,
          "aggregate_method": "avg",
          "function": "sum",
          "interval": 60,
          "disabled": false
        },
        "field_scope": "default",
        "create_time": 1732761330.123,
        "update_time": 1733122815.456
      }
    ],
    "total": 150
  },
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```
