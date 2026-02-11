### 功能描述

【告警V2】告警事件总数查询

### 请求参数

| 字段       | 类型  | 必选 | 描述   |
|----------|-----|----|------|
| alert_id | str | 是  | 告警ID |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2"
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

| 字段    | 类型   | 描述           |
|-------|------|--------------|
| total | int  | 事件总数         |
| list  | list | 按来源分组的统计信息列表 |

#### list 元素字段说明

| 字段    | 类型     | 描述                           |
|-------|--------|------------------------------|
| value | string | 事件来源值（HOST/BCS/BKCI/DEFAULT） |
| alias | string | 事件来源显示名称（主机/BCS/蓝盾/业务上报）     |
| total | int    | 该来源的事件数量                     |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 156,
        "list": [
            {
                "value": "HOST",
                "alias": "主机",
                "total": 89
            },
            {
                "value": "BCS",
                "alias": "BCS",
                "total": 45
            },
            {
                "value": "BKCI",
                "alias": "蓝盾",
                "total": 12
            },
            {
                "value": "DEFAULT",
                "alias": "业务上报",
                "total": 10
            }
        ]
    }
}
```
