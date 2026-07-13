# RUM Span 数据协议

## 1 公共字段

### 1.1 顶层字段

| 字段               | 类型     | 描述                                                                             | 备注                                                                                |
|------------------|--------|--------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| `app_name`       | String | 应用名称                                                                           | 应用名                                                                               |
| `attributes`     | Object | 属性集                                                                            | 包含浏览器、设备、网络、异常等各类语义标签和度量                                                          |
| `bk_biz_id`      | String | 业务 ID                                                                          | 蓝鲸业务标识                                                                            |
| `elapsed_time`   | Number | 耗时（微秒）                                                                         | Span 从 start_time 到 end_time 的时间差                                                 |
| `end_time`       | String | 结束时间戳（微秒）                                                                      | Span 结束的时间                                                                        |
| `events`         | Object | 事件列表                                                                           | JSON 数组，span_type 为 error 时存在                                                     |
| `kind`           | Number | [Span 类型](https://opentelemetry.io/zh/docs/concepts/signals/traces/#span-kind) | 枚举值：<br/>- 未定义：0<br/>- 内部调用：1<br/>- 同步被调：2<br/>- 同步主调：3<br/>- 异步主调：4<br/>- 异步被调：5 |
| `links`          | Object | 关联 Span 列表                                                                     | JSON 数组                                                                           |
| `parent_span_id` | String | 父 Span ID                                                                      |                                                                                   |
| `resource`       | Object | 资源信息                                                                           | 产生此 Span 的服务、环境、SDK 等描述信息                                                         |
| `span_id`        | String | 当前 Span ID                                                                     |                                                                                   |
| `span_name`      | String | Span 名称                                                                        |                                                                                   |
| `start_time`     | String | 开始时间戳（微秒）                                                                      |                                                                                   |
| `status`         | Object | Span 执行状态                                                                      | 包含 `code` 和 `message`                                                             |
| `time`           | String | 数据上报时间戳                                                                        | ES 写入时间标记                                                                         |
| `trace_id`       | String | Trace ID                                                                       | 关联的链路追踪根标识                                                                        |
| `trace_state`    | String | Trace 状态                                                                       | 内部格式，例如 `map[]`                                                                   |

---

### 1.2 Attributes

#### 1.2.1 Span 公共属性

- 基础字段

| 字段                           | 类型      | 描述                                       | 备注                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
|------------------------------|---------|------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.span_type`       | String  | Span 类型                                  | 枚举值：<br/>- 文档加载：document<br/>- 路由切换：route<br/>- 静态资源：resource<br/>- HTTP / API：http<br/>- 长任务：longtask<br/>- 用户交互：action<br/>- Web 指标：vital<br/>- 错误：error<br/>- 自定义：custom                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `attributes.span_subtype`    | String  | Span 子类型，不同的 span_type 有不同的 span_subtype | 枚举值：<br/>1. document<br/>- 导航：navigate<br/>- 文档下载完成：document_fetch<br/>2. route<br/>- 压栈：pushState<br/>- 替换：replaceState<br/>- 弹栈：popstate<br/>- 哈希变化：hashchange<br/>3. resource<br/>- script<br/>- link<br/>- img<br/>- css<br/>- xmlhttprequest<br/>- fetch<br/>- video<br/>- audio<br/>- iframe<br/>- beacon<br/>- other<br/>4. http<br/>- fetch<br/>- xhr<br/>- beacon<br/>- sendbeacon<br/>5. longtask<br/>- 脚本执行：script<br/>- 布局：layout<br/>- 绘制：paint<br/>- 未归因：unknown<br/>6. action<br/>- 点击：click<br/>- 输入：input<br/>- keydown<br/>- scroll<br/>- pointerdown<br/>- submit<br/>- custom<br/>7. vital<br/>- lcp<br/>- fcp<br/>- cls<br/>- inp<br/>- fid<br/>- ttfb<br/>8. error<br/>- js<br/>- promise<br/>- resource_load<br/>- blank_screen<br/>- csp<br/>- network<br/>- cors<br/>- console<br/>- custom<br/>9. custom<br/>- websocket<br/>- <自定义> |
| `attributes.duration_bucket` | String  | 耗时分桶                                     | 枚举值：<br/>- <100ms<br/>- 100~500ms<br/>- 500ms~2s<br/>- >2s                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `attributes.event_label`     | String  | 中文事件标签                                   | 如 `API 调用`/`错误`等                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `attributes.result`          | String  | 结果                                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.rum.page.host`   | String  | 页面 host                                  | hostname:port                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `attributes.rum.page.path`   | String  | 页面 pathname                              | 不含 query 和 hash                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.rum.sampled`     | Boolean | 是否采样                                     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.status_class`    | String  | HTTP 状态段                                 |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.user.id`         | String  | 用户 ID                                    |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.os_name`         | String  | 操作系统名称，SDK 解析后的统一值                       |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `attributes.error_type`      | String  | 错误类型                                     | 枚举值：<br/>- none<br/>- http_4xx<br/>- http_5xx<br/>- network_timeout<br/>- js<br/>- promise<br/>- resource_load<br/>- blank_screen<br/>- csp<br/>- slow<br/>- longtask_blocking<br/>- network<br/>- custom                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `attributes.trace_scene`     | String  | 追踪场景                                     | 枚举值：<br/>- page_load<br/>- route_change<br/>- user_action<br/>- startup                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

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

| 字段                            | 类型      | 描述                      | 备注                              |
|-------------------------------|---------|-------------------------|---------------------------------|
| `attributes.device.cpu_cores` | Number  | 设备 cpu 核心数              |                                 |
| `attributes.device.id`        | String  | 设备终身标识（localStorage 持久） |                                 |
| `attributes.device.memory`    | Number  | 设备内存                    |                                 |
| `attributes.device.mobile`    | Boolean | 是否为移动设备                 |                                 |
| `attributes.device.platform`  | String  | 设备平台                    |                                 |
| `attributes.device_type`      | String  | 设备类型                    | 枚举值：<br/>- mobile<br/>- desktop |

- network

| 字段                                   | 类型      | 描述           | 备注                         |
|--------------------------------------|---------|--------------|----------------------------|
| `attributes.network.connection_type` | String  | 连接类型         | 非枚举值，浏览器 API 的直出值，SDK 只做转发 |
| `attributes.network.downlink`        | Number  | 预估下行带宽（Mbps） |                            |
| `attributes.network.effective_type`  | String  | 有效网络质量（4g 等） | 非枚举值，浏览器 API 的直出值，SDK 只做转发 |
| `attributes.network.rtt`             | Number  | 往返时延（毫秒）     |                            |
| `attributes.network.save_data`       | Boolean | 用户是否开启省流量模式  |                            |

- session

| 字段                              | 类型      | 描述     | 备注 |
|---------------------------------|---------|--------|----|
| `attributes.session.has_replay` | Boolean | 是否回放   |    |
| `attributes.session.id`         | String  | 会话唯一标识 |    |

- target

| 字段                                | 类型     | 描述               | 备注 |
|-----------------------------------|--------|------------------|----|
| `attributes.target_domain`        | String | 目标域名             |    |
| `attributes.target_label`         | String | 跨类型主标签，用于统一检索    |    |
| `attributes.target_path_template` | String | 目标低基数路径模板        |    |
| `attributes.target_value`         | Number | 主数值（状态码、耗时、字节数等） |    |

- user_agent

| 字段                               | 类型     | 描述       | 备注 |
|----------------------------------|--------|----------|----|
| `attributes.user_agent.name`     | String | UA 名称    |    |
| `attributes.user_agent.original` | String | UA 原始字符串 |    |
| `attributes.user_agent.os.name`  | String | UA 操作系统名 |    |
| `attributes.user_agent.version`  | String | UA 版本    |    |

- view

| 字段                               | 类型     | 描述     | 备注                                         |
|----------------------------------|--------|--------|--------------------------------------------|
| `attributes.view.id`             | String | 视图 ID  |                                            |
| `attributes.view.loading_type`   | String | 视图加载类型 | 枚举值：<br/>- route_change<br/>- initial_load |
| `attributes.view.url`            | String | 视图 URL |                                            |
| `attributes.view.url_path_group` | String | 视图路径分组 |                                            |

### 1.3 Resource

| 字段                                     | 类型     | 描述        | 备注                            |
|----------------------------------------|--------|-----------|-------------------------------|
| `resource.deployment.environment.name` | String | 部署环境名称    | 同 `app.environment`           |
| `resource.rum.provider`                | String | RUM 数据提供方 | 固定值 `blueking`，标识蓝鲸 RUM 采集器   |
| `resource.service.name`                | String | 服务名称      | 同应用名 `app.name`               |
| `resource.service.version`             | String | 服务版本      | 可选，如果没传 `app.version`，这个字段不存在 |
| `resource.telemetry.sdk.language`      | String | SDK 语言    | 固定值 `webjs`，表示前端 Web JS SDK   |

### 1.4 Status

| 字段               | 类型     | 描述   | 备注                                     |
|------------------|--------|------|----------------------------------------|
| `status.code`    | Number | 状态码  | 枚举值：<br/>- 未设置：0<br/>- 正常：1<br/>- 异常：2 |
| `status.message` | String | 状态描述 | 仅在 `status.code` == 2 时有值，正常 span 为空   |

## 2 专属字段

`span_type` 有九种类型，分别为 `document`、`http`、`resource`、`vital`、`error`、`longtask`、`action`、`route`、
`custom`，
下面根据类型梳理对应的专属字段。

### 2.1 document

一共有四种 span_name，分别为蓝鲸自研 pageView 插件上报的 `browser.view` 和 `browser.page_view`，OTel 官方插件上报的
`documentFetch` 和 `documentLoad`。

| 字段                             | 类型     | 描述            | 备注                                                                                                                                                                       |
|--------------------------------|--------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.event.source`      | String | 导航事件来源        | 枚举值：<br/>- load<br/>仅当 span_name 为 `browser.view` 和 `browser.page_view` 时上报                                                                                              |
| `attributes.trace_scene`       | String | 追踪场景          | 枚举值：<br/>- page_load                                                                                                                                                     |
| `attributes.view.end_reason`   | String | 结束原因          | 枚举值：<br/>- load（实际永不出现）<br/>- pushState<br/>- replaceState<br/>- popstate<br/>- hashchange<br/>- shutdown<br/>当 span_name 为 `browser.view` 且该 view 被后续路由或 shutdown 结束时上报 |
| `attributes.url.full`          | String | 完整资源 URL（已脱敏） | 仅当 span_name 为 `documentFetch` 和 `documentLoad` 时上报                                                                                                                      |
| `attributes.url.previous`      | String | 上一页 URL       | 仅当 span_name 为 `browser.view` 和 `browser.page_view` 时上报                                                                                                                  |
| `attributes.document.referrer` | String | 文档 referrer   | 仅当 span_name 为 `browser.view` 和 `browser.page_view` 时上报                                                                                                                  |

### 2.2 http（无数据上报，暂无法校验）

| 字段                                        | 类型      | 描述                     | 备注                                                                                             |
|-------------------------------------------|---------|------------------------|------------------------------------------------------------------------------------------------|
| `attributes.initiator_type`               | String  | 资源发起类型                 | 常见值：<br/>- img<br/>- script<br/>- xmlhttprequest<br/>- fetch<br/>- link<br/>- css<br/>- iframe |
| `attributes.http.request.method`          | String  | HTTP 请求方法（大写）          |                                                                                                |
| `attributes.http.response.status_code`    | Number  | HTTP 响应状态码             |                                                                                                |
| `attributes.resource.decoded_body_size`   | Number  | 解码后资源大小（字节）            |                                                                                                |
| `attributes.resource.encoded_body_size`   | Number  | 编码后资源大小（字节）            |                                                                                                |
| `attributes.transfer_size`                | Number  | 传输大小（字节数）              |                                                                                                |
| `attributes.url.full`                     | String  | 完整资源 URL（已脱敏）          |                                                                                                |
| `attributes.url.previous`                 | String  | 跳转前 URL                |                                                                                                |
| `attributes.target_domain`                | String  | 目标域名                   |                                                                                                |
| `attributes.target_path_template`         | String  | 目标路径模板                 |                                                                                                |
| `attributes.next_hop_protocol`            | String  | 下一跳协议                  | 例如 `h2` / `http/1.1`                                                                           |
| `attributes.cache_hit`                    | Boolean | 是否命中缓存                 |                                                                                                |
| `attributes.http.duration`                | Number  | httpBody 插件记录的请求耗时（ms） |                                                                                                |
| `attributes.http.request.body`            | String  |                        |                                                                                                |
| `attributes.http.response.body`           | String  |                        |                                                                                                |
| `attributes.http_body.request.truncated`  | Boolean |                        |                                                                                                |
| `attributes.http_body.response.truncated` | Boolean |                        |                                                                                                |

### 2.3 resource

一共有两种 span_name，分别为蓝鲸自研 resource 插件上报的 `browser.resource`，OTel 官方插件上报的 `resourceFetch`。

| 字段                                      | 类型      | 描述            | 备注                                                                                                                                      |
|-----------------------------------------|---------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.initiator_type`             | String  | 资源发起类型        | 常见值：<br/>- img<br/>- script<br/>- xmlhttprequest<br/>- fetch<br/>- link<br/>- css<br/>- iframe<br/>仅当 span_name 为 `browser.resource` 存在 |
| `attributes.http.response.status_code`  | Number  | HTTP 响应状态码    |                                                                                                                                         |
| `attributes.resource.decoded_body_size` | Number  | 解码后资源大小（字节）   | 仅当 span_name 为 `browser.resource` 时存在                                                                                                   |
| `attributes.resource.encoded_body_size` | Number  | 编码后资源大小（字节）   | 仅当 span_name 为 `browser.resource` 时存在                                                                                                   |
| `attributes.transfer_size`              | Number  | 传输大小（字节数）     | 仅当 span_name 为 `browser.resource` 时存在                                                                                                   |
| `attributes.url.full`                   | String  | 完整资源 URL（已脱敏） |                                                                                                                                         |
| `attributes.target_domain`              | String  | 目标域名          |                                                                                                                                         |
| `attributes.target_path_template`       | String  | 目标路径模板        |                                                                                                                                         |
| `attributes.next_hop_protocol`          | String  | 下一跳协议         | 仅当 span_name 为 `browser.resource` 时存在                                                                                                   |
| `attributes.cache_hit`                  | Boolean | 是否命中缓存        | 仅当 span_name 为 `browser.resource` 时存在                                                                                                   |

### 2.4 vital

| 字段                               | 类型     | 描述         | 备注                                                                                                                       |
|----------------------------------|--------|------------|--------------------------------------------------------------------------------------------------------------------------|
| `attributes.vital.id`            | String | Vital 唯一标识 |                                                                                                                          |
| `attributes.vital.metric`        | String | 指标名        | 枚举值：<br/>- cls<br/>- inp<br/>- lcp<br/>- fcp<br/>- ttfb<br/>术语介绍看下方表格                                                    |
| `attributes.vital.rating`        | String | 评级         | 枚举值：<br/>- good<br/>- needs-improvement<br/>- poor                                                                       |
| `attributes.vital.value`         | Number | 指标测量值      |                                                                                                                          |
| `attributes.rum.navigation.type` | String | 导航类型       | 枚举值：<br/>- back-forward<br/>- back-forward-cache<br/>- navigate<br/>- prerender<br/>- reload<br/>- restore<br/>- unknown |

`attributes.vital.metric` 的枚举值术语介绍如下：

| 值    | 描述                                                                    | 备注                                        |
|------|-----------------------------------------------------------------------|-------------------------------------------|
| cls  | [累积布局偏移（Cumulative Layout Shift）](https://web.dev/articles/cls)       | 一个以用户为中心的重要指标，用于衡量视觉稳定性                   |
| inp  | [交互到下一次绘制（Interaction to Next Paint）](https://web.dev/articles/inp)   | 稳定的核心网页指标，使用 Event Timing API 中的数据来评估响应速度 |
| lcp  | [最大内容绘制（Largest Contentful Paint, LCP）](https://web.dev/articles/lcp) | Core Web Vital 中的一个重要且稳定的指标，用于衡量页面加载的速度。  |
| fcp  | [首次内容绘制（First Contentful Paint）](https://web.dev/articles/fcp)        | 是一项以用户为中心的重要指标，用于衡量用户感知的加载速度              |
| ttfb | [首字节时间（Time to First Byte）](https://web.dev/articles/ttfb)            | 是指从浏览器发起请求到接收到服务器返回第一个数据字节所经过的时间          |

- vital.metric=cls

| 字段                                          | 类型     | 描述             | 备注                                                                                                                              |
|---------------------------------------------|--------|----------------|---------------------------------------------------------------------------------------------------------------------------------|
| `attributes.vital.cls.largest_shift_target` | String | 最大布局偏移的目标元素选择器 | 高基数字段，如 `body > div#app > button`，CLS 偏移的最大贡献者的 DOM 路径                                                                          |
| `attributes.vital.cls.largest_shift_value`  | Number | 最大单次布局偏移分值     | 该元素造成的单次最大偏移分数，注意这是"最大一次"的分数，不是 CLS 累积总分（总分在 vital.value 和 target_value 里）。值越小越好，接近 0 为优                                        |
| `attributes.vital.cls.load_state`           | String | 最大偏移发生时的页面     | 枚举值：<br/>- loading<br/>- dom-interactive<br/>- dom-content-loaded<br/>- complete<br/>用于判断 CLS 偏移发生在首屏哪个时期（体验越差时越可能在 loading 阶段） |

- vital.metric=inp

| 字段                                         | 类型     | 描述        | 备注                                                |
|--------------------------------------------|--------|-----------|---------------------------------------------------|
| `attributes.vital.inp.input_delay`         | String | 输入延迟（ms）  | 用户发起交互（如点击）到事件处理器开始执行的等待时间，反映主线程繁忙程度              |
| `attributes.vital.inp.interaction_target`  | String | 交互目标元素选择器 | 高基数字段，库提供的 DOM 选择器字符串，如 `body > div#app > button` |
| `attributes.vital.inp.interaction_type`    | String | 交互类型      | 用户触发方式，如 `pointer`、`keyboard`，说明 INP 由什么输入方式产生    |
| `attributes.vital.inp.presentation_delay`  | Number | 呈现延迟（ms）  | 事件处理回调完成之后，到浏览器实际渲染下一帧的耗时，CSS/布局/重绘瓶颈看这里          |
| `attributes.vital.inp.processing_duration` | Number | 处理耗时（ms）  | 事件处理回调（如 click handler）本身的执行时间，JS 逻辑过重时这个值会变大     |

- vital.metric=lcp

| 字段                                            | 类型     | 描述                  | 备注                                                                                 |
|-----------------------------------------------|--------|---------------------|------------------------------------------------------------------------------------|
| `attributes.vital.lcp.element_render_delay`   | Number | LCP 元素的渲染阻塞延迟（ms）   | LCP 元素资源加载完成后，到浏览器真正渲染该元素之间的等待时间。主要由主线程阻塞（长任务/JS 执行）导致。值越小越好                       |
| `attributes.vital.lcp.resource_load_duration` | Number | LCP 资源加载耗时（ms）      | LCP 元素依赖的外部资源（图片/字体等）从请求到下载完成的时间。如果 LCP 是纯文本节点，此项可能缺失。用于排查 CDN/网络/资源体积问题           |
| `attributes.vital.lcp.target`                 | String | LCP 目标元素的 DOM 选择器   | 高基数字段，LCP 候选元素的 CSS 选择器路径，如 `html > body > div#hero > img`                         |
| `attributes.vital.lcp.time_to_first_byte`     | Number | LCP 发生前的 TTFB（ms）   | 从导航开始到收到首字节的耗时。这是 LCP 的"基座"——如果 TTFB 本身就很高，后面两段也会相应推迟。LCP ≈ TTFB + 资源加载耗时 + 元素渲染延迟 |
| `attributes.vital.lcp.url`                    | String | LCP 元素对应资源 URL（已脱敏） | 高基数字段，LCP 为图片/背景图/视频海报等资源时，这里是该资源的地址；如果 LCP 是文本节点，此项缺失。用于定位是哪张图片拖慢了首屏              |

- vital.metric=fcp

| 字段                                        | 类型     | 描述                | 备注                                                                                                          |
|-------------------------------------------|--------|-------------------|-------------------------------------------------------------------------------------------------------------|
| `attributes.vital.fcp.load_state`         | String | FCP 发生时的页面加载阶段    | 枚举值：<br/>- loading<br/>- dom-interactive<br/>- dom-content-loaded<br/>- complete<br/>用于判断首次内容绘制发生在页面加载的哪个时期 |
| `attributes.vital.fcp.time_to_first_byte` | Number | FCP 发生前的首字节时间（ms） | 从导航开始到收到服务器首个响应字节的耗时。FCP 不可能早于 TTFB，此值揭示了"网络基座"耗时。当 FCP 延迟过高时，若此值大说明是服务端/网络问题，若小则可能是前端渲染阻塞                  |

- vital.metric=ttfb

| 字段                                          | 类型     | 描述                   | 备注                                                           |
|---------------------------------------------|--------|----------------------|--------------------------------------------------------------|
| `attributes.vital.ttfb.waiting_duration`    | Number | 请求就绪后的等待耗时（ms）       | 主要包括重定向处理、Service Worker 启动处理、请求排队                           |
| `attributes.vital.ttfb.dns_duration`        | Number | DNS 解析耗时（ms）         | 解析慢通常由 DNS 服务器延迟、复杂 CNAME 链或本地 DNS 缓存失效导致。多国/多地域部署时此值可能偏高    |
| `attributes.vital.ttfb.connection_duration` | Number | TCP + TLS 连接建立耗时（ms） | 包含 TCP 三次握手和 TLS/SSL 协商。HTTPS 强制、TLS 1.3 升级、CDN 边缘节点距离都会影响此值 |
| `attributes.vital.ttfb.request_duration`    | Number | 请求发送后等待首字节耗时（ms）     | 导航请求的发送报文极小，此值主要反映网络往返 RTT 与服务器从接到请求到吐出首字节的时间                |

### 2.5 error

- span_subtype == js（span_name == browser.error）

| 字段                                       | 类型      | 描述        | 备注                                                                   |
|------------------------------------------|---------|-----------|----------------------------------------------------------------------|
| `attributes.error.handled`               | Boolean | 错误是否被捕获   |                                                                      |
| `attributes.error.source`                | String  | 错误来源      | 枚举值：<br/>- window.error（固定值）<br/>- resource<br/>- unhandledrejection |
| `attributes.error.window_count`          | Number  | 窗口级错误累计次数 |                                                                      |
| `attributes.error.cross_origin`          | Boolean | 跨域脚本错误    | 条件字段：仅跨域脚本错误（消息为 `"Script error."` 且无 stack / filename）时存在           |
| `attributes.code.column`                 | Number  | 代码列号      |                                                                      |
| `attributes.code.filepath`               | String  | 代码文件路径    |                                                                      |
| `attributes.code.lineno`                 | Number  | 代码行号      |                                                                      |
| `attributes.exception.fingerprint`       | String  | 异常指纹      | 用于聚合同类异常                                                             |
| `attributes.exception.message`           | String  | 异常完整消息    |                                                                      |
| `attributes.exception.message_short`     | String  | 异常简短消息    | 适合列表展示                                                               |
| `attributes.exception.stacktrace`        | String  | 异常堆栈信息    |                                                                      |
| `attributes.exception.stack_top_frame`   | String  | 堆栈顶部帧     |                                                                      |
| `attributes.exception.type`              | String  | 异常类型      |                                                                      |
| `events.name`                            | String  | 事件名称      |                                                                      |
| `events.timestamp`                       | String  | 事件发生时间戳   |                                                                      |
| `events.attributes.message`              | String  | 事件消息      |                                                                      |
| `events.attributes.exception.type`       | String  | 异常类型      |                                                                      |
| `events.attributes.exception.message`    | String  | 异常的简短消息   |                                                                      |
| `events.attributes.exception.stacktrace` | String  | 异常的堆栈信息   | 根据 error 实例提取，不一定存在                                                  |

- span_subtype == promise（span_name == browser.unhandledrejection）

| 字段                                       | 类型      | 描述        | 备注                                                                   |
|------------------------------------------|---------|-----------|----------------------------------------------------------------------|
| `attributes.error.handled`               | Boolean | 错误是否被捕获   |                                                                      |
| `attributes.error.source`                | String  | 错误来源      | 枚举值：<br/>- window.error（固定值）<br/>- resource<br/>- unhandledrejection |
| `attributes.error.window_count`          | Number  | 窗口级错误累计次数 |                                                                      |
| `attributes.exception.fingerprint`       | String  | 异常指纹      | 用于聚合同类异常                                                             |
| `attributes.exception.message`           | String  | 异常完整消息    |                                                                      |
| `attributes.exception.message_short`     | String  | 异常简短消息    | 适合列表展示                                                               |
| `attributes.exception.stacktrace`        | String  | 异常堆栈信息    |                                                                      |
| `attributes.exception.stack_top_frame`   | String  | 堆栈顶部帧     |                                                                      |
| `attributes.exception.type`              | String  | 异常类型      |                                                                      |
| `events.name`                            | String  | 事件名称      |                                                                      |
| `events.timestamp`                       | String  | 事件发生时间戳   |                                                                      |
| `events.attributes.message`              | String  | 事件消息      |                                                                      |
| `events.attributes.exception.type`       | String  | 异常类型      |                                                                      |
| `events.attributes.exception.message`    | String  | 异常的简短消息   |                                                                      |
| `events.attributes.exception.stacktrace` | String  | 异常的堆栈信息   | 根据 error 实例提取，不一定存在                                                  |

- span_subtype == resource_load（span_name == browser.resource_error）

| 字段                                       | 类型      | 描述            | 备注                                                                   |
|------------------------------------------|---------|---------------|----------------------------------------------------------------------|
| `attributes.error.handled`               | Boolean | 错误是否被捕获       |                                                                      |
| `attributes.error.source`                | String  | 错误来源          | 枚举值：<br/>- window.error（固定值）<br/>- resource<br/>- unhandledrejection |
| `attributes.error.window_count`          | Number  | 窗口级错误累计次数     |                                                                      |
| `attributes.exception.fingerprint`       | String  | 异常指纹          | 用于聚合同类异常                                                             |
| `attributes.exception.message`           | String  | 异常完整消息        |                                                                      |
| `attributes.exception.message_short`     | String  | 异常简短消息        | 适合列表展示                                                               |
| `attributes.exception.stacktrace`        | String  | 异常堆栈信息        |                                                                      |
| `attributes.exception.stack_top_frame`   | String  | 堆栈顶部帧         |                                                                      |
| `attributes.exception.type`              | String  | 异常类型          | `TypeError` / `Error` 等                                              |
| `attributes.html.tag`                    | String  | 关联 HTML 标签    | 资源类错误时出现，例如 `IMG`                                                    |
| `attributes.url.full`                    | String  | 失败资源 URL（已脱敏） |                                                                      |
| `events.name`                            | String  | 事件名称          |                                                                      |
| `events.timestamp`                       | String  | 事件发生时间戳       |                                                                      |
| `events.attributes.message`              | String  | 事件消息          |                                                                      |
| `events.attributes.exception.type`       | String  | 异常类型          |                                                                      |
| `events.attributes.exception.message`    | String  | 异常的简短消息       |                                                                      |
| `events.attributes.exception.stacktrace` | String  | 异常的堆栈信息       | 根据 error 实例提取，不一定存在                                                  |

- span_subtype == blank_screen（span_name == browser.blank_screen）

| 字段                                       | 类型      | 描述              | 备注 |
|------------------------------------------|---------|-----------------|----|
| `attributes.blank_screen.score`          | Number  | 空白样本比例          |    |
| `attributes.blank_screen.threshold`      | Number  | 判定阈值            |    |
| `attributes.blank_screen.detected`       | Boolean | 是否判为白屏          |    |
| `attributes.blank_screen.root`           | String  | 采样根选择器          |    |
| `attributes.blank_screen.sample_total`   | Number  | 采样点总数           |    |
| `attributes.blank_screen.sample_valid`   | Number  | 有效采样数           |    |
| `attributes.blank_screen.sample_loading` | Number  | loading 样本次数    |    |
| `attributes.blank_screen.center_element` | String  | 视口中心元素选择器       |    |
| `attributes.blank_screen.dom_node_count` | Number  | body 下 DOM 节点总数 |    |

- span_subtype == csp（span_name == csp.violation）

| 字段                                   | 类型     | 描述               | 备注 |
|--------------------------------------|--------|------------------|----|
| `attributes.csp.blocked_uri`         | String | 被拦截资源（URL 类值已脱敏） |    |
| `attributes.csp.violated_directive`  | String | 违反的指令            |    |
| `attributes.csp.effective_directive` | String | 生效的指令            |    |
| `attributes.csp.disposition`         | String | enforce / report |    |
| `attributes.csp.source_file`         | String | 触发脚本（已脱敏）        |    |
| `attributes.csp.line_number`         | Number | 触发位置行号           |    |
| `attributes.csp.column_number`       | Number | 触发位置列号           |    |
| `attributes.csp.status_code`         | Number | 状态码              |    |
| `attributes.csp.fingerprint`         | String | 节流指纹（djb2 hash）  |    |
| `attributes.csp.window_count`        | Number | 节流窗口内触发次数        |    |
| `attributes.csp.original_policy`     | String | 完整策略，仅窗口首条携带     |    |

### 2.6 longtask（无数据上报，暂无法校验）

| 字段                                       | 类型     | 描述    | 备注 |
|------------------------------------------|--------|-------|----|
| `attributes.longtask.blocking_duration`  | Number | 长任务时长 |    |
| `attributes.longtask.attribution_script` | String | 归因脚本  |    |

### 2.7 action（无数据上报，暂无法校验）

| 字段                                 | 类型     | 描述                          | 备注 |
|------------------------------------|--------|-----------------------------|----|
| `attributes.action.type`           | String | 动作类型                        |    |
| `attributes.target_label`          | String | 跨类型主标签，用于统一检索               |    |
| `attributes.target.tag`            | String | 目标元素标签                      |    |
| `attributes.target.text_short`     | String | 目标文本前 32 字符                 |    |
| `attributes.session.start_time`    | Number | 会话开始时间戳                     |    |
| `attributes.session.previous_id`   | String | 轮换前的 session.id             |    |
| `attributes.session.rotate.reason` | String | init/inactivity/maxLifetime |    |

### 2.8 route

- span_name == browser.view

| 字段                           | 类型     | 描述      | 备注                                                                                                                                          |
|------------------------------|--------|---------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.event.source`    | String | 路由事件来源  | 枚举值：<br/>- pushState<br/>- replaceState<br/>- popstate<br/>- hashchange                                                                     |
| `attributes.trace_scene`     | String | 追踪场景    | 枚举值：<br/>- route_change                                                                                                                     |
| `attributes.view.end_reason` | String | 结束原因    | 枚举值：<br/>- load（实际永不出现）<br/>- pushState<br/>- replaceState<br/>- popstate<br/>- hashchange<br/>- shutdown<br/>当该 view 被后续路由或 shutdown 结束时上报 |
| `attributes.url.previous`    | String | 上一页 URL | 来源页面地址                                                                                                                                      |

- span_name == browser.page_view

| 字段                               | 类型     | 描述          | 备注                                                                                                                                  |
|----------------------------------|--------|-------------|-------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.event.source`        | String | 路由事件来源      | 枚举值：<br/>- pushState<br/>- replaceState<br/>- popstate<br/>- hashchange<br/>仅当 span_name 为 `browser.view` 和 `browser.page_view` 时上报 |
| `attributes.trace_scene`         | String | 追踪场景        | 枚举值：<br/>- route_change                                                                                                             |
| `attributes.url.previous`        | String | 上一页 URL     | 来源页面地址                                                                                                                              |

- span_name == browser.route_change（无数据，未验证）

| 字段                               | 类型     | 描述     | 备注                                                                                                                                  |
|----------------------------------|--------|--------|-------------------------------------------------------------------------------------------------------------------------------------|
| `attributes.event.source`        | String | 路由事件来源 | 枚举值：<br/>- pushState<br/>- replaceState<br/>- popstate<br/>- hashchange<br/>仅当 span_name 为 `browser.view` 和 `browser.page_view` 时上报 |
| `attributes.route.change.source` | String |        | routeTiming 插件                                                                                                                      |

### 2.9 custom（无数据上报，暂无法校验）

| 字段                           | 类型     | 描述                       | 备注 |
|------------------------------|--------|--------------------------|----|
| `attributes.rum.custom.name` | String | reportCustomEvent() 的事件名 |    |

- websocket 插件

| 字段                                        | 类型     | 描述                    | 备注          |
|-------------------------------------------|--------|-----------------------|-------------|
| `attributes.url.scheme`                   | String | `ws` / `wss`          |             |
| `attributes.server.address`               | String | 目标 host               |             |
| `attributes.network.protocol.name`        | String | 固定 `websocket`        |             |
| `attributes.websocket.direction`          | String | 消息收发方向 `in` / `out`   | metric 插件适用 |
| `attributes.websocket.error.phase`        | String | `connect` / `runtime` | 错误场景        |
| `attributes.websocket.error.window_count` | Number | 错误日志节流窗口内触发次数         |             |
| `attributes.websocket.close.code`         | Mixed  | 关闭事件状态码               |             |
| `attributes.websocket.close.reason`       | Mixed  | 关闭原因                  |             |
| `attributes.websocket.close.was_clean`    | Mixed  | 是否为干净关闭               |             |
