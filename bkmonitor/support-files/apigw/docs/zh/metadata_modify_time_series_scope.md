
### 功能描述

批量修改自定义时序指标分组
修改指定自定义时序数据源下的指标分组配置，支持更新维度配置、手动分组列表和自动分组规则，支持批量修改多个分组


### 请求参数

| 字段           | 类型   | 必选 | 描述        |
| -------------- | ------ | ---- | ----------- |
| scopes | list | 是 | 批量修改的分组列表，至少包含一个分组 |

#### scopes 列表项字段说明

| 字段           | 类型   | 必选 | 描述                                                               |
| -------------- | ------ | ---- |------------------------------------------------------------------|
| group_id | int | 是 | 自定义时序数据源 ID                                                      |
| scope_name | string | 是 | 指标分组名，最大长度 255                                                   |
| new_scope_name | string | 否 | 新的指标分组名，最大长度 255，用于修改分组名, data 创建来源的 scope 不允许修改 scope_name      |
| dimension_config | dict | 否 | 分组下的维度配置                                                         |
| manual_list | list | 否 | 手动分组的指标列表                                                        |
| auto_rules | list | 否 | 自动分组的匹配规则列表                                                      |
| delete_unmatched_dimensions | bool | 否 | 是否删除不再匹配的维度配置，默认为 false。对于导入分组场景来说，这个字段应该为 false，否则可能由于无法匹配而导入失败 |

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

### 请求参数示例

```json
{
	"scopes": [
		{
			"group_id": 123,
			"scope_name": "指标分组名1",
			"new_scope_name": "新指标分组名1",
			"dimension_config": {
				"dimension1": {
					"description": "维度1描述"
				}
			},
			"manual_list": ["metric1", "metric2"],
			"auto_rules": ["metric_prefix_*"],
			"delete_unmatched_dimensions": false
		},
		{
			"group_id": 123,
			"scope_name": "指标分组名2",
			"dimension_config": {},
			"manual_list": [],
			"auto_rules": []
		}
	]
}
```

### 响应参数

| 字段       | 类型   | 描述         |
| ---------- | ------ | ------------ |
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息     |
| data       | list   | 数据列表      |
| request_id | string | 请求ID       |

#### data字段说明

data 为列表类型，包含所有修改成功的分组结果

#### data列表项字段说明

| 字段                   | 类型   | 描述                                   |
| ---------------------- | ------ |--------------------------------------|
| group_id               | int    | 自定义时序数据源 ID                          |
| scope_name             | string | 指标分组名（如果使用了 new_scope_name，则返回新的分组名） |
| dimension_config       | dict   | 分组下的维度配置                             |
| manual_list            | list   | 手动分组的指标列表                            |
| auto_rules             | list   | 自动分组的匹配规则列表                          |
| create_from            | string | 创建来源                                 |

### 响应参数示例

```json
{
    "message":"OK",
    "code":200,
    "data": [
        {
            "group_id": 123,
            "scope_name": "新指标分组名1",
            "dimension_config": {
                "dimension1": {
                    "description": "维度1描述"
                }
            },
            "manual_list": ["metric1", "metric2"],
            "auto_rules": ["metric_prefix_*"],
            "create_from": "user"
        },
        {
            "group_id": 123,
            "scope_name": "指标分组名2",
            "dimension_config": {},
            "manual_list": [],
            "auto_rules": [],
            "create_from": "user"
        }
    ],
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```
