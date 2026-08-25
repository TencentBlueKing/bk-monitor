---
name: component
description: Component Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Component Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/component-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Container / Presentational** — 数据获取逻辑与渲染逻辑纠缠，组件无法复用与测试
  - 职责：ui-logic-split
  - 适用复杂度门槛：1/3
- **Headless Component** — 同一交互行为需要多套视觉呈现
  - 职责：behavior-without-ui
  - 适用复杂度门槛：2/3
- **Compound Component** — 组件配置项爆炸，props 无法表达灵活布局
  - 职责：composable-ui
  - 适用复杂度门槛：2/3
- **Custom Hook / Composable** — 有状态逻辑在多个组件间重复
  - 职责：stateful-logic-reuse
  - 适用复杂度门槛：1/3
- **Provider / Context** — 深层组件需要访问共享依赖，逐层传递不可维护
  - 职责：scoped-dependency
  - 适用复杂度门槛：2/3
- **Error Boundary** — 局部渲染异常导致整页白屏
  - 职责：failure-containment
  - 适用复杂度门槛：1/3

## 完整清单

- Container / Presentational
- Compound Component
- Controlled Component
- Uncontrolled Component
- Render Props
- Higher-Order Component
- Custom Hook
- Composable
- Provider
- Consumer
- Slot
- Headless Component
- Polymorphic Component
- Smart / Dumb Component
- Component Adapter
- Component Facade
- Component Registry
- Dynamic Component
- Portal
- Error Boundary
- Suspense Boundary

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
