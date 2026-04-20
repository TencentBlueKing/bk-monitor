### 功能描述

查询或创建Agent事件数据ID

### 请求参数

| 字段        | 类型  | 必选 | 描述   |
|-----------|-----|----|------|
| bk_biz_id | int | 是  | 业务ID |

### 请求参数示例

```json
{
    "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | object | 返回数据   |

#### data 字段说明

| 字段         | 类型  | 描述           |
|------------|-----|--------------|
| bk_data_id | int | Agent事件数据源ID |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_data_id": 1001
    }
}
```
