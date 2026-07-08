# RUM Span 数据协议

## 1 公共字段

### 1.1 顶层字段

| 字段               | 类型     | 描述         | 备注                                                                                |
|------------------|--------|------------|-----------------------------------------------------------------------------------|
| `app_name`       | String | 应用名称       | 应用名                                                                               |
| `attributes`     | Object | 属性集        | 包含浏览器、设备、网络、异常等各类语义标签和度量                                                          |
| `bk_biz_id`      | String | 业务 ID      | 蓝鲸业务标识                                                                            |
| `elapsed_time`   | Number | 耗时（微秒）     | Span 从 start_time 到 end_time 的时间差                                                 |
| `end_time`       | String | 结束时间戳（微秒）  | Span 结束的时间                                                                        |
| `events`         | Object | 事件序列化字符串   | JSON 数组                                                                           |
| `kind`           | Number | Span 类型    | `0`=Unspecified, `1`=Internal, `2`=Server, `3`=Client, `4`=Producer, `5`=Consumer |
| `links`          | Object | 关联 Span 列表 | JSON 数组                                                                           |
| `parent_span_id` | String | 父 Span ID  |                                                                                   |
| `resource`       | Object | 资源信息       | 产生此 Span 的服务、环境、SDK 等描述信息；详见 **4. Resource**                                      |
| `span_id`        | String | 当前 Span ID | 16 进制字符串，全链路唯一                                                                    |
| `span_name`      | String | Span 名称    | 例如 `browser.resource`、`browser.page_view` 等                                       |
| `start_time`     | String | 开始时间戳（微秒）  | 不可空                                                                               |
| `status`         | Object | Span 执行状态  | 包含 `code` 和 `message`；详见 **5. Status**                                            |
| `time`           | String | 数据上报时间戳    | ES 写入时间标记                                                                         |
| `trace_id`       | String | Trace ID   | 全链路追踪根标识                                                                          |
| `trace_state`    | String | Trace 状态   | 内部格式，例如 `map[]`                                                                   |

---

### 1.2 Attributes

#### 1.2.1 Span 公共属性

- 基础字段

| 字段                           | 类型      | 描述                 | 备注                                                                                                |
|------------------------------|---------|--------------------|---------------------------------------------------------------------------------------------------|
| `attributes.span_type`       | String  | Span 大类            | `document` / `http` / `resource` / `vital` / `error` / `longtask` / `action` / `route` / `custom` |
| `attributes.span_subtype`    | String  | Span 子类            | 例如 `xmlhttprequest`、`navigate`、`route_change`                                                     |
| `attributes.duration_bucket` | String  | 耗时分桶               | `<100ms`/`100~500ms`/`500ms~2s`/`>2s`                                                             |
| `attributes.event_label`     | String  | 中文事件标签             | 中文事件标签，如 `API 调用`/`错误`                                                                            |
| `attributes.result`          | String  | 结果                 |                                                                                                   |
| `attributes.rum.page.host`   | String  |                    |                                                                                                   |
| `attributes.rum.page.path`   | String  |                    |                                                                                                   |
| `attributes.rum.sampled`     | Boolean | 是否采样               |                                                                                                   |
| `attributes.status_class`    | String  | HTTP 状态段           |                                                                                                   |
| `attributes.user.id`         | String  | 用户 ID              |                                                                                                   |
| `attributes.os_name`         | String  | 操作系统名称，SDK 解析后的统一值 |                                                                                                   |
| `attributes.error_type`      | String  | 错误类型               |                                                                                                   |
| `attributes.trace_scene`     | String  | 追踪场景               |                                                                                                   |

- browser

| 字段                                   | 类型     | 描述      | 备注 |
|--------------------------------------|--------|---------|----|
| `attributes.browser.screen.height`   | Number | 屏幕尺寸的高度 |    |
| `attributes.browser.screen.width`    | Number | 屏幕尺寸的宽度 |    |
| `attributes.browser.viewport.height` | Number | 视口尺寸的高度 |    |
| `attributes.browser.viewport.width`  | Number | 视口尺寸的宽度 |    |
| `attributes.browser_name`            | String | 浏览器名称   |    |
| `attributes.browser_version`         | String | 浏览器版本   |    |

- device

| 字段                            | 类型     | 描述         | 备注 |
|-------------------------------|--------|------------|----|
| `attributes.device.cpu_cores` | Number | 设备 cpu 核心数 |    |
| `attributes.device.id`        | String | 设备 id      |    |
| `attributes.device.memory`    | Number | 设备内存       |    |
| `attributes.device_type`      | String | 设备类型       |    |

