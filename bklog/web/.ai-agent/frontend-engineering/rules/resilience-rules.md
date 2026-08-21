# Resilience Patterns

覆盖 19 个模式：

- Error Boundary
- Retry
- Backoff
- Timeout
- Circuit Breaker
- Bulkhead
- Fallback
- Graceful Degradation
- Offline First
- Offline Fallback
- Cache
- Stale While Revalidate
- Optimistic Update
- Rollback
- Recovery
- Dead Letter
- Idempotency
- Rate Limiting
- Backpressure

## Rules

RESILIENCE-001
Every external dependency SHOULD define failure behavior.

RESILIENCE-002
Retry MUST only apply to retryable failures.

RESILIENCE-003
Circuit Breaker MUST define open/closed/half-open behavior.

RESILIENCE-004
Fallback MUST preserve user-visible correctness.

RESILIENCE-005
Graceful degradation MUST define reduced functionality.

RESILIENCE-006
Offline-first MUST define synchronization conflict handling.

RESILIENCE-007
Optimistic updates MUST define rollback.

RESILIENCE-008
Idempotency MUST be defined for retryable mutations.

RESILIENCE-009
Error boundaries MUST define recovery scope.

RESILIENCE-010
Failures MUST NOT be silently swallowed.
