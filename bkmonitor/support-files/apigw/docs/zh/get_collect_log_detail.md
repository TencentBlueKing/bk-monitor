### 功能描述

获取采集下发单台主机/实例的详细日志信息


#### 接口参数

| 字段          | 类型  | 必选  | 描述       |
| ----------- | --- | --- | -------- |
| bk_biz_id   | int | 是   | 业务 ID    |
| id          | int | 是   | 采集配置 ID  |
| instance_id | str | 是   | 主机/实例 ID |
| task_id     | int | 否   | 任务 ID    |

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "instance_id": "host|instance|host|461",
  "id": 280,
  "task_id": 2572425
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

| 字段         | 类型  | 描述   |
| ---------- | --- | ---- |
| log_detail | str | 日志详情 |

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "log_detail": ""
  }
}
```
