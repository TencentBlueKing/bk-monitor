# RUM Span 接口协议

## 1 view_config - 页面视图配置

GET /rum/rum_api/rum_query/view_config/?app_name=rum-demo&bk_biz_id=2

### 1.1 Request

| 参数名称      | 类型      | 描述    |
|-----------|---------|-------|
| bk_biz_id | Integer | 业务 ID |
| app_name  | String  | 应用名称  |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo"
}
```

### 1.2 Response

- fields

| 参数名称                 | 类型               | 描述                       |
|----------------------|------------------|--------------------------|
| name                 | String           | 名称                       |
| alias                | String           | 别名                       |
| type                 | String           | 类型                       |
| is_searched          | Boolean          | 是否支持搜索                   |
| is_dimensions        | Boolean          | 是否支持维度统计                 |
| can_displayed        | Boolean          | 是否支持展示                   |
| supported_operations | Array[Operation] | 支持的操作符                   |
| group_name           | String           | 分组名称，和 groups.name 是关联关系 |

- Operation

| 参数名称        | 类型     | 描述  |
|-------------|--------|-----|
| operator    | String | 操作符 |
| label       | String | 标签  |
| placeholder | String | 占位符 |

- groups

| 参数名称 | 类型     | 描述   |
|------|--------|------|
| name | String | 分组名称 |

```json
{
  "span_config": {
    "fields": [
      {
        "name": "trace_id",
        "alias": "Trace ID",
        "type": "keyword",
        "is_searched": true,
        "is_dimensions": false,
        "can_displayed": true,
        "supported_operations": [
          {
            "operator": "equal",
            "label": "=",
            "placeholder": "请选择或直接输入，Enter分隔"
          }
        ],
        "group_name": "OT 标识"
      }
    ],
    "groups": [
      {
        "name": "OT 标识"
      }
    ]
  },
  "view_config": {},
  "session_config": {}
}
```

## 2 list_flatten_spans - 字段平铺的 Span 列表

POST /rum/rum_api/rum_query/list_flatten_spans/

### 2.1 Request

| 参数名称       | 类型            | 描述               |
|------------|---------------|------------------|
| bk_biz_id  | Integer       | 业务 ID            |
| app_name   | String        | 应用名称             |
| filters    | Array[Filter] | 过滤条件             |
| start_time | Integer       | 开始时间             |
| end_time   | Integer       | 结束时间             |
| query      | String        | 语句模式的querystring |
| sort       | Array[String] | 排序方式             |
| limit      | Integer       | 每页条数             |
| offset     | Integer       | 分页偏移             |

- Filter

| 参数名称     | 类型            | 描述    |
|----------|---------------|-------|
| key      | String        | 键名    |
| operator | String        | 操作符   |
| value    | Array[String] | 选择值列表 |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "filters": [
    {
      "key": "attributes.result",
      "operator": "equal",
      "value": [
        "success"
      ]
    }
  ],
  "start_time": 1783920405,
  "end_time": 1783924005,
  "query": "",
  "sort": [
    "-start_time"
  ],
  "limit": 30,
  "offset": 0
}
```

### 2.2 Response

