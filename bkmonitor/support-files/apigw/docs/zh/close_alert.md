### 功能描述

关闭告警

### 请求参数

| 字段        | 类型        | 必选 | 描述       |
|-----------|-----------|----|---------  |
| bk_biz_id | int       | 是  | 业务ID     |
| ids       | list[str] | 是  | 告警ID列表   |
| message   | str       | 否  | 关闭原因说明，默认为空字符串 |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "ids": ["16424876305819838", "16424876305819839"],
    "message": "问题已解决，手动关闭告警"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段                   | 类型        | 描述                                |
|----------------------|-----------|-----------------------------------|
| alerts_close_success | list[str] | 成功关闭的告警ID列表                       |
| alerts_not_exist     | list[str] | 不存在的告警ID列表                        |
| alerts_already_end   | list[str] | 已经结束的告警ID列表（包括已恢复、已关闭、已确认的告警）    |
| alerts_lock_failed   | list[str] | 加锁失败的告警ID列表（经过最多3次重试后仍然无法获取锁的告警） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "alerts_close_success": ["16424876305819838"],
        "alerts_not_exist": [],
        "alerts_already_end": ["16424876305819839"],
        "alerts_lock_failed": []
    }
}
```