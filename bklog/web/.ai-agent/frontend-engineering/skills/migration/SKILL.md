---
name: migration
description: Migration Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Migration Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/migration-rules.md`（8 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Strangler Fig** — 旧系统无法一次性替换
  - 职责：incremental-replacement
  - 适用复杂度门槛：2/3
  - 必需配套：characterization-test
- **Branch by Abstraction** — 需要在主干上替换实现而不长期拉分支
  - 职责：in-place-swap
  - 适用复杂度门槛：2/3
- **Feature Toggle** — 新旧实现需要可随时切换与灰度
  - 职责：runtime-switch
  - 适用复杂度门槛：1/3
- **Compatibility Layer** — 迁移期间新旧模型必须共存
  - 职责：legacy-bridge
  - 适用复杂度门槛：2/3
  - 必需配套：adapter

## 完整清单

- Strangler Fig
- Branch by Abstraction
- Parallel Run
- Anti-Corruption Layer
- Facade Migration
- Adapter Migration
- Incremental Migration
- Feature Toggle
- Dark Launch
- Shadow Traffic
- Dual Write
- Read Migration
- Compatibility Layer
- Modularization

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
