## Boundaries and approach

Limit executable changes to bklog/web's dependency manifest, lockfile and shared TimeRange wrapper. Other frontend packages keep their own dependency versions. Existing consumers in retrieval, client search, collection status and usage details already update their bound timezone. Consumers hiding timezone need no adaptation.

Retain controlled format and assign the selected format before persisting and emitting. The initial format still comes from the retrieval store. Preserve enableFormatClick=true and the Vue 2 import and stylesheet paths. Correct the timezone property's type to string.

## Validation and risks

Verify the wrapper with mocked store/storage and the published DateRange implementation with absolute, wall-clock and relative dates. Generate focused AAFE UI cases and run against task code on reserved port 41001 when the configured development environment is available. A 4.x beta upgrade changes the panel UI; unit results alone cannot establish visual compatibility.

## Review

Scope and scenarios reviewed against the TAPD body, npm metadata and published Vue 2 adapter. Lightweight specification accepted for implementation by the agent under the owner's autonomous execution policy and continuation instruction; this does not assert a separate user approval event.
