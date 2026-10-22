"""Event-level deduplication; ambiguous external effects must not be replayed."""

import copy
import hashlib
import json
import re
from datetime import timedelta

from bkmonitor.aiops.incident.consumption import strict_incident_delivery
from django.db import connections, router
from django.utils import timezone


class DeliveryConflict(ValueError):
    pass


class DeliveryBusy(RuntimeError):
    pass


class DeliveryUncertain(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


DIAGNOSIS_EVENTS = {
    "diagnosis.initialized": ("diagnosis_pending", "todo"),
    "diagnosis.requested": ("diagnosis_started", "running"),
    "diagnosis.succeeded": ("diagnosis_succeeded", "finished"),
    "diagnosis.failed": ("diagnosis_failed", "failed"),
}


def validate_diagnosis(payload):
    """Only the opt-in v1 diagnosis envelope belongs on the internal delta path."""
    events = payload.get("event_types")
    info = payload.get("incident_info")
    revision = payload.get("aggregate_revision")
    if (
        payload.get("schema_version") != "1.0"
        or payload.get("notice_source") != "bkfara"
        or payload.get("destination") != "bkfara_internal"
        or payload.get("notification_kind") != "diagnosis"
        or payload.get("sync_type") != "diagnosis"
        or not isinstance(events, list)
        or not events
        or any(not isinstance(event, str) or event not in DIAGNOSIS_EVENTS for event in events)
        or not isinstance(info, dict)
        or type(revision) is not int
        or revision < 1
        or type(payload.get("incident_id")) is not int
        or payload["incident_id"] < 1
    ):
        raise DeliveryConflict("invalid diagnosis envelope")
    for key in ("event_id", "policy_revision"):
        if not isinstance(payload.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", payload[key]):
            raise DeliveryConflict(f"invalid diagnosis {key}")
    if (
        payload.get("operation") != DIAGNOSIS_EVENTS[events[0]][0]
        or any(DIAGNOSIS_EVENTS[event][1] != info.get("diagnosis_status") for event in events)
        or info.get("scope_id") != payload.get("scope_id")
        or type(info.get("create_time")) is not int
        or not isinstance(info.get("analysis"), dict)
        or not isinstance(payload.get("changes"), dict)
    ):
        raise DeliveryConflict("inconsistent diagnosis snapshot")
    analysis = info["analysis"]
    if info["diagnosis_status"] == "todo":
        if analysis:
            raise DeliveryConflict("pending diagnosis must not reference a task")
    else:
        task_status = analysis.get("task_status")
        statuses = {
            "ready": "running",
            "inited": "running",
            "running": "running",
            "suspended": "running",
            "finished": "finished",
            "failed": "failed",
            "canceled": "failed",
            "skipped": "failed",
        }
        if (
            not isinstance(task_status, str)
            or statuses.get(task_status) != info["diagnosis_status"]
            or type(analysis.get("task_id")) is not int
            or analysis["task_id"] < 1
            or analysis.get("execution_backend") not in ("runtime", "bkflow")
        ):
            raise DeliveryConflict("inconsistent diagnosis task")
    change = payload["changes"].get("diagnosis_status")
    if change is not None and (
        not isinstance(change, dict)
        or change.get("to") != info["diagnosis_status"]
        or change.get("from") not in (None, "todo", "running", "finished", "failed")
    ):
        raise DeliveryConflict("invalid diagnosis change")


def consume_once(payload, handler, *, receipt_model=None):
    if not isinstance(payload, dict):
        raise DeliveryConflict("incident message must be an object")
    if payload.get("notice_source") == "bkfara" and payload.get("destination", "bkfara_internal") not in (
        "bkfara_internal",
        "incident_lifecycle",
    ):
        raise DeliveryConflict("notification routed to the wrong receiver")
    if payload.get("sync_type") == "diagnosis" or (
        payload.get("notice_source") == "bkfara" and "schema_version" in payload
    ):
        validate_diagnosis(payload)
    if payload.get("notice_source") != "bkfara" or "event_id" not in payload:
        handler(payload)
        return
    for key in ("event_id", "bk_tenant_id", "scope_id"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise DeliveryConflict(f"invalid {key}")
    if payload.get("sync_type") not in ("create", "update", "diagnosis") or payload.get("incident_actions"):
        raise DeliveryConflict("unsupported domain event")
    if not isinstance(payload.get("incident_info"), dict):
        raise DeliveryConflict("incident_info must be an object")
    info_scope = (payload.get("incident_info") or {}).get("scope_id")
    if info_scope is not None and str(info_scope) != payload["scope_id"]:
        raise DeliveryConflict("scope identity mismatch")
    if receipt_model is None:
        from bkmonitor.models.incident_delivery import IncidentDeliveryReceipt

        receipt_model = IncidentDeliveryReceipt
    database = router.db_for_write(receipt_model)
    connection = connections[database]
    if connection.in_atomic_block or not connection.get_autocommit():
        raise RuntimeError("delivery receipts require an independent commit before external effects")
    # Deduplication and completion must read the primary, including after a unique-key race.
    receipts = receipt_model.objects.using(database)
    # Hash opaque IDs so a case-insensitive database collation cannot alias them.
    delivery_key = digest(
        ["monitor.incident", "bkfara", payload["bk_tenant_id"], payload["scope_id"], payload["event_id"]]
    )
    try:
        payload_hash = digest(payload)
    except (TypeError, ValueError) as error:
        raise DeliveryConflict("incident payload must contain finite JSON values") from error
    receipt, created = receipts.get_or_create(
        delivery_key=delivery_key,
        defaults={
            "event_id": payload["event_id"],
            "bk_tenant_id": payload["bk_tenant_id"],
            "scope_id": payload["scope_id"],
            "payload_digest": payload_hash,
            "payload": copy.deepcopy(payload),
        },
    )
    if not created:
        if receipt.payload_digest != payload_hash:
            raise DeliveryConflict("event_id reused with a different payload")
        if receipt.status == "succeeded":
            return
        if receipt.status == "retry" and payload.get("sync_type") == "diagnosis":
            # Only a no-effect, missing-document diagnosis attempt can enter
            # retry. CAS prevents two consumers from reclaiming it together.
            if (
                receipts.filter(pk=receipt.pk, status="retry").update(
                    status="processing", started_at=timezone.now(), finished_at=None, error_type=""
                )
                != 1
            ):
                raise DeliveryBusy("diagnosis retry is already being processed")
        elif receipt.status == "processing" and receipt.started_at > timezone.now() - timedelta(minutes=30):
            raise DeliveryBusy("event is already being processed")
        else:
            # ES, remote API and notifications do not share the receipt transaction.
            # Expiry is not permission to repeat an effect whose outcome is unknown.
            receipts.filter(pk=receipt.pk, status="processing").update(
                status="uncertain", finished_at=timezone.now(), error_type="DeliveryOutcomeUnknown"
            )
            raise DeliveryUncertain("previous delivery requires reconciliation")
    token = strict_incident_delivery.set(True)
    try:
        handler(copy.deepcopy(payload))
    except DeliveryBusy as error:
        if payload.get("sync_type") == "diagnosis":
            receipts.filter(pk=receipt.pk, status="processing").update(
                status="retry", finished_at=timezone.now(), error_type=type(error).__name__
            )
            raise
        receipts.filter(pk=receipt.pk, status="processing").update(
            status="uncertain", finished_at=timezone.now(), error_type=type(error).__name__
        )
        raise DeliveryUncertain("delivery outcome requires reconciliation") from error
    except Exception as error:
        receipts.filter(pk=receipt.pk, status="processing").update(
            status="uncertain", finished_at=timezone.now(), error_type=type(error).__name__[:128]
        )
        raise DeliveryUncertain("delivery failed; external effects may have completed") from error
    finally:
        strict_incident_delivery.reset(token)
    completed = receipts.filter(pk=receipt.pk, status="processing").update(
        status="succeeded", finished_at=timezone.now()
    )
    if completed != 1:
        raise DeliveryUncertain("receipt no longer permits automatic completion")
