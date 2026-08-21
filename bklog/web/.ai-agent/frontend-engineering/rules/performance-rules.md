# Performance Patterns

覆盖 24 个模式：

- Memoization
- Caching
- Lazy Loading
- Code Splitting
- Tree Shaking
- Prefetching
- Preloading
- Virtualization
- Windowing
- Batching
- Debouncing
- Throttling
- Object Pooling
- Flyweight
- Structural Sharing
- Immutable Update
- Incremental Computation
- Incremental Rendering
- Worker Offloading
- WebAssembly
- Offscreen Processing
- Resource Pool
- Connection Pool
- Backpressure

## Rules

PERF-001
Performance patterns MUST be driven by measurable bottlenecks.

PERF-002
Do not introduce optimization patterns without identifying the bottleneck.

PERF-003
Memoization MUST define cache lifetime.

PERF-004
Caching MUST define invalidation.

PERF-005
Code splitting MUST consider network and interaction costs.

PERF-006
Virtualization MUST define measurement strategy.

PERF-007
Worker offloading MUST account for serialization and transfer costs.

PERF-008
WebAssembly MUST only be introduced when computation characteristics justify it.

PERF-009
Object pooling MUST only be introduced when allocation pressure is meaningful.

PERF-010
Optimization MUST NOT materially increase architectural complexity without measurable benefit.
