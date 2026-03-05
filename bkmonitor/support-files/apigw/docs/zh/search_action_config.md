### 功能描述

批量获取处理套餐

### 请求参数

| 字段        | 类型  | 必选 | 描述                                                      |
|-----------|-----|----|---------------------------------------------------------|
| bk_biz_id | int | 是  | 业务ID                                                    |
| page      | int | 否  | 当前页（默认1）                                                |
| page_size | int | 否  | 页面大小（默认10， 最大1000）                                      |
| order     | str | 否  | 排序方式（可选"id", "create_time", "update_time"如果想要反向在前面加"-"） |

### 请求参数示例

```json
{
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 处理套餐信息 |

#### data字段说明

| 字段    | 类型   | 描述        |
|-------|------|-----------|
| count | int  | 总条数       |
| data  | list | 相关的套餐数据列表 |

#### action_config_list

| 字段             | 类型   | 描述                                                                      |
|----------------|------|-------------------------------------------------------------------------|
| bk_biz_id      | str  | 业务ID                                                                    |
| id             | int  | 处理套餐ID                                                                  |
| name           | str  | 名称                                                                      |
| plugin_id      | str  | 插件ID，选项："1"（通知），"2"（HTTP回调），"3"（作业平台），"4"（标准运维），"5"（流程服务），"6"（标准运维公共流程） |
| desc           | str  | 描述                                                                      |
| execute_config | dict | 执行参数（根据plug_in对应的 plugin_type不同，返回参数也不同）                                |
| create_time    | str  | 创建时间                                                                    |
| create_user    | str  | 创建用户                                                                    |
| update_time    | str  | 更新时间                                                                    |
| update_user    | str  | 更新用户                                                                    |

#### execute_config 基本结构

| 字段              | 类型   | 描述                |
|-----------------|------|-------------------|
| template_detail | dict | 模板详情              |
| template_id     | str  | 周边系统的模板ID         |
| timeout         | int  | 执行超时时间（单位秒，默认600） |

#### template_detail 参数说明（plugin_id="2"，HTTP回调时）

| 字段                   | 类型   | 描述                 |
|----------------------|------|--------------------|
| method               | str  | 请求方法               |
| url                  | str  | 回调地址               |
| headers              | list | 请求头（KVPair格式，见下文）  |
| authorize            | dict | 认证信息（见下文）          |
| body                 | dict | 请求体（见下文）           |
| query_params         | list | 查询参数（KVPair格式，见下文） |
| failed_retry         | dict | 失败重试机制（见下文）        |
| need_poll            | bool | 是否需要轮询             |
| notify_interval      | int  | 通知间隔               |
| interval_notify_mode | str  | 通知模式               |

##### KVPair 格式说明（用于 headers、query_params）

| 字段         | 类型   | 描述   |
|------------|------|------|
| key        | str  | 字段名  |
| value      | str  | 字段值  |
| desc       | str  | 描述   |
| is_builtin | bool | 是否内置 |
| is_enabled | bool | 是否启用 |

##### authorize 认证信息

| 字段                   | 类型   | 描述        |
|----------------------|------|-----------|
| auth_type            | str  | 认证类型      |
| auth_config          | dict | 认证配置信息    |
| insecure_skip_verify | bool | 是否跳过SSL验证 |

##### body 请求体

| 字段           | 类型   | 描述             |
|--------------|------|----------------|
| data_type    | str  | 数据类型           |
| params       | list | 参数列表（KVPair格式） |
| content      | str  | 请求内容           |
| content_type | str  | 内容类型           |

##### failed_retry 失败重试机制

| 字段              | 类型   | 描述            |
|-----------------|------|---------------|
| is_enabled      | bool | 是否启用          |
| timeout         | int  | 超时时间（单位秒）     |
| max_retry_times | int  | 最大重试次数（最小0）   |
| retry_interval  | int  | 重试间隔（单位秒，最小0） |

#### template_detail 参数说明（plugin_id="1"，通知时）

| 字段                   | 类型   | 描述          |
|----------------------|------|-------------|
| template             | list | 通知模板配置（见下文） |
| voice_notice         | str  | 语音通知模式      |
| need_poll            | bool | 是否需要轮询      |
| notify_interval      | int  | 通知间隔（单位秒）   |
| interval_notify_mode | str  | 通知模式        |

##### template 通知模板配置

| 字段           | 类型  | 描述   |
|--------------|-----|------|
| signal       | str | 触发信号 |
| message_tmpl | str | 消息模板 |
| title_tmpl   | str | 标题模板 |

#### template_detail 参数说明（其他 plugin_id 时）

对于作业平台（plugin_id=3）、标准运维（plugin_id=4,6）、流程服务（plugin_id=5）等其他类型的插件，`template_detail` 的内容*
*由第三方平台的模板参数动态定义**。

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

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "count": 1,
        "data": [
            {
                "execute_config": {
                    "template_detail": {
                        "method": "GET",
                        "url": "http://www.baidu.com",
                        "headers": [],
                        "authorize": {
                            "auth_config": {},
                            "auth_type": "none",
                            "insecure_skip_verify": false
                        },
                        "body": {
                            "data_type": "default",
                            "content_type": "",
                            "content": "",
                            "params": []
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
                },
                "name": "测试新建处理套餐",
                "desc": "测试新建处理套餐1111",
                "plugin_id": "2",
                "is_enabled": false,
                "bk_biz_id": "2",
                "id": 1,
                "create_time": "2022-02-25 11:01:25+0800",
                "create_user": "admin",
                "update_time": "2022-02-25 15:19:23+0800",
                "update_user": "admin"
            }
        ]
    },
    "result": true
}
```