---
name: event
description: Event Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Event Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/event-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Domain Event** — 业务上有意义的变化需要被其他模块感知
  - 职责：business-occurrence
  - 适用复杂度门槛：3/3
- **Command Bus** — 命令的发起方与处理方需要解耦
  - 职责：command-dispatch
  - 适用复杂度门槛：3/3
  - 必需配套：command

## 完整清单

- Observer
- Event Emitter
- Pub/Sub
- Event Bus
- Domain Event
- Integration Event
- Command Bus
- Message Bus
- Event Queue
- Event Stream
- Event Sourcing
- Mediator
- Broadcast
- Reactive Stream

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
