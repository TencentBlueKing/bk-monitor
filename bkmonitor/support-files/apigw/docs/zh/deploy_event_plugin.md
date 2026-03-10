### 功能描述

部署告警源插件，支持创建或更新事件插件，并可选择性地更新已安装的插件实例

### 请求参数

| 字段                   | 类型         | 必选 | 描述                                            |
|----------------------|------------|----|-----------------------------------------------|
| plugin_id            | str        | 是  | 插件ID，必须以字母开头，只能包含字母、数字和下划线，最大长度64字符           |
| version              | str        | 否  | 插件版本号，默认为空，系统会自动生成版本号（格式：YYYY.MM.DD.时间戳）      |
| bk_biz_id            | str        | 否  | 业务ID，默认为0（全局插件）                               |
| plugin_type          | str        | 是  | 插件类型（创建后不可修改）                                 |
| plugin_display_name  | str        | 否  | 插件显示名称                                        |
| author               | str        | 否  | 插件作者                                          |
| scenario             | str        | 否  | 应用场景                                          |
| summary              | str        | 否  | 插件摘要                                          |
| description          | str        | 否  | 插件详细描述                                        |
| tutorial             | str        | 否  | 使用教程                                          |
| logo                 | str        | 否  | 插件Logo（Base64编码，格式：data:image/png;base64,xxx） |
| tags                 | list[str]  | 否  | 插件标签列表，默认为空列表                                 |
| config_params        | list[dict] | 否  | 配置参数列表                                        |
| ingest_config        | dict       | 是  | 接入配置                                          |
| normalization_config | list[dict] | 是  | 字段清洗规则列表                                      |
| alert_config         | list[dict] | 否  | 告警配置列表（仅写入，不在响应中返回）                           |
| clean_configs        | list[dict] | 否  | 清洗配置列表                                        |
| forced_update        | bool       | 否  | 是否强制更新已安装的插件实例，默认为false                       |

#### config_params 元素字段说明

配置参数用于定义插件的可配置项，这些参数会在创建插件实例时由用户填写。

| 字段            | 类型   | 必选 | 描述                        |
|---------------|------|----|---------------------------|
| field         | str  | 是  | 字段key                     |
| name          | str  | 是  | 字段显示名                     |
| desc          | str  | 否  | 字段描述                      |
| value         | str  | 否  | 字段值                       |
| default_value | str  | 否  | 字段默认值                     |
| is_required   | bool | 否  | 是否必填，默认false              |
| is_hidden     | bool | 否  | 是否隐藏（隐藏的参数不在前端显示），默认false |
| is_sensitive  | bool | 否  | 是否敏感（敏感信息会加密存储），默认false   |

#### ingest_config 字段说明

接入配置根据不同的插件类型有不同的字段要求。以下是通用字段：

| 字段              | 类型        | 必选 | 描述                                    |
|-----------------|-----------|----|---------------------------------------|
| source_format   | str       | 否  | 源数据格式，可选值：json、xml、prometheus，默认为json |
| multiple_events | bool      | 否  | 是否需要拆分事件，默认为false                     |
| events_path     | str       | 否  | 事件所在路径（当multiple_events为true时使用），默认为空 |
| collect_type    | str       | 否  | 接收类型，默认为bk-ingestor                   |
| is_external     | bool      | 否  | 是否依赖外网服务，默认为false                     |
| alert_sources   | list[str] | 否  | 告警来源列表，默认为空列表                         |

**HTTP Pull 类型插件额外字段：**

| 字段           | 类型   | 必选 | 描述                               |
|--------------|------|----|----------------------------------|
| url          | str  | 是  | 拉取数据的URL地址                       |
| method       | str  | 否  | HTTP请求方法，默认为GET                  |
| interval     | str  | 否  | 请求周期（秒），默认为60                    |
| overlap      | str  | 否  | 重叠时间（秒），默认为0                     |
| timeout      | str  | 否  | 请求超时（秒），默认为60                    |
| time_format  | str  | 否  | 时间格式，默认为空                        |
| headers      | dict | 否  | HTTP请求头                          |
| body         | dict | 否  | HTTP请求体                          |
| query_params | dict | 否  | URL查询参数                          |
| pagination   | dict | 否  | 分页配置，包含type（分页方式）和option（分页选项）字段 |

