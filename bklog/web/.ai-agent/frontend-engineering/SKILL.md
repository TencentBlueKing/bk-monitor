---
name: frontend-engineering
description: 前端设计模式工程体系。显式启用；先识别问题，再选出最小充分的模式组合。
---

# Frontend Architecture & Design Pattern System

> 设计模式是可组合能力，不是项目架构。

## 第一原则

**PATTERN-SYSTEM-001**：一个前端项目不能通过"选定一个设计模式并全局套用"来设计。
必须先识别问题与变化点，再为每个问题选出承担明确职责的模式，并检查组合的冲突、
冗余与总复杂度。

**PATTERN-SYSTEM-002**：没有用设计模式不是缺陷。只有当具体问题、变化点、架构边界
或可度量的约束成立时，才引入模式。

## 执行顺序

```text
User Request
   ↓
Pattern Gate ──── disabled ──→ 不加载任何 Pattern Skill
   ↓ enabled
Pattern Discovery      识别问题，不点名模式
   ↓
Pattern Selection      评分候选
   ↓
Pattern Composition    组合、冲突、冗余、最小充分
   ↓
Anti-Pattern Audit     审计项目，也审计我们自己的建议
   ↓
Validation
```

## 加载顺序

1. `.ai-agent/frontend-engineering/rules/pattern-gate.md` — 只有它可以在启用判定前读取
2. `.ai-agent/frontend-engineering/rules/pattern-composition.md`
3. `.ai-agent/frontend-engineering/rules/pattern-selection.md`
4. `.ai-agent/frontend-engineering/rules/pattern-boundary.md`、`pattern-overengineering.md`、`anti-pattern.md`
5. 命中的模式域规则：`.ai-agent/frontend-engineering/rules/<domain>-rules.md`

不要预读全部规则。命中哪个域读哪个。

## 16 个模式域

- `architecture` Architectural Patterns（15 个模式，10 条规则）
- `creational` Creational Patterns（12 个模式，8 条规则）
- `structural` Structural Patterns（14 个模式，8 条规则）
- `behavioral` Behavioral Patterns（19 个模式，12 条规则）
- `state` State Management Patterns（20 个模式，12 条规则）
- `component` Component Patterns（21 个模式，10 条规则）
- `data` Data Access Patterns（21 个模式，10 条规则）
- `async` Async Patterns（28 个模式，12 条规则）
- `rendering` Rendering Patterns（23 个模式，10 条规则）
- `performance` Performance Patterns（24 个模式，10 条规则）
- `resilience` Resilience Patterns（19 个模式，10 条规则）
- `integration` Integration Patterns（21 个模式，9 条规则）
- `module` Module Patterns（16 个模式，8 条规则）
- `event` Event Patterns（14 个模式，10 条规则）
- `testing` Testing Patterns（23 个模式，8 条规则）
- `migration` Migration Patterns（14 个模式，8 条规则）

## 与 DDD 的关系

DDD 决定业务模型和边界，设计模式负责解决这些边界内部的具体变化、协作、状态、创建、
通信、数据访问和性能问题。映射见 `.ai-agent/frontend-engineering/skills/ddd-pattern-bridge/SKILL.md`。

## 命令

```bash
aafe pattern gate "<request>"      # 是否启用
aafe pattern discover "<request>"  # 只识别问题
aafe pattern select "<request>"    # 评分 + 组合
aafe pattern audit "<request>"     # 反模式审计
aafe pattern catalog               # 模式目录
```
