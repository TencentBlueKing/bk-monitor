# Anti-Patterns Reference

**ANTI-PATTERN-001** A pattern used outside its problem domain is a potential anti-pattern.

**ANTI-PATTERN-002** Multiple patterns with overlapping responsibility MUST be reviewed.

**ANTI-PATTERN-003** A pattern that increases complexity without reducing meaningful change cost MUST be rejected.

**ANTI-PATTERN-004** Pattern count MUST NOT justify architecture quality.

**ANTI-PATTERN-005** Generic abstractions MUST NOT hide business semantics.

**ANTI-PATTERN-006** Global state MUST NOT become the default integration mechanism.

**ANTI-PATTERN-007** Event Bus MUST NOT replace normal function calls without architectural justification.

## 目录

| 反模式 | 违反 | 表现 | 处理 |
| --- | --- | --- | --- |
| God Component | ANTI-PATTERN-005 | 单个组件同时承担取数、业务规则、状态与渲染 | 按 Container/Presentational 或 Custom Hook 拆出取数与逻辑 |
| God Service | ANTI-PATTERN-005 | 单个 service 聚合了不相关的业务能力 | 按业务能力拆分，边界对齐 feature 或限界上下文 |
| God Store | ANTI-PATTERN-006 | 所有状态塞进单一 store，写入方不可控 | 区分服务端状态、UI 状态与真正的全局状态，就近管理 |
| God Facade | ANTI-PATTERN-005 | Facade 从简化入口退化为无边界的转发层 | Facade 只暴露用例级操作，不做业务判断 |
| God Event Bus | ANTI-PATTERN-007 | 所有模块通信都走事件总线，调用关系不可追踪 | 同层直接调用，仅跨边界的真实业务事件走总线 |
| God Context | ANTI-PATTERN-006 | 单个 Context 承载全部数据，任何变更触发全树重渲染 | 按变更频率拆分 Context，或改用 selector 订阅 |
| God Hook | ANTI-PATTERN-005 | 单个 Hook 内聚了多个无关关注点 | 按关注点拆分 Hook，每个只回答一个问题 |
| God Utility | ANTI-PATTERN-005 | utils 成为无归属代码的垃圾桶 | 把工具函数归还到它服务的业务模块 |
| Singleton Abuse | ANTI-PATTERN-006 | 用单例做全局可变状态而非真正的唯一实例约束 | 改为显式依赖注入，让依赖关系可见可测 |
| Factory Abuse | ANTI-PATTERN-003 | Factory 包装了没有变化的构造过程 | 构造无变化时直接 new 或直接调用 |
| Observer Explosion | ANTI-PATTERN-007 | 订阅关系数量失控，无人知道谁在监听谁 | 收敛订阅入口，建立事件命名与生命周期治理 |
| Event Spaghetti | ANTI-PATTERN-007 | 事件互相触发形成隐式控制流 | 禁止事件链式触发，改为显式编排 |
| State Explosion | ANTI-PATTERN-003 | 布尔状态组合出大量非法状态 | 用状态机或联合类型让非法状态不可表达 |
| Global State Abuse | ANTI-PATTERN-006 | 全局状态成为模块间默认集成方式 | 就近管理状态，跨模块通过显式接口协作 |
| Prop Drilling | ANTI-PATTERN-005 | 中间组件被迫感知它不使用的数据 | 用 Provider 提供作用域依赖，或提升状态到共同祖先 |
| Circular Dependency | ANTI-PATTERN-002 | 模块互相依赖，无法独立理解与测试 | 提取共享抽象或反转依赖方向 |
| Abstraction Explosion | ANTI-PATTERN-003 | 抽象层数超过其隔离的变化数量 | 删除没有对应变化点的抽象层 |
| Premature Abstraction | ANTI-PATTERN-003 | 为尚未出现的变化预留扩展点 | 等到第二个用例出现再抽象 |
| Pattern Overuse | ANTI-PATTERN-004 | 模式数量被当作架构质量的证明 | 按 Rule 011 收敛到最小充分组合 |
| Pattern Mismatch | ANTI-PATTERN-001 | 模式被用在它不解决的问题上 | 回到问题本身重新选型 |
| Leaky Abstraction | ANTI-PATTERN-005 | 调用方仍需了解被封装的实现细节 | 让抽象以调用方的语言表达，而不是实现的语言 |
| Repository Everywhere | ANTI-PATTERN-001 | 为没有数据访问变化的对象套上仓储层 | 只在数据来源确实可能变化时引入 Repository |
| Service Everywhere | ANTI-PATTERN-001 | Service 成为默认落点而非职责划分结果 | 让行为回到它所属的模型或用例中 |
| Adapter Everywhere | ANTI-PATTERN-001 | 为内部稳定接口也加适配层 | 只在跨越外部边界处适配 |
| Facade Everywhere | ANTI-PATTERN-001 | 每一层都加门面，形成纯转发链 | 只在子系统边界处提供门面 |

## 检测原则

- **observed** 与 **predicted** 必须区分：前者是项目确实存在的问题，后者是我们即将
  给出的建议会造成的问题。
- 没有证据的反模式指控本身就是缺陷。
- 对自己提出的组合做审计，是 ANTI-PATTERN-003 / 004 唯一诚实的执行方式。