| 参数名称                                       | 类型           | 描述                                                                                                                                                                                  |
|--------------------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| app_name                                   | String       | 应用名称                                                                                                                                                                                |
| bk_biz_id                                  | String       | 业务 ID                                                                                                                                                                               |
| elapsed_time                               | Integer      | 耗时（微秒）                                                                                                                                                                              |
| end_time                                   | Integer      | Span 结束时间戳（微秒）                                                                                                                                                                      |
| events                                     | Array[Event] | 事件列表                                                                                                                                                                                |
| kind                                       | Integer      | 枚举值：<br/>- 未定义：0<br/>- 内部调用：1<br/>- 同步被调：2<br/>- 同步主调：3<br/>- 异步主调：4<br/>- 异步被调：5                                                                                                   |
| links                                      | Array[Link]  | 关联链接                                                                                                                                                                                |
| parent_span_id                             | String       | 父 Span ID                                                                                                                                                                           |
| span_id                                    | String       | Span ID                                                                                                                                                                             |
| span_name                                  | String       | Span 名称                                                                                                                                                                             |
| start_time                                 | Integer      | Span 开始时间戳（微秒）                                                                                                                                                                      |
| time                                       | String       | 采集时间戳                                                                                                                                                                               |
| trace_id                                   | String       | Trace ID                                                                                                                                                                            |
| trace_state                                | String       | Trace 状态标识                                                                                                                                                                          |
| attributes.action.id                       | String       | 操作 ID                                                                                                                                                                               |
| attributes.browser.screen.height           | Integer      | 浏览器屏幕高度                                                                                                                                                                             |
| attributes.browser.screen.width            | Integer      | 浏览器屏幕宽度                                                                                                                                                                             |
| attributes.browser.viewport.height         | Integer      | 浏览器视口高度                                                                                                                                                                             |
| attributes.browser.viewport.width          | Integer      | 浏览器视口宽度                                                                                                                                                                             |
| attributes.device.id                       | String       | 设备 ID                                                                                                                                                                               |
| attributes.network.effective_type          | String       | 网络有效类型                                                                                                                                                                              |
| attributes.network.status                  | String       | 网络状态                                                                                                                                                                                |
| attributes.outcome.type                    | String       | 结果类型                                                                                                                                                                                |
| attributes.resource.render_blocking_status | String       | 资源渲染阻塞状态                                                                                                                                                                            |
| attributes.resource.type                   | String       | 资源类型                                                                                                                                                                                |
| attributes.server.address                  | String       | 服务端地址                                                                                                                                                                               |
| attributes.session.has_replay              | Boolean      | 是否有会话回放                                                                                                                                                                             |
| attributes.session.id                      | String       | 会话 ID                                                                                                                                                                               |
| attributes.session.type                    | String       | 会话类型                                                                                                                                                                                |
| attributes.span_type                       | String       | Span 类型，枚举值：<br/>- 文档加载：document<br/>- 路由切换：route<br/>- 静态资源：resource<br/>- HTTP / API：http<br/>- 长任务：longtask<br/>- 用户交互：action<br/>- Web 指标：vital<br/>- 错误：error<br/>- 自定义：custom |
| attributes.url.full                        | String       | 完整 URL                                                                                                                                                                              |
| attributes.view.id                         | String       | 页面视图 ID                                                                                                                                                                             |
| attributes.view.loading_type               | String       | 页面加载类型                                                                                                                                                                              |
| attributes.view.url                        | String       | 页面 URL                                                                                                                                                                              |
| attributes.view.url_template               | String       | 页面 URL 模板                                                                                                                                                                           |
| resource.deployment.environment.name       | String       | 部署环境名称                                                                                                                                                                              |
| resource.device.type                       | String       | 设备类型                                                                                                                                                                                |
| resource.service.name                      | String       | 服务名称                                                                                                                                                                                |
| resource.service.version                   | String       | 服务版本                                                                                                                                                                                |
| resource.session.sample_rate               | Integer      | 会话采样率                                                                                                                                                                               |
| resource.telemetry.sdk.language            | String       | SDK 语言                                                                                                                                                                              |
| resource.telemetry.sdk.name                | String       | SDK 名称                                                                                                                                                                              |
| resource.telemetry.sdk.version             | String       | SDK 版本                                                                                                                                                                              |
| resource.user_agent.name                   | String       | 用户代理名称（浏览器）                                                                                                                                                                         |
| resource.user_agent.os.name                | String       | 用户代理操作系统                                                                                                                                                                            |
| resource.user_agent.version                | String       | 用户代理版本                                                                                                                                                                              |
| status.code                                | Integer      | 状态码（0=OK, 1=Error, 2=Unset）                                                                                                                                                         |
| status.message                             | String       | 状态消息                                                                                                                                                                                |

