# Design

## Exploration and evidence
- src/main.js created() currently redirects missing space to /un-authorized.
- src/preload.ts resolves current space separately from getAllSpaceList; the latter already deduplicates full-list requests.
- src/global/bk-space-choice/index.tsx debounceUpdateRouter clears indexId; space-switch-route.ts defines normal/scene switching rules.
- src/views/retrieve-v3/use-app-init.tsx owns index adaptation and initialization; index.tsx mounts retrieval content after initialization.
- src/views/un-authorized/index.tsx currently derives exception type from route.query.type.

## Boundaries and decomposition
1. Record unresolved-space state in existing reactive application state during preload/bootstrap. Limit inline handling to the retrieve homepage; preserve non-home route handling.
2. Reuse UnAuthorized with an optional explicit exception type for embedding; maintain query-based fallback for existing route users. Avoid adding display-only flags to URL.
3. Gate homepage data initialization and content mounting while space resolution has failed. Keep global navigation and space selection interactive.
4. In the space selector, distinguish failed-space recovery from ordinary switching before updating store. Recovery preserves initial route index and compatible query, clears stale error state, and invokes the existing homepage initialization path.
5. Leave index matching/fallback algorithm intact. Verify the initialization watcher does not clear restored index during recovery; retain existing scene reset for ordinary switches.

## Risk review and extension points
Guard against stale requests or async list arrival incorrectly clearing failure state. Do not infer current-space validity solely from a lazily loaded full list. Failed recovery or empty target index list must exit loading. Check legacy un-authorized entry recovery without widening unrelated routes. Existing state, component props, and pure route helpers are sufficient; no new dependencies.

## Verification plan
Focused cases: invalid space with original index, valid/invalid target index, no spaces, full-list failure, ordinary and scene switches. Run focused lint and meaningful route/state tests. Generate UI cases using the supplied bundled aafe test --diff command. E2E execution requires the session-authorized URL and port 41001 for local servers. Report blocked/skipped execution truthfully.
