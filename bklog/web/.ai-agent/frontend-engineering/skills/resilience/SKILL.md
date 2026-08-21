---
name: resilience
description: Resilience Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Resilience Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/resilience-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Fallback / Graceful Degradation** — 依赖不可用时功能完全不可用
  - 职责：degraded-path
  - 适用复杂度门槛：1/3
- **Stale While Revalidate** — 每次都等最新数据导致体验差
  - 职责：freshness-tradeoff
  - 适用复杂度门槛：2/3
- **Rollback** — 乐观更新失败后状态不一致
  - 职责：failure-recovery
  - 适用复杂度门槛：2/3
- **Idempotency** — 重试导致重复提交
  - 职责：safe-retry
  - 适用复杂度门槛：2/3

## 完整清单

- Error Boundary
- Retry
- Backoff
- Timeout
- Circuit Breaker
- Bulkhead
- Fallback
- Graceful Degradation
- Offline First
- Offline Fallback
- Cache
- Stale While Revalidate
- Optimistic Update
- Rollback
- Recovery
- Dead Letter
- Idempotency
- Rate Limiting
- Backpressure

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
