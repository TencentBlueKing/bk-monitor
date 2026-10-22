"""Atomic, revision-guarded projection of diagnosis-only notifications."""

from alarm_backends.service.access.incident.delivery import DeliveryBusy, DeliveryConflict


SCRIPT = """
if (ctx._source.extra_info == null ||
    ctx._source.extra_info.notice_source != 'bkfara' ||
    ctx._source.extra_info.scope_id != params.scope_id ||
    ctx._source.extra_info.bk_tenant_id != params.bk_tenant_id) {
    throw new IllegalArgumentException('incident notification scope mismatch');
}
def previous = ctx._source.extra_info.diagnosis_notification;
if (previous != null && previous.revision == params.snapshot.revision &&
    previous.event_id != params.snapshot.event_id) {
    throw new IllegalArgumentException('incident notification revision collision');
}
if (previous == null || previous.revision < params.snapshot.revision) {
    ctx._source.extra_info.diagnosis_notification = params.snapshot;
    ctx._source.extra_info.diagnosis_status = params.snapshot.diagnosis_status;
    ctx._source.extra_info.analysis = params.snapshot.analysis;
} else { ctx.op = 'noop'; }
"""


def update_diagnosis(payload, document_model):
    info = payload["incident_info"]
    create_time = info.get("create_time")
    if type(create_time) is not int or type(payload.get("incident_id")) is not int:
        raise DeliveryConflict("invalid incident identity")
    document_id = f"{create_time}{payload['incident_id']}"
    hits = document_model.search(all_indices=True).filter("term", id=document_id).execute().hits
    if not hits:
        # Never create an incomplete incident from a status-only notification.
        raise DeliveryBusy("incident has not been synchronized")
    params = {
        "scope_id": payload["scope_id"],
        "bk_tenant_id": payload["bk_tenant_id"],
        "snapshot": {
            "revision": payload["aggregate_revision"],
            "diagnosis_status": info["diagnosis_status"],
            "analysis": info["analysis"],
            "event_id": payload["event_id"],
        },
    }
    client = document_model._index._get_connection()
    # Rollover may temporarily expose two copies; update both without reindexing
    # a stale whole document or overwriting unrelated extra_info keys.
    for hit in hits:
        client.update(
            index=hit.meta.index,
            id=hit.meta.id,
            retry_on_conflict=3,
            body={"script": {"lang": "painless", "source": SCRIPT, "params": params}},
        )
