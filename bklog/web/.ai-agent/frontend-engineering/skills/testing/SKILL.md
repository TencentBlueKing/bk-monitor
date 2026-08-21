---
name: testing
description: Testing Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Testing Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/testing-rules.md`（8 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Test Double** — 测试依赖真实外部系统导致缓慢与不稳定
  - 职责：dependency-isolation
  - 适用复杂度门槛：1/3
- **Contract Test** — 前后端接口契约变更无人察觉
  - 职责：boundary-agreement
  - 适用复杂度门槛：2/3
- **Characterization Test** — 重构遗留代码时缺少行为基准
  - 职责：legacy-safety-net
  - 适用复杂度门槛：1/3

## 完整清单

- Test Pyramid
- Testing Trophy
- Unit Test
- Component Test
- Integration Test
- Contract Test
- E2E
- Snapshot
- Golden Master
- Characterization Test
- Property-Based Testing
- Mutation Testing
- Test Double
- Mock
- Stub
- Spy
- Fake
- Fixture
- Test Data Builder
- Object Mother
- Page Object
- Screenplay Pattern
- Contract Testing

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
