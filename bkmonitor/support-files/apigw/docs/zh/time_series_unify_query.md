### 功能描述

统一查询接口 (适配图表展示)

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段                     | 类型         | 必选 | 描述                                             |
|------------------------|------------|----|------------------------------------------------|
| target                 | list       | 否  | 监控目标列表,默认值[]                                   |
| target_filter_type     | str        | 否  | 监控目标过滤方法，可选值为`auto`(默认值)、`query`、`post-query`。 |
| post_query_filter_dict | dict       | 否  | 后置查询过滤条件,默认值{}                                 |
| bk_biz_id              | int        | 是  | 业务ID                                           |
| query_configs          | list[dict] | 是  | 查询配置列表                                         |
| expression             | str        | 是  | 查询表达式，允许为空                                     |
| stack                  | str        | 否  | 堆叠标识，允许为空                                      |
| function               | dict       | 否  | 功能函数                                           |
| functions              | list[dict] | 否  | 计算函数列表                                         |
| start_time             | int        | 是  | 开始时间                                           |
| end_time               | int        | 是  | 结束时间                                           |
| limit                  | int        | 否  | 限制每个维度的点数                                      |
| slimit                 | int        | 否  | 限制维度数量                                         |
| down_sample_range      | str        | 否  | 降采样周期                                          |
| format                 | str        | 否  | 输出格式，可选值为`time_series`(默认)、`heatmap`、`table`   |
| type                   | str        | 否  | 类型，可选值为`instant`、`range`(默认)。                  |
| series_num             | int        | 否  | 查询数据条数                                         |

#### query_configs

| 字段                | 类型         | 描述                         | 是否必选 |
|-------------------|------------|----------------------------|------|
| data_type_label   | str        | 数据类型，默认为`"time_series"`    | 否    |
| data_source_label | str        | 数据来源                       | 是    |
| table             | str        | 结果表名，默认为空字符串               | 否    |
| data_label        | str        | 数据标签，默认为空字符串               | 否    |
| metrics           | list[dict] | 查询指标，默认为空列表                | 否    |
| where             | list       | 过滤条件，默认为空列表                | 否    |
| group_by          | list       | 聚合字段，默认为空列表                | 否    |
| interval_unit     | str        | 聚合周期单位，可选值为`"s"`(默认)、`"m"` | 否    |
| interval          | str        | 时间间隔，默认为`"auto"`           | 否    |
| filter_dict       | dict       | 过滤条件，默认为空字典                | 否    |
| time_field        | str        | 时间字段，允许为空或为`None`          | 否    |
| promql            | str        | PromQL，允许为空。               | 否    |
| query_string      | str        | 日志查询语句，默认为空字符串             | 否    |
| index_set_id      | int        | 索引集ID，允许为`None`            | 否    |
| functions         | list[dict] | 计算函数参数，默认为空列表。             | 否    |

#### query_configs.metrics

| 字段      | 类型   | 描述               | 是否必选 |
|---------|------|------------------|------|
| method  | str  | 方法，默认为空字符串。      | 否    |
| field   | str  | 字段，默认为空字符串。      | 否    |
| alias   | str  | 别名。              | 否    |
| display | bool | 是否显示，默认为`False`。 | 否    |

#### query_configs.functions

| 字段     | 类型         | 描述  | 是否必选 |
|--------|------------|-----|------|
| id     | str        | 函数名 | 是    |
| params | list[dict] | 参数  | 是    |

#### functions

| 字段     | 类型         | 描述  | 是否必选 |
|--------|------------|-----|------|
| id     | str        | 函数名 | 是    |
| params | list[dict] | 参数  | 是    |

#### 请求示例

