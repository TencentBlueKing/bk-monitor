### 功能描述

获取指标数据


#### 接口参数

| 字段                 | 类型   | 必选 | 描述     |
|--------------------|------|----|--------|
| bk_biz_id          | int  | 是  | 业务ID   |
| data_source_label  | list | 否  | 指标数据源  |
| data_type_label    | str  | 否  | 指标数据类型 |
| data_source        | list | 否  | 数据源    |
| result_table_label | list | 否  | 结果表标签  |
| tag                | str  | 否  | 标签     |
| conditions         | list | 否  | 条件     |
| page               | int  | 否  | 页码     |
| page_size          | int  | 否  | 每页数目   |

#### 请求示例

```json
{
  "conditions": [
    {
      "key": "query",
      "value": ""
    }
  ],
  "data_source": [
    [
      "bk_monitor",
      "time_series"
    ]
  ],
  "data_type_label": "time_series",
  "tag": "",
  "page": 1,
  "page_size": 20,
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 结果     |

#### data

| 字段               | 类型   | 描述    |
|------------------|------|-------|
| metric_list      | list | 指标信息  |
| tag_list         | list | 标签信息  |
| data_source_list | list | 数据源信息 |
| scenario_list    | list | 场景信息  |
| count            | int  | 指标总数  |

#### data.metric_list

| 字段                      | 类型        | 描述          |
|-------------------------|-----------|-------------|
| bk_biz_id               | int       | 业务ID        |
| id                      | int       | ID          |
| result_table_id         | str       | SQL查询表      |
| result_table_name       | str       | 表别名         |
| metric_field            | str       | 指标名         |
| metric_field_name       | str       | 指标别名        |
| unit                    | str       | 单位          |
| dimensions              | list      | 维度名         |
| related_name            | str       | 插件名、拨测任务名   |
| related_id              | str       | 插件id、拨测任务id |
| result_table_label      | str       | 表标签         |
| data_source_label       | str       | 数据源标签       |
| result_table_label_name | str       | 表标签别名       |
| data_type_label         | str       | 数据类型标签      |
| data_target             | str       | 数据目标标签      |
| default_dimensions      | list[str] | 默认维度列表      |
| default_condition       | list      | 默认监控条件      |
| description             | str       | 指标含义        |
| collect_interval        | int       | 指标采集周期      |
| extend_fields           | dict      | 额外字段        |
| use_frequency           | int       | 使用频率        |
| readable_name           | str       | 指标可读名       |
| metric_id               | str       | 指标ID        |
| data_label              | str       | db标识        |
| default_trigger_config  | str       | 默认触发配置      |
| disabled                | bool      | 是否失效        |
| name                    | str       | 指标名称        |
| promql_metric           | str       | promql指标    |
| remarks                 | list[str] | 指标备注        |
| time_field              | str       | 时间字段        |

#### data.metric_list.dimensions

| 字段           | 类型   | 描述    |
|--------------|------|-------|
| name         | str  | 维度名称  |
| id           | str  | 维度 ID |
| is_dimension | bool | 是否是维度 |
| type         | str  | 类型    |

#### data.tag_list

| 字段   | 类型  | 描述   |
|------|-----|------|
| id   | str | 标签ID |
| name | str | 标签名称 |

#### data.data_source_list

| 字段                | 类型  | 描述     |
|-------------------|-----|--------|
| id                | str | 数据源ID  |
| name              | str | 数据源名称  |
| data_source_label | str | 数据源标签  |
| data_type_label   | str | 数据类型标签 |
| count             | str | 指标数量   |

#### data.scenario_list

| 字段    | 类型  | 描述   |
|-------|-----|------|
| id    | str | 场景ID |
| name  | str | 场景名称 |
| count | str | 指标数量 |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "metric_list": [
      {
        "id": 58,
        "name": "磁盘空间使用率",
        "bk_biz_id": 0,
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "dimensions": [
          {
            "id": "bk_agent_id",
            "name": "Agent ID",
            "is_dimension": true,
            "type": "string"
          },
          {
            "id": "bk_biz_id",
            "name": "业务ID",
            "is_dimension": true,
            "type": "string"
          }
        ],
        "collect_interval": 1,
        "unit": "percent",
        "metric_field": "in_use",
        "result_table_id": "system.disk",
        "time_field": "time",
        "result_table_label": "os",
        "result_table_label_name": "操作系统",
        "metric_field_name": "磁盘空间使用率",
        "result_table_name": "磁盘",
        "readable_name": "system.disk.in_use",
        "data_label": "",
        "description": "磁盘空间使用率",
        "remarks": [],
        "default_condition": [],
        "default_dimensions": [
          "bk_target_ip",
          "bk_target_cloud_id",
          "mount_point"
        ],
        "default_trigger_config": {
          "check_window": 5,
          "count": 1
        },
        "related_id": "system",
        "related_name": "system",
        "extend_fields": {},
        "use_frequency": 6316,
        "disabled": false,
        "data_target": "host_target",
        "promql_metric": "bkmonitor:system:disk:in_use",
        "metric_id": "bk_monitor.system.disk.in_use"
      }
    ],
    "tag_list": [
      {
        "id": "__COMMON_USED__",
        "name": "常用"
      },
      {
        "id": "113",
        "name": "script_test_71_94"
      },
      {
        "id": "118",
        "name": "script_test_wwzz_96"
      }
    ],
    "data_source_list": [
      {
        "count": 2326,
        "data_source_label": "bk_monitor",
        "data_type_label": "time_series",
        "id": "bk_monitor_time_series",
        "name": "监控采集指标"
      },
      {
        "count": 0,
        "data_source_label": "prometheus",
        "data_type_label": "time_series",
        "id": "prometheus_time_series",
        "name": "Prometheus"
      }
    ],
    "scenario_list": [
      {
        "id": "uptimecheck",
        "name": "服务拨测",
        "count": 15
      },
      {
        "id": "application_check",
        "name": "业务应用",
        "count": 274
      },
      {
        "id": "apm",
        "name": "APM",
        "count": 191
      }
    ],
    "count": 2326
  }
}
```
