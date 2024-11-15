### 功能描述

关闭APM应用数据上报

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段           | 类型   | 必选 | 描述         |
| -------------- | ------ | ---- | ------------ |
| type           | string | 是   | 插件ID       |
| application_id | int    | 否   | 应用id       |
| bk_biz_id      | int    | 否   | 业务id       |
| app_name       | string | 否   | 应用名称     |
| space_uid      | string | 否   | 空间唯一标识 |

- type 是必须的，传参格式为：type + application_id； 或 type + bk_biz_id + app_name；或 type + space_uid + app_name；

#### 请求示例

```json
{
  "application_id": 52,
  "type": "profiling"
}
或者
{
  "type": "profiling",
  "bk_biz_id": 2，
  "app_name":"test"
}
```

### 返回结果

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 数据         |

#### data字段说明

data 字段无内容

#### 结果示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```