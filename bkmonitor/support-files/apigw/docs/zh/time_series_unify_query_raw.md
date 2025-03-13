### 功能描述

统一查询接口 (原始数据)


#### 接口参数

| 字段                     | 类型         | 必选 | 描述                                            |
|------------------------|------------|----|-----------------------------------------------|
| target                 | list       | 否  | 监控目标列表,默认值[]                                  |
| target_filter_type     | str        | 否  | 监控目标过滤方法，可选值为`auto`(默认值)、`query`、`post-query` |
| post_query_filter_dict | dict       | 否  | 后置查询过滤条件,默认值{}                                |
| bk_biz_id              | int        | 是  | 业务ID                                          |
| query_configs          | list[dict] | 是  | 查询配置列表                                        |
| expression             | str        | 是  | 查询表达式，允许为空                                    |
| stack                  | str        | 否  | 堆叠标识，允许为空                                     |
| function               | dict       | 否  | 功能函数                                          |
| functions              | list[dict] | 否  | 计算函数列表                                        |
| start_time             | int        | 是  | 开始时间                                          |
| end_time               | int        | 是  | 结束时间                                          |
| limit                  | int        | 否  | 限制每个维度的点数                                     |
| slimit                 | int        | 否  | 限制维度数量                                        |
| down_sample_range      | str        | 否  | 降采样周期                                         |
| format                 | str        | 否  | 输出格式，可选值为`time_series`(默认)、`heatmap`、`table`  |
| type                   | str        | 否  | 类型，可选值为`instant`、`range`(默认)。                 |
| series_num             | int        | 否  | 查询数据条数                                        |

#### query_configs

| 字段                | 类型         | 必选 | 描述                         |
|-------------------|------------|----|----------------------------|
| data_type_label   | str        | 否  | 数据类型，默认为`"time_series"`    |
| data_source_label | str        | 是  | 数据来源                       |
| table             | str        | 否  | 结果表名，默认为空字符串               |
| data_label        | str        | 否  | 数据标签，默认为空字符串               |
| metrics           | list[dict] | 否  | 查询指标，默认为空列表                |
| where             | list       | 否  | 过滤条件，默认为空列表                |
| group_by          | list       | 否  | 聚合字段，默认为空列表                |
| interval_unit     | str        | 否  | 聚合周期单位，可选值为`"s"`(默认)、`"m"` |
| interval          | str        | 否  | 时间间隔，默认为`"auto"`           |
| filter_dict       | dict       | 否  | 过滤条件，默认为空字典                |
| time_field        | str        | 否  | 时间字段，允许为空或为`None`          |
| promql            | str        | 否  | PromQL，允许为空。               |
| query_string      | str        | 否  | 日志查询语句，默认为空字符串             |
| index_set_id      | int        | 否  | 索引集ID，允许为`None`            |
| functions         | list[dict] | 否  | 计算函数参数，默认为空列表。             |

#### query_configs.metrics

| 字段      | 类型   | 必选 | 描述               |
|---------|------|----|------------------|
| method  | str  | 否  | 方法，默认为空字符串。      |
| field   | str  | 否  | 字段，默认为空字符串。      |
| alias   | str  | 否  | 别名。              |
| display | bool | 否  | 是否显示，默认为`False`。 |

#### query_configs.functions

| 字段     | 类型         | 必选 | 描述  |
|--------|------------|----|-----|
| id     | str        | 是  | 函数名 |
| params | list[dict] | 是  | 参数  |

#### functions

| 字段     | 类型         | 必选 | 描述  |
|--------|------------|----|-----|
| id     | str        | 是  | 函数名 |
| params | list[dict] | 是  | 参数  |

#### 请求示例

```json
//以下查询基本等价于：avg(rate(bk_monitor:container_cpu_usage_seconds_total[2m]))
{
  "down_sample_range": "30s",
  "step": "auto",
  "format": "time_series",
  "type": "range",
  "start_time": 1737488117,
  "end_time": 1737509717,
  "expression": "a",
  "display": true,
  "query_configs": [
    {
      "data_source_label": "bk_monitor",
      "data_type_label": "time_series",
      "metrics": [
        {
          "field": "container_cpu_usage_seconds_total",
          "method": "AVG",
          "alias": "a"
        }
      ],
      "table": "",
      "group_by": [],
      "display": true,
      "where": [],
      "interval": "auto",
      "interval_unit": "s",
      "time_field": "time",
      "filter_dict": {},
      "functions": [
        {
          "id": "rate",
          "params": [
            {
              "id": "window",
              "value": "2m"
            }
          ]
        }
      ]
    }
  ],
  "target": [],
  "bk_biz_id": "2"
}
```

### 响应参数

| 字段      | 类型         | 描述       |
|---------|------------|----------|
| series  | list[dict] | 时序数据样本信息 |
| metrics | list[dict] | 指标信息     |