```json
{
  "total": 1,
  "data": [
    {
      "app_name": "transfer",
      "attributes.browser.screen.height": 720,
      "attributes.browser.screen.width": 1280,
      "attributes.browser.viewport.height": 720,
      "attributes.browser.viewport.width": 1280,
      "attributes.browser_name": "Chrome",
      "attributes.browser_version": "148",
      "attributes.device.cpu_cores": 32,
      "attributes.device.id": "1a63fea8-2f6f-4967-8be6-d21b2977d5a3",
      "attributes.device.memory": 32,
      "attributes.device.mobile": false,
      "attributes.device.platform": "Linux",
      "attributes.device_type": "desktop",
      "attributes.duration_bucket": "500ms~2s",
      "attributes.error_type": "none",
      "attributes.event_label": "静态资源",
      "attributes.http.response.status_code": 0,
      "attributes.initiator_type": "script",
      "attributes.network.downlink": 10,
      "attributes.network.effective_type": "4g",
      "attributes.network.rtt": 0,
      "attributes.network.save_data": false,
      "attributes.next_hop_protocol": "",
      "attributes.os_name": "Linux",
      "attributes.resource.decoded_body_size": 0,
      "attributes.resource.encoded_body_size": 0,
      "attributes.result": "success",
      "attributes.rum.page.host": "127.0.0.1",
      "attributes.rum.page.path": "/otelfrontenddemo/",
      "attributes.rum.sampled": true,
      "attributes.rum_view_load_apdex_type": "tolerating",
      "attributes.session.has_replay": false,
      "attributes.session.id": "e396a98a-4387-4461-ba32-cc1d807b2259",
      "attributes.span_subtype": "script",
      "attributes.span_type": "resource",
      "attributes.status_class": "0xx",
      "attributes.target_domain": "unpkg.com",
      "attributes.target_label": "unpkg.com/@blueking/open-telemetry/dist/bk-rum.global.js",
      "attributes.target_path_template": "/@blueking/open-telemetry/dist/bk-rum.global.js",
      "attributes.target_value": 0,
      "attributes.transfer_size": 0,
      "attributes.url.full": "https://unpkg.com/@blueking/open-telemetry/dist/bk-rum.global.js",
      "attributes.user.id": "user-001",
      "attributes.user_agent.name": "Chrome",
      "attributes.user_agent.os.name": "Linux",
      "attributes.user_agent.version": "148",
      "attributes.view.id": "fa6a7310-8cfe-4a9a-99c3-9564516fc616",
      "attributes.view.loading_type": "initial_load",
      "attributes.view.url": "https://127.0.0.1/otelfrontenddemo/#trending",
      "attributes.view.url_path_group": "/otelfrontenddemo/",
      "bk_biz_id": "2",
      "elapsed_time": 1033500,
      "end_time": 1783338029588300,
      "events": [],
      "kind": 1,
      "links": [],
      "parent_span_id": "",
      "resource.deployment.environment.name": "production",
      "resource.rum.provider": "blueking",
      "resource.service.name": "demo-app",
      "resource.service.version": "1.0.0",
      "resource.telemetry.sdk.language": "webjs",
      "span_id": "29926da51cae17cf",
      "span_name": "browser.resource",
      "start_time": 1783338028554800,
      "status.code": 0,
      "status.message": "",
      "time": "1783338037000",
      "trace_id": "206fa04fb665bf8ef1fba9255b59c3e1",
      "trace_state": "map[]"
    }
  ]
}
```

## 3 span_detail - Span 数据详情

POST /rum/rum_api/rum_query/span_detail/

