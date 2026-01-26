### 功能描述

查询应用下的服务列表，支持分页、排序、筛选和多维度过滤。适用于 APM 场景的服务管理和监控。

### 请求参数

| 字段                  | 类型         | 必选 | 描述                                                                |
|---------------------|------------|----|-------------------------------------------------------------------|
| bk_biz_id           | int        | 是  | 业务 ID                                                             |
| app_name            | string     | 是  | 应用名称                                                              |
| start_time          | int        | 是  | 数据开始时间（Unix 时间戳，秒）                                                |
| end_time            | int        | 是  | 数据结束时间（Unix 时间戳，秒）                                                |
| keyword             | string     | 否  | 查询关键词，用于模糊搜索服务名称                                                  |
| page                | int        | 否  | 页码，默认为 1                                                          |
| page_size           | int        | 否  | 每页条数，默认为 10                                                       |
| sort                | string     | 否  | 排序方式，格式为 `字段名` 或 `-字段名`（降序）                                       |
| filter              | string     | 否  | 分类过滤条件，默认 `all`，可选值见下文                                            |
| filter_dict         | dict       | 否  | 筛选条件字典                                                            |
| field_conditions    | List[dict] | 否  | OR 条件列表，用于多条件组合筛选                                                 |
| view_mode           | string     | 否  | 展示模式，可选 `page_home`（首页）、`page_services`（服务列表页），默认 `page_services` |
| include_data_status | bool       | 否  | 是否包含数据状态信息，默认 `false`                                             |

#### filter 枚举值说明

| 枚举值             | 含义   |
|-----------------|------|
| `all`           | 全部   |
| `http`          | HTTP |
| `rpc`           | RPC  |
| `db`            | 数据库  |
| `messaging`     | 消息队列 |
| `async_backend` | 异步后台 |
| `other`         | 其他   |

#### field_conditions 字段说明

`field_conditions` 是一个列表，每个元素包含以下字段：

| 字段    | 类型           | 必选 | 描述            |
|-------|--------------|----|---------------| 
| key   | string       | 是  | 筛选字段名         |
| value | List[string] | 是  | 筛选值列表，至少包含一个值 |

**支持的筛选字段（key）**

| 字段名 (key)      | 描述                                           |
|:---------------|:---------------------------------------------|
| `category`     | 服务分类，可选值同 `filter` 枚举值                       |
| `language`     | 编程语言，如 `python`、`java`、`go` 等                |
| `apply_module` | 数据上报类型，可选 `metric`、`log`、`trace`、`profiling` |
| `have_data`    | 数据状态，可选 `true`（有数据）、`false`（无数据）             |
| `labels`       | 自定义标签                                        |

### 请求参数示例