#### series 时序数据样本信息

| 字段         | 类型    | 描述    |
|:-----------|:------|:------|
| \_time\_   | int   | 样本时间戳 |
| \_result\_ | float | 样本值   |

#### metrics 指标信息

| 字段                      | 类型         | 描述             |
|:------------------------|:-----------|:---------------|
| id                      | int        | 指标数据库ID        |
| result_table_id         | str        | 结果表ID。         |
| result_table_name       | str        | 结果表名称。         |
| metric_field            | str        | 指标字段名称         |
| metric_field_name       | str        | 指标字段的描述名称      |
| unit                    | str        | 指标的单位          |
| unit_conversion         | int        | 单位转换因子         |
| dimensions              | list[dict] | 维度列表，包含维度的详细信息 |
| plugin_type             | str        | 插件类型           |
| related_name            | str        | 相关名称           |
| related_id              | str        | 相关ID           |
| collect_config          | str        | 收集配置           |
| collect_config_ids      | str        | 收集配置ID列表       |
| result_table_label      | str        | 结果表的标签         |
| data_source_label       | str        | 数据源标签。         |
| data_type_label         | str        | 数据类型标签         |
| data_target             | str        | 数据目标           |
| default_dimensions      | list       | 默认的维度列表        |
| default_condition       | list       | 默认的条件列表        |
| description             | str        | 指标的描述信息        |
| collect_interval        | int        | 数据收集的时间间隔      |
| category_display        | str        | 类别显示名称         |
| result_table_label_name | str        | 结果表标签的名称       |
| extend_fields           | dict       | 扩展字段           |
| use_frequency           | int        | 使用频率           |
| is_duplicate            | int        | 是否为重复记录的标识     |
| readable_name           | str        | 可读的指标名称        |
| metric_md5              | str        | 指标的MD5值，用于唯一标识 |
| data_label              | str        | 数据标签           |
| metric_id               | str        | 指标ID           |

#### metrics.dimensions

| 字段           | 类型   | 描述       |
|:-------------|:-----|:---------|
| id           | str  | 维度的唯一标识符 |
| name         | str  | 维度的名称    |
| is_dimension | bool | 是否为维度的标识 |
| type         | str  | 维度的数据类型  |

#### 响应示例

```json
{
  "series": [
    {
      "_time_": 1737488580000,
      "_result_": 0.0238261915
    },
    {
      "_time_": 1737488640000,
      "_result_": 0.023178433
    },
    {
      "_time_": 1737488700000,
      "_result_": 0.0234621885
    },
    {
      "_time_": 1737488760000,
      "_result_": 0.0233849344
    },
    {
      "_time_": 1737488820000,
      "_result_": 0.0232223858
    },
    {
      "_time_": 1737488880000,
      "_result_": 0.0231977122
    },
    {
      "_time_": 1737488940000,
      "_result_": 0.0222301911
    },
    ....
  ],
  "metrics": [
    {
      "id": 56164772,
      "result_table_id": "",
      "result_table_name": "container_cpu",
      "metric_field": "container_cpu_usage_seconds_total",
      "metric_field_name": "CPU使用量",
      "unit": "",
      "unit_conversion": 1.0,
      "dimensions": [
        {
          "id": "pod",
          "name": "pod",
          "is_dimension": true,
          "type": "string"
        },
        {
          "id": "namespace",
          "name": "namespace",
          "is_dimension": true,
          "type": "string"
        },
        {
          "id": "job",
          "name": "job",
          "is_dimension": true,
          "type": "string"
        },
        {
          "id": "instance",
          "name": "instance",
          "is_dimension": true,
          "type": "string"
        },
        {
          "id": "target",
          "name": "target",
          "is_dimension": true,
          "type": "string"
        },
        ....
      ],
      "plugin_type": "",
      "related_name": "container",
      "related_id": "container",
      "collect_config": "",
      "collect_config_ids": "",
      "result_table_label": "kubernetes",
      "data_source_label": "bk_monitor",
      "data_type_label": "time_series",
      "data_target": "none_target",
      "default_dimensions": [
        "bk_target_ip",
        "bk_target_cloud_id"
      ],
      "default_condition": [],
      "description": "每个CPU内核上的累积占用时间 (单位：秒)，使用rate函数可计算出CPU每分钟使用量",
      "collect_interval": 1,
      "category_display": "container",
      "result_table_label_name": "Kubernetes",
      "extend_fields": {},
      "use_frequency": 3,
      "is_duplicate": 0,
      "readable_name": "container_cpu_usage_seconds_total",
      "metric_md5": "57f722eb535abf2c68c99e35562886c1",
      "data_label": "",
      "metric_id": "bk_monitor..container_cpu_usage_seconds_total"
    }
  ]
}
```