- network

| 字段                                   | 类型      | 描述           | 备注 |
|--------------------------------------|---------|--------------|----|
| `attributes.network.connection_type` | String  | 连接类型         |    |
| `attributes.network.downlink`        | Number  | 预估下行带宽（Mbps） |    |
| `attributes.network.effective_type`  | String  | 有效网络类型       |    |
| `attributes.network.rtt`             | Number  | 往返时延（毫秒）     |    |
| `attributes.network.save_data`       | Boolean | 用户是否开启省流量模式  |    |

- session

| 字段                              | 类型      | 描述     | 备注 |
|---------------------------------|---------|--------|----|
| `attributes.session.has_replay` | Boolean | 是否回放   |    |
| `attributes.session.id`         | String  | 会话唯一标识 |    |

- target

| 字段                                | 类型     | 描述     | 备注 |
|-----------------------------------|--------|--------|----|
| `attributes.target_domain`        | String | 目标域名   |    |
| `attributes.target_label`         | String | 目标标签   |    |
| `attributes.target_path_template` | String | 目标路径模板 |    |
| `attributes.target_value`         | Number | 目标数值   |    |

- user_agent

| 字段                               | 类型     | 描述       | 备注 |
|----------------------------------|--------|----------|----|
| `attributes.user_agent.name`     | String | UA 名称    |    |
| `attributes.user_agent.original` | String | UA 原始字符串 |    |
| `attributes.user_agent.os.name`  | String | UA 操作系统名 |    |
| `attributes.user_agent.version`  | String | UA 版本    |    |

- view

| 字段                               | 类型     | 描述     | 备注 |
|----------------------------------|--------|--------|----|
| `attributes.view.id`             | String | 视图 ID  |    |
| `attributes.view.loading_type`   | String | 视图加载类型 |    |
| `attributes.view.url`            | String | 视图 URL |    |
| `attributes.view.url_path_group` | String | 视图路径分组 |    |

### 1.3 Resource

| 字段                                     | 类型     | 描述        | 备注                                      |
|----------------------------------------|--------|-----------|-----------------------------------------|
| `resource.deployment.environment.name` | String | 部署环境名称    | 例如 `development`、`production`、`staging` |
| `resource.rum.provider`                | String | RUM 数据提供方 | 固定值 `blueking`，标识蓝鲸 RUM 采集器             |
| `resource.service.name`                | String | 服务名称      | 对应应用名，例如 `bk-monitor`                   |
| `resource.service.version`             | String | 服务版本      | 对应应用版本号，例如 `1.0.0`                      |
| `resource.telemetry.sdk.language`      | String | SDK 语言    | 固定值 `webjs`，表示前端 Web JS SDK             |

---

### 1.4 Events

| 字段                                       | 类型     | 描述      | 备注 |
|------------------------------------------|--------|---------|----|
| `events.name`                            | String | 事件名称    |    |
| `events.timestamp`                       | String | 事件发生时间戳 |    |
| `events.attributes.message`              | String | 事件消息    |    |
| `events.attributes.exception.type`       | String | 异常类型    |    |
| `events.attributes.exception.message`    | String | 异常的简短消息 |    |
| `events.attributes.exception.stacktrace` | String | 异常的堆栈信息 |    |

---

### 1.5 Status

| 字段               | 类型     | 描述   | 备注                           |
|------------------|--------|------|------------------------------|
| `status.code`    | Number | 状态码  | `0`=Unset, `1`=Ok, `2`=Error |
| `status.message` | String | 状态描述 | `--` 表示无额外描述；通常为空字符串或异常原因描述  |

## 2 专属字段

`span_type` 有九种类型，分别为 `document` / `http` / `resource` / `vital` / `error` / `longtask` / `action` / `route` /
`custom`，
下面根据类型梳理对应的专属字段。

### 2.1 document

| 字段                             | 类型     | 描述          | 备注             |
|--------------------------------|--------|-------------|----------------|
| `attributes.event.source`      | String | 导航事件来源      | `load` 等       |
| `attributes.trace_scene`       | String | 追踪场景        | 例如 `page_load` |
| `attributes.view.end_reason`   | String | 结束原因        |                |
| `attributes.url.previous`      | String | 上一页 URL     | 首次加载时为空字符串     |
| `attributes.document.referrer` | String | 文档 referrer |                |

### 2.2 http / resource

