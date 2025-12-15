### 功能描述

查询自定义时序指标分组列表
支持通过 group_id、scope_ids 和 scope_name 进行查询，返回列表结果

### 请求参数

| 字段         | 类型     | 必选 | 描述                                           |
|------------|--------|----|----------------------------------------------|
| group_id   | int    | 是  | 自定义时序数据源 ID                                 |
| scope_ids  | list   | 否  | 指标分组ID列表，如果提供了此字段，则使用 scope_ids 进行精确查询（支持多个ID） |
| scope_name | string | 否  | 指标分组名称，支持模糊查询（不区分大小写） |

### 请求参数示例

#### 示例1：查询指定数据源下的所有分组
```json
{
  "group_id": 123
}
```

#### 示例2：查询指定数据源下的多个分组
```json
{
  "group_id": 123,
  "scope_ids": [1, 2, 3]
}
```

#### 示例3：通过名称模糊查询
```json
{
  "group_id": 123,
  "scope_name": "cpu"
}
```

#### 示例4：组合查询
```json
{
  "group_id": 123,
  "scope_ids": [1, 2],
  "scope_name": "memory"
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

| 字段               | 类型     | 描述                                       |
|------------------|--------|------------------------------------------|
| scope_id         | int    | 自定义时序指标分组 ID（未分组时为 None）                 |
| group_id         | int    | 自定义时序数据源 ID                              |
| scope_name       | string | 指标分组名                                    |
| dimension_config | dict   | 分组下的维度配置（key 为维度名，value 为维度配置对象）         |
| auto_rules       | list   | 自动分组的匹配规则列表                              |
| metric_list      | list   | 包含完整的指标配置信息列表                            |
| create_from      | string | 创建来源（user: 用户创建，data: 数据自动创建，未分组时为 None） |

#### metric_list 列表项字段说明

| 字段               | 类型     | 描述                   |
|------------------|--------|----------------------|
| metric_name      | string | 指标名称                 |
| field_id         | int    | 字段ID      |
| field_scope      | string | 字段所属分组    |
| tag_list         | list   | 指标的维度名称列表（字符串列表）     |
| field_config     | dict   | 字段配置对象（包含指标的详细配置信息） |
| create_time      | float  | 创建时间（Unix时间戳，秒级浮点数，可能为 None） |
| last_modify_time | float  | 最后更新时间（Unix时间戳，秒级浮点数，可能为 None） |

#### field_config 配置对象字段说明

| 字段               | 类型     | 描述                    |
|------------------|--------|-----------------------|
| alias             | string | 指标别名                  |
| unit             | string | 指标单位                  |
| hidden           | bool   | 是否隐藏                  |
| aggregate_method | string | 聚合方法（如 avg、sum、max 等） |
| function         | string | 常用聚合函数                |
| interval         | int    | 默认聚合周期（秒）             |
| disabled         | bool   | 是否禁用                  |

#### dimension_config 配置对象字段说明

`dimension_config` 是一个字典，key 为维度名称，value 为维度配置对象，包含以下字段：

| 字段     | 类型     | 描述      |
|--------|--------|---------|
| alias   | string | 维度别名    |
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
          "alias": "维度1别名",
          "common": true,
          "hidden": false
        },
        "dimension2": {
          "alias": "维度2别名",
          "common": false,
          "hidden": false
        }
      },
      "auto_rules": [
        "metric_prefix_*"
      ],
      "metric_list": [
        {
          "metric_name": "metric1",
          "field_id": 1001,
          "field_scope": "default",
          "tag_list": [
            "dimension1",
            "dimension2"
          ],
          "field_config": {
            "alias": "指标1别名",
            "unit": "ms",
            "hidden": false,
            "aggregate_method": "avg",
            "function": "sum",
            "interval": 60,
            "disabled": false
          },
          "create_time": 1732761330.123,
          "last_modify_time": 1733122815.456
        },
        {
          "metric_name": "metric2",
          "field_id": 1002,
          "field_scope": "default",
          "tag_list": [
            "dimension1"
          ],
          "field_config": {
            "alias": "指标2别名",
            "unit": "count",
            "hidden": false,
            "aggregate_method": "sum",
            "function": "max",
            "interval": 60,
            "disabled": false
          },
          "create_time": 1732847400.789,
          "last_modify_time": 1732968320.012
        }
      ],
      "create_from": "user"
    },
    {
      "scope_id": 2,
      "group_id": 123,
      "scope_name": "指标分组名2",
      "dimension_config": {},
      "auto_rules": [],
      "metric_list": [],
      "create_from": "data"
    }
  ],
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```

