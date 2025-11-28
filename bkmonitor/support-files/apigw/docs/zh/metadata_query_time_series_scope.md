### 功能描述

查询自定义时序指标分组列表
支持通过 group_id 和 scope_name 进行模糊匹配查询，返回列表结果

### 请求参数

| 字段         | 类型     | 必选 | 描述                                           |
|------------|--------|----|----------------------------------------------|
| group_id   | int    | 否  | 自定义时序数据源 ID，对 APM 场景需要传递 scope_name 来区分不同的服务 |
| scope_name | string | 否  | 指标分组名，支持模糊匹配                                 |

### 请求参数示例

```json
{
  "group_id": 123,
  "scope_name": "指标分组名"
}
```

### 响应参数

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | list   | 数据列表   |
| request_id | string | 请求 ID  |

#### data字段说明

data 为列表类型，包含所有匹配的结果

#### data列表项字段说明

| 字段               | 类型     | 描述                               |
|------------------|--------|----------------------------------|
| scope_id         | int    | 自定义时序指标分组 ID                     |
| group_id         | int    | 自定义时序数据源 ID                      |
| scope_name       | string | 指标分组名                            |
| dimension_config | dict   | 分组下的维度配置（key 为维度名，value 为维度配置对象） |
| manual_list      | list   | 手动分组的指标列表                        |
| auto_rules       | list   | 自动分组的匹配规则列表                      |
| metric_list      | list   | 包含完整的指标配置信息列表                    |
| create_from      | string | 创建来源（user: 用户创建，data: 数据自动创建）    |

#### metric_list 列表项字段说明

| 字段               | 类型     | 描述                    |
|------------------|--------|-----------------------|
| metric_name      | string | 指标名称                  |
| desc             | string | 指标描述                  |
| unit             | string | 指标单位                  |
| hidden           | bool   | 是否隐藏                  |
| aggregate_method | string | 聚合方法（如 avg、sum、max 等） |
| function         | string | 常用聚合函数                |
| interval         | int    | 默认聚合周期（秒）             |

#### dimension_config 配置对象字段说明

`dimension_config` 是一个字典，key 为维度名称，value 为维度配置对象，包含以下字段：

| 字段     | 类型     | 描述      |
|--------|--------|---------|
| desc   | string | 维度描述    |
| common | bool   | 是否为常用维度 |
| hidden | bool   | 是否隐藏该维度 |

### 响应参数示例

```json
{
  "message": "OK",
  "code": 200,
  "data": [
    {
      "scope_id": 1,
      "group_id": 123,
      "scope_name": "指标分组名1",
      "dimension_config": {
        "dimension1": {
          "desc": "维度1描述",
          "common": true,
          "hidden": false
        },
        "dimension2": {
          "desc": "维度2描述",
          "common": false,
          "hidden": false
        }
      },
      "manual_list": [
        "metric1",
        "metric2"
      ],
      "auto_rules": [
        "metric_prefix_*"
      ],
      "metric_list": [
        {
          "metric_name": "metric1",
          "desc": "指标1描述",
          "unit": "ms",
          "hidden": false,
          "aggregate_method": "avg",
          "function": "sum",
          "interval": 60
        },
        {
          "metric_name": "metric2",
          "desc": "指标2描述",
          "unit": "count",
          "hidden": false,
          "aggregate_method": "sum",
          "function": "max",
          "interval": 60
        }
      ],
      "create_from": "user"
    },
    {
      "scope_id": 2,
      "group_id": 123,
      "scope_name": "指标分组名2",
      "dimension_config": {},
      "manual_list": [],
      "auto_rules": [],
      "metric_list": [],
      "create_from": "data"
    }
  ],
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```

