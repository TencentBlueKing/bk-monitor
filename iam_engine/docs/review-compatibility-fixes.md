# IAM compatibility review follow-up

## Scope

This follow-up fixes five review findings without changing product permission
models, front-end code, global Celery settings, or existing user grants.

| Finding | Change | Direct regression coverage |
| --- | --- | --- |
| V3 caches did not survive a new Permission | Bounded process-local V3 client reuse, isolated by tenant, credentials, gateway, system, codec and compatibility mode | Cross-Permission cache hit, TTL expiry, configuration isolation; existing concurrent/tenant cache tests |
| DRF split multi-action batches and hid V3 SDK failures | Reuse the public product batch entry; retain native resource construction and complete metadata | One request for two actions, exact SDK exception propagation, real SDK policy evaluation of space coverage, V4/Union batch selection |
| Application generation hid unknown Actions | Validate registered Actions before choosing a backend; SDK-reported V3 failure keeps the configured fallback, while raised SDK exceptions propagate | Product methods and both Web application HTTP view contracts; real SDK validation/JSON errors propagate through both application methods; MCP preserves the V3 SDK success flag and avoids duplicate generation |
| API eager execution exhausted grant retries inline | Web retains its SaaS app/default queue; eager API compensation uses a dedicated backend producer and celery_cron, sharing broker/cluster connection configuration with the backend worker | Producer connection/routing configuration, eager/non-eager dispatch, real Celery/Kombu in-memory delivery and retry with frozen request/expiry |
| Default action_categories IDs changed | Static metadata defaults to V3 codec IDs without building a provider; explicit V4 remains unchanged | Group/index consistency, absent/empty backend without credentials, existing explicit V3/V4 tests |

## Validation

Offline verification uses the repository runners, with outbound sockets/HTTP
blocked and local test dependencies. It is not live IAM or broker verification.

- Monitor/common IAM, RPC, MCP, APM and RUM suite: 1015 passed, 1 skipped, 21 deselected.
- Supplementary business permission suite: 89 passed.
- BKLog IAM and decision-query suite: 634 passed.
- API-role grant task suite: 15 passed, 1 skipped; Worker-role grant task suite: 16 passed.
- Worker offline startup and task registration passed. Worker-role tests use
  Django's existing test bootstrap branch, without a persistent cache-node DB.
  The worker-only case loads the actual scheduler app and verifies that broker,
  transport options, queue declaration and task registration match the producer.
- Ruff checks on the changed Python files: passed.

The unknown-Action application endpoint contract is HTTP 400, result=false,
with error_details.code=3399001 under the unchanged MonitorJSONRenderer.

## Review and remaining boundaries

The follow-up keeps V3 SDK batch failures distinct from explicit denial. Space
ancestor metadata is preserved when consolidating Action queries. Client reuse
does not cache the operation's mode, user-facing Provider, or authorization
writer. The queued task uses the existing frozen payload and retry policy.
The preceding review overstated completion of the eager-task fix: publishing to
celery_cron on the SaaS broker did not establish delivery to a backend consumer.
The follow-up removes that route, shares the worker's broker configuration, and
tests actual Celery message publication and retry with an in-memory transport.
It also removes the overly broad V3 application-URL exception fallback. The SDK
still reports ordinary request failures through its return tuple; validation
and response-decoding exceptions now retain the original V3 propagation.
The focused re-review found no additional actionable regression in these fixes;
this is not an assertion that all live permission paths have been verified.

Historical issues are recorded, not fixed here: the BKLog V3 index-set callback
contains an unassigned QuerySet.filter call; Grafana empty managed-ACL revocation
and legacy APM maintainer asynchronous authorization require separate follow-up.
No changes to these historical paths are included.

Live V4, broker/worker delivery, historical-service HTTP comparison and the
remaining asynchronous acceptance gaps still require their own evidence. This
follow-up does not rebuild, deploy, or change the existing validation runtime.
