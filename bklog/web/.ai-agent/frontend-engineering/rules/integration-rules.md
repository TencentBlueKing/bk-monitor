# Integration Patterns

覆盖 21 个模式：

- Adapter
- Anti-Corruption Layer
- Facade
- Gateway
- BFF
- API Gateway
- Backend for Frontend
- Open Host Service
- Published Language
- Event Bus
- Message Bus
- Pub/Sub
- WebSocket
- SSE
- Polling
- Long Polling
- Webhook
- PostMessage
- BroadcastChannel
- Shared Worker
- Service Worker

## Rules

INTEGRATION-001
External API contracts MUST NOT automatically become internal domain contracts.

INTEGRATION-002
Adapters SHOULD isolate external contract changes.

INTEGRATION-003
Integration failures MUST be isolated from core UI behavior.

INTEGRATION-004
Event-driven integration MUST define event ownership.

INTEGRATION-005
Cross-context communication MUST define contract versioning.

INTEGRATION-006
BFF SHOULD be introduced only when frontend-specific aggregation is needed.

INTEGRATION-007
Polling MUST define interval and termination conditions.

INTEGRATION-008
WebSocket MUST define reconnect behavior.

INTEGRATION-009
Service Worker MUST define cache ownership and invalidation.
