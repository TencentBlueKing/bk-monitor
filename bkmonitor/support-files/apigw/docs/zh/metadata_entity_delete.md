### 功能描述

删除实体资源


### 请求参数

| 字段       | 类型 | 必选 | 描述     |
| ---------- | ---- | ---- | -------- |
| kind | string | 是   | 实体类型   |
| namespace | string | 否   | 命名空间，可选。如果提供了 bk_biz_id，则会被自动转换覆盖 |
| name | string | 是   | 资源名称 |
| bk_biz_id | int | 否   | 业务ID，可选。如果提供，会自动转换为 space_uid 并覆盖 namespace |

### 请求参数示例

```json
{
    "kind": "CustomRelationStatus",
    "namespace": "default",
    "name": "relation-001"
}
```

或使用 bk_biz_id：

```json
{
    "kind": "CustomRelationStatus",
    "name": "relation-001",
    "bk_biz_id": 2
}
```

### 响应参数

| 字段    | 类型     | 描述        |
| ------- |--------|-----------| 
| result  | bool   | 请求是否成功    |
| code    | int    | 返回的状态码    |
| message | string | 描述信息      |
| data    | null   | 数据        |


### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```
