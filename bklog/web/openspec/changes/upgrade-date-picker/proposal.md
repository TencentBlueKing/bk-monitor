## Why

TAPD story 138287855 requests the current 4.x date picker and its migration behavior. The log frontend currently uses 3.0.7. npm reports 4.0.0-beta.9 as the newest 4.x release (the latest tag remains on 3.0.8).

## What Changes

- Pin @blueking/date-picker to 4.0.0-beta.9 and update the npm lockfile.
- Write format changes back to the controlled format value in the shared Vue 2 TimeRange wrapper.
- Preserve its existing events, timezone propagation, format entry, persistence and duration limits.
- Leave optional smart parsing disabled: the requirement provides no host parser or API contract.
