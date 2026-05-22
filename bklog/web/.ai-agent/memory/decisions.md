# Architecture Decisions Memory

Record durable decisions, alternatives, tradeoffs and consequences here.

## 2026-05-21 retrieve-v2 字段设置收起态吸顶

- 背景：`field-filter.vue` 收起态入口在纵向滚动后定位不正确，原因是按钮模板内联 `position: absolute; top: 64px; transform: translate(-50%, -50%)` 覆盖样式，同时外层 `.field-list-sticky` 仅在展开态 `.is-show` 时 sticky。
- 决策：展开态继续使用 `.field-list-sticky.is-show { top: var(--offset-search-bar) }` 对齐字段设置面板；收起态新增 `.field-list-sticky.is-close { position: sticky; top: 0 }`，吸顶位置同步日志结果表头 `.bklog-row-container.row-header { top: 0; height: 32px }`。
- 实现：移除 `field-filter.vue` 内联定位，把默认按钮定位沉到 `field-filter.scss`；收起态按钮 `top: 16px; left: 0`，使 24px 按钮中心对齐 row-header 32px 高度中线。
- 约束：不要把展开态 `var(--offset-search-bar)` 复用于收起态，否则纵向滚动结果区时收起入口会和 row-header 错位。
