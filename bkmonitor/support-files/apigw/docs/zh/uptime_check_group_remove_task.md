### 功能描述

拨测任务组移除拨测任务

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段          | 类型  | 必选 | 描述      |
|-------------|-----|----|---------|
| group_id    | int | 是  | 拨测任务组ID |
| task_id     | int | 是  | 拨测任务ID  |
| bk_biz_id   | int | 是  | 业务ID    |

#### 示例数据
```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "group_id": 10003,
    "task_id": 10002,
    "bk_biz_id": 2
}
```

### 响应参数
| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 数据         |

####  data字段说明
| 字段         | 类型  | 描述 |
|:-----------|-----|----|
| msg        | str | 描述 |

#### 示例数据
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "msg": "拨测分组(group3)移除任务(task2)成功"
    }
}
```
