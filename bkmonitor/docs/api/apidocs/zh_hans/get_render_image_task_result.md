### 功能描述

获取图片渲染结果

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| task_id | string | 是   | 任务id   |

#### 示例数据

```json
{
    "task_id": "xxxxxxxxxxxxx"
}
```

### 响应参数

| 字段名  | 类型   | 描述         |
| ------- | ------ | ------------ |
| status  | string | 任务状态, success, failed, pending, rendering |
| image_url | string | 图片地址     |
| error | string | 错误信息     |

#### 示例数据

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