#### normalization_config 元素字段说明

字段清洗规则用于将原始事件数据映射到标准字段。

| 字段     | 类型   | 必选 | 描述                       |
|--------|------|----|--------------------------|
| field  | str  | 是  | 映射字段（标准字段名）              |
| expr   | str  | 是  | 表达式（支持Jinja2模板语法），可为空字符串 |
| option | dict | 否  | 选项（扩展配置），默认为空字典          |

#### alert_config 元素字段说明

告警配置用于定义不同类型的告警规则。

| 字段    | 类型         | 必选 | 描述            |
|-------|------------|----|---------------|
| name  | str        | 是  | 告警名称          |
| rules | list[dict] | 否  | 规则参数列表，默认为空列表 |

##### rules 元素字段说明

| 字段        | 类型        | 必选 | 描述                               |
|-----------|-----------|----|----------------------------------|
| key       | str       | 是  | 匹配字段                             |
| value     | list[str] | 是  | 匹配值列表                            |
| method    | str       | 是  | 匹配方法，可选值：eq（等于）、neq（不等于）、reg（正则） |
| condition | str       | 否  | 复合条件，可选值：and、or、空字符串，默认为空字符串     |

#### clean_configs 元素字段说明

清洗配置用于在数据处理过程中进行额外的数据清洗和转换。

| 字段                   | 类型         | 必选 | 描述                                       |
|----------------------|------------|----|------------------------------------------|
| rules                | list[dict] | 否  | 规则参数列表（使用与alert_config相同的rules结构），默认为空列表 |
| alert_config         | list[dict] | 否  | 告警名称清洗规则（使用与alert_config相同的结构），默认为空列表    |
| normalization_config | list[dict] | 是  | 字段清洗规则列表（使用与normalization_config相同的结构）   |

### 请求参数示例

