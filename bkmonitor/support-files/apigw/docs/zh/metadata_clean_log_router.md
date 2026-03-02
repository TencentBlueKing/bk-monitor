### 功能描述

清理日志路由配置

### 请求参数

| 字段         | 类型  | 必选 | 描述   |
|------------|-----|----|------|
| data_label | str | 是  | 数据标签 |

### 请求参数示例

```json
{
    "data_label": "test_label"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | null   | 无返回数据  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
