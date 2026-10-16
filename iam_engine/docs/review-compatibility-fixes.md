# IAM compatibility review follow-up

## Scope

This follow-up fixes five review findings without changing product permission
models, front-end code, global Celery settings, or existing user grants.

| Finding | Change | Direct regression coverage |
| --- | --- | --- |
| V3 caches did not survive a new Permission | Bounded process-local V3 client reuse, isolated by tenant, credentials, gateway, system, codec and compatibility mode | Cross-Permission cache hit, TTL expiry, configuration isolation; existing concurrent/tenant cache tests |
| DRF split multi-action batches and hid V3 SDK failures | Reuse the public product batch entry; retain native resource construction and complete metadata | One request for two actions, exact SDK exception propagation, real SDK policy evaluation of space coverage, V4/Union batch selection |
| Application generation hid unknown Actions | Validate registered Actions before choosing a backend; only URL generation failures use the V3 fallback | Product methods and both application HTTP view contracts; local model errors propagate; MCP preserves the V3 SDK success flag and avoids duplicate generation |
| API eager execution exhausted grant retries inline | Task-specific Celery extension enqueues to the existing celery_cron queue even in an eager producer | Eager/non-eager dispatch never runs the task inline; real task.retry preserves countdown, payload and expiry |
| Default action_categories IDs changed | Static metadata defaults to V3 codec IDs without building a provider; explicit V4 remains unchanged | Group/index consistency, absent/empty backend without credentials, existing explicit V3/V4 tests |

## Validation

Offline verification uses the repository runners, with outbound sockets/HTTP
blocked and local test dependencies. It is not live IAM or broker verification.

- Monitor/common IAM, RPC, MCP, APM and RUM suite: 1007 passed, 21 deselected.
- Supplementary business permission suite: 89 passed.
- BKLog IAM and decision-query suite: 634 passed.
- API-role grant task suite: 11 passed; Worker offline startup and task registration passed.
- Ruff checks on the changed Python files: passed.

The unknown-Action application endpoint contract is HTTP 400, result=false,
with error_details.code=3399001 under the unchanged MonitorJSONRenderer.

## Review and remaining boundaries

The follow-up keeps V3 SDK batch failures distinct from explicit denial. Space
ancestor metadata is preserved when consolidating Action queries. Client reuse
does not cache the operation's mode, user-facing Provider, or authorization
writer. The queued task uses the existing frozen payload and retry policy.
The focused re-review found no further actionable defect in these five fixes;
this is not an assertion that all live permission paths have been verified.

Historical issues are recorded, not fixed here: the BKLog V3 index-set callback
contains an unassigned QuerySet.filter call; Grafana empty managed-ACL revocation
and legacy APM maintainer asynchronous authorization require separate follow-up.
No changes to these historical paths are included.

Live V4, broker/worker delivery, historical-service HTTP comparison and the
remaining asynchronous acceptance gaps still require their own evidence. This
follow-up does not rebuild, deploy, or change the existing validation runtime.
