---
name: creational
description: Creational Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Creational Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/creational-rules.md`（8 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Factory** — 创建逻辑随类型变化，调用方不应关心具体构造
  - 职责：object-creation
  - 适用复杂度门槛：2/3
- **Builder** — 对象构造步骤多、可选参数多
  - 职责：complex-construction
  - 适用复杂度门槛：2/3
- **Registry** — 能力需要被注册、查找与替换
  - 职责：extension-lookup
  - 适用复杂度门槛：2/3
- **Dependency Injection** — 依赖硬编码导致无法替换与测试
  - 职责：dependency-wiring
  - 适用复杂度门槛：2/3
  - 职责冲突：service-locator
- **Service Locator** — 集中查找依赖，但会隐藏依赖关系
  - 职责：dependency-lookup
  - 适用复杂度门槛：3/3
  - 职责冲突：dependency-injection
- **Singleton** — 确实只能存在一个实例（连接池、全局调度器）
  - 职责：single-instance
  - 适用复杂度门槛：3/3

## 完整清单

- Factory Method
- Abstract Factory
- Builder
- Prototype
- Singleton
- Object Pool
- Dependency Injection
- Dependency Injection Container
- Service Locator
- Registry
- Factory Function
- Functional Factory

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
