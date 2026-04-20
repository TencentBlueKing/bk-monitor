### 功能描述

查询插件列表



### 请求参数

| 字段         | 类型   | 必填 | 描述                                                                 |
|--------------|--------|------|----------------------------------------------------------------------|
| bk_biz_id    | int    | 是   | 业务ID，为0时查询全业务插件（需要管理公共插件权限）                 |
| page         | int    | 否   | 页数，-1表示不分页                                                   |
| page_size    | int    | 否   | 每页数量                                                             |
| search_key   | string | 否   | 查询关键字，支持搜索插件ID、创建人、更新人、插件展示名               |
| plugin_type  | string | 否   | 插件类型过滤，如：Exporter、Script、JMX、DataDog、Pushgateway等      |
| labels       | string | 否   | 标签过滤，多个标签用英文逗号分隔                                     |
| order        | string | 否   | 排序字段，支持：plugin_id、create_user、update_user、status等，降序在字段前加"-" |
| status       | string | 否   | 插件状态过滤，可选值：release（正式版）、debug（调试版）             |
| with_virtual | string | 否   | 是否包含虚拟插件，可选值："true"、"false"                          |

### 请求参数示例
```json
{
    "bk_biz_id": 1,
    "search_key": "xxxexporter",
    "plugin_type": "Script",
    "labels": "os,application",
    "order": "-update_time",
    "status": "release",
    "page": 1,
    "page_size": 10,
    "with_virtual": "false"
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | list   | data数据     |

#### data 字段说明

| 字段        | 类型 | 描述         |
| ----------- | ---- | ------------ |
| count       | dict  | 插件类型数量 |
| list | list | 插件列表 |
#### list 字段说明

| 字段        | 类型 | 描述         |
| ----------- | ---- | ------------ |
| plugin_id       | string  | 插件id |
| plugin_display_name | string  | 插件展示名 |
| plugin_type       | string  | 插件类型 |
| tag       | string  | 插件标签 |
| bk_biz_id       | int  | 业务id |
| related_conf_count       | int  | 关联采集配置数 |
| status       |  string  | 插件状态 |
| create_user       | string  | 创建人 |
| create_time       | string  | 创建时间 |
| update_user       | string  | 更新人 |
| update_time       | string  | 更新时间 |
| config_version       | int  | 插件配置版本 |
| info_version       | int  | 插件信息版本 |
| edit_allowed       | bool  | 是否允许编辑 |
| delete_allowed       | bool  | 是否允许删除 |
| export_allowed       | bool  | 是否允许导出 |
| logo       | string  | logo |
| is_official       | bool  | 是否官方 |
| is_safety       | bool  | 是否未被改动(签名校验)|
| label_info       | dict  | 标签信息 |


#### label_info详情

| 字段        | 类型 | 描述         |
| ----------- | ---- | ------------ |
| first_label       | string  | 插件标签 |
| first_label_name       | string  | 插件标签名|
| second_label       | string  | 插件标签|
| second_label_name       | string  |插件标签名|

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "count": {
      "Exporter": 8,
      "Script": 34,
      "JMX": 0,
      "DataDog": 0,
      "Pushgateway": 1,
      "Built-In": 0,
      "Log": 0,
      "Process": 0,
      "SNMP_Trap": 0,
      "SNMP": 3
    },
    "list": [
      {
        "plugin_id": "bk_collector",
        "plugin_display_name": "apm-rum接收",
        "plugin_type": "Pushgateway",
        "tag": "",
        "bk_biz_id": 2,
        "related_conf_count": 0,
        "status": "normal",
        "create_user": "admin",
        "create_time": "2023-02-15 15:12:29",
        "update_user": "admin",
        "update_time": "2023-02-15 15:16:22",
        "config_version": 1,
        "info_version": 2,
        "edit_allowed": true,
        "delete_allowed": true,
        "export_allowed": true,
        "label_info": {
          "first_label": "hosts",
          "first_label_name": "主机&云平台",
          "second_label": "os",
          "second_label_name": "操作系统"
        },
        "logo": "",
        "is_official": false,
        "is_safety": true
      }
    ]
  }
}
```
