# Anti-Pattern Catalog

## Purpose

Name what has gone wrong, with evidence, and say how to resolve it.

Detection MUST distinguish:

- **observed** — the project demonstrably does this
- **predicted** — the composition we are about to recommend would cause this

Accusing a codebase of an anti-pattern without evidence is itself a defect.

## Catalog

### God Component

- 违反：ANTI-PATTERN-005
- 表现：单个组件同时承担取数、业务规则、状态与渲染
- 处理：按 Container/Presentational 或 Custom Hook 拆出取数与逻辑

### God Service

- 违反：ANTI-PATTERN-005
- 表现：单个 service 聚合了不相关的业务能力
- 处理：按业务能力拆分，边界对齐 feature 或限界上下文

### God Store

- 违反：ANTI-PATTERN-006
- 表现：所有状态塞进单一 store，写入方不可控
- 处理：区分服务端状态、UI 状态与真正的全局状态，就近管理

### God Facade

- 违反：ANTI-PATTERN-005
- 表现：Facade 从简化入口退化为无边界的转发层
- 处理：Facade 只暴露用例级操作，不做业务判断

### God Event Bus

- 违反：ANTI-PATTERN-007
- 表现：所有模块通信都走事件总线，调用关系不可追踪
- 处理：同层直接调用，仅跨边界的真实业务事件走总线

### God Context

- 违反：ANTI-PATTERN-006
- 表现：单个 Context 承载全部数据，任何变更触发全树重渲染
- 处理：按变更频率拆分 Context，或改用 selector 订阅

### God Hook

- 违反：ANTI-PATTERN-005
- 表现：单个 Hook 内聚了多个无关关注点
- 处理：按关注点拆分 Hook，每个只回答一个问题

### God Utility

- 违反：ANTI-PATTERN-005
- 表现：utils 成为无归属代码的垃圾桶
- 处理：把工具函数归还到它服务的业务模块

### Singleton Abuse

- 违反：ANTI-PATTERN-006
- 表现：用单例做全局可变状态而非真正的唯一实例约束
- 处理：改为显式依赖注入，让依赖关系可见可测

### Factory Abuse

- 违反：ANTI-PATTERN-003
- 表现：Factory 包装了没有变化的构造过程
- 处理：构造无变化时直接 new 或直接调用

### Observer Explosion

- 违反：ANTI-PATTERN-007
- 表现：订阅关系数量失控，无人知道谁在监听谁
- 处理：收敛订阅入口，建立事件命名与生命周期治理

### Event Spaghetti

- 违反：ANTI-PATTERN-007
- 表现：事件互相触发形成隐式控制流
- 处理：禁止事件链式触发，改为显式编排

### State Explosion

- 违反：ANTI-PATTERN-003
- 表现：布尔状态组合出大量非法状态
- 处理：用状态机或联合类型让非法状态不可表达

### Global State Abuse

- 违反：ANTI-PATTERN-006
- 表现：全局状态成为模块间默认集成方式
- 处理：就近管理状态，跨模块通过显式接口协作

### Prop Drilling

- 违反：ANTI-PATTERN-005
- 表现：中间组件被迫感知它不使用的数据
- 处理：用 Provider 提供作用域依赖，或提升状态到共同祖先

### Circular Dependency

- 违反：ANTI-PATTERN-002
- 表现：模块互相依赖，无法独立理解与测试
- 处理：提取共享抽象或反转依赖方向

### Abstraction Explosion

- 违反：ANTI-PATTERN-003
- 表现：抽象层数超过其隔离的变化数量
- 处理：删除没有对应变化点的抽象层

### Premature Abstraction

- 违反：ANTI-PATTERN-003
- 表现：为尚未出现的变化预留扩展点
- 处理：等到第二个用例出现再抽象

### Pattern Overuse

- 违反：ANTI-PATTERN-004
- 表现：模式数量被当作架构质量的证明
- 处理：按 Rule 011 收敛到最小充分组合

### Pattern Mismatch

- 违反：ANTI-PATTERN-001
- 表现：模式被用在它不解决的问题上
- 处理：回到问题本身重新选型

### Leaky Abstraction

- 违反：ANTI-PATTERN-005
- 表现：调用方仍需了解被封装的实现细节
- 处理：让抽象以调用方的语言表达，而不是实现的语言

### Repository Everywhere

- 违反：ANTI-PATTERN-001
- 表现：为没有数据访问变化的对象套上仓储层
- 处理：只在数据来源确实可能变化时引入 Repository

### Service Everywhere

- 违反：ANTI-PATTERN-001
- 表现：Service 成为默认落点而非职责划分结果
- 处理：让行为回到它所属的模型或用例中

### Adapter Everywhere

- 违反：ANTI-PATTERN-001
- 表现：为内部稳定接口也加适配层
- 处理：只在跨越外部边界处适配

### Facade Everywhere

- 违反：ANTI-PATTERN-001
- 表现：每一层都加门面，形成纯转发链
- 处理：只在子系统边界处提供门面
