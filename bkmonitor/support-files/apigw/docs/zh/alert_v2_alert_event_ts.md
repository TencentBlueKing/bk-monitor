### 功能描述

【告警V2】告警事件时序数据查询

### 请求参数

| 字段         | 类型        | 必选 | 描述                                                               |
|------------|-----------|----|------------------------------------------------------------------|
| alert_id   | str       | 是  | 告警ID                                                             |
| sources    | list[str] | 否  | 事件来源列表，可选值：HOST（主机）、BCS（容器）、BKCI（蓝盾）、DEFAULT（业务上报），不传或为空表示查询所有来源 |
| interval   | int       | 否  | 时序数据的时间间隔（秒），默认为300                                              |
| start_time | int       | 否  | 开始时间（Unix时间戳，秒）                                                  |
| end_time   | int       | 否  | 结束时间（Unix时间戳，秒）                                                  |

### 请求参数示例

```json
{
    "alert_id": "f1c6877ba046e2d32bfd8393b4dd26f7.1763554080.2860.2978.2",
    "sources": ["HOST"],
    "interval": 300,
    "start_time": 1763553000,
    "end_time": 1763557000
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

| 字段           | 类型   | 描述          |
|--------------|------|-------------|
| series       | list | 时序数据列表      |
| metrics      | list | 指标元数据列表     |
| query_config | dict | 查询配置，用于前端跳转 |

#### series 元素字段说明

| 字段                     | 类型     | 描述                          |
|------------------------|--------|-----------------------------|
| datapoints             | list   | 数据点列表，每个元素为[值, 时间戳（毫秒）]格式   |
| target                 | string | 指标名称（包含维度信息）                |
| metric_field           | string | 指标字段名                       |
| alias                  | string | 指标别名                        |
| dimensions             | dict   | 维度信息（key-value对）            |
| dimensions_translation | dict   | 维度翻译信息（key-value对，将ID翻译为名称） |
| unit                   | string | 单位                          |
| type                   | string | 图表类型（line或bar）              |
| stack                  | string | 堆叠标识（可选）                    |

#### query_config 字段说明

| 字段            | 类型         | 描述              |
|---------------|------------|-----------------|
| bk_biz_id     | int        | 业务ID            |
| start_time    | int        | 开始时间（Unix时间戳，秒） |
| end_time      | int        | 结束时间（Unix时间戳，秒） |
| expression    | str        | 查询表达式           |
| query_configs | list[dict] | 查询配置列表          |
| app_name      | str        | 应用名称（APM场景）     |
| service_name  | str        | 服务名称（APM场景）     |

#### query_configs 元素字段说明

| 字段                | 类型           | 描述                                         |
|-------------------|--------------|--------------------------------------------|
| data_source_label | string       | 数据源标签（如custom、bk_monitor_collector、bk_apm） |
| data_type_label   | string       | 数据类型标签（如event、log）                         |
| table             | string       | 结果表名                                       |
| metrics           | list[dict]   | 指标配置列表                                     |
| where             | list[dict]   | 过滤条件列表                                     |
| group_by          | list[string] | 分组字段列表                                     |
| interval          | int          | 聚合周期（秒）                                    |
| time_field        | string       | 时间字段名                                      |

#### query_configs.metrics 元素字段说明

| 字段     | 类型     | 描述   |
|--------|--------|------|
| field  | string | 指标名  |
| method | string | 汇聚方法 |
| alias  | string | 别名   |

#### query_configs.where 元素字段说明

| 字段        | 类型     | 描述                 |
|-----------|--------|--------------------|
| key       | string | 过滤字段名              |
| method    | string | 匹配方法（如eq、neq、reg等） |
| value     | list   | 匹配值列表              |
| condition | string | 条件关系（如and、or），可选   |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "series": [
            {
                "datapoints": [
                    [5, 1763553000000],
                    [8, 1763553300000],
                    [12, 1763553600000],
                    [6, 1763553900000],
                    [9, 1763554200000]
                ],
                "target": "SUM(_index)",
                "metric_field": "a",
                "alias": "a",
                "dimensions": {},
                "dimensions_translation": {},
                "unit": "",
                "type": "bar"
            }
        ],
        "metrics": [],
        "query_config": {
            "bk_biz_id": 2,
            "start_time": 1763553000,
            "end_time": 1763557000,
            "expression": "a",
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "data_type_label": "event",
                    "table": "gse_system_event",
                    "metrics": [
                        {
                            "field": "_index",
                            "method": "SUM",
                            "alias": "a"
                        }
                    ],
                    "where": [
                        {
                            "key": "source",
                            "method": "eq",
                            "value": ["HOST"]
                        }
                    ],
                    "group_by": [],
                    "interval": 300,
                    "time_field": "time"
                }
            ]
        }
    }
}
```
