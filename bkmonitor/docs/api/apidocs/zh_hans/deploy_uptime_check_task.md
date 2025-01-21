### 功能描述

下发拨测任务

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段        | 类型  | 必选 | 描述     |
|-----------|-----|----|--------|
| bk_biz_id | int | 是  | 业务ID   |
| task_id   | int | 是  | 拨测任务ID |

#### 示例数据

```json
{
  "bk_biz_id": 2,
  "task_id": 10018
}
```

### 响应参数

| 字段    | 类型    | 描述         |
| ------- |-------| ------------ |
| result  | bool  | 请求是否成功 |
| code    | int   | 返回的状态码 |
| message | str   | 描述信息     |
| data    | str   | 描述信息         |

#### 示例数据

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": "success"
}
```

