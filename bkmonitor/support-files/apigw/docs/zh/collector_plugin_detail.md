### 功能描述

查询插件详情


### 请求参数

| 字段      | 类型   | 必填 | 描述                                      |
|-----------|--------|------|---------------------------------------------|
| plugin_id | string | 是   | 插件ID，通过URL路径传递|


### 请求参数示例
```json
{
    "plugin_id": "sss_script"
}
```

**说明**：plugin_id 通过 URL 路径传递，不需要在请求体中传递。

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 插件信息     |


#### data 字段说明

| 字段                    | 类型   | 描述                                                      |
|-------------------------|--------|-------------------------------------------------------------|
| plugin_id               | string | 插件ID                                                     |
| plugin_display_name     | string | 插件展示名                                                 |
| plugin_type             | string | 插件类型，如：Exporter、Script、JMX、DataDog、Pushgateway等 |
| tag                     | string | 插件标签                                                   |
| bk_biz_id               | int    | 业务ID                                                    |
| related_conf_count      | int    | 关联采集配置数                                            |
| status                  | string | 插件状态，可选值：normal（正式版）、draft（草稿）            |
| create_user             | string | 创建人                                                    |
| create_time             | string | 创建时间，格式：`YYYY-MM-DD HH:mm:ss+0800`                |
| update_user             | string | 更新人                                                    |
| update_time             | string | 更新时间，格式：`YYYY-MM-DD HH:mm:ss+0800`                |
| config_version          | int    | 插件配置版本                                              |
| info_version            | int    | 插件信息版本                                              |
| description_md          | string | 插件描述（Markdown格式）                                  |
| edit_allowed            | bool   | 是否允许编辑                                              |
| is_support_remote       | bool   | 是否支持远程采集                                          |
| label                   | string | 标签，如：os、application等                              |
| logo                    | string | 插件Logo图片内容（Base64编码）                           |
| is_official             | bool   | 是否官方插件                                              |
| is_safety               | bool   | 是否未被改动（签名校验）                                  |
| stage                   | string | 版本阶段，如：release、debug、unregister                 |
| signature               | string | 插件签名                                                  |
| collector_json          | dict   | 采集器配置，具体结构取决于插件类型                       |
| config_json             | list   | 参数配置列表，详见config_json字段说明                   |
| metric_json             | list   | 指标配置列表，详见metric_json字段说明                   |
| os_type_list            | list   | 支持的操作系统列表，如：["linux","windows","linux_aarch64"] |
| enable_field_blacklist  | bool   | 是否启用字段黑名单                                        |
| is_split_measurement    | bool   | 是否拆分测量值（仅虚拟插件）                            |


#### collector_json 字段说明
> 字段与格式取决于实际插件类型

#### config_json 字段说明

config_json 是一个 list，每个元素是一个 dict，包含以下字段：

| 字段        | 类型   | 描述                                                |
|-------------|--------|-------------------------------------------------------|
| name        | string | 参数名                                              |
| type        | string | 值类型，如：text、password、file等                  |
| mode        | string | 参数类型，如：collector（采集器参数）、env（环境变量）等 |
| default     | string | 默认值                                             |
| description | string | 参数描述                                           |
| visible     | bool   | 是否可见（可选）                                   |
| required    | bool   | 是否必填（可选）                                   |
#### metric_json 字段说明

metric_json 是一个 list，每个元素是一个 dict，表示一个指标表，包含以下字段：

| 字段       | 类型   | 描述                       |
|------------|--------|------------------------------|
| table_name | string | 表名（指标分组名）           |
| table_desc | string | 表描述（指标分组描述）       |
| fields     | list   | 字段列表，详见fields字段说明 |

#### fields 字段说明

fields 是一个 list，每个元素是一个 dict，表示一个指标或维度字段，包含以下字段：

| 字段             | 类型   | 描述                                                  |
|------------------|--------|-------------------------------------------------------------|
| name             | string | 字段名（指标名或维度名）                                  |
| type             | string | 字段类型，如：double（浮点型）、string（字符串）、long（整型）等 |
| monitor_type     | string | 监控类型，可选值：metric（指标）、dimension（维度）         |
| unit             | string | 单位，如：none、percent、bytes等                         |
| description      | string | 字段描述                                                  |
| is_diff_metric   | bool   | 是否为差值指标（需要计算增量）                            |
| is_active        | bool   | 是否启用                                                  |
| source_name      | string | 原始字段名（如果与 name 不同）                            |
| dimensions       | list   | 维度列表，元素为 string 类型，如：["id","record_type"] |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "plugin_id": "bk_collector",
    "plugin_display_name": "apm-rum接收",
    "plugin_type": "Pushgateway",
    "tag": "",
    "label": "os",
    "status": "normal",
    "logo": "",
    "collector_json": {},
    "config_json": [
      {
        "default": "",
        "mode": "collector",
        "type": "text",
        "name": "metrics_url",
        "description": "采集URL"
      }
    ],
    "metric_json": [
      {
        "table_name": "Group1",
        "table_desc": "分组1",
        "fields": [
          {
            "description": "",
            "type": "double",
            "monitor_type": "metric",
            "unit": "none",
            "name": "bk_collector_exporter_sent_duration_in_ms_sum",
            "is_diff_metric": false,
            "is_active": true,
            "source_name": "",
            "dimensions": []
          }
          
        ]
      }
    ],
    "description_md": "### 依赖说明...",
    "config_version": 1,
    "info_version": 2,
    "stage": "release",
    "bk_biz_id": 2,
    "signature": "dcssdscds...",
    "is_support_remote": true,
    "is_official": false,
    "is_safety": true,
    "create_user": "admin",
    "update_user": "admin",
    "os_type_list": [
      "linux",
      "windows",
      "linux_aarch64"
    ],
    "create_time": "2023-02-15 15:16:05+0800",
    "update_time": "2023-02-15 15:16:22+0800",
    "related_conf_count": 0,
    "edit_allowed": true
  }
}

```
