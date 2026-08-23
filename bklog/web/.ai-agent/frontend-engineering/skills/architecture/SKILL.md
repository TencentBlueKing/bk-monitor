---
name: architecture
description: Architectural Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Architectural Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/architecture-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Layered Architecture** — 依赖方向混乱，业务规则散落在 UI 与基础设施中
  - 职责：dependency-direction
  - 适用复杂度门槛：2/3
- **Plugin Architecture** — 第三方或业务方需要在不改核心代码的前提下扩展能力
  - 职责：extension-surface
  - 适用复杂度门槛：3/3
  - 必需配套：registry
- **Micro Frontend** — 多团队独立开发部署同一产品
  - 职责：deployment-boundary
  - 适用复杂度门槛：3/3
  - 职责冲突：modular-monolith
- **Modular Monolith** — 需要清晰模块边界但没有独立部署诉求
  - 职责：module-boundary
  - 适用复杂度门槛：2/3
  - 职责冲突：micro-frontend
- **Unidirectional Data Flow** — 状态变更来源不明，难以追踪谁改了什么
  - 职责：data-direction
  - 适用复杂度门槛：2/3

## 完整清单

- Layered Architecture
- Clean Architecture
- Hexagonal Architecture
- Onion Architecture
- Feature-Sliced Architecture
- Modular Monolith
- Micro Frontend
- Plugin Architecture
- Event-Driven Architecture
- Pipe and Filter
- MVC
- MVP
- MVVM
- Flux
- Unidirectional Data Flow

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
