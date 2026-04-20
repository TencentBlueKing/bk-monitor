### 功能描述

获取时区信息

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段        | 类型     | 描述                    |
|-----------|--------|-----------------------|
| name      | string | 时区显示名称（格式：中文名称(时区标识)） |
| time_zone | string | 时区标识（如Asia/Shanghai）  |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "name": "中国标准时间(Asia/Shanghai)",
            "time_zone": "Asia/Shanghai"
        },
        {
            "name": "美国东部时间(America/New_York)",
            "time_zone": "America/New_York"
        },
        {
            "name": "欧洲中部时间(Europe/Paris)",
            "time_zone": "Europe/Paris"
        },
        {
            "name": "日本标准时间(Asia/Tokyo)",
            "time_zone": "Asia/Tokyo"
        }
    ]
}
```
