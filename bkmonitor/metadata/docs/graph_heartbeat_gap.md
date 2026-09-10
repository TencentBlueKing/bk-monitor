# Graph relation heartbeat window

This metadata-only change proposes the optional `SurrealDBBinding.spec.heartbeat_gap_ms`
contract. BKBase must implement this field before it is enabled. No SurrealDB DDL is
executed by metadata, and no database migration is required.

## Configuration

Use the existing GlobalConfig administration interface:

- `GRAPH_RELATION_HEARTBEAT_GAP_MS`: global default, `null` by default (omit the field).
- `GRAPH_RELATION_HEARTBEAT_GAP_MS_OVERRIDES`: tenant/business mapping, for example
  `{"tenant-a": {"123": 300000, "456": 600000}}`.

Overrides use the binding's tenant and actual labeled business ID. They never consult
another tenant. Values are integer milliseconds from 1 through 86400000. A tenant/business
`null` omits the field even when a global default exists. Omission is not a request to
reset a previously applied database parameter: explicitly send 300000 to restore five minutes.

Settings changes take effect on subsequent binding composition/apply, after the normal
DynamicSettings cache refresh. Updating GlobalConfig alone does not trigger a BKBase
apply or demonstrate that a database parameter has changed. Reapply the existing graph
binding using the metadata workflow and verify BKBase and the database independently.

## Required downstream work

BKBase should validate the field and persist it in the binding's exact namespace/database,
for example as `$graph_heartbeat_gap_ms`, consumed by the five-argument
`fn::upsert_relation`. Existing schemas must retain their parameter when an older binding
omits the field. Read-back of the applied value is required before reporting success.

The value controls relation expiry and segment continuity, not write batching or heartbeat
report frequency. Increasing it does not eliminate the UPDATE on each distinct heartbeat.
It also delays expiry. Changing it can produce overlaps or bridge gaps when existing segments
were written with another threshold. Effective-time/version and transition semantics must
be agreed and tested downstream before allowing live changes; metadata does not rewrite
existing intervals. No automatic database cleanup or gray rollout is part of this change.
