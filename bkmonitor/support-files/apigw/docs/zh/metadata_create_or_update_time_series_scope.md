
### 功能描述

批量创建或更新自定义时序指标分组
如果指标分组已存在则更新，不存在则创建。支持批量操作多个分组。


### 请求参数

| 字段           | 类型   | 必选 | 描述        |
| -------------- | ------ | ---- | ----------- |
| scopes | list | 是 | 批量创建或更新的分组列表，至少包含一个分组 |

#### scopes 列表项字段说明

| 字段           | 类型   | 必选 | 描述             |
| -------------- | ------ | ---- |----------------|
| group_id | int | 是 | 自定义时序数据源 ID    |
| scope_name | string | 是 | 指标分组名，最大长度 255 |
| new_scope_name | string | 否 | 新的指标分组名（仅更新时生效），最大长度 255 |
| dimension_config | dict | 否 | 分组下的维度配置，默认为空字典 |
| manual_list | list | 否 | 手动分组的指标列表，默认为空列表 |
| auto_rules | list | 否 | 自动分组的匹配规则列表，默认为空列表 |
| delete_unmatched_dimensions | bool | 否 | 是否删除不再匹配的维度配置（仅更新时生效），默认为 false。对于导入分组场景，建议设置为 false |


### 请求参数示例

```json
{
	"scopes": [
		{
			"group_id": 123,
			"scope_name": "指标分组名1",
			"dimension_config": {
				"metric1": ["dim1", "dim2"]
			},
			"manual_list": ["metric1", "metric2"],
			"auto_rules": [
				{
					"pattern": "cpu_*",
					"type": "wildcard"
				}
			]
		},
		{
			"group_id": 123,
			"scope_name": "指标分组名2",
			"new_scope_name": "新的指标分组名2",
			"delete_unmatched_dimensions": true
		}
	]
}
```

### 创建的逻辑说明
- **创建**：如果指定的 group_id 和 scope_name 组合不存在，则创建新的指标分组

#### dimension_config 具体内容说明

维度配置是一个字典，key 为维度名称，value 为维度配置信息

#### manual_list 具体内容说明

手动分组的指标列表，包含需要手动分组的指标名称

#### auto_rules 具体内容说明

自动分组的匹配规则列表，每个规则用于匹配指标名称

#### dimension_config 与 manual_list 、 auto_rules 之间的关系
1. dimension_config 视为 X
2. 根据 manual_list 和 auto_rules 获取指标维度的并集，视为 Y
3. 最终维度集合是 X | Y

### 更新的逻辑说明
- **更新**：如果指定的 group_id 和 scope_name 组合已存在，则更新该分组
    - 如果提供了 new_scope_name，则会重命名分组
    - 如果 delete_unmatched_dimensions 为 true，会删除不再匹配 manual_list 和 auto_rules 的维度配置

#### dimension_config 具体内容说明

维度配置是一个字典，key 为维度名称，value 为维度配置信息

#### manual_list 具体内容说明

手动分组的指标列表，包含需要手动分组的指标名称

#### auto_rules 具体内容说明

自动分组的匹配规则列表，每个规则用于匹配指标名称

#### dimension_config 与 manual_list 、 auto_rules 和 delete_unmatched_dimensions 之间的关系
1. 先将旧 dimension_config 用传递进来的 dimension_config 进行覆盖，得到 X
2. 根据 manual_list 和 auto_rules 获取指标维度的并集，得到 Y
3. 当 delete_unmatched_dimensions 为 true 则最终集合为 (X & Y) | Y，反之 X | Y

### 响应参数

| 字段       | 类型   | 描述         |
| ---------- | ------ | ------------ |
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息     |
| data       | list   | 创建或更新的分组结果列表 |
| request_id | string | 请求ID       |

#### data 列表项字段说明

| 字段       | 类型   | 描述         |
| ---------- | ------ | ------------ |
| group_id   | int    | 自定义时序数据源 ID |
| scope_name | string | 指标分组名 |
| action     | string | 操作类型，created 或 updated |

### 响应参数示例

```json
{
    "message":"OK",
    "code":200,
    "data": [
        {
            "group_id": 123,
            "scope_name": "指标分组名1",
            "action": "created"
        },
        {
            "group_id": 123,
            "scope_name": "新的指标分组名2",
            "action": "updated"
        }
    ],
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```