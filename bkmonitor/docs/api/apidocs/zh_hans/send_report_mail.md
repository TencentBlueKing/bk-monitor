### 功能描述

发送订阅报表

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段 | 类型  | 必选 | 描述   |
|----|-----|----|------|
| id | int | 是  | 报表ID |

#### 示例数据

```json
{
  "id": 10003
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | null | 数据     |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": null
}
```
