### 功能描述

将图表保存到指定的仪表盘

### 请求参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | int | 是 | 业务ID |
| panels | list[object] | 是 | 图表配置列表，不能为空 |
| dashboard_uids | list[string] | 是 | 目标仪表盘UID列表，可以为空 |

#### panels 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| name | string | 是 | 图表名称 |
| queries | list[object] | 是 | 查询配置列表，不能为空 |
| fill | bool | 否 | 是否填充区域，默认为false |
| min_y_zero | bool | 否 | Y轴最小值是否为0，默认为false |
| datasource | string | 否 | 数据源名称或UID |

#### queries 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| expression | string | 否 | 表达式，可以为空 |
| alias | string | 否 | 别名，默认为空 |
| query_configs | list[object] | 是 | 查询配置列表 |
| function | object | 否 | 函数配置，默认为空对象 |
| functions | list[object] | 否 | 计算函数列表，默认为空列表 |

#### query_configs 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| data_source_label | string | 是 | 数据来源标签 |
| data_type_label | string | 否 | 数据类型标签，默认为"time_series" |
| display | bool | 否 | 是否显示，默认为false |
| metrics | list[object] | 否 | 查询指标列表（非PromQL查询时必填） |
| promql | string | 否 | PromQL查询语句，默认为空 |
| table | string | 否 | 结果表名 |
| data_label | string | 否 | 数据库标识 |
| where | list | 否 | 过滤条件，默认为空列表 |
| group_by | list | 否 | 聚合字段，默认为空列表 |
| interval | string/int | 否 | 时间间隔，默认为60 |
| interval_unit | string | 否 | 聚合周期单位，可选值：`s`（秒）、`m`（分）、`h`（小时），默认为"s" |
| filter_dict | object | 否 | 过滤条件字典，默认为空对象 |
| time_field | string | 否 | 时间字段 |
| query_string | string | 否 | 日志查询语句（日志平台数据源使用） |
| index_set_id | int | 否 | 索引集ID（日志平台数据源使用） |
| index | object | 否 | 索引集配置（日志平台数据源使用） |
| metric | string | 否 | 指标（日志平台数据源使用） |
| method | string | 否 | 汇聚方法（日志平台数据源使用） |
| functions | list[object] | 否 | 计算函数参数列表，默认为空列表 |

#### metrics 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| field | string | 是 | 字段名 |
| method | string | 是 | 聚合方法 |
| alias | string | 否 | 别名 |
| display | bool | 否 | 是否显示，默认为false |

#### functions 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| id | string | 是 | 函数ID |
| params | list[object] | 是 | 函数参数列表，可以为空 |

#### params 元素字段说明

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| id | string | 是 | 参数ID |
| value | string | 是 | 参数值 |

#### 请求示例

**基础时序数据查询**：
```json
{
    "bk_biz_id": 2,
    "dashboard_uids": ["dashboard-uid-1", "dashboard-uid-2"],
    "panels": [
        {
            "name": "CPU使用率",
            "fill": false,
            "min_y_zero": true,
            "queries": [
                {
                    "alias": "a",
                    "expression": "",
                    "query_configs": [
                        {
                            "data_source_label": "bk_monitor",
                            "data_type_label": "time_series",
                            "table": "system.cpu_summary",
                            "metrics": [
                                {
                                    "field": "usage",
                                    "method": "AVG",
                                    "alias": "a"
                                }
                            ],
                            "interval": 60,
                            "interval_unit": "s",
                            "where": [],
                            "group_by": ["ip", "bk_cloud_id"]
                        }
                    ]
                }
            ]
        }
    ]
}
```

**PromQL查询**：
```json
{
    "bk_biz_id": 2,
    "dashboard_uids": ["dashboard-uid-1"],
    "panels": [
        {
            "name": "内存使用率",
            "queries": [
                {
                    "alias": "",
                    "expression": "",
                    "query_configs": [
                        {
                            "data_source_label": "prometheus",
                            "data_type_label": "time_series",
                            "promql": "avg(system_mem_pct_used)",
                            "interval": 60
                        }
                    ]
                }
            ]
        }
    ]
}
```

**日志平台数据源**：
```json
{
    "bk_biz_id": 2,
    "dashboard_uids": ["dashboard-uid-1"],
    "panels": [
        {
            "name": "日志统计",
            "datasource": "日志平台",
            "queries": [
                {
                    "alias": "",
                    "expression": "",
                    "query_configs": [
                        {
                            "data_source_label": "bk_log_search",
                            "data_type_label": "time_series",
                            "query_string": "status: 500",
                            "index_set_id": 123,
                            "metric": "log_count",
                            "method": "value_count",
                            "interval": 60,
                            "interval_unit": "s"
                        }
                    ]
                }
            ]
        }
    ]
}
```

### 响应参数

| 字段 | 类型 | 描述 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 返回的状态码 |
| message | string | 描述信息 |
| data | list | 返回数据，包含每个仪表盘的更新结果 |

#### data 元素字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| result | bool | 该仪表盘更新是否成功 |
| code | int | 状态码 |
| message | string | 消息 |
| data | object | 更新结果数据 |

#### data.data 字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| uid | string | 仪表盘唯一标识 |
| pluginId | string | 插件ID |
| title | string | 仪表盘标题 |
| imported | bool | 是否已导入 |
| importedUri | string | 导入的URI |
| importedUrl | string | 导入的URL（仪表盘访问地址） |
| slug | string | URL友好的标识符 |
| dashboardId | int | 仪表盘ID |
| folderId | int | 所属文件夹ID |
| folderUid | string | 所属文件夹唯一标识 |
| description | string | 描述信息 |
| path | string | 路径 |
| removed | bool | 是否已删除 |

#### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": [
        {
            "result": true,
            "code": 200,
            "message": "OK",
            "data": {
                "uid": "dashboard-uid-1",
                "pluginId": "",
                "title": "CPU监控",
                "imported": true,
                "importedUri": "db/cpu-usage",
                "importedUrl": "/grafana/d/dashboard-uid-1/cpu-usage",
                "slug": "cpu-usage",
                "dashboardId": 123,
                "folderId": 10,
                "folderUid": "folder-uid-1",
                "description": "",
                "path": "",
                "removed": false
            }
        },
        {
            "result": true,
            "code": 200,
            "message": "OK",
            "data": {
                "uid": "dashboard-uid-2",
                "pluginId": "",
                "title": "系统监控",
                "imported": true,
                "importedUri": "db/system-monitor",
                "importedUrl": "/grafana/d/dashboard-uid-2/system-monitor",
                "slug": "system-monitor",
                "dashboardId": 456,
                "folderId": 10,
                "folderUid": "folder-uid-1",
                "description": "",
                "path": "",
                "removed": false
            }
        }
    ]
}
```
