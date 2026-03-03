### 功能描述

获取告警标签列表及其统计信息

### 请求参数

| 字段           | 类型         | 必选 | 描述                        |
|--------------|------------|----|---------------------------|
| bk_biz_ids   | list[int]  | 否  | 业务ID列表，为null时表示查询所有有权限的业务 |
| status       | list[str]  | 否  | 告警状态列表                    |
| conditions   | list[dict] | 否  | 搜索条件列表，默认为空列表             |
| query_string | str        | 否  | 查询字符串，默认为空                |
| start_time   | int        | 是  | 开始时间（Unix时间戳，秒）           |
| end_time     | int        | 是  | 结束时间（Unix时间戳，秒）           |
| username     | str        | 否  | 负责人用户名                    |

#### conditions 元素字段说明

| 字段        | 类型   | 必选 | 描述                             |
|-----------|------|----|--------------------------------|
| key       | str  | 是  | 匹配字段名                          |
| value     | list | 是  | 匹配值列表                          |
| method    | str  | 否  | 匹配方法，如\"eq\"（等于）、\"neq\"（不等于）等 |
| condition | str  | 否  | 条件关系，如\"and\"、\"or\"           |

### 请求参数示例

```json
{
    "bk_biz_ids": [2, 3],
    "status": ["ABNORMAL"],
    "conditions": [
        {
            "key": "severity",
            "value": [1, 2]
        }
    ],
    "query_string": "alert_name: CPU*",
    "start_time": 1704067200,
    "end_time": 1704153600,
    "username": "admin"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 返回数据   |

#### data 元素字段说明

| 字段    | 类型     | 描述                   |
|-------|--------|----------------------|
| id    | string | 标签唯一标识（格式：tags.标签键名） |
| name  | string | 标签键名                 |
| count | int    | 该标签在查询时间范围内出现的告警数量   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "id": "tags.app_name",
            "name": "app_name",
            "count": 156
        },
        {
            "id": "tags.module",
            "name": "module",
            "count": 89
        },
        {
            "id": "tags.cluster",
            "name": "cluster",
            "count": 45
        },
        {
            "id": "tags.service",
            "name": "service",
            "count": 123
        }
    ]
}
```
