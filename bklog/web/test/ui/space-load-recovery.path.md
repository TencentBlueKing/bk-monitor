# Space load recovery — verification and UI paths

TAPD: 1010158081137994989 / #137994989
Branch: feat/space-load-recovery/#137994989

## Impact and review

- Direct (mixed: UI, logic, store): bootstrap marks unresolved space; RetrieveHub renders UnAuthorized without mounting either retrieval version; the selector retains original index/query specifically for recovery; UnAuthorized accepts an explicit exception type.
- Indirect: useNavMenu defers recovery routing to the selector; existing space authorization/menu updates remain in that flow. Existing index matching, cached/default index fallback and ordinary scene switching algorithms are unchanged.
- Risks to verify in the browser: navigation/request timing, recovery into a space with/without the original index, and empty/error space lists. Unit/component mocks do not establish real API or browser success.
- No Figma constraints were supplied in this requirement.

## Executed checks

- PASS: `node --test test/unit/space-load-recovery.test.cjs` — 11 tests, using mocked boundaries and production functions/render callbacks.
- PASS: focused ESLint and Prettier checks for all eight changed source files.
- PASS: `tsc --noEmit --skipLibCheck --target es2020 src/global/bk-space-choice/space-switch-route.ts` — helper type check, not a full application build.
- PASS: `git -c core.whitespace=cr-at-eol diff --check` — existing CRLF in space selector retained.
- AAFE impact run from repository root: 20260909T080047-idu6 (static baseline included generated runtime artifacts; manual scope narrowed to eight source files).
- AAFE UI plan from task checkout's bklog/web: 20260909T080613-u2hp. Command: bundled `aafe test --diff --config-root=/Users/lixintao/github/bk-monitor/bklog/web --mcp-config-root=/Users/lixintao/github/aafe-agent-runtime`.
- AAFE classified primary=e2e. It generated four accessibility smoke cases, not business acceptance coverage. Generated `/retrieve-hub` and `/un-authorized/tenant-mismatch` paths are file-based inference and MUST NOT be used as product routes. Actual routes are `/retrieve/:indexId?` and `/un-authorized` in hash mode.
- E2E SKIPPED (2026-09-10, blocking-only-v1): workspace default https://bklog.bkop.woa.com is a template target, but this uncommitted change is not verified deployed there. Source e2e.devServer is not configured; auth.checkUrl and auth.readySelector are null. Legacy local settings hardcode 8011 instead of reserved 41002. No browser/authentication attempt failed; optional UI execution is omitted with this evidence gap. No E2E pass is claimed.

## Required fixture and target

Owner-provided full test URL must serve this task's code. Confirm URL role if it includes hash/query. Use authorized test fixtures for a selectable space and an index it contains; preserve that index in the initial path while supplying a nonmatching space. Do not guess production identifiers.

## P-001 / P0 — failed initial space, original index exists in target space

1. navigate | supplied test URL with `#/retrieve/<fixture-index>` and invalid space fixture | capture original full URL.
2. assert | `.bk-exception` | space unauthorized text visible; full URL unchanged; no index-field/query request for the unresolved space; `.v3-bklog-root` absent.
3. click | `.biz-menu-select .menu-select-name` | dropdown opens; placeholder “请选择业务” is visible before selection.
4. fill | `.menu-select-search input` | value=authorized fixture space name; its `.biz-list .list-item` becomes visible after full-list loading.
5. click | fixture space's `.biz-list .list-item` | return/stay on `/retrieve/<fixture-index>` with selected spaceUid and bizId.
6. assert | index selector and resulting field/query requests | original index selected using existing adaptation; loading terminates; unauthorized message disappears.
7. screenshot | unified AAFE run artifacts | recovery result and selected index.

## P-002 / P1 — original index absent in selected space

1. navigate | equivalent invalid-space URL with index absent from target fixture | unauthorized view shown, URL retained.
2. click/fill/click | same dropdown sequence as P-001 | select the target fixture space.
3. assert | index selector | existing adaptation chooses the existing fallback; no permanent loading or repeated requests for absent index.

## P-003 / P1 — ordinary scene switching regression

1. navigate | supplied environment's valid scene retrieval fixture | successful current space with scene filters and index.
2. click/fill/click | space dropdown | select another authorized space.
3. assert | URL and scene panel | original normal-switch behavior: remove old index and space-specific filters, retain allowed global query fields, default scene=k8s.

## P-004 / P1 — no selectable spaces and failed navigation

1. navigate | invalid-space fixture with mocked empty full-space response | unauthorized view remains.
2. click | `.menu-select-name` | dropdown remains usable and shows empty list; no retrieval component is mounted.
3. repeat with full-list failure or cancelled navigation fixture | unauthorized view remains, and selecting a space never clears the failure state before successful routing.

## Pending delivery

Delivery proceeds under blocking-only-v1 with optional UI verification skipped: commit includes --story=137994989; bundled AAFE PR and TAPD comment record the residual browser/API timing risk. The task/commit marker in TAPD identifies the delivered revision.
