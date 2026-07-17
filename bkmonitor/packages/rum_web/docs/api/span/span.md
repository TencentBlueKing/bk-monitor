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

| 参数名称                               | 类型               | 描述       |
|------------------------------------|------------------|----------|
| name                               | String           | 名称       |
| alias                              | String           | 别名       |
| type                               | String           | 类型       |
| is_searched                        | Boolean          | 是否支持搜索   |
| is_dimensions                      | Boolean          | 是否支持维度统计 |
| can_displayed                      | Boolean          | 是否支持展示   |
| supported_operations               | Array[Operation] | 支持的操作符   |
| group_name                         | String           | 分组名称     |

- Operation

| 参数名称        | 类型     | 描述  |
|-------------|--------|-----|
| operator    | String | 操作符 |
| label       | String | 标签  |
| placeholder | String | 占位符 |

- groups

| 参数名称        | 类型     | 描述   |
|-------------|--------|------|
| name        | String | 分组名称 |

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

| 参数名称               | 类型            | 描述               |
|--------------------|---------------|------------------|
| bk_biz_id          | Integer       | 业务 ID            |
| app_name           | String        | 应用名称             |
| filters            | Array[Filter] | 过滤条件             |
| start_time         | Integer       | 开始时间             |
| end_time           | Integer       | 结束时间             |
| query              | String        | 语句模式的querystring |
| sort               | Array[String] | 排序方式             |
| limit              | Integer       | 每页条数             |
| offset             | Integer       | 分页偏移             |

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