```json
//以下查询基本等价于：sum(rate(bk_monitor:container_cpu_usage_seconds_total{pod=~"(bk-monitor-unify-query-7b8658dc5d-9j8jr|bk-monitor-unify-query-7b8658dc5d-z22pv)"}[2m])) by(pod)

{
  "display": true,
  "down_sample_range": "20s",
  "end_time": 1737445607,
  "expression": "a",
  "format": "time_series",
  "query_configs": [
    {
      "data_source_label": "bk_monitor",
      "data_type_label": "time_series",
      "display": true,
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
      ],
      "group_by": [
        "pod"
      ],
      "interval": 60,
      "interval_unit": "s",
      "metrics": [
        {
          "alias": "a",
          "field": "container_cpu_usage_seconds_total",
          "method": "SUM"
        }
      ],
      "table": "",
      "time_field": "time",
      "where": [
        {
          "key": "pod",
          "method": "eq",
          "value": [
            "bk-monitor-unify-query-7b8658dc5d-9j8jr",
            "bk-monitor-unify-query-7b8658dc5d-z22pv"
          ]
        }
      ]
    }
  ],
  "start_time": 1737424007,
  "step": "auto",
  "target": [],
  "type": "range",
  "bk_biz_id": "2"
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 结果     |

#### data 字段说明

| 字段      | 类型         | 描述       |
|---------|------------|----------|
| series  | list[dict] | 时序数据样本信息 |
| metrics | list[dict] | 指标信息     |

#### data.series 时序数据样本信息

| 字段                     | 类型   | 描述              |
|:-----------------------|:-----|:----------------|
| dimensions             | dict | 时间序列的维度信息       |
| target                 | str  | 查询的目标表达式        |
| metric_field           | str  | 指标字段名称          |
| datapoints             | list | 时间序列数据点，包含值和时间戳 |
| alias                  | str  | 指标的别名           |
| type                   | str  | 数据展示的类型，如折线图    |
| dimensions_translation | dict | 维度翻译信息          |
| unit                   | str  | 指标的单位           |

#### data.metrics 指标信息

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

#### data.metrics.dimensions

| 字段           | 类型   | 描述       |
|:-------------|:-----|:---------|
| id           | str  | 维度的唯一标识符 |
| name         | str  | 维度的名称    |
| is_dimension | bool | 是否为维度的标识 |
| type         | str  | 维度的数据类型  |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "series": [
      {
        "dimensions": {
          "pod": "bk-monitor-unify-query-7b8658dc5d-9j8jr"
        },
        "target": "SUM(container_cpu_usage_seconds_total){pod=bk-monitor-unify-query-7b8658dc5d-9j8jr}",
        "metric_field": "_result_",
        "datapoints": [
          [
            0.016888,
            1737423960000
          ],
          [
            0.018065,
            1737424020000
          ],
          [
            0.017532,
            1737424080000
          ],
          [
            0.017575,
            1737424140000
          ],
          .....
        ],
        "alias": "_result_",
        "type": "line",
        "dimensions_translation": {},
        "unit": ""
      },
      {
        "dimensions": {
          "pod": "bk-monitor-unify-query-7b8658dc5d-z22pv"
        },
        "target": "SUM(container_cpu_usage_seconds_total){pod=bk-monitor-unify-query-7b8658dc5d-z22pv}",
        "metric_field": "_result_",
        "datapoints": [
          [
            0.019122,
            1737423960000
          ],
          [
            0.019653,
            1737424020000
          ],
          [
            0.022681,
            1737424080000
          ],
          [
            0.019766,
            1737424140000
          ],
          [
            0.019805,
            1737424200000
          ],
          ......
        ],
        "alias": "_result_",
        "type": "line",
        "dimensions_translation": {},
        "unit": ""
      }
    ],
    "metrics": [
      {
        "id": 160,
        "result_table_id": "",
        "result_table_name": "container_cpu",
        "metric_field": "container_cpu_usage_seconds_total",
        "metric_field_name": "CPU使用量",
        "unit": "",
        "unit_conversion": 1,
        "dimensions": [
          {
            "id": "exported_namespace",
            "name": "exported_namespace",
            "is_dimension": true,
            "type": "string"
          },
          {
            "id": "service",
            "name": "service",
            "is_dimension": true,
            "type": "string"
          },
          {
            "id": "bk_endpoint_url",
            "name": "bk_endpoint_url",
            "is_dimension": true,
            "type": "string"
          },
          {
            "id": "metrics_path",
            "name": "metrics_path",
            "is_dimension": true,
            "type": "string"
          }
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
        "result_table_label_name": "kubernetes",
        "extend_fields": {},
        "use_frequency": 3,
        "is_duplicate": 0,
        "readable_name": "container_cpu_usage_seconds_total",
        "metric_md5": "f320ad309575605576ae6718904e4d89",
        "data_label": "",
        "metric_id": "bk_monitor..container_cpu_usage_seconds_total"
      }
    ]
  }
}
```

