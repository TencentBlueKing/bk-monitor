### 功能描述

获取所属日历下所有父类事项列表

### 请求参数

| 字段           | 类型        | 必选 | 描述       |
|--------------|-----------|----|----------| 
| calendar_ids | list[int] | 是  | 所属日历ID列表 |

### 请求参数示例

```json
{
    "calendar_ids": [1, 2, 3]
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

| 字段    | 类型   | 描述   |
|-------|------|------|
| total | int  | 事项总数 |
| list  | list | 事项列表 |

#### list 元素字段说明

| 字段            | 类型     | 描述                |
|---------------|--------|-------------------|
| id            | int    | 事项ID              |
| name          | string | 事项名称              |
| start_time    | int    | 事项开始时间（Unix时间戳，秒） |
| end_time      | int    | 事项结束时间（Unix时间戳，秒） |
| update_user   | string | 更新人               |
| update_time   | string | 更新时间              |
| create_time   | string | 创建时间              |
| create_user   | string | 创建人               |
| calendar_id   | int    | 所属日历ID            |
| calendar_name | string | 所属日历名称            |
| deep_color    | string | 日历深色              |
| light_color   | string | 日历浅色              |
| repeat        | dict   | 重复事项配置信息          |
| parent_id     | int    | 父事项ID（如果是子事项则有值）  |
| is_first      | bool   | 是否为首次事项           |

#### repeat 字段说明

| 字段           | 类型        | 描述                                                                            |
|--------------|-----------|-------------------------------------------------------------------------------|
| freq         | string    | 重复频率，可选值：day（每天）、week（每周）、month（每月）、year（每年）                                  |
| interval     | int       | 重复间隔，表示每隔多少个周期重复一次                                                            |
| every        | list[int] | 重复区间，根据freq不同有不同含义：day时为空列表[]；week时为0-6（周日到周六）；month时为1-31（日期）；year时为1-12（月份） |
| until        | int       | 重复结束时间（Unix时间戳，秒），为null表示无限重复                                                 |
| exclude_date | list[int] | 排除的日期列表（Unix时间戳，秒），这些日期不会生成事项                                                 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 3,
        "list": [
            {
                "id": 1,
                "name": "每周例会",
                "start_time": 1704067200,
                "end_time": 1704070800,
                "update_user": "admin",
                "update_time": "2024-01-01 10:00:00",
                "create_time": "2024-01-01 09:00:00",
                "create_user": "admin",
                "calendar_id": 1,
                "calendar_name": "工作日历",
                "deep_color": "#3A84FF",
                "light_color": "#E1ECFF",
                "repeat": {
                    "freq": "week",
                    "interval": 1,
                    "every": [1],
                    "until": 1735689599,
                    "exclude_date": []
                },
                "parent_id": null,
                "is_first": true
            },
            {
                "id": 2,
                "name": "月度总结",
                "start_time": 1704153600,
                "end_time": 1704157200,
                "update_user": "admin",
                "update_time": "2024-01-02 10:00:00",
                "create_time": "2024-01-02 09:00:00",
                "create_user": "admin",
                "calendar_id": 1,
                "calendar_name": "工作日历",
                "deep_color": "#3A84FF",
                "light_color": "#E1ECFF",
                "repeat": {
                    "freq": "month",
                    "interval": 1,
                    "every": [1],
                    "until": 1735689599,
                    "exclude_date": []
                },
                "parent_id": null,
                "is_first": true
            },
            {
                "id": 3,
                "name": "系统维护",
                "start_time": 1704240000,
                "end_time": 1704243600,
                "update_user": "admin",
                "update_time": "2024-01-03 10:00:00",
                "create_time": "2024-01-03 09:00:00",
                "create_user": "admin",
                "calendar_id": 2,
                "calendar_name": "维护日历",
                "deep_color": "#FF9C01",
                "light_color": "#FFE8C3",
                "repeat": {},
                "parent_id": null,
                "is_first": true
            }
        ]
    }
}
```
