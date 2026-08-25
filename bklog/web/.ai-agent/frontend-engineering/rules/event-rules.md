# Event Patterns

覆盖 14 个模式：

- Observer
- Event Emitter
- Pub/Sub
- Event Bus
- Domain Event
- Integration Event
- Command Bus
- Message Bus
- Event Queue
- Event Stream
- Event Sourcing
- Mediator
- Broadcast
- Reactive Stream

## Rules

EVENT-001
Event MUST have a clearly defined owner.

EVENT-002
Event name MUST represent a meaningful occurrence or command.

EVENT-003
Event payload MUST have a stable contract.

EVENT-004
Event listeners MUST define lifecycle.

EVENT-005
Global Event Bus SHOULD NOT become uncontrolled application state.

EVENT-006
Events MUST NOT replace direct function calls without a coupling problem.

EVENT-007
Event-driven flows MUST provide tracing capability.

EVENT-008
Event ordering MUST be defined where required.

EVENT-009
Event duplication MUST be considered.

EVENT-010
Event-driven architecture MUST define failure semantics.
