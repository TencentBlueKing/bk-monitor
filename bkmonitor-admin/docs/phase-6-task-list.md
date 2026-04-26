# 第六期计划：Custom Report 与 APM 管理视图

## 目标

第六期面向两类和 DataSource、ResultTable 紧密相关的资源：

- `metadata.custom_report`：统一展示自定义指标、自定义事件、日志三类自定义上报资源。
- `APM`：展示 APM 应用、关联 DataSource、ResultTable、Service 和 Topo 信息。

本期仍以只读信息展示为主，先完成页面、RPC 契约和 mock 验收，后续再补真实后端 RPC 实现与 AI 辅助排障能力。

## 设计原则

- 列表页只展示定位、状态、数量和核心关联信息，不展开大字段。
- `TimeSeriesMetric` 与 `ResultTableField` 一样可能非常大，只允许通过独立分页接口懒加载。
- 自定义指标、自定义事件、日志统一使用 `custom_report` 页面模型，但保留原始 `report_type`，避免把线上差异隐藏掉。
- 自定义指标/事件需要显式展示来源关系：来自 `monitor_web` 自定义上报页面，或被 APM 关联使用。
- APM 详情以应用为中心，优先展示 DataSource、ResultTable、Service、Topo Node/Relation 的关系。
- 页面跳转关系必须围绕现有 DataSource、ResultTable、DataLink 视图建立。

## 页面任务

| 状态 | 任务 | 说明 |
| --- | --- | --- |
| Done | 新增 `Custom Report` 导航与列表页 | 支持类型、业务、DataId、TableId、名称、来源和 APM 关联过滤 |
| Done | 新增 `Custom Report` 详情页 | 展示 group、关联 DataSource、ResultTable、monitor_web/APM 关系 |
| Done | 新增 TimeSeriesMetric 分页展示 | 仅自定义指标详情页加载，默认 20 条 |
| Done | 新增 `APM` 导航与应用列表页 | 支持业务、应用名、DataId、TableId、状态过滤 |
| Done | 新增 `APM` 详情页 | 展示 DataSource、ResultTable、Service、Topo Node/Relation |
| Done | 接入 mock 数据验收 | 无后端 RPC 时可通过 mock fallback 查看完整页面 |

## RPC 任务

| 状态 | 函数 | 说明 |
| --- | --- | --- |
| Planned | `admin.custom_report.list` | 三类自定义上报资源列表 |
| Planned | `admin.custom_report.detail` | 单个自定义上报资源详情 |
| Planned | `admin.custom_report.metric_list` | TimeSeriesMetric 分页查询 |
| Planned | `admin.apm.application_list` | APM 应用列表 |
| Planned | `admin.apm.application_detail` | APM 应用详情 |
| Planned | `admin.apm.service_list` | APM Service 分页查询 |
| Planned | `admin.apm.topo` | APM Topo Node/Relation 查询 |

## 验收记录

- 2026-04-26：完成前端页面、mock 数据、导航路由与 RPC operation 映射。
