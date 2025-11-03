### 功能描述

删除通知组


### 请求参数

| 字段         | 类型 | 必选 | 描述   |
|------------| ---- | ---- |------|
| bk_biz_ids | list | 是   | 业务ID |
| ids        | list | 是   | 通知组ID |

### 请求参数示例

```json
{
  "ids": [
    1
  ],
  "bk_biz_ids": [
    2
  ]
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | null   | 返回数据     |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": null,
    "result": true
}
```
