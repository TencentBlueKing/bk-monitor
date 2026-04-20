### 功能描述

获取插件升级日志

### 请求参数

| 字段             | 类型  | 必选 | 描述     |
|----------------|-----|----|--------|
| bk_biz_id      | int | 是  | 业务ID   |
| plugin_id      | str | 是  | 插件ID   |
| config_id      | str | 是  | 配置ID   |
| config_version | int | 是  | 插件版本   |
| info_version   | int | 是  | 插件信息版本 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "plugin_id": "example_plugin",
    "config_id": "123",
    "config_version": 1,
    "info_version": 1
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

| 字段                  | 类型     | 描述        |
|---------------------|--------|-----------|
| plugin_id           | string | 插件ID      |
| plugin_display_name | string | 插件显示名称    |
| plugin_version      | string | 插件版本      |
| runtime_params      | list   | 运行时参数配置列表 |
| version_log         | list   | 版本发行历史列表  |

#### runtime_params 元素字段说明

| 字段          | 类型     | 描述                                                                        |
|-------------|--------|---------------------------------------------------------------------------|
| name        | string | 参数名称                                                                      |
| type        | string | 参数类型（可选值：text、password、switch、file、encrypt、host、service、code、list、custom） |
| mode        | string | 参数模式（collector: 采集器参数, plugin: 插件参数）                                      |
| default     | any    | 默认值                                                                       |
| value       | any    | 当前值                                                                       |
| visible     | bool   | 是否可见                                                                      |
| description | string | 参数描述                                                                      |
| alias       | string | 参数别名                                                                      |
| key         | string | 参数键名（可选，与name字段作用类似）                                                      |
| required    | bool   | 是否必填                                                                      |
| election    | list   | 列表选项（当type为list时使用）                                                       |
| options     | dict   | 其他选项配置                                                                    |
| auth_json   | list   | 认证信息配置（用于SNMP等需要认证的插件类型）                                                  |
| file_base64 | string | 文件Base64编码内容（当type为file时使用）                                               |

#### version_log 元素字段说明

| 字段          | 类型     | 描述     |
|-------------|--------|--------|
| version     | string | 版本号    |
| version_log | string | 版本更新日志 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "plugin_id": "example_plugin",
        "plugin_display_name": "示例插件",
        "plugin_version": "1.1",
        "runtime_params": [
            {
                "name": "port",
                "type": "text",
                "mode": "collector",
                "default": "9090",
                "value": "8080",
                "visible": true,
                "description": "监听端口",
                "alias": "端口",
                "required": true
            },
            {
                "name": "timeout",
                "type": "text",
                "mode": "plugin",
                "default": "30",
                "value": "60",
                "visible": true,
                "description": "超时时间（秒）",
                "alias": "超时时间",
                "required": false
            },
            {
                "name": "log_level",
                "type": "list",
                "mode": "plugin",
                "default": "INFO",
                "value": "DEBUG",
                "visible": true,
                "description": "日志级别",
                "alias": "日志级别",
                "required": false,
                "election": ["DEBUG", "INFO", "WARNING", "ERROR"]
            }
        ],
        "version_log": [
            {
                "version": "1.1",
                "version_log": "优化性能，修复已知问题"
            },
            {
                "version": "1.0",
                "version_log": "该插件诞生了!"
            }
        ]
    }
}
```
