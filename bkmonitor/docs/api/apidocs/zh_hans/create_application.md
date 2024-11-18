### 功能描述

创建应用

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段              | 类型   | 必选 | 描述                                 |
| ----------------- | ------ | ---- | ------------------------------------ |
| bk_biz_id         | int    | 是   | 业务id                               |
| app_name          | string | 是   | 应用名                               |
| app_alias         | string | 是   | 应用别名                             |
| description       | string | 否   | 应该相关的描述，默认: 空字符串       |
| enabled_profiling | bool   | 否   | 是否开启 Profiling 功能，默认: false |
| enabled_trace     | bool   | 否   | 是否开启 Trace 功能，默认: true      |
| enabled_metric    | bool   | 否   | 是否开启 Metric 功能，默认: true     |
| enabled_log       | bool   | 否   | 是否开启 Log 功能，默认: false       |



#### 请求示例

```json
{
  "app_name": "app_name",
  "app_alias": "app_alias",
  "description": "description",
  "enabled_profiling": false,
  "enabled_trace": true,
  "enabled_metric": true,
  "enabled_log": true,
  "bk_biz_id": 2
}
```

### 返回结果

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 返回数据     |

#### data字段说明

| 字段                 | 类型   | 描述                    |
| -------------------- | ------ | ----------------------- |
| application_id       | int    | 应用id                  |
| is_enabled           | bool   | 是否可用                |
| is_deleted           | bool   | 是否已删除              |
| create_user          | string | 创建者                  |
| create_time          | string | 创建时间                |
| update_user          | string | 更新者                  |
| update_time          | string | 更新时间                |
| bk_biz_id            | int    | 业务id                  |
| app_name             | string | 应用名                  |
| app_alias            | string | 应用别名                |
| description          | string | 应用描述                |
| is_enabled_profiling | bool   | 是否开启 Profiling 功能 |
| is_enabled_metric    | bool   | 是否开启 Metric 功能    |
| is_enabled_log       | bool   | 是否开启 Log 功能       |
| is_enabled_trace     | bool   | 是否开启 Trace 功能     |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "application_id": 110,
    "is_enabled": true,
    "is_deleted": false,
    "create_user": "admin",
    "create_time": "2023-11-15 17:59:38+0800",
    "update_user": "admin",
    "update_time": "2023-11-15 17:59:38+0800",
    "bk_biz_id": 2,
    "app_name": "app_name",
    "app_alias": "app_alias",
    "description": "description",
    "is_enabled_profiling": false,
    "is_enabled_metric": true,
    "is_enabled_log": true,
    "is_enabled_trace": true
  }
}
```