

### 功能描述

查询自定义时序指标分组列表
支持通过 group_id 和 scope_name 进行模糊匹配查询，返回列表结果


### 请求参数

| 字段           | 类型   | 必选 | 描述                                           |
| -------------- | ------ | ---- |----------------------------------------------|
| group_id | int | 否 | 自定义时序数据源 ID，对 APM 场景需要传递 scope_name 来区分不同的服务 |
| scope_name | string | 否 | 指标分组名，支持模糊匹配                                 |


### 请求参数示例

```json
{
	"group_id": 123,
	"scope_name": "指标分组名"
}
```

### 响应参数

| 字段       | 类型   | 描述     |
| ---------- | ------ |--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | list   | 数据列表   |
| request_id | string | 请求 ID  |

#### data字段说明

data 为列表类型，包含所有匹配的结果

#### data列表项字段说明

| 字段                   | 类型   | 描述          |
| ---------------------- | ------ |-------------|
| group_id               | int    | 自定义时序数据源 ID |
| scope_name             | string | 指标分组名       |
| dimension_config       | dict   | 分组下的维度配置    |
| manual_list            | list   | 手动分组的指标列表   |
| auto_rules             | list   | 自动分组的匹配规则列表 |
| create_from            | string | 创建来源        |

### 响应参数示例

```json
{
    "message":"OK",
    "code":200,
    "data": [
        {
            "group_id": 123,
            "scope_name": "指标分组名1",
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
            "create_from": "data"
        }
    ],
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```

