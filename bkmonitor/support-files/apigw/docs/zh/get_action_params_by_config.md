### 功能描述

根据套餐ID获取当前告警处理参数

### 请求参数

| 字段             | 类型         | 必选 | 描述                        |
|----------------|------------|----|---------------------------|
| config_ids     | list[int]  | 否  | 套餐ID列表，与action_configs二选一 |
| action_configs | list[dict] | 否  | 套餐配置列表，与config_ids二选一     |
| action_id      | int        | 否  | 事件ID，默认为0                 |
| alert_ids      | list[str]  | 是  | 告警ID列表                    |
| bk_biz_id      | str        | 是  | 业务ID                      |

#### action_configs 字段说明（当不使用config_ids时）

| 字段             | 类型   | 必选 | 描述                  |
|----------------|------|----|---------------------|
| id             | int  | 是  | 套餐ID                |
| plugin_id      | int  | 是  | 插件ID                |
| bk_biz_id      | int  | 是  | 业务ID                |
| desc           | str  | 否  | 套餐描述，默认为空字符串        |
| execute_config | dict | 是  | 执行配置，根据插件类型不同结构有所不同 |

#### execute_config 参数详细说明

`execute_config` 是一个 JSON 对象，其结构根据不同的插件类型（`plugin_type`）有所不同：

**基础结构（所有插件类型通用）**

| 字段              | 类型   | 必选 | 描述                            |
|-----------------|------|----|-------------------------------|
| template_detail | dict | 是  | 执行配置详情，根据插件类型不同而不同            |
| template_id     | str  | 否  | 第三方系统模板ID（仅用于周边系统插件）          |
| timeout         | int  | 否  | 超时时间（秒），默认600，范围60-604800（7天） |

**template_detail 结构（根据插件类型不同）**

##### 1. 通知类插件（plugin_type="notice"）

| 字段                   | 类型         | 必选 | 描述                                                  |
|----------------------|------------|----|-----------------------------------------------------|
| template             | list[dict] | 是  | 通知模板配置列表                                            |
| need_poll            | bool       | 否  | 是否需要轮询，默认true                                       |
| notify_interval      | int        | 否  | 通知间隔（秒），默认3600，最小60                                 |
| interval_notify_mode | str        | 否  | 间隔通知模式，默认"standard"                                 |
| voice_notice         | str        | 否  | 语音通知模式，默认"parallel"，可选值："parallel"（并行）、"serial"（串行） |

**template 元素字段说明：**

| 字段           | 类型  | 必选 | 描述                                                    |
|--------------|-----|----|-------------------------------------------------------|
| signal       | str | 是  | 触发信号，可选值："abnormal"（异常）、"recovered"（恢复）、"closed"（关闭）等 |
| message_tmpl | str | 否  | 通知内容模板，支持Jinja2语法，默认为空                                |
| title_tmpl   | str | 否  | 通知标题模板，支持Jinja2语法，默认为空                                |

##### 2. HTTP回调插件（plugin_type="webhook"）

| 字段                   | 类型         | 必选 | 描述                                  |
|----------------------|------------|----|-------------------------------------|
| method               | str        | 否  | 请求方法，默认"GET"，可选值："GET"、"POST"、"PUT" |
| url                  | str        | 是  | 回调地址（URL格式）                         |
| headers              | list[dict] | 否  | 请求头列表，默认为空列表                        |
| authorize            | dict       | 否  | 认证配置                                |
| body                 | dict       | 否  | 请求体配置                               |
| query_params         | list[dict] | 否  | 查询参数列表，默认为空列表                       |
| need_poll            | bool       | 否  | 是否需要轮询，默认true                       |
| notify_interval      | int        | 否  | 通知间隔（秒），默认3600，最小60                 |
| interval_notify_mode | str        | 否  | 间隔通知模式，默认"standard"                 |
| failed_retry         | dict       | 否  | 失败重试配置                              |

**authorize 字段说明：**

| 字段          | 类型   | 必选 | 描述                                                                                            |
|-------------|------|----|-----------------------------------------------------------------------------------------------|
| auth_type   | str  | 是  | 认证类型，可选值："none"（无认证）、"basic_auth"（基础认证）、"bearer_token"（Bearer Token）、"tencent_auth"（腾讯云API验证） |
| auth_config | dict | 否  | 认证配置，根据auth_type不同而不同                                                                         |

**body 字段说明：**

