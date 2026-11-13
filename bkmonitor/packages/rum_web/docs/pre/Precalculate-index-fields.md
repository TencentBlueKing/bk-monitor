# 预计算索引字段说明

本文档描述 View 和 Session 预计算索引当前使用的字段、类型及含义，字段定义以对应的 Elasticsearch index template 为准。

## 索引概览

| 数据类型 | Index pattern | Document ID | 说明 |
| --- | --- | --- | --- |
| View | `rum_global_view_precalculate_auto_*` | `attributes.view.id` | 按 `view.id` 聚合，增量和最终快照覆盖同一文档 |
| Session | `rum_global_session_precalculate_auto_*` | `attributes.session.id` | 按 `session.id` 聚合，增量和最终快照覆盖同一文档 |

### 类型约定

- 时间戳和耗时字段统一使用 `long`，数值单位为微秒（µs）；`date` 字段使用 `yyyy-MM-dd`。
- 公共计数字段使用 View 的标准类型 `long`。
- `close_reason` 是平台派生的窗口关闭原因，取值为 `normal` 或 `timeout`。
- View 的 `end_reason` 保留 SDK 上报的原始 `view.end_reason`；Session 没有对应的原始字段，只写入 `close_reason`。

## View 和 Session 公共字段

以下字段在两个索引中使用相同的字段名和类型。

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `time` | `long` | 预计算文档写入时间，由公共 Emitter 统一补充，单位 µs。 |
| `bk_biz_id` | `integer` | 蓝鲸业务 ID。 |
| `app_name` | `keyword` | RUM 应用名称。 |
| `attributes.session.id` | `keyword` | Session ID，用于关联同一 Session 下的事件和 View。 |
| `attributes.user.id` | `keyword` | 用户 ID，通常已脱敏。 |
| `attributes.session.has_replay` | `boolean` | Session 是否包含回放；当前协议固定为 `false`。 |
| `resource.service.name` | `keyword` | 服务名称。 |
| `resource.service.version` | `keyword` | 服务版本。 |
| `resource.deployment.environment.name` | `keyword` | 部署环境，如 `development`、`production`。 |
| `resource.telemetry.sdk.name` | `keyword` | Telemetry SDK 名称。 |
| `resource.telemetry.sdk.language` | `keyword` | Telemetry SDK 语言。 |
| `resource.telemetry.sdk.version` | `keyword` | Telemetry SDK 版本。 |
| `resource.user_agent.name` | `keyword` | 浏览器名称。 |
| `resource.user_agent.version` | `keyword` | 浏览器版本。 |
| `resource.user_agent.os.name` | `keyword` | 操作系统名称。 |
| `resource.device.type` | `keyword` | 设备类型，如 `desktop`、`mobile`、`tablet`。 |
| `attributes.network.effective_type` | `keyword` | 有效网络质量，如 `slow-2g`、`2g`、`3g`、`4g`。 |
| `action_count` | `long` | Action / Click 事件数量。 |
| `resource_count` | `long` | Resource 事件总数。 |
| `error_count` | `long` | 错误类事件数量。 |
| `request_count` | `long` | XHR / Fetch 请求数量，即 `resource.type` 为 `xhr` 或 `fetch` 的数量。 |
| `request_error_count` | `integer` | XHR / Fetch 的错误或超时数量。 |
| `long_task_count` | `long` | Long Task 事件数量。 |
| `frustration_count` | `long` | 挫败行为数量。 |
| `trace_count` | `integer` | Span Link 数量，不去重。 |
| `min_start_time` | `long` | 开始时间，单位 µs；View 取 SDK 上报的 `view.started_at`，Session 取会话内最早事件时间。 |
| `max_end_time` | `long` | 聚合对象内最晚事件时间，单位 µs。 |
| `date` | `date` | 开始时间（`min_start_time`）对应的 UTC 日期，格式 `yyyy-MM-dd`，用于日索引命名与按天筛选。 |
| `duration` | `long` | 聚合对象持续时长，单位 µs。 |
| `updated_at_ts` | `long` | 本次快照更新时间，单位 µs。 |
| `close_time` | `long` | 窗口关闭时间；增量快照为 `0`，单位 µs。 |
| `is_active` | `boolean` | 是否仍处于活动窗口；当前由 `closed` 派生。 |
| `close_reason` | `keyword` | 平台派生的窗口关闭原因：观察到 View/Session `phase=end` 为 `normal`，否则为 `timeout`。 |
| `attributes.view.loading_time` | `long` | View 加载耗时，单位 µs；Session 中表示会话内平均 View 加载耗时。 |
## View 专属字段

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `attributes.view.id` | `keyword` | View ID，同时作为 View 文档 ID 和路由键。 |
| `attributes.view.name` | `keyword` | View 名称。 |
| `attributes.view.url_template` | `keyword` | 当前 View 的 URL 路径模板，最大长度 2048。 |
| `attributes.view.loading_type` | `keyword` | View 加载类型，如首次加载或路由切换。 |
| `attributes.view.previous_url_template` | `keyword` | 前一个 View 的 URL 路径模板，最大长度 2048。 |
| `view_loading_time_source` | `keyword` | View 加载耗时来源。 |
| `end_reason` | `keyword` | SDK 原始 `view.end_reason`，保留上游语义。 |
| `version` | `long` | View 事件版本号。 |
| `web_vitals.fcp` | `long` | FCP 指标，单位 µs。 |
| `web_vitals.ttfb` | `long` | TTFB 指标，单位 µs。 |
| `web_vitals.lcp` | `long` | LCP 指标，单位 µs；Session 中为会话内最大值。 |
| `web_vitals.inp` | `long` | INP 指标，单位 µs；Session 中为会话内最大值。 |
| `web_vitals.cls` | `double` | CLS 指标；Session 中为会话内最大值。 |
## Session 专属字段

| 字段 | 类型 | 描述 |
| --- | --- | --- |
| `view_count` | `integer` | Session 内不同 `view.id` 的数量。 |
| `enter_url_template` | `keyword` | Session 入口 View 的 URL 模板，最大长度 2048。 |
| `exit_url_template` | `keyword` | Session 退出 View 的 URL 模板，最大长度 2048。 |