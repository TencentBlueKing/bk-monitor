# Frontend Architecture Reference

## 三个顶级能力

```text
Frontend Engineering
│
├── DDD System            业务模型 / 边界 / 领域行为
├── Design Pattern System 变化隔离 / 协作 / 状态 / 创建 / 数据 / 异步
└── Architecture System   模块边界 / 依赖方向 / 技术架构
```

## 组合方式

```text
            Frontend Engineering
                   │
     ┌─────────────┼─────────────┐
     ↓             ↓             ↓
    DDD       Architecture    Patterns
     └─────────────┼─────────────┘
                   ↓
          Pattern Composition
                   ↓
           Target Architecture
                   ↓
            Existing Project
                   ↓
              Code Mapping
                   ↓
                Refactor
                   ↓
              Validation
```

## DDD → Pattern 映射

| DDD 构造块 | 候选模式 | 承担的职责 |
| --- | --- | --- |
| Bounded Context | Feature Module, Public API | 模块 / 特性边界 |
| Aggregate | State Machine, Command, Repository | 一致性边界内的状态、操作与持久化 |
| Domain Service | Strategy, Specification | 独立于模型变化的业务策略 |
| Domain Event | Domain Event, Observer, Pub/Sub | 跨边界传播业务事实 |
| Application Service | Facade, Mediator | 用例入口与协作编排 |

映射是候选而非结论：Domain Service 只有在确实存在多种策略时才成为 Strategy。
