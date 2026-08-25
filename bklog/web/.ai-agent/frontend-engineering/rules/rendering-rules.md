# Rendering Patterns

覆盖 23 个模式：

- CSR
- SSR
- SSG
- ISR
- Hydration
- Partial Hydration
- Progressive Hydration
- Streaming
- Islands Architecture
- Virtualization
- Windowing
- Incremental Rendering
- Progressive Rendering
- Lazy Rendering
- Offscreen Rendering
- Canvas Rendering
- WebGL Rendering
- Worker Rendering
- Double Buffering
- Layered Rendering
- Skeleton
- Placeholder
- Optimistic Rendering

## Rules

RENDER-001
Rendering strategy MUST be selected according to data volume, interaction and runtime constraints.

RENDER-002
Virtualization SHOULD be considered for large collections.

RENDER-003
Virtualization MUST NOT be introduced where the data set is small and complexity outweighs benefit.

RENDER-004
Rendering MUST separate data lifecycle from visual lifecycle when needed.

RENDER-005
Heavy computation SHOULD be moved outside the rendering critical path.

RENDER-006
Canvas MUST NOT automatically replace DOM.

RENDER-007
SSR MUST define hydration behavior.

RENDER-008
Streaming MUST define progressive failure behavior.

RENDER-009
Skeleton UI MUST represent actual loading states rather than fake progress.

RENDER-010
Optimistic Rendering MUST define rollback behavior.