| 字段           | 类型         | 必选 | 描述                                                                    |
|--------------|------------|----|-----------------------------------------------------------------------|
| data_type    | str        | 否  | 数据类型，默认"text"，可选值："default"、"raw"、"form_data"、"x_www_form_urlencoded" |
| params       | list[dict] | 否  | 参数列表（用于form_data和x_www_form_urlencoded）                               |
| content      | str        | 否  | 请求内容（用于raw类型）                                                         |
| content_type | str        | 否  | 内容类型，默认"text"，可选值："text"、"json"、"html"、"xml"                          |

**headers/query_params/params 元素字段说明（KVPair格式）：**

| 字段         | 类型   | 必选 | 描述           |
|------------|------|----|--------------|
| key        | str  | 是  | 键名，最大长度64    |
| value      | str  | 否  | 键值，默认为空      |
| desc       | str  | 否  | 描述，默认为空      |
| is_builtin | bool | 否  | 是否内置，默认false |
| is_enabled | bool | 否  | 是否启用，默认true  |

##### 3. 第三方系统插件（其他plugin_type）

对于第三方系统插件，`template_detail` 的结构由第三方系统定义，需要通过 `template_id` 指定模板，并根据模板要求的参数进行配置。

### 请求参数示例

```json
{
    "config_ids": [36457],
    "alert_ids": ["16424876305819838"],
    "bk_biz_id": "5000140"
}
```

或者使用action_configs：

```json
{
    "action_configs": [
        {
            "id": 36457,
            "plugin_id": 1,
            "bk_biz_id": 5000140,
            "desc": "通知套餐",
            "execute_config": {
                "template_detail": {
                    "need_poll": true,
                    "notify_interval": 7200
                }
            }
        }
    ],
    "alert_ids": ["16424876305819838"],
    "bk_biz_id": "5000140"
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

| 字段             | 类型   | 描述                  |
|----------------|------|---------------------|
| result         | bool | 处理结果                |
| action_configs | list | 处理套餐配置列表，包含渲染后的模板参数 |

#### data.action_configs 字段说明

| 字段             | 类型        | 描述                  |
|----------------|-----------|---------------------|
| id             | int       | 套餐ID                |
| name           | str       | 套餐名称                |
| plugin_id      | int       | 插件ID                |
| plugin_name    | str       | 插件名称                |
| plugin_type    | str       | 插件类型                |
| bk_biz_id      | int       | 业务ID                |
| desc           | str       | 套餐描述                |
| execute_config | dict      | 执行配置                |
| alert_ids      | list[str] | 告警ID列表              |
| alert_context  | dict      | 告警上下文信息（仅包含字符串类型的值） |

#### execute_config

| 字段              | 类型   | 描述                   |
|-----------------|------|----------------------|
| template_detail | dict | 执行配置详情，根据插件类型不同而不同   |
| template_id     | str  | 第三方系统模板ID（仅用于周边系统插件） |
| timeout         | int  | 超时时间（秒）              |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "result": true,
        "action_configs": [
            {
                "id": 36457,
                "name": "告警通知",
                "plugin_id": 1,
                "plugin_name": "通知",
                "plugin_type": "notice",
                "bk_biz_id": 5000140,
                "desc": "通知套餐，策略ID: 41868",
                "execute_config": {
                    "template_detail": {
                        "need_poll": true,
                        "notify_interval": 7200,
                        "interval_notify_mode": "standard",
                        "template": [
                            {
                                "signal": "abnormal",
                                "message_tmpl": "告警级别: 致命\n开始时间: 2022-01-18 14:27:33\n持续时间: 5分钟",
                                "title_tmpl": "demo - CPU使用率告警"
                            }
                        ]
                    },
                    "origin_template_detail": {
                        "need_poll": true,
                        "notify_interval": 7200,
                        "interval_notify_mode": "standard",
                        "template": [
                            {
                                "signal": "abnormal",
                                "message_tmpl": "{{content.level}}\n{{content.begin_time}}\n{{content.duration}}",
                                "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}"
                            }
                        ]
                    },
                    "context_inputs": {}
                },
                "alert_ids": ["16424876305819838"],
                "alert_context": {
                    "alarm.name": "CPU使用率告警",
                    "business.bk_biz_name": "demo",
                    "content.level": "致命",
                    "content.begin_time": "2022-01-18 14:27:33",
                    "content.duration": "5分钟"
                }
            }
        ]
    }
}
```
