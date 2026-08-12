from __future__ import annotations

from django.db import models

from apps.iam.iam_engine.provider.capabilities import AuthorizationGrantState, AuthorizationGrantTarget


class IAMAuthorizationGrant(models.Model):
    """一个逻辑授权在一个 IAM 目标版本上的持久化执行意图。"""

    class TargetVersion(models.TextChoices):
        V3 = AuthorizationGrantTarget.V3.value, "V3"
        V4 = AuthorizationGrantTarget.V4.value, "V4"

    class State(models.TextChoices):
        PENDING = AuthorizationGrantState.PENDING.value, "Pending"
        PROCESSING = AuthorizationGrantState.PROCESSING.value, "Processing"
        SUCCEEDED = AuthorizationGrantState.SUCCEEDED.value, "Succeeded"
        RETRY_WAIT = AuthorizationGrantState.RETRY_WAIT.value, "Retry wait"
        UNKNOWN = AuthorizationGrantState.UNKNOWN.value, "Unknown"
        FAILED_FINAL = AuthorizationGrantState.FAILED_FINAL.value, "Failed final"

    logical_key = models.CharField(max_length=64)
    target_version = models.CharField(max_length=8, choices=TargetVersion.choices)
    grant_type = models.CharField(max_length=32, default="creator_action")
    intent_version = models.PositiveSmallIntegerField(default=1)

    tenant_id = models.CharField(max_length=64)
    subject_type = models.CharField(max_length=32, default="user")
    subject_id = models.CharField(max_length=255)
    operator = models.CharField(max_length=255)
    resource_system = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=64)
    resource_id = models.CharField(max_length=255)
    semantic_role = models.CharField(max_length=64)
    role_id = models.CharField(max_length=64, blank=True, default="")

    payload = models.JSONField(default=dict)
    expired_at = models.BigIntegerField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)

    state = models.CharField(max_length=24, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    lease_owner = models.CharField(max_length=64, blank=True, default="")
    lease_until = models.DateTimeField(null=True, blank=True)

    last_error_type = models.CharField(max_length=64, blank=True, default="")
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    last_error_message = models.CharField(max_length=512, blank=True, default="")
    succeeded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("logical_key", "target_version"),
                name="uniq_iam_grant_logical_target",
            )
        ]
        indexes = [
            models.Index(fields=("state", "next_retry_at"), name="iam_grant_retry_idx"),
            models.Index(fields=("state", "lease_until"), name="iam_grant_lease_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.logical_key}:{self.target_version}:{self.state}"
