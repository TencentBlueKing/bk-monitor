# Query String 语法参考

本文档描述日志查询的 query_string 语法规则和转换示例。

## 基础语法

### 关键字搜索

直接输入关键字，在所有字段中搜索：

```
exception
error
timeout
```

### 字段搜索

指定字段名和值：

```
level:ERROR
status:500
path:/api/users
```

### 短语搜索

使用双引号匹配完整短语：

```
"connection refused"
log:"trace_id=abc123"
message:"user login failed"
```

### 通配符

- `*` 匹配零个或多个字符
- `?` 匹配单个字符

```
path:*api*
host:web-server-?
filename:app*.log
```

## 逻辑运算符

### AND

同时满足多个条件时必须显式使用 `AND`：

```
level:ERROR AND status:500
```

禁止使用 `level:ERROR status:500` 这类空格拼接。真实环境已验证空格不能可靠等价于 `AND`，可能扩大查询范围。

### OR

满足任一条件：

```
level:ERROR OR level:WARN
status:(500 OR 502 OR 503)
```

### NOT

排除某个条件：

```
NOT level:DEBUG
level:ERROR AND NOT path:*health*
```

### 括号分组

控制优先级：

```
(level:ERROR OR level:WARN) AND path:*api*
status:500 AND (path:/api/* OR path:/rpc/*)
```

## 范围查询

### 数值范围

```
status:[400 TO 499]     # 包含边界
status:{400 TO 500}     # 不包含边界
response_time:>1000     # 大于
response_time:>=1000    # 大于等于
response_time:<100      # 小于
```

### 时间范围

```
@timestamp:[${START_TIME_ISO} TO ${END_TIME_ISO}]
```

## 特殊查询

### 字段存在性

```
_exists_:trace_id       # trace_id 字段存在
NOT _exists_:error_msg  # error_msg 字段不存在
```

### 正则表达式

使用 `/pattern/` 语法：

```
path:/\/api\/v[0-9]+\/.*/
message:/error.*timeout/
```

### 转义特殊字符

以下字符需要转义：`+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /`

```
path:\/api\/users        # 转义斜杠
message:error\:timeout   # 转义冒号
```

## 自然语言转换示例

| 用户表达 | query_string |
| --- | --- |
| 查询 ERROR 日志 | `level:ERROR` |
| 查询 ERROR 或 WARN 日志 | `level:ERROR OR level:WARN` |
| 查询包含 exception 的日志 | `exception` |
| 查询状态码 5xx 的日志 | `status:[500 TO 599]` |
| 查询路径包含 api 的日志 | `path:*api*` |
| 查询 ERROR 但排除健康检查 | `level:ERROR AND NOT path:*health*` |
| 查询响应时间超过 1 秒的 | `response_time:>1000` |
| 查询某个 trace_id | `trace_id:"abc123def456"` |
| 查询登录失败的日志 | `"login failed"` 或 `message:*login*failed*` |
| 查询某个 IP 的日志 | `client_ip:<host-ip>` |
| 查询某个用户的操作 | `user_id:<user-id>` |
| 查询数据库连接错误 | `"database connection" AND error` |
| 查询超时错误 | `timeout OR "timed out"` |

## 复杂查询示例

### 查询生产环境的 API 错误

```
env:production AND level:ERROR AND path:/api/*
```

### 查询特定服务的慢请求

```
service:order-service AND response_time:>2000
```

### 查询异常堆栈

```
"Exception" AND ("NullPointerException" OR "IndexOutOfBoundsException")
```

### 查询特定时间段的登录失败

```
action:login AND status:failed
```

### 排除噪音日志

```
level:ERROR AND NOT (path:*health* OR path:*metrics* OR message:*heartbeat*)
```

## 字段名映射

不同索引集的字段名可能不同，查询前应先调用 `get_index_set_fields` 或 `get_scene_log_fields` 确认：

| 常见语义 | 可能的字段名 |
| --- | --- |
| 日志内容 | `log`, `message`, `msg`, `content` |
| 日志级别 | `level`, `log_level`, `severity` |
| 时间戳 | `@timestamp`, `time`, `dtEventTimeStamp` |
| 服务名 | `service`, `service_name`, `app` |
| 主机 | `host`, `hostname`, `ip`, `serverIp` |
| 路径 | `path`, `url`, `uri`, `request_path` |
| 状态码 | `status`, `status_code`, `http_status` |
| 追踪 ID | `trace_id`, `traceId`, `request_id` |

K8s、Host和自定义应用等场景的路由维度与内容字段也必须来自实时场景 schema。例如某些 K8s 场景中，`cluster_id` 用于 `table_id_conditions`，命名空间使用内容字段 `__ext.io_kubernetes_pod_namespace` 放入 `query_string`；不得固定假设 `namespace` 是动态路由维度。

## 场景模式注意事项

IaaS 场景模式（`target_type=scene`）不支持 `conditions` 参数，所有过滤条件需在 `query_string` 中表达：

```
# 索引集模式可用 conditions
conditions: {
  "field_list": [{"field_name": "level", "op": "eq", "value": ["ERROR"]}]
}

# 场景模式需转为 query_string
query_string: "level:ERROR"
```

## 聚类下钻

从日志聚类模式下钻到原始日志时，使用 `__dist_{pattern_level}` 字段：

```
# pattern_level=05 时
conditions: {
  "field_list": [
    {"field_name": "__dist_05", "op": "eq", "value": ["返回的signature"]}
  ]
}
```
