# retrieve-display-fields

## ADDED Requirements

### Requirement: Display fields hide object tree chrome

显示字段中的 Object 字段不得展示下拉箭头和子节点数量。树展开仅在可选字段（`isFieldObject`）启用。

#### Scenario: Object field in display list

- **WHEN** 字段出现在显示字段列表且未标记为对象树节点
- **THEN** 不渲染子节点数量和展开箭头

#### Scenario: Object field in optional tree

- **WHEN** 字段在可选字段树中以 `isFieldObject` 渲染且存在子节点
- **THEN** 继续展示子节点数量和展开箭头
