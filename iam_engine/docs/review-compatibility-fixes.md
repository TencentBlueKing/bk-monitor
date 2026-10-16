# IAM compatibility review follow-up

## Scope

This follow-up fixes five review findings without changing product permission
models, front-end code, global Celery settings, or existing user grants.

| Finding | Change | Direct regression coverage |
| --- | --- | --- |
| V3 caches did not survive a new Permission | Bounded process-local V3 client reuse, isolated by tenant, credentials, gateway, system, codec and compatibility mode | Cross-Permission cache hit, TTL expiry, configuration isolation; existing concurrent/tenant cache tests |
| DRF split multi-action batches and hid V3 SDK failures | Reuse the public product batch entry; retain native resource construction and complete metadata | One request for two actions, exact SDK exception propagation, real SDK policy evaluation of space coverage, V4/Union batch selection |
| Application generation hid unknown Actions | Validate registered Actions before choosing a backend; SDK-reported V3 failure keeps the configured fallback, while raised SDK exceptions propagate | Product methods and both Web application HTTP view contracts; real SDK validation/JSON errors propagate through both application methods; MCP preserves the V3 SDK success flag and avoids duplicate generation |
| API eager execution exhausted grant retries inline | No asynchronous compensation in either product; all roles record per-target failures by default and raise only for explicit strict calls; alarm backend changes reverted | Mode/role matrix, one write per target, no commit callback or grant task; actual APM creator/maintainer callers continue after V4 failure |
| Default action_categories IDs changed | Static metadata defaults to V3 codec IDs without building a provider; explicit V4 remains unchanged | Group/index consistency, absent/empty backend without credentials, existing explicit V3/V4 tests |

## Validation

Offline verification uses the repository runners, with outbound sockets/HTTP
blocked and local test dependencies. It is not live IAM or broker verification.

- Monitor/common IAM, RPC, MCP, APM and RUM suite: 1039 passed, 21 deselected.
- Supplementary business permission suite: 89 passed.
- BKLog IAM and decision-query suite: 610 passed; prior task tests were removed.
- API caller/grant/application suite: 93 passed, 2 deselected (Web-only HTTP
  renderer assertions; both run successfully in the Web suite).
- Worker grant/writer suite: 20 passed, using Django's existing test bootstrap branch.
- Actual baseline V3 URL method versus the current facade through the real SDK:
  3 passed (empty success, nonempty success, reported failure); source-isolation
  comparison only, not historical-service HTTP E2E.
- Removed-task startup checks and no-commit-callback assertions replace broker delivery checks.
- Ruff checks on changed Python files and git diff --check: passed.

The unknown-Action application endpoint contract is HTTP 400, result=false,
with error_details.code=3399001 under the unchanged MonitorJSONRenderer.

The new `packages/apm_web/tests/test_creator_authorization_compatibility.py`
contains 27 caller-level cases. These execute the real `Application.authorization`
and business-maintainer task, including API's `delay -> eager apply` chain,
while substituting IAM transport, CMDB and application lookup. Both grant-failure
sides and all three modes are covered; explicit owners still run. They are
offline caller regressions, not application-creation HTTP E2E or live IAM proof.

Reproduce the API subset from the repository root using the Monitor Python
environment (never deploy runner overrides):

```bash
python iam_engine/tests/run_monitor_offline.py --role api \
  packages/apm_web/tests/test_creator_authorization_compatibility.py \
  tests/iam/test_apply_url_fallback.py tests/iam/test_review_compatibility.py \
  ../iam_engine/tests/test_monitor_dual_write.py \
  -k 'not apply_endpoints_keep_unknown_action_400'
```

The main Web collection includes this new caller test alongside the existing
IAM/common, RPC, MCP, APM and RUM labels. Worker settings do not install the Web
APM application: only IAM grant/writer tests run in the actual Worker process;
Web/API caller coverage must not be described as Worker business E2E.

## Review and remaining boundaries

The follow-up keeps V3 SDK batch failures distinct from explicit denial. Space
ancestor metadata is preserved when consolidating Action queries. Client reuse
does not cache the operation's mode, user-facing Provider, or authorization
writer. The previously introduced broker route has been superseded by the latest
requirement: no asynchronous creator-grant compensation in either product.
Task bindings, broker producer, retry classifier/backoff/settings and transaction
callbacks have been removed. The alarm backend scheduler is restored to the PR
base. Web/API/Worker share the same failure contract: only explicit strict calls
raise CreatorGrantFailed; default V3 remains unchanged. In particular, V4 failure
does not suppress APM business-maintainer dispatch or skip later maintainers.
The retry_scheduled result field is retained for compatibility and always false.
It also removes the overly broad V3 application-URL exception fallback. The SDK
still reports ordinary request failures through its return tuple; validation
and response-decoding exceptions now retain the original V3 propagation.
Successful V3 SDK responses retain the URL exactly, including an empty URL;
SDK-reported failures retain the original error message log and fallback.
The focused re-review found no additional actionable regression in these fixes;
this is not an assertion that all live permission paths have been verified.

Historical issues are recorded, not fixed here: the BKLog V3 index-set callback
contains an unassigned QuerySet.filter call; Grafana empty managed-ACL revocation
and legacy APM maintainer asynchronous authorization require separate follow-up.
No changes to these historical paths are included.

Live V4 synchronous writes, historical-service HTTP comparison and the
remaining asynchronous acceptance gaps still require their own evidence. This
follow-up does not rebuild, deploy, or change the existing validation runtime.

For BKLog upgrades, the removed grant task may still have pending, delayed or
running messages. Drain it and coordinate old producers before removing Worker
registration, or explicitly inventory and handle unfinished grants. See the
[upgrade notice](../README.md#bklog-升级前排空旧创建者授权任务). IAM migration of existing
grants must not be assumed to recover grant intents that were never persisted.
