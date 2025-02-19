### 功能描述

获取拨测任务组信息

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段       | 类型  | 必选 | 描述      |
|----------|-----|----|---------|
| group_id | str | 是  | 拨测任务组ID |

#### 示例数据

`路径参数`

```json
{
  "group_id": "10002"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data字段说明

| 字段        | 类型   | 描述      |
|:----------|------|---------|
| id        | int  | 拨测任务组ID |
| name      | str  | 拨测任务组名字 |
| bk_biz_id | int  | 业务ID    |
| task_list | list | 拨测任务列表  |

#### data.task_list

| 字段   | 类型  | 描述     |
|------|-----|--------|
| id   | int | 拨测任务ID |
| name | str | 拨测任务名字 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 10002,
    "name": "group22",
    "bk_biz_id": 2,
    "logo": "",
    "task_list": [
      {
        "id": 10001,
        "name": "task1"
      },
      {
        "id": 10002,
        "name": "task2"
      }
    ]
  }
}
```
