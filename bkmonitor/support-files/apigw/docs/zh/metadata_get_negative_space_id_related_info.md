### 功能描述

按负数空间 ID 查询空间类型、空间 ID，以及关联的正数业务 ID。

负数 ID 为空间自增 ID 的相反数。没有关联蓝鲸业务时，`bk_biz_id` 为空。

### 请求参数

| 字段          | 类型  | 必选 | 描述        |
|-------------|-----|----|-----------|
| negative_id | int | 是  | 负数空间 ID   |

### 请求参数示例

```json
{
    "negative_id": -123456
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 空间关联信息 |

#### data 字段说明

| 字段              | 类型   | 描述                          |
|-----------------|------|-----------------------------|
| negative_biz_id | int  | 请求的负数空间 ID                  |
| bk_biz_id       | str  | 关联的蓝鲸业务 ID，没有关联时为空          |
| space_type      | str  | 空间类型 ID，如 `bkci`、`bksaas`   |
| space_id        | str  | 空间 ID                       |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "negative_biz_id": -123456,
        "bk_biz_id": "2",
        "space_type": "bkci",
        "space_id": "test_space"
    }
}
```
