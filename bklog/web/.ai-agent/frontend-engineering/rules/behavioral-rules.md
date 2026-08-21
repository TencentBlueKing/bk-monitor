# Behavioral Patterns

覆盖 19 个模式：

- Strategy
- State
- Command
- Observer
- Mediator
- Chain of Responsibility
- Template Method
- Visitor
- Iterator
- Interpreter
- Memento
- Null Object
- Policy
- Specification
- Rule Engine
- Pipeline
- Middleware
- Hook
- Callback

## Rules

BEHAVIORAL-001
Strategy isolates interchangeable behavior.

BEHAVIORAL-002
State models behavior that changes according to state.

BEHAVIORAL-003
Strategy and State MUST NOT be confused.

BEHAVIORAL-004
Command encapsulates an action.

BEHAVIORAL-005
Command SHOULD be considered for Undo/Redo.

BEHAVIORAL-006
Observer MUST NOT create uncontrolled event chains.

BEHAVIORAL-007
Mediator SHOULD reduce direct peer-to-peer coupling.

BEHAVIORAL-008
Chain of Responsibility SHOULD be used for ordered processing.

BEHAVIORAL-009
Pipeline MUST explicitly define stage contracts.

BEHAVIORAL-010
Middleware MUST have a clear execution boundary.

BEHAVIORAL-011
Rule Engine SHOULD be used when rules change independently from orchestration.

BEHAVIORAL-012
Specification SHOULD represent reusable business predicates.
