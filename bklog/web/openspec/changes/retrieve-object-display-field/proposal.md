# Proposal: Hide object tree chrome in display fields

## Why

日志检索左侧「显示字段」里，Object 字段会带出下拉箭头和子节点数量。该区域只应展示已选字段本身；树展开只属于「可选字段」。

## What Changes

- 显示字段列表不再渲染 Object 下拉与子节点数量。
- 可选字段（及同结构的内置字段树）继续用 `isFieldObject` 展示树元信息。
- 显示字段的显隐切换保持可用。

## TAPD

- story: 1010158081138975895
- short_id: 138975895
