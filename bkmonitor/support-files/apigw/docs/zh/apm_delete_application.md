### 功能描述

删除应用

### 请求参数

| 字段名            | 类型  | 是否必选 | 描述     |
|----------------|-----|------|--------|
| application_id | int | 否    | 应用ID   |
| bk_biz_id      | int | 否    | 业务ID   |
| app_name       | str | 否    | 应用名称   |
| space_uid      | str | 否    | 空间唯一标识 |

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "app_name": "my_app"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 删除结果   |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "success": true
  }
}
```
