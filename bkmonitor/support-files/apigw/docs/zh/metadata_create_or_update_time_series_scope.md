### 功能描述

批量创建或更新自定义时序指标分组
如果指标分组已存在则更新，不存在则创建。支持批量操作多个分组。

### 请求参数

| 字段           | 类型   | 必选 | 描述                                                |
|--------------|------|----|-------------------------------------------------|
| group_id     | int  | 是  | 自定义时序数据源 ID                                      |
| scopes       | list | 是  | 批量创建或更新的分组列表，至少包含一个分组                           |

#### scopes 列表项字段说明

| 字段                          | 类型     | 必选 | 描述                                                   |
|-----------------------------|--------|----|------------------------------------------------------|
| scope_id                    | int    | 否  | 指标分组 ID，存在时更新，反之创建                              
| scope_name                  | string | 否  | 指标分组名，最大长度 255，对于 default 分组无法编辑                     |
| dimension_config            | dict   | 否  | 分组下的维度配置，默认为空字典                                      |
| auto_rules                  | list   | 否  | 自动分组的匹配规则列表，默认为空列表                                   |

#### 重要说明：全量更新机制

**对于更新操作，所有列表和字典类型的字段（`dimension_config`、`auto_rules`）均采用全量更新方式，而非增量更新。**

这意味着：
- 如果传递了 `auto_rules`，会完全替换原有的 `auto_rules`，而不是追加
- 如果传递了 `dimension_config`，会完全替换原有的 `dimension_config`，而不是合并

**因此，在更新时必须传递完整的字段内容，包括需要保留的旧数据和新增的数据。**

### 请求参数示例

```json
{
  "group_id": 123,
  "scopes": [
    {
      "scope_name": "指标分组名1",
      "dimension_config": {
        "dimension1": {
          "description": "维度1描述"
        }
      },
      "auto_rules": [
        "metric_prefix_*"
      ]
    },
    {
      "scope_id": 2,
      "scope_name": "指标分组名2"
    }
  ]
}
```

### 响应参数

| 字段         | 类型     | 描述           |
|------------|--------|--------------|
| result     | bool   | 请求是否成功       |
| code       | int    | 返回的状态码       |
| message    | string | 描述信息         |
| data       | list   | 创建或更新的分组结果列表 |
| request_id | string | 请求ID         |

#### data 列表项字段说明

| 字段               | 类型     | 描述           |
|------------------|--------|--------------|
| scope_id         | int    | 指标分组 ID |
| group_id         | int    | 自定义时序数据源 ID  |
| scope_name       | string | 指标分组名        |
| dimension_config | dict   | 分组下的维度配置     |
| auto_rules       | list   | 自动分组的匹配规则列表  |
| create_from      | string | 创建来源         |

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
          "description": "维度1描述"
        }
      },
      "auto_rules": [
        "metric_prefix_*"
      ],
      "create_from": "user"
    },
    {
      "scope_id": 2,
      "group_id": 123,
      "scope_name": "新的指标分组名2",
      "dimension_config": {},
      "auto_rules": [],
      "create_from": "user"
    }
  ],
  "result": true,
  "request_id": "408233306947415bb1772a86b9536867"
}
```