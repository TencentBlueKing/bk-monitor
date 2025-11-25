

### 功能描述

创建自定义时序指标分组
在指定的自定义时序数据源下创建一个指标分组，支持手动分组和自动分组两种方式


### 请求参数

| 字段           | 类型   | 必选 | 描述        |
| -------------- | ------ | ---- | ----------- |
| bk_tenant_id  | string | 是   | 租户ID |
| group_id | int | 是 | 自定义时序数据源ID |
| scope_name | string | 是 | 指标分组名，最大长度255 |
| dimension_config | dict | 否 | 分组下的维度配置，默认为空字典 |
| manual_list | list | 否 | 手动分组的指标列表，默认为空列表 |
| auto_rules | list | 否 | 自动分组的匹配规则列表，默认为空列表 |

#### dimension_config具体内容说明

维度配置是一个字典，key为维度名称，value为维度配置信息

#### manual_list具体内容说明

手动分组的指标列表，包含需要手动分组的指标名称

#### auto_rules具体内容说明

自动分组的匹配规则列表，每个规则用于匹配指标名称

### 请求参数示例

```json
{
	"bk_tenant_id": "default",
	"group_id": 123,
	"scope_name": "指标分组名",
	"dimension_config": {
		"dimension1": {
			"description": "维度1描述"
		}
	},
	"manual_list": ["metric1", "metric2"],
	"auto_rules": ["metric_prefix_*"]
}
```

### 响应参数

| 字段       | 类型   | 描述         |
| ---------- | ------ | ------------ |
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息     |
| data       | dict   | 数据         |
| request_id | string | 请求ID       |

#### data字段说明

| 字段                   | 类型   | 描述             |
| ---------------------- | ------ | ---------------- |
| group_id               | int    | 自定义时序数据源ID |
| scope_name             | string | 指标分组名         |
| dimension_config       | dict   | 分组下的维度配置   |
| manual_list            | list   | 手动分组的指标列表 |
| auto_rules             | list   | 自动分组的匹配规则列表 |
| create_from            | string | 创建来源          |

### 响应参数示例

```json
{
    "message":"OK",
    "code":200,
    "data": {
        "group_id": 123,
        "scope_name": "指标分组名",
        "dimension_config": {
            "dimension1": {
                "description": "维度1描述"
            }
        },
        "manual_list": ["metric1", "metric2"],
        "auto_rules": ["metric_prefix_*"],
        "create_from": "user"
    },
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```

