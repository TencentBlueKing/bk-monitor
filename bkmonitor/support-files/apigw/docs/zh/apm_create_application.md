### 功能描述

快速创建APM应用

### 请求参数

| 字段名               | 类型        | 是否必选 | 描述                      |
|-------------------|-----------|------|-------------------------|
| bk_biz_id         | int       | 否    | 业务ID                    |
| app_name          | str       | 是    | 应用名称                    |
| app_alias         | str       | 否    | 应用别名                    |
| description       | str       | 否    | 应用描述                    |
| plugin_id         | str       | 否    | 插件ID                    |
| deployment_ids    | list[str] | 否    | 部署环境列表                  |
| language_ids      | list[str] | 否    | 支持的语言列表                 |
| space_uid         | str       | 否    | 空间唯一标识                  |
| enabled_profiling | bool      | 否    | 是否开启Profiling功能，默认false |
| enabled_trace     | bool      | 否    | 是否开启Trace功能，默认true      |
| enabled_metric    | bool      | 否    | 是否开启Metric功能，默认true     |
| enabled_log       | bool      | 否    | 是否开启Log功能，默认false       |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "app_name": "demo-app",
  "app_alias": "演示应用",
  "description": "这是一个演示应用",
  "plugin_id": "opentelemetry",
  "deployment_ids": ["centos"],
  "language_ids": ["python"],
  "space_uid": "bkcc__2",
  "enabled_profiling": false,
  "enabled_trace": true,
  "enabled_metric": true,
  "enabled_log": false
}
```

### 响应参数

| 字段      | 类型   | 描述      |
|---------|------|---------|
| result  | bool | 请求是否成功  |
| code    | int  | 返回的状态码  |
| message | str  | 描述信息    |
| data    | str  | 应用token |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": "YOUR_APPLICATION_TOKEN_HERE"
}
```