| 字段                                        | 类型      | 描述                     | 备注                                                        |
|-------------------------------------------|---------|------------------------|-----------------------------------------------------------|
| `attributes.initiator_type`               | String  | 资源发起类型                 | 例如 `fetch` / `script` / `xmlhttprequest` / `link` / `img` |
| `attributes.http.request.method`          | String  | HTTP 请求方法              |                                                           |
| `attributes.http.response.status_code`    | Number  | HTTP 响应状态码             |                                                           |
| `attributes.resource.decoded_body_size`   | Number  | 解码后资源大小（字节）            |                                                           |
| `attributes.resource.encoded_body_size`   | Number  | 编码后资源大小（字节）            |                                                           |
| `attributes.transfer_size`                | Number  | 传输大小（字节）               |                                                           |
| `attributes.url.full`                     | String  | 完整资源 URL               |                                                           |
| `attributes.url.previous`                 | String  | 跳转前 URL                |                                                           |
| `attributes.target_domain`                | String  | 目标域名                   |                                                           |
| `attributes.target_path_template`         | String  | 目标路径模板                 |                                                           |
| `attributes.next_hop_protocol`            | String  | 下一跳协议                  | 例如 `h2` / `http/1.1`                                      |
| `attributes.cache_hit`                    | Boolean | 是否命中缓存                 |                                                           |
| `attributes.http.duration`                | Number  | httpBody 插件记录的请求耗时（ms） |                                                           |
| `attributes.http.request.body`            | String  |                        |                                                           |
| `attributes.http.response.body`           | String  |                        |                                                           |
| `attributes.http_body.request.truncated`  | Boolean |                        |                                                           |
| `attributes.http_body.response.truncated` | Boolean |                        |                                                           |

### 2.3 vital

| 字段                                            | 类型     | 描述              | 备注                                               |
|-----------------------------------------------|--------|-----------------|--------------------------------------------------|
| `attributes.vital.id`                         | String | Vital 唯一标识      |                                                  |
| `attributes.vital.metric`                     | String | 指标名             | `ttfb` / `lcp` / `fcp` / `cls` / `inp` / `fid` 等 |
| `attributes.vital.rating`                     | String | 评级              | `good` / `needs-improvement` / `poor`            |
| `attributes.vital.value`                      | Number | 指标测量值           |                                                  |
| `attributes.vital.ttfb.connection_duration`   | Number | TTFB 连接耗时（毫秒）   | `vital.metric=ttfb` 时出现                          |
| `attributes.vital.ttfb.dns_duration`          | Number | TTFB DNS 耗时（毫秒） |                                                  |
| `attributes.vital.ttfb.request_duration`      | Number | TTFB 请求耗时（毫秒）   |                                                  |
| `attributes.vital.ttfb.waiting_duration`      | Number | TTFB 等待耗时（毫秒）   |                                                  |
| `attributes.vital.lcp.element_render_delay`   | Number | LCP 元素渲染延迟（毫秒）  | `vital.metric=lcp` 时出现                           |
| `attributes.vital.lcp.resource_load_duration` | Number | LCP 资源加载耗时（毫秒）  |                                                  |
| `attributes.vital.lcp.target`                 | String | LCP 目标元素选择器     |                                                  |
| `attributes.vital.lcp.time_to_first_byte`     | Number | LCP TTFB（毫秒）    |                                                  |
| `attributes.vital.lcp.url`                    | String | LCP 目标资源 URL    |                                                  |
| `attributes.vital.fcp.load_state`             | String | FCP 加载状态        | `vital.metric=fcp` 时出现                           |
| `attributes.vital.fcp.time_to_first_byte`     | Number | FCP TTFB（毫秒）    |                                                  |
| `attributes.vital.cls.largest_shift_target`   | String | CLS 最大布局偏移目标    | `vital.metric=cls` 时出现                           |
| `attributes.vital.cls.largest_shift_value`    | Number | CLS 最大偏移值       |                                                  |
| `attributes.vital.cls.load_state`             | String | CLS 加载状态        |                                                  |
| `attributes.vital.inp.*`                      | Mixed  | INP 相关子字段       | `vital.metric=inp` 时出现                           |
| `attributes.rum.navigation.type`              | String | 导航类型            | `navigate` / `reload` 等                          |

### 2.4 error

