### 功能描述

开启APM应用指定数据源

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段      | 类型   | 必选 | 描述     |
| --------- | ------ | ---- | -------- |
| bk_biz_id | int    | 是   | 业务id   |
| app_name  | string | 是   | 应用名称 |
| type      | string | 是   | 插件ID   |

#### 请求示例

```json
{
  "type": "profiling",
  "bk_biz_id": 2,
  "app_name":"test"
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