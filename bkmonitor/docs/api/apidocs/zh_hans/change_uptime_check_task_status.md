### 功能描述

启停拨测任务

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型  | 必选 | 描述     |
|-----------|-----|----|--------|
| task_id   | int | 是  | 拨测任务ID |
| status    | str | 是  | 拨测任务状态 |

#### 示例数据

```json
{
  "status": "running",
  "task_id": 10013
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段     | 类型  | 描述     |
|--------|-----|--------|
| id     | int | 拨测任务ID |
| status | str | 拨测任务状态 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 10013,
    "status": "running"
  }
}
```


