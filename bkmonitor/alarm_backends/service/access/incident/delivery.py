"""Event-level deduplication; ambiguous external effects must not be replayed."""

import copy
import hashlib
import json
from datetime import timedelta

from bkmonitor.aiops.incident.consumption import strict_incident_delivery
from django.db import connection
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


def consume_once(payload, handler, *, receipt_model=None):
    if payload.get("notice_source") != "bkfara" or "event_id" not in payload:
        handler(payload)
        return
    for key in ("event_id", "bk_tenant_id", "scope_id"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise DeliveryConflict(f"invalid {key}")
    if payload.get("sync_type") not in {"create", "update"} or payload.get("incident_actions"):
        raise DeliveryConflict("unsupported domain event")
    info_scope = (payload.get("incident_info") or {}).get("scope_id")
    if info_scope is not None and str(info_scope) != payload["scope_id"]:
        raise DeliveryConflict("scope identity mismatch")
    if connection.in_atomic_block:
        raise RuntimeError("delivery receipts require an independent commit before external effects")
    if receipt_model is None:
        from bkmonitor.models.incident_delivery import IncidentDeliveryReceipt

        receipt_model = IncidentDeliveryReceipt
    # Hash opaque IDs so a case-insensitive database collation cannot alias them.
    delivery_key = digest(
        ["monitor.incident", "bkfara", payload["bk_tenant_id"], payload["scope_id"], payload["event_id"]]
    )
    payload_hash = digest(payload)
    receipt, created = receipt_model.objects.get_or_create(
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
        if receipt.status == "processing" and receipt.started_at > timezone.now() - timedelta(minutes=30):
            raise DeliveryBusy("event is already being processed")
        # ES, remote API and notifications do not share the receipt transaction.
        # Expiry is not permission to repeat an effect whose outcome is unknown.
        receipt_model.objects.filter(pk=receipt.pk, status="processing").update(
            status="uncertain", finished_at=timezone.now(), error_type="DeliveryOutcomeUnknown"
        )
        raise DeliveryUncertain("previous delivery requires reconciliation")
    token = strict_incident_delivery.set(True)
    try:
        handler(copy.deepcopy(payload))
    except Exception as error:
        receipt_model.objects.filter(pk=receipt.pk, status="processing").update(
            status="uncertain", finished_at=timezone.now(), error_type=type(error).__name__[:128]
        )
        raise DeliveryUncertain("delivery failed; external effects may have completed") from error
    finally:
        strict_incident_delivery.reset(token)
    completed = receipt_model.objects.filter(pk=receipt.pk, status="processing").update(
        status="succeeded", finished_at=timezone.now()
    )
    if completed != 1:
        raise DeliveryUncertain("receipt no longer permits automatic completion")
