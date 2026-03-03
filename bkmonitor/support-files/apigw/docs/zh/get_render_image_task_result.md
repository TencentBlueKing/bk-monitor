### 功能描述

获取图片渲染结果


### 请求参数

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| task_id | string | 是   | 任务id，UUID格式的字符串   |

### 请求参数示例

```json
{
    "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 响应参数

| 字段名  | 类型   | 描述         |
| ------- | ------ | ------------ |
| status  | string | 任务状态，可选值：pending（待处理）、rendering（渲染中）、success（成功）、failed（失败） |
| image_url | string | 图片地址，任务未完成时为null     |
| error | string | 错误信息，任务成功时为null     |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "status": "success",
        "image_url": "https://xxx.com/xxx.png",
        "error": null
    },
    "result": true
}
```