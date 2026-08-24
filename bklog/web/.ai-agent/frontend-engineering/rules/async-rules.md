# Async Patterns

覆盖 28 个模式：

- Promise
- Async/Await
- Future
- Observable
- Reactive Stream
- Pipeline
- Queue
- Scheduler
- Debounce
- Throttle
- Cancellation
- Retry
- Backoff
- Timeout
- Circuit Breaker
- Bulkhead
- Concurrency Limit
- Request Deduplication
- Request Coalescing
- Race Prevention
- Latest Wins
- First Wins
- Sequential Execution
- Parallel Execution
- Waterfall
- Prefetch
- Background Task
- Worker

## Rules

ASYNC-001
Every asynchronous workflow MUST define failure behavior.

ASYNC-002
Long-running async operations SHOULD support cancellation when meaningful.

ASYNC-003
Retry MUST NOT be introduced without retryability analysis.

ASYNC-004
Retry MUST define maximum attempts.

ASYNC-005
Retry SHOULD use backoff where repeated requests may overload dependencies.

ASYNC-006
Concurrent requests MUST define race behavior.

ASYNC-007
Latest-Wins MUST be used intentionally, not accidentally.

ASYNC-008
Debounce and Throttle MUST NOT be treated as interchangeable.

ASYNC-009
Request deduplication MUST define cache/request lifecycle.

ASYNC-010
Parallel execution MUST define partial failure semantics.

ASYNC-011
Worker-based execution MUST define serialization boundaries.

ASYNC-012
Async state MUST remain consistent with UI lifecycle.
