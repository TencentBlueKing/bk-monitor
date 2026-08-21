---
name: structural
description: Structural Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Structural Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/structural-rules.md`（8 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Adapter** — 外部 API 形状与内部模型不一致
  - 职责：external-boundary
  - 适用复杂度门槛：2/3
- **Anti-Corruption Layer** — 外部模型正在污染内部领域模型
  - 职责：model-protection
  - 适用复杂度门槛：3/3
  - 必需配套：adapter
- **Facade** — 调用方需要面对过多子系统细节
  - 职责：entry-surface
  - 适用复杂度门槛：2/3
- **Composite** — 需要以统一方式处理叶子与容器
  - 职责：tree-structure
  - 适用复杂度门槛：2/3
- **Decorator** — 需要在不改原实现的前提下叠加行为
  - 职责：behavior-augmentation
  - 适用复杂度门槛：2/3
- **Proxy** — 访问需要被拦截：懒加载、鉴权、埋点
  - 职责：access-control
  - 适用复杂度门槛：2/3

## 完整清单

- Adapter
- Bridge
- Composite
- Decorator
- Facade
- Flyweight
- Proxy
- Wrapper
- Module
- Layer
- Anti-Corruption Layer
- Data Mapper
- DTO
- View Model

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
