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


class NoticeDeliveryRetry(Exception):
    """Keep the queue message unacknowledged while a known failure can be retried."""


def digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def dispatch_once(event_key, channel, recipient, send):
    from bkmonitor.models.incident_delivery import IncidentNoticeDelivery

    if not connections[IncidentNoticeDelivery.objects.db].get_autocommit():
        raise NoticeDeliveryRetry("notification delivery requires an independently committed claim")
    try:
        return _dispatch(IncidentNoticeDelivery, event_key, channel, recipient, send)
    except DatabaseError as exc:
        raise NoticeDeliveryRetry("cannot persist incident notification receipt") from exc


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
            raise NoticeDeliveryRetry("incident notification is already in flight")
        # A timeout cannot tell us whether the external channel accepted the message.
        model.objects.filter(key=key, status=Status.SENDING, updated_at=row.updated_at).update(
            status=Status.UNCERTAIN, updated_at=now
        )
        row.refresh_from_db()
    if row.status == Status.UNCERTAIN:
        logger.error("Incident notification outcome needs reconciliation: delivery_key=%s", key)
        return {recipient: {"result": False, "message": "delivery outcome uncertain; reconciliation required"}}
    claimed = model.objects.filter(key=key, status__in=[Status.PENDING, Status.FAILED]).update(
        status=Status.SENDING, attempts=F("attempts") + 1, updated_at=now
    )
    if not claimed:
        raise NoticeDeliveryRetry("incident notification was claimed by another consumer")
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
    if status == Status.FAILED:
        raise NoticeDeliveryRetry("incident notification channel reported failure")
    if status == Status.UNCERTAIN:
        logger.error("Incident notification outcome needs reconciliation: delivery_key=%s", key)
        return {recipient: {"result": False, "message": "delivery outcome uncertain; reconciliation required"}}
    return response
