# Scenario Pack: Design Patterns

Use this pack when implementing new features that may need a design pattern.

Workflow:
1. Analyze feature variability, lifecycle, state, extensibility and operation history.
2. Ask pattern interview questions if constraints are unclear.
3. Select the simplest sufficient pattern.
4. Produce a concrete landing plan before coding.
5. Record the decision and tradeoffs in Memory/ADR.

Pattern map:
- Strategy: interchangeable algorithms/providers
- Factory: complex object creation
- Registry: plugin or extension point
- State Machine: complex lifecycle and illegal states
- Command: undo/redo/replay/audit
- Pipeline: multi-stage processing
- Observer: decoupled event notification
- Adapter: third-party or compatibility boundary
- Composition: UI behavior composition