```json
{
  "app_name": "trpc-cluster-access-demo",
  "start_time": 1769064077,
  "end_time": 1769067677,
  "filter": "all",
  "sort": "-service_name",
  "field_conditions": [
    {
      "key": "language",
      "value": [
        "go"
      ]
    },
    {
      "key": "apply_module",
      "value": [
        "trace"
      ]
    },
    {
      "key": "have_data",
      "value": [
        "true"
      ]
    },
    {
      "key": "category",
      "value": [
        "http"
      ]
    }
  ],
  "page": 1,
  "page_size": 20,
  "keyword": "bk",
  "view_mode": "page_home",
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 服务列表数据 |

#### data 字段说明

| 字段      | 类型         | 描述               |
|---------|------------|------------------|
| total   | int        | 服务总数             |
| columns | List[dict] | 展示列的元数据          |
| data    | List[dict] | 服务列表（Service 对象） |
| filter  | List[dict] | 可用的筛选项列表         |

#### data.columns 字段说明

`columns` 是一个列表，定义了表格的列配置，每个元素包含以下字段：

| 字段          | 类型          | 描述                                                  |
|-------------|-------------|-----------------------------------------------------|
| id          | string      | 列标识，对应 `data.data` 中的字段名                            |
| name        | string      | 列显示名称                                               |
| sortable    | bool/string | 是否可排序，可选 `false`、`true`、`custom`（自定义排序）             |
| disabled    | bool        | 是否禁用，禁用后该列不可被隐藏(强制显示)                               |
| checked     | bool        | 是否默认显示，disabled 为 `true` 时，此设置无效                    |
| type        | string      | 列类型，如 `link`、`datapoints`、`data_status`、`collect` 等 |
| width       | int/null    | 列宽度（像素）                                             |
| min_width   | int/null    | 最小列宽度（像素）                                           |
| filterable  | bool        | 是否可筛选                                               |
| filter_list | List        | 筛选项列表                                               |
| actionId    | string/null | 操作 ID                                               |
| asyncable   | bool        | 是否为异步加载字段                                           |
| props       | dict        | 额外属性配置，如 `{"align": "center"}`                      |


#### data.data 字段说明（Service 对象）

| 字段                    | 类型           | 描述                                  |
|-----------------------|--------------|-------------------------------------|
| app_name              | string       | 应用名称                                |
| service_name          | dict         | 服务名称（复杂对象，见下文详细说明）                  |
| type                  | string       | 服务类型（已做国际化处理）                       |
| language              | string       | 编程语言                                |
| category              | string       | 服务分类（英文标识）                          |
| kind                  | string       | 服务类型标识                              |
| collect               | dict         | 收藏信息（复杂对象，见下文详细说明）                  |
| labels                | List[string] | 自定义标签列表                             |
| request_count         | dict         | 调用次数（异步加载，复杂对象，见下文详细说明）             |
| error_rate            | dict         | 错误率（异步加载，复杂对象，见下文详细说明）              |
| avg_duration          | dict         | 平均响应耗时（异步加载，复杂对象，见下文详细说明）           |
| metric_data_status    | dict         | 指标数据状态（异步加载，复杂对象，见下文详细说明）           |
| log_data_status       | dict         | 日志数据状态（异步加载，复杂对象，见下文详细说明）           |
| trace_data_status     | dict         | 调用链数据状态（异步加载，复杂对象，见下文详细说明）          |
| profiling_data_status | dict         | 性能分析数据状态（异步加载，复杂对象，见下文详细说明）         |
| strategy_count        | int          | 关联的策略数（异步加载，仅 `page_services` 模式返回） |
| alert_status          | string       | 告警状态（异步加载，仅 `page_services` 模式返回）   |
| operation             | List[dict]   | 操作项列表（复杂对象，见下文详细说明）                 |

#### data.data 中的复杂字段详细说明

**1. service_name 字段（链接对象）**

| 字段       | 类型     | 描述                   |
|----------|--------|----------------------|
| target   | string | 链接打开方式，如 `self`（当前页） |
| value    | string | 服务名称                 |
| url      | string | 服务详情页链接              |
| key      | string | 保留字段                 |
| icon     | string | 服务图标（Base64 编码的 SVG） |
| syncTime | bool   | 是否同步时间参数到链接          |

**2. collect 字段（收藏对象）**

| 字段         | 类型     | 描述                 |
|------------|--------|--------------------|
| is_collect | bool   | 是否已收藏              |
| api        | string | 收藏操作的 API 接口名      |
| params     | dict   | API 调用参数，包含服务名和应用名 |

**3. request_count / error_rate / avg_duration 字段（指标数据对象）**

| 字段         | 类型          | 描述                                                  |
|------------|-------------|-----------------------------------------------------|
| datapoints | List/null   | 数据点列表，格式为 `[[value, timestamp], ...]`，异步加载时为 `null` |
| unit       | string/null | 单位，如 `percentunit`（百分比）、`ns`（纳秒），异步加载时为 `null`      |

**4. metric_data_status / log_data_status / trace_data_status / profiling_data_status 字段（数据状态对象）**

| 字段   | 类型     | 描述                                                                  |
|------|--------|---------------------------------------------------------------------|
| icon | string | 状态图标标识，可选 `normal`（正常）、`no_data`（无数据）、`disabled`（已禁用），异步加载时为 `null` |

**5. operation 字段（操作列表）**

`operation` 是一个列表，每个元素包含以下字段：

| 字段     | 类型     | 描述                   |
|--------|--------|----------------------|
| target | string | 链接打开方式，如 `self`（当前页） |
| value  | string | 操作名称，如 `配置`          |
| url    | string | 操作链接                 |
| key    | string | 保留字段                 |
| icon   | string | 操作图标                 |

#### data.filter 字段说明

`filter` 是一个列表，每个元素包含以下字段：

| 字段   | 类型         | 描述        |
|------|------------|-----------|
| id   | string     | 筛选项标识     |
| name | string     | 筛选项名称     |
| data | List[dict] | 筛选项的可选值列表 |

**data 中每个元素的字段**

| 字段    | 类型     | 描述     |
|-------|--------|--------|
| id    | string | 选项标识   |
| name  | string | 选项名称   |
| count | int    | 该选项的数量 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "columns": [
            {
                "id": "collect",
                "name": "",
                "sortable": false,
                "disabled": true,
                "checked": true,
                "type": "collect",
                "width": 40,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": false,
                "props": {}
            },
            {
                "id": "service_name",
                "name": "服务名称",
                "sortable": "custom",
                "disabled": true,
                "checked": true,
                "type": "link",
                "width": null,
                "min_width": 200,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": false,
                "props": {}
            },
            {
                "id": "request_count",
                "name": "调用次数",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "datapoints",
                "width": null,
                "min_width": 160,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {}
            },
            {
                "id": "error_rate",
                "name": "错误率",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "datapoints",
                "width": null,
                "min_width": 160,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {}
            },
            {
                "id": "avg_duration",
                "name": "平均响应耗时",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "datapoints",
                "width": null,
                "min_width": 160,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {}
            },
            {
                "id": "metric_data_status",
                "name": "指标",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "data_status",
                "width": 55,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {
                    "align": "center"
                }
            },
            {
                "id": "log_data_status",
                "name": "日志",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "data_status",
                "width": 55,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {
                    "align": "center"
                }
            },
            {
                "id": "trace_data_status",
                "name": "调用链",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "data_status",
                "width": 70,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {
                    "align": "center"
                }
            },
            {
                "id": "profiling_data_status",
                "name": "性能分析",
                "sortable": false,
                "disabled": false,
                "checked": true,
                "type": "data_status",
                "width": 80,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": true,
                "props": {
                    "align": "center"
                }
            },
            {
                "id": "operation",
                "name": "操作",
                "sortable": false,
                "disabled": true,
                "checked": true,
                "type": "link_list",
                "width": 80,
                "min_width": null,
                "filterable": false,
                "filter_list": [],
                "actionId": null,
                "asyncable": false,
                "props": {}
            }
        ],
        "total": 7,
        "data": [
            {
                "app_name": "trpc-cluster-access-demo",
                "collect": {
                    "is_collect": false,
                    "api": "apm_metric.collectService",
                    "params": {
                        "service_name": "bkm.web",
                        "app_name": "trpc-cluster-access-demo"
                    }
                },
                "service_name": {
                    "target": "self",
                    "value": "bkm.web",
                    "url": "/service/?filter-service_name=bkm.web&filter-app_name=trpc-cluster-access-demo",
                    "key": "",
                    "icon": "xxx",
                    "syncTime": true
                },
                "type": "远程调用",
                "language": "go",
                "operation": [
                    {
                        "target": "self",
                        "value": "配置",
                        "url": "/service-config?app_name=trpc-cluster-access-demo&service_name=bkm.web",
                        "key": "",
                        "icon": ""
                    }
                ],
                "category": "rpc",
                "kind": "service",
                "labels": [],
                "metric_data_status": {
                    "icon": "normal"
                },
                "log_data_status": {
                    "icon": "normal"
                },
                "trace_data_status": {
                    "icon": "normal"
                },
                "profiling_data_status": {
                    "icon": "no_data"
                },
                "request_count": {
                    "datapoints": null,
                    "unit": null
                },
                "error_rate": {
                    "datapoints": null,
                    "unit": "percentunit"
                },
                "avg_duration": {
                    "datapoints": null,
                    "unit": "ns"
                }
            }
        ],
        "filter": [
            {
                "id": "category",
                "name": "分类",
                "data": [
                    {
                        "id": "http",
                        "name": "网页",
                        "count": 0
                    },
                    {
                        "id": "rpc",
                        "name": "远程调用",
                        "count": 8
                    },
                    {
                        "id": "db",
                        "name": "数据库",
                        "count": 0
                    },
                    {
                        "id": "messaging",
                        "name": "消息队列",
                        "count": 0
                    },
                    {
                        "id": "async_backend",
                        "name": "后台任务",
                        "count": 0
                    },
                    {
                        "id": "other",
                        "name": "其他",
                        "count": 0
                    }
                ]
            },
            {
                "id": "language",
                "name": "语言",
                "data": [
                    {
                        "id": "go",
                        "name": "go",
                        "count": 8
                    }
                ]
            },
            {
                "id": "labels",
                "name": "自定义标签",
                "data": []
            }
        ]
    }
}
```

