# Creational Patterns

覆盖 12 个模式：

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

## Rules

CREATIONAL-001
Factory MUST encapsulate meaningful creation variation.

CREATIONAL-002
Factory MUST NOT wrap trivial constructors.

CREATIONAL-003
Singleton MUST NOT be used merely for global access.

CREATIONAL-004
Global mutable state MUST NOT be disguised as Singleton.

CREATIONAL-005
DI MUST have a clear dependency boundary.

CREATIONAL-006
Service Locator SHOULD be avoided when it hides dependencies.

CREATIONAL-007
Builder SHOULD be used when object construction is genuinely complex.

CREATIONAL-008
Prototype SHOULD be used only when cloning semantics are meaningful.