```json
{
  "total": 0,
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

## 3 list_flatten_views - 字段平铺的 View 列表

POST /rum/rum_api/rum_query/list_flatten_views/

### 3.1 Request

| 参数名称               | 类型            | 描述               |
|--------------------|---------------|------------------|
| bk_biz_id          | Integer       | 业务 ID            |
| app_name           | String        | 应用名称             |
| filters            | Array[Filter] | 过滤条件             |
| start_time         | Integer       | 开始时间             |
| end_time           | Integer       | 结束时间             |
| query              | String        | 语句模式的querystring |
| sort               | Array[String] | 排序方式             |
| limit              | Integer       | 每页条数             |
| offset             | Integer       | 分页偏移             |

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
      "key": "loading_type",
      "operator": "equal",
      "value": [
        "route_change"
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

### 3.2 Response

```json
{
  "total": 0,
  "data": [
    {
      "id": "fa6a7310-8cfe-4a9a-99c3-9564516fc616",
      "url": "https://127.0.0.1/otelfrontenddemo/#trending",
      "url_path_group": "/otelfrontenddemo/",
      "start_time": 1783338029588300,
      "end_time": 1783338029588400,
      "duration": 100,
      "referrer": "",
      "loading_type": "route_change",
      "navigation_type": "reload",
      "vital.fcp": 140,
      "vital.lcp": 140,
      "vital.cls": 0.04,
      "vital.inp": 140,
      "vital.ttfb": 140,
      "request_count": 10,
      "error_count": 10,
      "resource_count": 5,
      "action_count": 8,
      "session_id": "e396a98a-4387-4461-ba32-cc1d807b2259",
      "user.id": "xiaoming",
      "app_name": "",
      "env": "",
      "release_version": "1.1",
      "device_type": "",
      "browser_name": "Chrome 89",
      "browser_version": "114.1",
      "os_name": "windows 11",
      "geo.country": "中国",
      "geo.city": "广东",
      "network.effective_type": ""
    }
  ],
  "type": "pre_calculation"
}
```

## 4 list_flatten_sessions - 字段平铺的 Session 列表

POST /rum/rum_api/rum_query/list_flatten_sessions/

### 4.1 Request

| 参数名称               | 类型            | 描述               |
|--------------------|---------------|------------------|
| bk_biz_id          | Integer       | 业务 ID            |
| app_name           | String        | 应用名称             |
| filters            | Array[Filter] | 过滤条件             |
| start_time         | Integer       | 开始时间             |
| end_time           | Integer       | 结束时间             |
| query              | String        | 语句模式的querystring |
| sort               | Array[String] | 排序方式             |
| limit              | Integer       | 每页条数             |
| offset             | Integer       | 分页偏移             |

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
      "key": "attributes.trpc.namespace",
      "operator": "equal",
      "value": [
        "Development"
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

### 4.2 Response

```json
{
  "total": 0,
  "data": [
    {
      "session_id": "session-1783492607893-5d7a11b3ef8368",
      "user.id": "xiaoming",
      "start_time": 1783493852767599,
      "end_time": 1783493852821299,
      "duration": 100,
      "is_active": false,
      "has_replay": false,
      "entry_view": "https://127.0.0.1/otelfrontenddemo/#trending",
      "exit_view": "https://127.0.0.1/otelfrontenddemo/#trending",
      "view_count": 10,
      "trace_count": 10,
      "error_count": 5,
      "action_count": 6,
      "request_count": 7,
      "bounced": false,
      "app_name": "rum-demo",
      "env": "production",
      "release_version": "1.1.1",
      "device_type": "desktop",
      "browser_name": "Chrome 89",
      "browser_version": "114.1",
      "os_name": "Linux",
      "synthetic_type": "",
      "geo.country": "中国",
      "geo.city": "广东",
      "network.effective_type": ""
    }
  ],
  "type": "pre_calculation"
}
```

## 5 span_detail - Span 数据详情

POST /rum/rum_api/rum_query/span_detail/

### 5.1 Request

```json
{
    "bk_biz_id": 2,
    "app_name": "rum-demo",
    "span_id": "48c032307a517658"
}
```

### 5.2 Response

```json
{
    "rum_tree": {
        "spans": [
            {
                "id": "3e2ea0cf24104297",
                "app_name": "rum-demo",
                "traceID": "145eecb04f9d0ea9ddd2a23d5894cebd",
                "spanID": "3e2ea0cf24104297",
                "duration": 23071,
                "flags": 0,
                "color": "#96C989",
                "logs": [
                    {
                        "timestamp": 1784172549564571,
                        "fields": [
                            {
                                "key": "helloworld.kind",
                                "value": 2,
                                "type": "string",
                                "query_key": "events.attributes.helloworld.kind",
                                "query_value": 2
                            },
                            {
                                "key": "helloworld.step",
                                "value": "traces_span_event_demo",
                                "type": "string",
                                "query_key": "events.attributes.helloworld.step",
                                "query_value": "traces_span_event_demo"
                            },
                            {
                                "key": "message",
                                "value": "Before do_something",
                                "type": "string",
                                "query_key": "events.name.message",
                                "query_value": "Before do_something"
                            }
                        ]
                    },
                    {
                        "timestamp": 1784172549587605,
                        "fields": [
                            {
                                "key": "helloworld.kind",
                                "value": 2,
                                "type": "string",
                                "query_key": "events.attributes.helloworld.kind",
                                "query_value": 2
                            },
                            {
                                "key": "helloworld.step",
                                "value": "traces_span_event_demo",
                                "type": "string",
                                "query_key": "events.attributes.helloworld.step",
                                "query_value": "traces_span_event_demo"
                            },
                            {
                                "key": "message",
                                "value": "After do_something",
                                "type": "string",
                                "query_key": "events.name.message",
                                "query_value": "After do_something"
                            }
                        ]
                    }
                ],
                "operationName": "span_event_demo/do_something",
                "service_name": "srv_test_one_01",
                "startTime": 1784172549564548,
                "kind": 1,
                "tags": [
                    {
                        "key": "span.kind",
                        "value": "internal",
                        "type": "string"
                    }
                ],
                "error": false,
                "message": "",
                "attributes": [
                    {
                        "type": "string",
                        "key": "apdex_type",
                        "value": "satisfied",
                        "query_key": "attributes.apdex_type",
                        "query_value": "satisfied"
                    },
                    {
                        "type": "string",
                        "key": "span.kind",
                        "value": "1(内部(internal))",
                        "query_key": "kind",
                        "query_value": 1
                    },
                    {
                        "type": "string",
                        "key": "span.trace_state",
                        "value": "map[]",
                        "query_key": "trace_state",
                        "query_value": "map[]"
                    },
                    {
                        "type": "string",
                        "key": "span.status_code",
                        "value": "0(UNSET)",
                        "query_key": "status.code",
                        "query_value": 0
                    },
                    {
                        "type": "string",
                        "key": "span.status_message",
                        "value": "",
                        "query_key": "status.message",
                        "query_value": ""
                    }
                ],
                "resource": [
                    {
                        "type": "string",
                        "key": "bk.instance.id",
                        "value": "python:srv_test_one_01:::",
                        "query_key": "resource.bk.instance.id",
                        "query_value": "python:srv_test_one_01:::"
                    },
                    {
                        "type": "string",
                        "key": "host.name",
                        "value": "VM-117-185-tencentos",
                        "query_key": "resource.host.name",
                        "query_value": "VM-117-185-tencentos"
                    },
                    {
                        "type": "string",
                        "key": "os.type",
                        "value": "linux",
                        "query_key": "resource.os.type",
                        "query_value": "linux"
                    },
                    {
                        "type": "string",
                        "key": "os.version",
                        "value": "6.6.47-12.tl4.x86_64",
                        "query_key": "resource.os.version",
                        "query_value": "6.6.47-12.tl4.x86_64"
                    },
                    {
                        "type": "string",
                        "key": "process.command",
                        "value": "/app/main.py",
                        "query_key": "resource.process.command",
                        "query_value": "/app/main.py"
                    },
                    {
                        "type": "string",
                        "key": "process.command_args",
                        "value": [
                            "/app/main.py"
                        ],
                        "query_key": "resource.process.command_args",
                        "query_value": [
                            "/app/main.py"
                        ]
                    },
                    {
                        "type": "string",
                        "key": "process.command_line",
                        "value": "/app/main.py",
                        "query_key": "resource.process.command_line",
                        "query_value": "/app/main.py"
                    },
                    {
                        "type": "string",
                        "key": "process.executable.name",
                        "value": "/.venv/bin/python",
                        "query_key": "resource.process.executable.name",
                        "query_value": "/.venv/bin/python"
                    },
                    {
                        "type": "string",
                        "key": "process.executable.path",
                        "value": "/.venv/bin",
                        "query_key": "resource.process.executable.path",
                        "query_value": "/.venv/bin"
                    },
                    {
                        "type": "string",
                        "key": "process.parent_pid",
                        "value": 0,
                        "query_key": "resource.process.parent_pid",
                        "query_value": 0
                    },
                    {
                        "type": "string",
                        "key": "process.pid",
                        "value": 1,
                        "query_key": "resource.process.pid",
                        "query_value": 1
                    },
                    {
                        "type": "string",
                        "key": "process.runtime.description",
                        "value": "3.11.14 (main, Jan 13 2026, 03:12:14) [GCC 14.2.0]",
                        "query_key": "resource.process.runtime.description",
                        "query_value": "3.11.14 (main, Jan 13 2026, 03:12:14) [GCC 14.2.0]"
                    },
                    {
                        "type": "string",
                        "key": "process.runtime.name",
                        "value": "cpython",
                        "query_key": "resource.process.runtime.name",
                        "query_value": "cpython"
                    },
                    {
                        "type": "string",
                        "key": "process.runtime.version",
                        "value": "3.11.14",
                        "query_key": "resource.process.runtime.version",
                        "query_value": "3.11.14"
                    },
                    {
                        "type": "string",
                        "key": "service.name",
                        "value": "srv_test_one_01",
                        "query_key": "resource.service.name",
                        "query_value": "srv_test_one_01"
                    },
                    {
                        "type": "string",
                        "key": "telemetry.sdk.language",
                        "value": "python",
                        "query_key": "resource.telemetry.sdk.language",
                        "query_value": "python"
                    },
                    {
                        "type": "string",
                        "key": "telemetry.sdk.name",
                        "value": "opentelemetry",
                        "query_key": "resource.telemetry.sdk.name",
                        "query_value": "opentelemetry"
                    },
                    {
                        "type": "string",
                        "key": "telemetry.sdk.version",
                        "value": "1.40.0",
                        "query_key": "resource.telemetry.sdk.version",
                        "query_value": "1.40.0"
                    }
                ],
                "events": [
                    {
                        "name": "Before do_something",
                        "timestamp": 1784172549564571,
                        "duration": 23,
                        "attributes": [
                            {
                                "type": "string",
                                "key": "helloworld.kind",
                                "value": 2,
                                "query_key": "events.attributes.helloworld.kind",
                                "query_value": 2
                            },
                            {
                                "type": "string",
                                "key": "helloworld.step",
                                "value": "traces_span_event_demo",
                                "query_key": "events.attributes.helloworld.step",
                                "query_value": "traces_span_event_demo"
                            }
                        ]
                    },
                    {
                        "name": "After do_something",
                        "timestamp": 1784172549587605,
                        "duration": 23057,
                        "attributes": [
                            {
                                "type": "string",
                                "key": "helloworld.kind",
                                "value": 2,
                                "query_key": "events.attributes.helloworld.kind",
                                "query_value": 2
                            },
                            {
                                "type": "string",
                                "key": "helloworld.step",
                                "value": "traces_span_event_demo",
                                "query_key": "events.attributes.helloworld.step",
                                "query_value": "traces_span_event_demo"
                            }
                        ]
                    }
                ],
                "icon": "http://bkmonitor.bkop.woa.com/static/monitor/img/apm/other.svg",
                "processID": "p1"
            }
        ],
        "processes": {
            "p1": {
                "serviceName": "srv_test_one_01",
                "tags": [
                    {
                        "key": "bk.instance.id",
                        "value": "python:srv_test_one_01:::",
                        "type": "string",
                        "query_key": "resource.bk.instance.id",
                        "query_value": "python:srv_test_one_01:::"
                    },
                    {
                        "key": "host.name",
                        "value": "VM-117-185-tencentos",
                        "type": "string",
                        "query_key": "resource.host.name",
                        "query_value": "VM-117-185-tencentos"
                    },
                    {
                        "key": "os.type",
                        "value": "linux",
                        "type": "string",
                        "query_key": "resource.os.type",
                        "query_value": "linux"
                    },
                    {
                        "key": "os.version",
                        "value": "6.6.47-12.tl4.x86_64",
                        "type": "string",
                        "query_key": "resource.os.version",
                        "query_value": "6.6.47-12.tl4.x86_64"
                    },
                    {
                        "key": "process.command",
                        "value": "/app/main.py",
                        "type": "string",
                        "query_key": "resource.process.command",
                        "query_value": "/app/main.py"
                    },
                    {
                        "key": "process.command_args",
                        "value": [
                            "/app/main.py"
                        ],
                        "type": "string",
                        "query_key": "resource.process.command_args",
                        "query_value": [
                            "/app/main.py"
                        ]
                    },
                    {
                        "key": "process.command_line",
                        "value": "/app/main.py",
                        "type": "string",
                        "query_key": "resource.process.command_line",
                        "query_value": "/app/main.py"
                    },
                    {
                        "key": "process.executable.name",
                        "value": "/.venv/bin/python",
                        "type": "string",
                        "query_key": "resource.process.executable.name",
                        "query_value": "/.venv/bin/python"
                    },
                    {
                        "key": "process.executable.path",
                        "value": "/.venv/bin",
                        "type": "string",
                        "query_key": "resource.process.executable.path",
                        "query_value": "/.venv/bin"
                    },
                    {
                        "key": "process.parent_pid",
                        "value": 0,
                        "type": "string",
                        "query_key": "resource.process.parent_pid",
                        "query_value": 0
                    },
                    {
                        "key": "process.pid",
                        "value": 1,
                        "type": "string",
                        "query_key": "resource.process.pid",
                        "query_value": 1
                    },
                    {
                        "key": "process.runtime.description",
                        "value": "3.11.14 (main, Jan 13 2026, 03:12:14) [GCC 14.2.0]",
                        "type": "string",
                        "query_key": "resource.process.runtime.description",
                        "query_value": "3.11.14 (main, Jan 13 2026, 03:12:14) [GCC 14.2.0]"
                    },
                    {
                        "key": "process.runtime.name",
                        "value": "cpython",
                        "type": "string",
                        "query_key": "resource.process.runtime.name",
                        "query_value": "cpython"
                    },
                    {
                        "key": "process.runtime.version",
                        "value": "3.11.14",
                        "type": "string",
                        "query_key": "resource.process.runtime.version",
                        "query_value": "3.11.14"
                    },
                    {
                        "key": "service.name",
                        "value": "srv_test_one_01",
                        "type": "string",
                        "query_key": "resource.service.name",
                        "query_value": "srv_test_one_01"
                    },
                    {
                        "key": "telemetry.sdk.language",
                        "value": "python",
                        "type": "string",
                        "query_key": "resource.telemetry.sdk.language",
                        "query_value": "python"
                    },
                    {
                        "key": "telemetry.sdk.name",
                        "value": "opentelemetry",
                        "type": "string",
                        "query_key": "resource.telemetry.sdk.name",
                        "query_value": "opentelemetry"
                    },
                    {
                        "key": "telemetry.sdk.version",
                        "value": "1.40.0",
                        "type": "string",
                        "query_key": "resource.telemetry.sdk.version",
                        "query_value": "1.40.0"
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

## 6 view_detail - View 数据详情

POST /rum/rum_api/rum_query/view_detail/

### 6.1 Request

```json
{
    "bk_biz_id": 2,
    "app_name": "rum-demo",
    "view_id": "fa6a7310-8cfe-4a9a-99c3-9564516fc616"
}
```

### 6.2 Response

Tips：
- `span_classify` 对比 apm 新增加了 `filter_operator` 字段，供 `仅慢节点` 使用
- `rum_tree` 对比 apm 的 `trace_tree` 去除了 `processes` 字段，感觉没有用途
- `rum_tree` -> `spans` 缺少 SDK 版本字段
```json
{
  "id": "view-1783493293590-804a03375b189",
  "original_data": [],
  "span_classify": [{
    "name": "LCP 关键路径",
    "filter_key": "is_critical_path",
    "filter_operator": "=", 
    "filter_value": true,
    "count": 6,
    "icon": "mc-time"
  }],
  "rum_tree": {
    "spans": [{
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
      "attributes": [{
        "type": "string",
        "key": "lcp.element_url",
        "value": "/static/img/hero.jpg",
        "query_key": "attributes.lcp.element_url",
        "query_value": "/static/img/hero.jpg"
      }]
    }]
  },
  "rum_info": {
    "start_time": 1784269780001041,
    "end_time": 1784269780001326,
    "duration": 100,
    "span_count": 10,
    "error_count": 2,
    "longtask_count": 4,
    "app_name": "rum-demo",
    "release_version": "1.2.0",
    "env": "prod",
    "view.url": "/order/submit",
    "referrer": "/order/list",
    "loading_type": "route_change",
    "session_id": "session-1783492607893-5d7a11b3ef8368",
    "user_id": "xiaoming",
    "root_span_id": "f3318599c774e21e"
  }
}
```

## 7 session_detail - Session 数据详情

POST /rum/rum_api/rum_query/session_detail/

### 7.1 Request

```json
{
    "bk_biz_id": 2,
    "app_name": "rum-demo",
    "session_id": "fa6a7310-8cfe-4a9a-99c3-9564516fc616"
}
```

### 7.2 Response

- 同 `view_detail` 接口返回一致

```json
{}
```

## 8 span_link_context - Span 链路上下文（document、http、longtask、action、error）

POST /rum/rum_api/rum_query/span_link_context/

### 8.1 Request

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "span_id": "48c032307a517658",
  "interval": 5
}
```

### 8.2 Response

- `span` 数据结构直接复用 `view_detail`

```json
{
  "span_trees": [],
  "adjacent_timeline_spans": []
}
```

## 9 span_biz_impact - Span 业务影响（error、http）

POST /rum/rum_api/rum_query/span_biz_impact/

### 9.1 Request

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "span_id": "48c032307a517658"
}
```

### 9.2 Response

```json
{
  "affected_stat": {
    "user_count": 100,
    "session_count": 50
  },
  "version_relation": {
    "first": "1.2.1",
    "current": "1.2.2"
  }
}
```

## 10 rum_charts - 获取 rum 的图表

GET /rum/rum_api/rum_query/rum_charts/

场景：span 详情业务影响 Tab

### 10.1 Request

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "space_uid": "bkcc__2"
}
```

### 10.2 Response

- 复制 APM 的数据结构，仅供参考

```json
[{
  "title": "耗时",
  "gridPos": {
    "x": 16,
    "y": 16,
    "w": 8,
    "h": 4
  },
  "options": {
    "rum_time_series": {
      "unit": "ms"
    }
  },
  "id": 3,
  "type": "rum-history-stat",
  "targets": [
    {
      "data_type": "time_series",
      "api": "apm_metric.dynamicUnifyQuery",
      "datasource": "time_series",
      "alias": "P95",
      "data": {
        "app_name": "rum-demo",
        "expression": "a",
        "query_configs": [
          {
            "display": true,
            "interval_unit": "s",
            "data_label": "",
            "data_type_label": "time_series",
            "data_source_label": "custom",
            "table": "2_bkapm_metric_trpc-cluster-access-demo.__default__",
            "time_field": "time",
            "where": [],
            "metrics": [
              {
                "field": "rum-metrics-name",
                "alias": "a",
                "method": "SUM"
              }
            ],
            "functions": [
              {
                "id": "rate",
                "params": [
                  {
                    "id": "window",
                    "value": "120s"
                  }
                ]
              },
              {
                "id": "histogram_quantile",
                "params": [
                  {
                    "id": "scalar",
                    "value": 0.95
                  }
                ]
              }
            ],
            "group_by": [
              "le"
            ]
          }
        ],
        "unify_query_param": {
          "expression": "a",
          "query_configs": [
            {
              "display": true,
              "interval_unit": "s",
              "data_label": "",
              "data_type_label": "time_series",
              "data_source_label": "custom",
              "table": "rum_metric.__default__",
              "time_field": "time",
              "where": [],
              "metrics": [
                {
                  "field": "rum_bucket",
                  "alias": "a",
                  "method": "SUM"
                }
              ],
              "functions": [
                {
                  "id": "rate",
                  "params": [
                    {
                      "id": "window",
                      "value": "120s"
                    }
                  ]
                },
                {
                  "id": "histogram_quantile",
                  "params": [
                    {
                      "id": "scalar",
                      "value": 0.95
                    }
                  ]
                }
              ],
              "group_by": [
                "le"
              ]
            }
          ]
        },
        "fill_bar": true,
        "unit": "ns"
      }
    }
  ]
}]
```



