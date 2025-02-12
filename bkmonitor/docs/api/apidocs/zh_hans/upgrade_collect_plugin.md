### 功能描述

采集配置插件升级

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型   | 必选  | 描述       |
| --------- | ---- | --- | -------- |
| bk_biz_id | int  | 是   | 业务 ID     |
| id        | int  | 是   | 采集配置 ID   |
| params    | Dict | 是   | 采集配置参数   |
| realtime  | bool | 否   | 是否实时刷新缓存 |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "id": 280,
  "params": {},
  "realtime": false
}
```

### 返回结果

| 字段      | 类型     | 描述     |
| ------- | ------ | ------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data 字段说明

| 字段            | 类型  | 描述        |
| ------------- | --- | --------- |
| id            | int | 采集配置 ID   |
| deployment_id | int | 部署版本历史 ID |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 280,
    "deployment_id": 1
  }
}
```
