# Component Patterns

覆盖 21 个模式：

- Container / Presentational
- Compound Component
- Controlled Component
- Uncontrolled Component
- Render Props
- Higher-Order Component
- Custom Hook
- Composable
- Provider
- Consumer
- Slot
- Headless Component
- Polymorphic Component
- Smart / Dumb Component
- Component Adapter
- Component Facade
- Component Registry
- Dynamic Component
- Portal
- Error Boundary
- Suspense Boundary

## Rules

COMPONENT-001
Components SHOULD have explicit responsibility boundaries.

COMPONENT-002
Business logic SHOULD NOT be duplicated across components.

COMPONENT-003
Container / Presentational separation SHOULD only be introduced when it reduces complexity.

COMPONENT-004
Compound Components SHOULD be used for coordinated component APIs.

COMPONENT-005
Controlled Components SHOULD be preferred when state ownership must remain external.

COMPONENT-006
Headless Components SHOULD separate behavior from presentation.

COMPONENT-007
Hooks / Composables MUST NOT become unbounded service containers.

COMPONENT-008
Provider MUST have a clearly defined dependency scope.

COMPONENT-009
Component abstractions MUST be driven by repeated variation.

COMPONENT-010
Do not create a component abstraction for a single usage without meaningful reuse value.
