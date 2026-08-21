---
name: performance
description: Performance Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Performance Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/performance-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Memoization** — 相同输入被反复计算
  - 职责：recompute-avoidance
  - 适用复杂度门槛：2/3
- **Code Splitting** — 首包体积过大
  - 职责：bundle-size
  - 适用复杂度门槛：1/3
- **Batching** — 细碎更新触发过多渲染或请求
  - 职责：update-coalescing
  - 适用复杂度门槛：2/3
- **Worker Offloading** — 重计算阻塞主线程
  - 职责：main-thread-relief
  - 适用复杂度门槛：3/3

## 完整清单

- Memoization
- Caching
- Lazy Loading
- Code Splitting
- Tree Shaking
- Prefetching
- Preloading
- Virtualization
- Windowing
- Batching
- Debouncing
- Throttling
- Object Pooling
- Flyweight
- Structural Sharing
- Immutable Update
- Incremental Computation
- Incremental Rendering
- Worker Offloading
- WebAssembly
- Offscreen Processing
- Resource Pool
- Connection Pool
- Backpressure

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
