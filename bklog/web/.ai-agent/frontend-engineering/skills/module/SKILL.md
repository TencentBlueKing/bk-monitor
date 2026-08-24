---
name: module
description: Module Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Module Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/module-rules.md`（8 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Feature Module** — 按技术类型分目录导致一个需求改十个文件夹
  - 职责：feature-boundary
  - 适用复杂度门槛：2/3
- **Public API / Barrel** — 模块内部实现被外部随意引用
  - 职责：module-surface
  - 适用复杂度门槛：1/3
- **Dynamic Import** — 低频模块被打进首包
  - 职责：deferred-load
  - 适用复杂度门槛：1/3
- **Module Federation** — 多个独立构建的应用需要运行时共享模块
  - 职责：runtime-sharing
  - 适用复杂度门槛：3/3

## 完整清单

- ES Module
- Namespace
- Barrel
- Facade Module
- Feature Module
- Domain Module
- Layer Module
- Dependency Injection
- Plugin
- Registry
- Dynamic Import
- Module Federation
- Micro Frontend
- Package Boundary
- Public API
- Internal API

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
