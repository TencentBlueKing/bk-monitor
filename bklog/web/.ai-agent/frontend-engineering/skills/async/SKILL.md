---
name: async
description: Async Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Async Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/async-rules.md`（12 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Debounce** — 高频输入触发过多请求或计算
  - 职责：input-rate-limit
  - 适用复杂度门槛：1/3
- **Throttle** — 高频事件导致渲染或计算压力
  - 职责：event-rate-limit
  - 适用复杂度门槛：1/3
- **Cancellation** — 过期请求覆盖了最新结果
  - 职责：stale-response
  - 适用复杂度门槛：1/3
- **Retry** — 瞬时故障导致请求失败
  - 职责：transient-failure
  - 适用复杂度门槛：1/3
  - 必需配套：timeout
- **Timeout** — 请求可能永远挂起
  - 职责：bounded-wait
  - 适用复杂度门槛：1/3
- **Circuit Breaker** — 持续失败的下游拖垮整个前端
  - 职责：failure-isolation
  - 适用复杂度门槛：3/3
  - 必需配套：fallback
- **Request Deduplication** — 同一请求被并发发起多次
  - 职责：duplicate-suppression
  - 适用复杂度门槛：2/3
- **Concurrency Limit** — 并发过高压垮浏览器或服务端
  - 职责：parallel-bound
  - 适用复杂度门槛：2/3

## 完整清单

- Promise
- Async/Await
- Future
- Observable
- Reactive Stream
- Pipeline
- Queue
- Scheduler
- Debounce
- Throttle
- Cancellation
- Retry
- Backoff
- Timeout
- Circuit Breaker
- Bulkhead
- Concurrency Limit
- Request Deduplication
- Request Coalescing
- Race Prevention
- Latest Wins
- First Wins
- Sequential Execution
- Parallel Execution
- Waterfall
- Prefetch
- Background Task
- Worker

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
