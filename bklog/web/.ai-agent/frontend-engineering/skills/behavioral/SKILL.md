---
name: behavioral
description: Behavioral Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Behavioral Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/behavioral-rules.md`（12 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Strategy** — 同一能力存在多种可替换实现，需要运行时选择或后续扩展
  - 职责：algorithm-variation
  - 适用复杂度门槛：2/3
- **State Machine** — 状态多、流转规则明确、非法状态必须被禁止
  - 职责：workflow-state
  - 适用复杂度门槛：2/3
  - 职责冲突：reducer
- **Command** — 用户操作需要记录、回放、撤销、重做或审计
  - 职责：user-operation
  - 适用复杂度门槛：2/3
- **Observer** — 一处变化需要通知多个订阅方，发布方不应依赖订阅方
  - 职责：change-notification
  - 适用复杂度门槛：2/3
  - 职责冲突：event-bus
- **Mediator** — 多个组件两两通信导致网状依赖
  - 职责：interaction-hub
  - 适用复杂度门槛：3/3
  - 职责冲突：event-bus
- **Chain of Responsibility** — 请求需要按顺序交给可能处理它的多个处理者
  - 职责：sequential-handling
  - 适用复杂度门槛：3/3
- **Pipeline** — 任务由稳定的多个阶段串联，每阶段可插拔或可观测
  - 职责：staged-processing
  - 适用复杂度门槛：2/3
- **Specification** — 业务判定条件被复制粘贴到多处
  - 职责：reusable-predicate
  - 适用复杂度门槛：3/3

## 完整清单

- Strategy
- State
- Command
- Observer
- Mediator
- Chain of Responsibility
- Template Method
- Visitor
- Iterator
- Interpreter
- Memento
- Null Object
- Policy
- Specification
- Rule Engine
- Pipeline
- Middleware
- Hook
- Callback

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
