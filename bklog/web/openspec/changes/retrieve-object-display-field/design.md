# Design

## Approach

`FieldItem` 当前用 `children.length || children_count` 决定是否画 badge/expand，显示字段虽未走 `bigTreeRender`，但 Object 元数据仍带 `children_count`，因此会误展示。

抽离 `shouldShowObjectFieldTreeMeta`：仅当 `isFieldObject === true` 且子节点数 > 0 时展示。显示字段不传 `isFieldObject`，默认 false。

## Boundaries

- Presentation only: `field-filter-comp/field-item`。
- 不改 store / field tree / 显示字段显隐协议。
- 内置字段仍走 `bigTreeRender`，与可选字段同一树通道。

## Decomposition

1. 纯函数判断树元信息是否展示。
2. `FieldItem` 接入该判断。
3. node:test 覆盖显示字段 / 可选字段边界。
