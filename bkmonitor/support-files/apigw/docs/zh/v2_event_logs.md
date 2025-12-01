### 功能描述

新版事件检索

### 请求参数

| 字段          | 类型 | 必选 | 描述               |
| ------------- | ---- | ---- | ------------------ |
| bk_biz_id     | int  | 是   | 业务ID             |
| start_time    | int  | 否   | 开始时间（时间戳） |
| end_time      | int  | 否   | 结束时间（时间戳） |
| limit         | int  | 否   | 数量限制，默认10   |
| offset        | int  | 否   | 偏移量，默认0      |
| query_configs | list | 是   | 查询配置列表       |
| sort          | list | 否   | 排序字段列表       |

#### query_configs 数据格式

| 字段              | 类型   | 必选 | 描述              |
| ----------------- | ------ | ---- | ----------------- |
| table             | string | 是   | 结果表            |
| data_type_label   | string | 是   | 数据类型标签      |
| data_source_label | string | 是   | 数据源标签        |
| query_string      | string | 否   | 查询语句，默认"*" |
| filter_dict       | dict   | 否   | 过滤条件，默认{}  |
| where             | list   | 否   | 过滤条件，默认[]  |
| group_by          | list   | 否   | 聚合字段，默认[]  |

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "start_time": 1701388800,
    "end_time": 1701475200,
    "limit": 10,
    "offset": 0,
    "query_configs": [
        {
            "table": "system_event",
            "data_type_label": "event",
            "data_source_label": "bk_monitor",
            "query_string": "*error*",
            "filter_dict": {},
            "where": [],
            "group_by": []
        }
    ],
    "sort": ["-time"]
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 数据         |

#### data 字段说明

| 字段 | 类型 | 描述     |
| ---- | ---- | -------- |
| list | list | 事件列表 |

#### list 字段说明

| 字段          | 类型   | 描述                            |
| ------------- | ------ | ------------------------------- |
| time          | object | 数据上报时间                    |
| type          | object | 事件等级                        |
| event_name    | object | 事件名                          |
| event.content | object | 内容                            |
| target        | object | 目标                            |
| source        | object | 事件来源                        |
| _meta         | object | 元数据                          |
| origin_data   | object | 原始数据                        |
| value         | string | 字段值                          |
| alias         | string | 显示别名                        |
| url           | string | 链接地址（仅target字段）        |
| detail        | object | 详细信息（仅event.content字段） |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "list": [
            {
                "time": {
                    "value": "2023-12-01T10:30:00+08:00",
                    "alias": "2023-12-01 10:30:00"
                },
                "type": {
                    "value": "warning",
                    "alias": "warning"
                },
                "event_name": {
                    "value": "CPU使用率过高",
                    "alias": "CPU使用率过高"
                },
                "event.content": {
                    "value": "CPU使用率达到95%",
                    "alias": "CPU使用率达到95%",
                    "detail": {
                        "event.content": {
                            "label": "事件内容",
                            "value": "CPU使用率达到95%",
                            "alias": "CPU使用率达到95%"
                        }
                    }
                },
                "target": {
                    "value": "192.168.1.100",
                    "alias": "192.168.1.100",
                    "url": ""
                },
                "source": {
                    "value": "host",
                    "alias": "系统/主机"
                },
                "_meta": {
                    "__data_label": "system_event",
                    "__source": "host",
                    "__domain": "system",
                    "_time_": 1701388200000
                },
                "origin_data": {
                    "time": "2023-12-01T10:30:00+08:00",
                    "event_name": "CPU使用率过高",
                    "event.content": "CPU使用率达到95%",
                    "target": "192.168.1.100",
                    "domain": "system",
                    "source": "host",
                    "type": "warning"
                }
            }
        ]
    }
}
```