### 3.1 Request

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "span_id": "48c032307a517658"
}
```

### 3.2 Response

- rum_tree.spans.processID 用来和 processes 做关联

```json
{
  "rum_tree": {
    "spans": [
      {
        "id": "f3318599c774e21e",
        "span_name": "POST /query/ts",
        "span_type": "http",
        "view_url": "/order/submit",
        "kind": 1,
        "duration": 100,
        "start_time": 1784269780001041,
        "result": "success",
        "app_name": "rum-demo",
        "release_version": "1.2.0",
        "session_id": "session-1783492607893-5d7a11b3ef8368",
        "user_id": "xiaoming",
        "end_time": 1784269780001042,
        "trace_id": "e010dae8b9759c375fa31d99d3f49101",
        "parent_span_id": "g8899599c774e21e",
        "parent_span_name": "routeChange",
        "attributes": [
          {
            "type": "string",
            "key": "lcp.element_url",
            "value": "/static/img/hero.jpg",
            "query_key": "attributes.lcp.element_url",
            "query_value": "/static/img/hero.jpg"
          }
        ],
        "processID": "p1"
      }
    ],
    "processes": {
      "p1": {
        "serviceName": "rum-service",
        "tags": [
          {
            "key": "bk.instance.id",
            "value": ":unify-query::123456789:",
            "type": "string",
            "query_key": "resource.bk.instance.id",
            "query_value": ":unify-query::123456789:"
          },
          {
            "key": "net.host.ip",
            "value": "123456789",
            "type": "string",
            "query_key": "resource.net.host.ip",
            "query_value": "123456789"
          },
          {
            "key": "service.name",
            "value": "unify-query",
            "type": "string",
            "query_key": "resource.service.name",
            "query_value": "unify-query"
          }
        ]
      }
    }
  },
  "origin_data": {
    "bk_biz_id": "2",
    "app_name": "transfer",
    "attributes": {
      "rum.page.host": "127.0.0.1"
    },
    "elapsed_time": 1033500,
    "start_time": 1783338028554800,
    "end_time": 1783338029588300,
    "events": [],
    "kind": 1,
    "links": [],
    "parent_span_id": "",
    "resource": {
      "deployment.environment.name": "production",
      "rum.provider": "blueking",
      "service.name": "demo-app",
      "service.version": "1.0.0",
      "telemetry.sdk.language": "webjs"
    },
    "span_id": "29926da51cae17cf",
    "span_name": "browser.resource",
    "status": {
      "code": 0,
      "message": ""
    },
    "time": "1783338037000",
    "trace_id": "206fa04fb665bf8ef1fba9255b59c3e1",
    "trace_state": "map[]"
  }
}
```

## 4 fields_topk - 字段 topk

POST /rum/rum_api/rum_query/fields_topk/

| 参数名称 | 类型     | 描述                                       |
|------|--------|------------------------------------------|
| mode | string | 枚举值：<br/>- span<br/>- view<br/>- session |

### 4.1 Request

```json
{
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999805,
  "end_time": 1786003405,
  "limit": 5,
  "fields": [
    "kind"
  ],
  "bk_biz_id": 2
}
```

### 4.2 Response

```json
[
  {
    "field": "kind",
    "distinct_count": 5,
    "list": [
      {
        "value": "1",
        "count": 4127148,
        "proportions": 88.504
      },
      {
        "value": "3",
        "count": 294804,
        "proportions": 6.321
      },
      {
        "value": "2",
        "count": 241082,
        "proportions": 5.169
      },
      {
        "value": "5",
        "count": 94,
        "proportions": 0.002
      },
      {
        "value": "4",
        "count": 93,
        "proportions": 0.001
      }
    ]
  }
]
```

## 5 field_statistics_info - 字段统计信息

POST /rum/rum_api/rum_query/field_statistics_info/

### 5.1 Request

```json
{
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999917,
  "end_time": 1786003517,
  "field": {
    "field_name": "span_name",
    "field_type": "keyword"
  },
  "bk_biz_id": 2
}
```

### 5.2 Response

```json
{
  "distinct_count": 544,
  "field_count": 4647434,
  "total_count": 4647434,
  "field_percent": 100
}
```

## 6 field_statistics_graph - 字段统计图表

POST /rum/rum_api/rum_query/field_statistics_graph/

### 6.1 Request

- field.values 传 topk 接口的 list[*].value 的值

```json
{
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999917,
  "end_time": 1786003517,
  "field": {
    "field_name": "span_name",
    "field_type": "keyword",
    "values": [
      "build-metadata-query",
      "check-must-query-feature-flag",
      "query-ts-to-query-metric",
      "http-api-metadata",
      "jwt-auth"
    ]
  },
  "bk_biz_id": 2
}
```

### 6.2 Response

```json
{
  "series": [
    {
      "dimensions": {
        "span_name": "build-metadata-query"
      },
      "target": "count(span_name){span_name=build-metadata-query}",
      "metric_field": "_result_",
      "datapoints": [
        [
          3498,
          1785999840000
        ]
      ],
      "alias": "_result_",
      "stat": {},
      "type": "bar",
      "dimensions_translation": {},
      "unit": ""
    }
  ],
  "metrics": []
}
```

