"""Durable receipts for BKFara domain events consumed by Monitor."""

from django.db import models


class IncidentDeliveryReceipt(models.Model):
    delivery_key = models.CharField(max_length=64, unique=True)
    event_id = models.CharField(max_length=128)
    bk_tenant_id = models.CharField(max_length=128)
    scope_id = models.CharField(max_length=128)
    payload_digest = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, default="processing")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    error_type = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        app_label = "bkmonitor"
        db_table = "incident_delivery_receipt"
