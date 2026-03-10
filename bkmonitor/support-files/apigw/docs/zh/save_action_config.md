### 功能描述

保存处理套餐

### 请求参数

| 字段             | 类型   | 必选 | 描述                                                           |
|----------------|------|----|--------------------------------------------------------------|
| bk_biz_id      | int  | 是  | 业务ID                                                         |
| name           | str  | 是  | 名称                                                           |
| plugin_id      | int  | 是  | 插件ID，可选项：1（通知），2（HTTP回调），3（作业平台），4（标准运维），5（流程服务），6（标准运维公共流程） |
| desc           | str  | 否  | 描述                                                           |
| execute_config | dict | 是  | 执行参数（根据 plugin_id 对应的 plugin_type 不同，所需参数也不同）                |

#### execute_config 基本结构

| 字段              | 类型   | 必选 | 描述                                   |
|-----------------|------|----|--------------------------------------|
| template_detail | dict | 是  | 模板详情（具体内容根据 plugin_type 不同而不同，见下文说明） |
| template_id     | str  | 否  | 周边系统的模板ID                            |
| timeout         | int  | 否  | 执行超时时间（单位秒，默认600，范围60-604800）        |

#### template_detail 参数说明（plugin_id=2时）

| 字段                   | 类型   | 必选 | 描述                                            |
|----------------------|------|----|-----------------------------------------------|
| method               | str  | 否  | 请求方法，可选（"POST","GET","PUT"）默认"GET"            |
| url                  | str  | 是  | 回调地址                                          |
| headers              | list | 否  | 请求头（KVPair格式，见下文）                             |
| authorize            | dict | 否  | 认证信息（见下文）                                     |
| body                 | dict | 否  | 请求体（见下文）                                      |
| query_params         | list | 否  | 查询参数（KVPair格式，见下文）                            |
| failed_retry         | dict | 否  | 失败重试机制（见下文）                                   |
| need_poll            | bool | 否  | 是否需要轮询（默认true）                                |
| notify_interval      | int  | 否  | 通知间隔（单位秒，最小60，默认3600）                         |
| interval_notify_mode | str  | 否  | 通知模式（可选"increasing", "standard"，默认"standard"） |

##### KVPair 格式说明（用于 headers、query_params）

| 字段         | 类型   | 必选 | 描述   |
|------------|------|----|------|
| key        | str  | 是  | 字段名  |
| value      | str  | 否  | 字段值  |
| desc       | str  | 否  | 描述   |
| is_builtin | bool | 否  | 是否内置 |
| is_enabled | bool | 否  | 是否启用 |

##### authorize 认证信息

| 字段          | 类型   | 必选 | 描述                                                           |
|-------------|------|----|--------------------------------------------------------------|
| auth_type   | str  | 是  | 认证类型（可选"none", "basic_auth", "bearer_token", "tencent_auth"） |
| auth_config | dict | 否  | 认证配置信息                                                       |

##### body 请求体

| 字段           | 类型   | 必选 | 描述                                                                      |
|--------------|------|----|-------------------------------------------------------------------------|
| data_type    | str  | 否  | 数据类型（可选"default", "raw", "form_data", "x_www_form_urlencoded"，默认"text"） |
| params       | list | 否  | 参数列表（KVPair格式）                                                          |
| content      | str  | 否  | 请求内容（当data_type为raw时使用）                                                 |
| content_type | str  | 否  | 内容类型（可选"text","json", "html","xml"，默认"text"）                            |

##### failed_retry 失败重试机制

| 字段              | 类型   | 必选 | 描述                       |
|-----------------|------|----|--------------------------|
| is_enabled      | bool | 否  | 是否启用（默认true）             |
| timeout         | int  | 否  | 超时时间（单位秒，默认1，范围1-604800） |
| max_retry_times | int  | 是  | 最大重试次数（最小0）              |
| retry_interval  | int  | 是  | 重试间隔（单位秒，最小0）            |

#### template_detail 参数说明（plugin_id=1时）

| 字段                   | 类型   | 必选 | 描述                                              |
|----------------------|------|----|-------------------------------------------------|
| template             | list | 是  | 通知模板配置（见下文）                                     |
| voice_notice         | str  | 否  | 语音通知模式（可选"parallel"并行, "serial"串行，默认"parallel"） |
| need_poll            | bool | 否  | 是否需要轮询（默认true）                                  |
| notify_interval      | int  | 否  | 通知间隔（单位秒，最小60，默认3600）                           |
| interval_notify_mode | str  | 否  | 通知模式（可选"increasing", "standard"，默认"standard"）   |

##### template 通知模板配置

| 字段           | 类型  | 必选 | 描述                                                                                                                               |
|--------------|-----|----|----------------------------------------------------------------------------------------------------------------------------------|
| signal       | str | 是  | 触发信号（可选"abnormal"异常, "recovered"恢复, "closed"关闭, "ack"确认, "no_data"无数据, "execute"执行, "execute_success"执行成功, "execute_failed"执行失败） |
| message_tmpl | str | 否  | 消息模板                                                                                                                             |
| title_tmpl   | str | 否  | 标题模板                                                                                                                             |