| 字段                                     | 类型              | 描述         | 备注                                                   |
|----------------------------------------|-----------------|------------|------------------------------------------------------|
| `attributes.error.handled`             | Boolean         | 错误是否被捕获    |                                                      |
| `attributes.error.source`              | String          | 错误来源       | `window.error` / `resource` / `unhandledrejection` 等 |
| `attributes.error.window_count`        | Number          | 窗口级错误累计次数  |                                                      |
| `attributes.error.cross_origin`        | Boolean         | 跨域脚本错误     |                                                      |
| `attributes.code.column`               | String / Number | 代码列号       | JS 错误时出现，未上报时为 `--`                                  |
| `attributes.code.filepath`             | String          | 代码文件路径     |                                                      |
| `attributes.code.lineno`               | String / Number | 代码行号       |                                                      |
| `attributes.exception.fingerprint`     | String          | 异常指纹       | 用于聚合同类异常                                             |
| `attributes.exception.message`         | String          | 异常完整消息     |                                                      |
| `attributes.exception.message_short`   | String          | 异常简短消息     | 适合列表展示                                               |
| `attributes.exception.stacktrace`      | String          | 异常堆栈信息     |                                                      |
| `attributes.exception.stack_top_frame` | String          | 堆栈顶部帧      |                                                      |
| `attributes.exception.type`            | String          | 异常类型       | `TypeError` / `Error` 等                              |
| `attributes.html.tag`                  | String          | 关联 HTML 标签 | 资源类错误时出现，例如 `IMG`                                    |

- csp 插件采集

| 字段                                   | 类型 | 描述 | 备注 |
|--------------------------------------|----|----|----|
| `attributes.csp.blocked_uri`         |    |    |    |
| `attributes.csp.violated_directive`  |    |    |    |
| `attributes.csp.effective_directive` |    |    |    |
| `attributes.csp.source_file`         |    |    |    |
| `attributes.csp.line_number`         |    |    |    |
| `attributes.csp.status_code`         |    |    |    |
| `attributes.csp.fingerprint`         |    |    |    |
| `attributes.csp.window_count`        |    |    |    |
| `attributes.csp.original_policy`     |    |    |    |

- blank_screen

| 字段                                                                                                                             | 类型      | 描述              | 备注 |
|--------------------------------------------------------------------------------------------------------------------------------|---------|-----------------|----|
| `attributes.blank_screen.score`                                                                                                | Number  | 空白样本比例          |    |
| `attributes.blank_screen.threshold`                                                                                            | Number  | 判定阈值            |    |
| `attributes.blank_screen.detected`                                                                                             | Boolean | 是否判为白屏          |    |
| `attributes.blank_screen.root`                                                                                                 | String  | 采样根选择器          |    |
| `attributes.blank_screen.sample_total`<br/>`attributes.blank_screen.sample_valid`<br/>`attributes.blank_screen.sample_loading` | Number  | 采样统计            |    |
| `attributes.blank_screen.center_element`                                                                                       | String  | 视口中心元素选择器       |    |
| `attributes.blank_screen.dom_node_count`                                                                                       | Number  | body 下 DOM 节点总数 |    |

### 2.5 longtask

| 字段                                       | 类型     | 描述    | 备注 |
|------------------------------------------|--------|-------|----|
| `attributes.longtask.blocking_duration`  | Number | 长任务时长 |    |
| `attributes.longtask.attribution_script` | String | 归因脚本  |    |

### 2.6 action

| 字段                                 | 类型     | 描述                          | 备注 |
|------------------------------------|--------|-----------------------------|----|
| `attributes.action.type`           | String | 动作类型                        |    |
| `attributes.target.tag`            | String | 目标元素标签                      |    |
| `attributes.target.text_short`     | String | 目标文本前 32 字符                 |    |
| `attributes.session.start_time`    | Number | 会话开始时间戳                     |    |
| `attributes.session.previous_id`   | String | 轮换前的 session.id             |    |
| `attributes.session.rotate.reason` | String | init/inactivity/maxLifetime |    |

### 2.7 route

| 字段                               | 类型     | 描述          | 备注                          |
|----------------------------------|--------|-------------|-----------------------------|
| `attributes.event.source`        | String | 路由事件来源      | `popstate` / `hashchange` 等 |
| `attributes.view.end_reason`     | String | 结束原因        |                             |
| `attributes.url.previous`        | String | 上一页 URL     | 来源页面地址                      |
| `attributes.route.change.source` | String |             | routeTiming 插件              |
| `attributes.document.referrer`   | String | 文档 referrer |                             |

### 2.8 custom

| 字段                           | 类型     | 描述                       | 备注 |
|------------------------------|--------|--------------------------|----|
| `attributes.rum.custom.name` | String | reportCustomEvent() 的事件名 |    |
