---
name: rendering
description: Rendering Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Rendering Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/rendering-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Virtualization** — 长列表一次性渲染导致卡顿
  - 职责：large-list
  - 适用复杂度门槛：2/3
- **Server-Side Rendering** — 首屏时间与 SEO 不达标
  - 职责：first-paint
  - 适用复杂度门槛：3/3
- **Progressive Hydration** — 整页 hydration 阻塞交互
  - 职责：interaction-readiness
  - 适用复杂度门槛：3/3
- **Skeleton / Placeholder** — 加载期间布局跳动、白屏感强
  - 职责：perceived-loading
  - 适用复杂度门槛：1/3

## 完整清单

- CSR
- SSR
- SSG
- ISR
- Hydration
- Partial Hydration
- Progressive Hydration
- Streaming
- Islands Architecture
- Virtualization
- Windowing
- Incremental Rendering
- Progressive Rendering
- Lazy Rendering
- Offscreen Rendering
- Canvas Rendering
- WebGL Rendering
- Worker Rendering
- Double Buffering
- Layered Rendering
- Skeleton
- Placeholder
- Optimistic Rendering

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
