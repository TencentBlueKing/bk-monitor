### 功能描述

根据space_uid查询data_source

### 请求参数

| 字段                  | 类型        | 必选 | 描述               |
|---------------------|-----------|----|------------------|
| space_uid_list      | list[str] | 是  | 数据源所属空间uid列表     |
| is_platform_data_id | bool      | 否  | 是否为平台级ID（默认true） |

### 请求参数示例

```json
{
    "space_uid_list": ["bkcc__2", "bkci__demo"],
    "is_platform_data_id": true
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 数据     |

#### data 元素字段说明

| 字段         | 类型     | 描述    |
|------------|--------|-------|
| data_name  | string | 数据源名称 |
| bk_data_id | int    | 数据源ID |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "result": true,
    "data": [
        {
            "data_name": "bkmonitor_time_series_1001",
            "bk_data_id": 1001
        },
        {
            "data_name": "bkmonitor_event_1002",
            "bk_data_id": 1002
            }
        ]
}
```
