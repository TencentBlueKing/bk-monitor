# Pattern Composition Reference

## 一个真实业务模块的组合图

```text
                    ┌───────────────┐
                    │   Facade      │
                    └───────┬───────┘
                            │
             ┌──────────────┼──────────────┐
             ↓              ↓              ↓
        Command         Strategy        State
             │              │              │
             ↓              ↓              ↓
        Application      Policy        State Machine
             │
             ↓
        Repository
             │
       ┌─────┴─────┐
       ↓           ↓
     Cache       API Adapter
       │           │
       └─────┬─────┘
             ↓
        Async Pipeline
             │
             ↓
       Retry / Timeout
             │
             ↓
        Rendering
             │
       ┌─────┴──────┐
       ↓            ↓
 Virtualization   Memoization
```

这是 Skill 应该生成的结果，而不是 "OrderPage → Strategy Pattern"。

## 正确的工作方式

```text
业务问题 → 变化点 → 边界
   ↓
State + Command + Strategy + Repository + Adapter + Facade + Event + Async + Cache + Rendering
   ↓
组合架构 → 项目现有代码映射 → 渐进式落地 → Validation
```

## 组合检查清单

- 每个模式是否有明确职责？（RULE-003）
- 是否存在职责重叠？（RULE-005 / RULE-009）
- 是否存在冗余模式？（RULE-010）
- 是否是最小充分组合？（RULE-011）
- 模式数量是否被当成质量指标？（RULE-012）