### 使用说明

1. **分页查询**：通过 `page` 和 `page_size` 参数控制分页，返回结果中的 `total` 字段表示总数。

2. **排序功能**：`sort` 参数支持按字段排序，字段名前加 `-` 表示降序，如 `-service_name` 表示按服务名称降序排列。

3. **筛选功能**：
    - `filter`：用于快速筛选服务分类
    - `filter_dict`：用于精确匹配筛选
    - `field_conditions`：用于多条件 OR 组合筛选，同一个 `field_conditions` 元素内的多个值为 OR 关系

4. **异步数据加载**：
    - 部分字段（如 `request_count`、`error_rate`、`avg_duration`、数据状态、策略数、告警状态）为异步加载，首次请求可能不包含这些数据，需要通过异步接口单独获取。
    - 数据状态信息可通过 `include_data_status` 参数控制是否返回数据状态信息

5. **展示模式**：
    - `page_home`：首页模式，返回的 `filter` 包含所有筛选维度
    - `page_services`：服务列表页模式，返回的 `filter` 仅包含分类筛选，部分列（如策略数、告警状态）仅在此模式下返回

6. **关键词搜索**：`keyword` 参数支持对服务名称进行模糊搜索。

7. **自定义标签**：服务可以配置自定义标签，通过 `field_conditions` 中的 `labels` 字段进行筛选。

