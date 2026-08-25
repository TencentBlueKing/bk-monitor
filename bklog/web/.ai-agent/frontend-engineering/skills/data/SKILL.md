---
name: data
description: Data Access Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Data Access Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/data-rules.md`（10 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Repository** — 数据访问细节散落在组件与业务代码中
  - 职责：data-access
  - 适用复杂度门槛：2/3
- **Data Mapper** — 接口结构与视图模型形状不一致
  - 职责：model-translation
  - 适用复杂度门槛：1/3
- **Cache Aside** — 重复请求相同数据造成浪费
  - 职责：read-cache
  - 适用复杂度门槛：2/3
- **Normalization** — 同一实体在多处冗余存储导致不一致
  - 职责：entity-store
  - 适用复杂度门槛：3/3
- **Pagination** — 一次性拉取全量数据不可行
  - 职责：bounded-fetch
  - 适用复杂度门槛：1/3

## 完整清单

- Repository
- DAO
- Data Mapper
- Active Record
- Unit of Work
- Identity Map
- Cache Aside
- Read Through
- Write Through
- Write Behind
- CQRS
- DTO
- Serializer
- Deserializer
- Normalization
- Denormalization
- Pagination
- Cursor
- Lazy Loading
- Prefetch
- Batching

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