```json
{
    "plugin_id": "custom_event_plugin",
    "version": "1.0.0",
    "bk_biz_id": "2",
    "plugin_type": "http_push",
    "plugin_display_name": "自定义事件插件",
    "author": "admin",
    "scenario": "monitoring",
    "summary": "用于接收自定义事件的插件",
    "description": "该插件可以接收来自第三方系统的自定义事件数据",
    "tutorial": "配置完成后，使用提供的URL和Token进行事件上报",
    "tags": ["custom", "event"],
    "config_params": [
        {
            "field": "api_key",
            "name": "API密钥",
            "desc": "用于认证的API密钥",
            "value": "",
            "default_value": "",
            "is_required": true,
            "is_hidden": false,
            "is_sensitive": true
        }
    ],
    "ingest_config": {
        "source_format": "json",
        "multiple_events": false,
        "events_path": "",
        "collect_type": "bk-ingestor",
        "is_external": false,
        "alert_sources": []
    },
    "normalization_config": [
        {
            "field": "alert_name",
            "expr": "event.title",
            "option": {}
        },
        {
            "field": "event_name",
            "expr": "event.name",
            "option": {}
        }
    ],
    "alert_config": [
        {
            "name": "严重告警",
            "rules": [
                {
                    "key": "severity",
                    "value": ["critical"],
                    "method": "eq",
                    "condition": ""
                }
            ]
        }
    ],
    "forced_update": false
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

| 字段                   | 类型         | 描述                                 |
|----------------------|------------|------------------------------------|
| id                   | int        | 插件ID                               |
| plugin_id            | str        | 插件标识                               |
| version              | str        | 插件版本号                              |
| bk_biz_id            | str        | 业务ID                               |
| plugin_type          | str        | 插件类型                               |
| plugin_type_display  | str        | 插件类型显示名称                           |
| plugin_display_name  | str        | 插件显示名称                             |
| author               | str        | 插件作者                               |
| scenario             | str        | 应用场景                               |
| scenario_display     | str        | 应用场景显示名称                           |
| summary              | str        | 插件摘要                               |
| description          | str        | 插件详细描述                             |
| tutorial             | str        | 使用教程                               |
| logo                 | str        | 插件Logo（Base64编码）                   |
| tags                 | list[str]  | 插件标签列表                             |
| config_params        | list[dict] | 配置参数列表                             |
| ingest_config        | dict       | 接入配置                               |
| normalization_config | list[dict] | 字段清洗规则列表                           |
| alert_config         | list[dict] | 告警配置列表                             |
| clean_configs        | list[dict] | 清洗配置列表                             |
| main_type            | str        | 主类型                                |
| main_type_display    | str        | 主类型显示名称                            |
| is_official          | bool       | 是否官方插件                             |
| category             | str        | 分类                                 |
| category_display     | str        | 分类显示名称                             |
| is_installed         | bool       | 是否已安装                              |
| updatable            | bool       | 是否可更新                              |
| plugin_instance_id   | int        | 插件实例ID，未安装时为null                   |
| popularity           | int        | 受欢迎程度                              |
| status               | str        | 插件状态                               |
| create_user          | str        | 创建用户                               |
| create_time          | str        | 创建时间                               |
| update_user          | str        | 更新用户                               |
| update_time          | str        | 更新时间                               |
| package_dir          | str        | 插件包目录                              |
| updated_instances    | dict       | 更新的插件实例信息（仅在forced_update为true时返回） |

##### updated_instances 字段说明

| 字段                | 类型        | 描述          |
|-------------------|-----------|-------------|
| succeed_instances | list[int] | 成功更新的实例ID列表 |
| failed_instances  | list[int] | 更新失败的实例ID列表 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "id": 123,
        "plugin_id": "custom_event_plugin",
        "version": "1.0.0",
        "bk_biz_id": "2",
        "plugin_type": "http_push",
        "plugin_type_display": "HTTP推送",
        "plugin_display_name": "自定义事件插件",
        "author": "admin",
        "scenario": "monitoring",
        "scenario_display": "监控",
        "summary": "用于接收自定义事件的插件",
        "description": "该插件可以接收来自第三方系统的自定义事件数据",
        "tutorial": "配置完成后，使用提供的URL和Token进行事件上报",
        "logo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "tags": ["custom", "event"],
        "config_params": [
            {
                "field": "api_key",
                "name": "API密钥",
                "desc": "用于认证的API密钥",
                "value": "",
                "default_value": "",
                "is_required": true,
                "is_hidden": false,
                "is_sensitive": true
            }
        ],
        "ingest_config": {
            "source_format": "json",
            "multiple_events": false,
            "events_path": "",
            "collect_type": "bk-ingestor",
            "is_external": false,
            "alert_sources": []
        },
        "normalization_config": [
            {
                "field": "alert_name",
                "display_name": "告警名称",
                "type": "string",
                "description": "告警的名称",
                "expr": "event.title",
                "option": {}
            },
            {
                "field": "event_name",
                "display_name": "事件名称",
                "type": "string",
                "description": "事件的名称",
                "expr": "event.name",
                "option": {}
            }
        ],
        "alert_config": [
            {
                "name": "严重告警",
                "rules": [
                    {
                        "key": "severity",
                        "value": ["critical"],
                        "method": "eq",
                        "condition": ""
                    }
                ]
            }
        ],
        "clean_configs": [],
        "main_type": "event",
        "main_type_display": "事件",
        "is_official": true,
        "category": "event",
        "category_display": "事件插件",
        "is_installed": false,
        "updatable": false,
        "plugin_instance_id": null,
        "popularity": 0,
        "status": "available",
        "create_user": "admin",
        "create_time": "2024-01-15 10:30:00",
        "update_user": "admin",
        "update_time": "2024-01-15 10:30:00",
        "package_dir": "/data/plugins/custom_event_plugin",
        "updated_instances": {
            "succeed_instances": [1, 2, 3],
            "failed_instances": []
        }
    }
}
```