#### template_detail 参数说明（其他 plugin_type 时）

对于作业平台、标准运维、流程服务等其他类型的插件，`template_detail` 的内容**由第三方平台的模板参数动态定义**。

**工作原理**：

1. **用户必须提供** `template_detail` 参数，包含模板所需的变量值
2. 系统会根据 `execute_config.template_id` 调用第三方平台的 API 获取该模板的参数定义
3. 系统会**验证**用户提供的参数是否在第三方平台返回的参数列表中
4. 系统会**自动过滤掉**不在参数列表中的字段，只保留有效字段

**不同平台的参数格式**：

##### 作业平台（plugin_id=3）

`template_detail` 的参数对应作业平台执行方案中的**全局变量**：

- **key 格式**：`{变量id}_{变量类型}`（例如：`1_1` 表示 id=1, type=1 的字符串变量）
- **value**：变量的值

##### 标准运维（plugin_id=4,6）

`template_detail` 的参数对应标准运维流程中的**全局变量**：

- **key**：标准运维中定义的变量 key（通常格式为 `${var_name}`）
- **value**：变量的值

##### 流程服务（plugin_id=5）

`template_detail` 的参数对应流程服务中的**表单字段**：

- **key**：流程服务中定义的字段 key
- **value**：字段的值

### 请求参数示例

#### 示例1：HTTP回调类型（plugin_id=2）

```json
{
    "bk_biz_id": 2,
    "name": "测试HTTP回调套餐",
    "desc": "测试HTTP回调套餐描述",
    "plugin_id": 2,
    "execute_config": {
        "template_detail": {
            "method": "POST",
            "url": "http://www.example.com/webhook",
            "headers": [
                {
                    "key": "Content-Type",
                    "value": "application/json",
                    "desc": "内容类型",
                    "is_builtin": false,
                    "is_enabled": true
                }
            ],
            "authorize": {
                "auth_type": "none",
                "auth_config": {}
            },
            "body": {
                "data_type": "raw",
                "content_type": "json",
                "content": "{\"alert\": \"{{alarm.name}}\", \"level\": \"{{alarm.level}}\"}"
            },
            "query_params": [],
            "need_poll": false,
            "notify_interval": 7200,
            "failed_retry": {
                "is_enabled": true,
                "max_retry_times": 2,
                "retry_interval": 2,
                "timeout": 10
            }
        },
        "timeout": 600
    }
}
```

#### 示例2：通知类型（plugin_id=1）

```json
{
    "bk_biz_id": 2,
    "name": "测试通知套餐",
    "desc": "测试通知套餐描述",
    "plugin_id": 1,
    "execute_config": {
        "template_detail": {
            "template": [
                {
                    "signal": "abnormal",
                    "message_tmpl": "告警内容: {{alarm.name}}\\n告警级别: {{alarm.level}}",
                    "title_tmpl": "【告警通知】{{alarm.name}}"
                },
                {
                    "signal": "recovered",
                    "message_tmpl": "告警已恢复: {{alarm.name}}",
                    "title_tmpl": "【恢复通知】{{alarm.name}}"
                }
            ],
            "voice_notice": "parallel",
            "need_poll": true,
            "notify_interval": 3600,
            "interval_notify_mode": "standard"
        },
        "timeout": 600
    }
}
```

#### 示例3：作业平台类型（plugin_id=3）

```json
{
    "bk_biz_id": 2,
    "name": "测试作业平台套餐",
    "desc": "执行作业平台任务",
    "plugin_id": 3,
    "execute_config": {
        "template_id": "123",
        "template_detail": {
            "1_1": "字符串变量的值",
            "2_3": "0:127.0.0.1",
            "3_1": "数组变量的值"
        },
        "timeout": 600
    }
}
```

#### 示例4：标准运维类型（plugin_id=4）

```json
{
    "bk_biz_id": 2,
    "name": "测试标准运维套餐",
    "desc": "执行标准运维流程",
    "plugin_id": 4,
    "execute_config": {
        "template_id": "456",
        "template_detail": {
            "${bk_timing}": "1",
            "${job_ip_list}": "127.0.0.1",
            "${custom_param}": "自定义参数值"
        },
        "timeout": 600
    }
}
```

### 响应参数

| 字段      | 类型   | 描述        |
|---------|------|-----------|
| result  | bool | 请求是否成功    |
| code    | int  | 返回的状态码    |
| message | str  | 描述信息      |
| data    | dict | 创建的处理套餐信息 |

#### data

| 字段 | 类型  | 描述          |
|----|-----|-------------|
| id | int | 创建的处理套餐配置ID |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "id": 1
    },
    "result": true
}
```