# Project Design Memory

Record architecture, domain boundaries, module ownership, state ownership and long-term design constraints here.

## retrieve-v2 search-result-panel sticky ownership

- `.field-list-sticky` 是字段设置区域 sticky owner。
- 展开态 `.field-list-sticky.is-show`：跟随趋势图/搜索栏偏移，`top: var(--offset-search-bar)`。
- 收起态 `.field-list-sticky.is-close`：跟随日志结果表头，`top: 0`，与 `.bklog-row-container.row-header` 同步。
- `.search-field-filter-new.is-close` 内部只负责按钮尺寸和视觉样式，不应承担 viewport sticky 计算。
