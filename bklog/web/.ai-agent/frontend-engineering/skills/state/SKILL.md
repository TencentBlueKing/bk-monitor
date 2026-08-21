---
name: state
description: State Management Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# State Management Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/state-rules.md`（12 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Reducer** — 状态更新分散，难以追踪与测试
  - 职责：state-transition
  - 适用复杂度门槛：2/3
  - 职责冲突：state-machine
- **Server State** — 服务端数据被当作本地状态手工同步
  - 职责：remote-cache
  - 适用复杂度门槛：2/3
  - 职责冲突：global-state
- **Global State** — 跨页面共享的少量真正全局状态
  - 职责：shared-state
  - 适用复杂度门槛：3/3
  - 职责冲突：server-state
- **Lifted State** — 少数兄弟组件需要共享状态
  - 职责：local-sharing
  - 适用复杂度门槛：1/3
- **Derived State** — 派生数据被冗余存储导致不一致
  - 职责：computed-view
  - 适用复杂度门槛：1/3
- **Undo/Redo** — 用户需要撤销与重做操作
  - 职责：history-navigation
  - 适用复杂度门槛：2/3
  - 必需配套：command
- **Optimistic State** — 交互需要立即反馈，不等服务端确认
  - 职责：perceived-latency
  - 适用复杂度门槛：2/3
  - 必需配套：rollback
- **Event Sourcing** — 必须保留状态变更的完整历史
  - 职责：append-only-history
  - 适用复杂度门槛：3/3
  - 必需配套：domain-event
- **CQRS** — 读模型与写模型的形状和负载差异极大
  - 职责：read-write-split
  - 适用复杂度门槛：3/3

## 完整清单

- Local State
- Lifted State
- Global State
- Derived State
- Server State
- Finite State Machine
- State Machine
- Reducer
- Event Sourcing
- CQRS
- Reactive State
- Observable State
- Actor Model
- Store
- Selector
- Command State
- Snapshot
- Undo/Redo
- Optimistic State
- Transactional State

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
