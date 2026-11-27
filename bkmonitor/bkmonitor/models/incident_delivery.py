from django.db import models

from constants.incident_delivery import IncidentNoticeDeliveryStatus


class IncidentNoticeDelivery(models.Model):
    """One durable delivery claim per event, channel and recipient."""

    key = models.CharField(primary_key=True, max_length=64)
    event_key = models.CharField(max_length=64, db_index=True)
    channel = models.CharField(max_length=64)
    recipient = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        default=IncidentNoticeDeliveryStatus.PENDING,
        choices=IncidentNoticeDeliveryStatus.choices,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "bkmonitor"
        db_table = "bkmonitor_incident_notice_delivery"
