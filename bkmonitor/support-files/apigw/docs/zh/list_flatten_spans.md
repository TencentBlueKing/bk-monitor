### 功能描述

获取 Span 列表数据

### 请求参数

| 字段名        | 类型   | 必选 | 描述      |
|------------|------|----|---------|
| bk_biz_id  | int  | 是  | 业务 ID   |
| app_name   | str  | 是  | 应用名称    |
| start_time | int  | 是  | 查询开始时间戳 |
| end_time   | int  | 是  | 查询结束时间戳 |
| offset     | int  | 否  | 分页偏移量   |
| limit      | int  | 否  | 每页数量    |
| filters    | list | 否  | 过滤条件列表  |
| query      | str  | 否  | 查询字符串   |
| sort       | list | 否  | 排序      |

#### filters 列表元素

| 字段名      | 类型     | 描述    |
|----------|--------|-------|
| key      | str    | 查询键   |
| operator | str    | 操作符   |
| value    | list   | 查询值   |
| options  | object | 操作符选项 |

#### filters 列表元素中 options 字段

| 字段名            | 类型   | 描述                 |
|----------------|------|--------------------|
| is_wildcard    | bool | 是否使用通配符            |
| group_relation | str  | 分组关系，`OR` 或者 `AND` |

#### query 查询语法

- 操作符：
  `:`等于某一值、`:*`存在任意形式 、`>`大于某一值、 `<`小于某一值、`>=`大于或等于某一值、`<=`小于或等于某一值
- 精确匹配（支持AND、OR)：
  `author:"John Smith" AND age:20`
- 精确匹配（支持AND、OR)：
  `status:active
  title:(quick brown)`
- 字段名模糊匹配：
  `vers\*on:(quick brown)`
- 通配符匹配：
  `qu?ck bro*`
- 正则匹配：
  `name:/joh?n(ah[oa]n)/`
- 范围匹配：
  `count:[1 TO 5]`、
  `count:[1 TO 5}`、
  `count:[10 TO *]`

### 请求参数示例

```json
{
    "app_name": "app_name",
    "filters": [
        {
            "key": "elapsed_time",
            "operator": "between",
            "value": [
                "479",
                "802"
            ]
        }
    ],
    "start_time": 1755048571,
    "end_time": 1755052171,
    "query": "trace_id : 123",
    "sort": [],
    "limit": 30,
    "offset": 0,
    "bk_biz_id": 1
}
```

### 响应参数

| 字段名     | 类型     | 描述         |
|---------|--------|------------|
| result  | bool   | 请求是否成功     |
| code    | int    | 返回的状态码     |
| message | str    | 描述信息       |
| data    | object | Trace 数据对象 |

#### data 对象字段

| 字段名   | 类型   | 描述         |
|-------|------|------------|
| total | int  | 总记录数       |
| data  | list | Trace 数据列表 |

#### data 列表中的 Trace 对象字段

| 字段名            | 类型   | 描述        |
|----------------|------|-----------|
| elapsed_time   | int  | 耗时        |
| end_time       | int  | 结束时间      |
| kind           | int  | 类型        |
| links          | list | 关联信息      |
| parent_span_id | str  | 父 Span ID |
| span_id        | str  | Span ID   |
| span_name      | str  | 接口名称      |
| start_time     | int  | 开始时间      |
| time           | str  | 时间        |
| trace_id       | str  | Trace ID  |
| trace_state    | str  | Trace 状态  |
| attributes     | dict | 属性信息的顶层字段 |
| resource       | dict | 资源信息的顶层字段 |
| events         | dict | 事件信息的顶层字段 |
| status.code    | int  | 状态        |
| status.message | str  | 状态详情      |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "total": 0,
        "data": [
            {
                "elapsed_time": 3358,
                "end_time": 1755510539999456,
                "kind": 3,
                "links": [],
                "parent_span_id": "d7040ffc628fce2a",
                "span_id": "d5fce183a66d9931",
                "span_name": "trpc.bkm.user.UserService/GetUserInfo",
                "start_time": 1755510539996097,
                "time": "1755510546000",
                "trace_id": "6f6c8375b0ff70a99c1534bd164bfbfd",
                "trace_state": "",
                "attributes.baggage": "",
                "attributes.net.host.ip": "",
                "attributes.net.host.name": "bkm-cart-6dbfb8bf8f-zj6gv",
                "attributes.net.host.port": "39218",
                "attributes.net.peer.ip": "",
                "attributes.net.peer.port": "19001",
                "attributes.trpc.callee_method": "GetUserInfo",
                "attributes.trpc.callee_service": "trpc.bkm.user.UserService",
                "attributes.trpc.caller_method": "AddItem",
                "attributes.trpc.caller_service": "trpc.bkm.cart.CartService",
                "attributes.trpc.envname": "test",
                "attributes.trpc.namespace": "Development",
                "attributes.trpc.status_code": 0,
                "attributes.trpc.status_msg": "",
                "attributes.trpc.status_type": 0,
                "events.name": [
                    "SENT",
                    "RECEIVED"
                ],
                "events.timestamp": [
                    1755510539996107,
                    1755510539999370
                ],
                "resource.bk.instance.id": "go:bkm.cart:::",
                "resource.cmdb.module.id": "",
                "resource.server.owner": "",
                "resource.service.name": "bkm.cart",
                "resource.service_name": "bkm.cart",
                "resource.telemetry.sdk.language": "go",
                "resource.telemetry.sdk.name": "opentelemetry",
                "status.code": 1,
                "status.message": "",
                "events.attributes.ctx.deadline": [
                    "997.771472ms",
                    "994.508982ms"
                ],
                "events.attributes.message.detail": [
                    "{}",
                    "{\"email\":\"@test.com\",\"phones\":[{\"number\":\"123\",\"type\":1}]}"
                ],
                "events.attributes.message.uncompressed_size": [
                    2,
                    58
                ]
            }
        ]
    }
}
```