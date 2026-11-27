"""Durable per-recipient claims; uncertain external outcomes are never blindly replayed."""

import hashlib
import json
import logging
from datetime import timedelta

from django.db import DatabaseError, connections
from django.db.models import F
from django.utils import timezone

from constants.incident_delivery import (
    AMBIGUOUS_FAILURE_NOTICE_WAYS,
    DELIVERY_UNCERTAIN_AFTER_SECONDS,
    IncidentNoticeDeliveryStatus as Status,
)

logger = logging.getLogger(__name__)


def delivery_failure(recipient, key, message):
    logger.error("Incident notification needs reconciliation: delivery_key=%s reason=%s", key, message)
    return {recipient: {"result": False, "message": message}}


def digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def dispatch_once(event_key, channel, recipient, send):
    from bkmonitor.models.incident_delivery import IncidentNoticeDelivery

    key = digest([event_key, channel, recipient])
    try:
        if not connections[IncidentNoticeDelivery.objects.db].get_autocommit():
            return delivery_failure(recipient, key, "notification claim requires autocommit; not sent")
        return _dispatch(IncidentNoticeDelivery, event_key, channel, recipient, send)
    except DatabaseError:
        # Never replay completed incident writes because a notification receipt failed.
        logger.exception("Cannot persist incident notification receipt: delivery_key=%s", key)
        return delivery_failure(recipient, key, "receipt storage unavailable; reconcile before retry")


def _dispatch(model, event_key, channel, recipient, send):
    key = digest([event_key, channel, recipient])
    row, _ = model.objects.get_or_create(
        key=key, defaults={"event_key": event_key, "channel": channel, "recipient": recipient}
    )
    now = timezone.now()
    if row.status == Status.SENT:
        return {recipient: {"result": True, "message": "already delivered"}}
    if row.status == Status.SENDING:
        if row.updated_at > now - timedelta(seconds=DELIVERY_UNCERTAIN_AFTER_SECONDS):
            return delivery_failure(recipient, key, "incident notification is already in flight")
        # A timeout cannot tell us whether the external channel accepted the message.
        model.objects.filter(key=key, status=Status.SENDING, updated_at=row.updated_at).update(
            status=Status.UNCERTAIN, updated_at=now
        )
        row.refresh_from_db()
    if row.status in {Status.FAILED, Status.UNCERTAIN}:
        return delivery_failure(recipient, key, "previous delivery failed or was uncertain; reconciliation required")
    claimed = model.objects.filter(key=key, status=Status.PENDING).update(
        status=Status.SENDING, attempts=F("attempts") + 1, updated_at=now
    )
    if not claimed:
        return delivery_failure(recipient, key, "incident notification was claimed by another consumer")
    try:
        response = send()
    except Exception:
        logger.exception("Incident notification returned no definitive result: delivery_key=%s", key)
        response = {}
    outcome = response.get(recipient) if isinstance(response, dict) else None
    result = outcome.get("result") if isinstance(outcome, dict) else None
    if result is False and channel in AMBIGUOUS_FAILURE_NOTICE_WAYS:
        result = None
    status = Status.SENT if result is True else Status.FAILED if result is False else Status.UNCERTAIN
    model.objects.filter(key=key, status__in=[Status.SENDING, Status.UNCERTAIN]).update(
        status=status, updated_at=timezone.now()
    )
    if status in {Status.FAILED, Status.UNCERTAIN}:
        return delivery_failure(recipient, key, "delivery failed or was uncertain; reconciliation required")
    return response
