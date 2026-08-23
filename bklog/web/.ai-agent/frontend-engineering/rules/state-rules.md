# State Management Patterns

覆盖 20 个模式：

- Local State
- Lifted State
- Global State
- Derived State
- Server State
- Finite State Machine
- State Machine
- Reducer
- Event Sourcing
- CQRS
- Reactive State
- Observable State
- Actor Model
- Store
- Selector
- Command State
- Snapshot
- Undo/Redo
- Optimistic State
- Transactional State

## Rules

STATE-001
State MUST have an explicit ownership boundary.

STATE-002
Do not globalize state merely because multiple components access it.

STATE-003
Derived state SHOULD NOT be duplicated as independent mutable state.

STATE-004
Server state SHOULD NOT automatically become client global state.

STATE-005
State transitions MUST be explicit for complex workflows.

STATE-006
Finite State Machine SHOULD be considered for state-heavy UI workflows.

STATE-007
Reducer MUST remain deterministic where its architectural role requires it.

STATE-008
Selectors SHOULD prevent unnecessary state coupling.

STATE-009
Optimistic state MUST define rollback behavior.

STATE-010
Undo/Redo MUST define history boundaries.

STATE-011
Event Sourcing MUST NOT be introduced simply because events exist.

STATE-012
CQRS MUST NOT be introduced merely because read/write operations differ.
