from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.iam.error_summary import sanitize_error_summary
from apps.iam.models import IAMAuthorizationGrant


class IAMAuthorizationGrantRepository:
    """授权意图的唯一创建、CAS 抢占与状态流转。"""

    RETRY_DELAYS_SECONDS = (60, 300, 900, 3600)

    def ensure(self, *, logical_key: str, target_version: str, defaults: dict[str, Any]) -> IAMAuthorizationGrant:
        try:
            with transaction.atomic():
                grant, _ = IAMAuthorizationGrant.objects.get_or_create(
                    logical_key=logical_key,
                    target_version=target_version,
                    defaults=defaults,
                )
                return grant
        except IntegrityError:
            # 并发插入由唯一约束收敛，读取胜出的冻结快照。
            return IAMAuthorizationGrant.objects.get(logical_key=logical_key, target_version=target_version)

    def claim(self, grant_id: int, *, lease_owner: str) -> IAMAuthorizationGrant | None:
        now = timezone.now()
        due = Q(state=IAMAuthorizationGrant.State.PENDING) | Q(
            state__in=(IAMAuthorizationGrant.State.RETRY_WAIT, IAMAuthorizationGrant.State.UNKNOWN),
            next_retry_at__lte=now,
        )
        updated = (
            IAMAuthorizationGrant.objects.filter(pk=grant_id)
            .filter(due, attempts__lt=settings.BK_IAM_GRANT_MAX_ATTEMPTS)
            .update(
                state=IAMAuthorizationGrant.State.PROCESSING,
                attempts=F("attempts") + 1,
                lease_owner=lease_owner,
                lease_until=now + timedelta(seconds=settings.BK_IAM_GRANT_LEASE_SECONDS),
                updated_at=now,
            )
        )
        if not updated:
            # 历史数据或 lease 恢复路径也必须服从统一的最大尝试次数。
            IAMAuthorizationGrant.objects.filter(
                pk=grant_id,
                attempts__gte=settings.BK_IAM_GRANT_MAX_ATTEMPTS,
            ).filter(due).update(
                state=IAMAuthorizationGrant.State.FAILED_FINAL,
                next_retry_at=None,
                lease_owner="",
                lease_until=None,
                last_error_type="MaxAttemptsExceeded",
                last_error_message="authorization grant reached the maximum attempt limit",
                updated_at=now,
            )
            return None
        return IAMAuthorizationGrant.objects.get(pk=grant_id)

    @staticmethod
    def mark_succeeded(grant: IAMAuthorizationGrant, *, lease_owner: str, result: Any) -> bool:
        """Persist success only while the caller still owns the processing lease."""

        now = timezone.now()
        return bool(
            IAMAuthorizationGrant.objects.filter(
                pk=grant.pk,
                state=IAMAuthorizationGrant.State.PROCESSING,
                lease_owner=lease_owner,
                lease_until__gte=now,
            ).update(
                state=IAMAuthorizationGrant.State.SUCCEEDED,
                result=result,
                next_retry_at=None,
                lease_owner="",
                lease_until=None,
                last_error_type="",
                last_error_code="",
                last_error_message="",
                succeeded_at=now,
                updated_at=now,
            )
        )

    def mark_failed(
        self,
        grant: IAMAuthorizationGrant,
        *,
        lease_owner: str,
        state: str,
        error: Exception,
        error_code: str = "",
    ) -> tuple[bool, str]:
        """Persist a classified failure and report whether the processing lease was still owned."""

        now = timezone.now()
        final_state = state
        if grant.attempts >= settings.BK_IAM_GRANT_MAX_ATTEMPTS:
            final_state = IAMAuthorizationGrant.State.FAILED_FINAL
        retry_at = None
        if final_state in (IAMAuthorizationGrant.State.RETRY_WAIT, IAMAuthorizationGrant.State.UNKNOWN):
            delay_index = min(max(grant.attempts - 1, 0), len(self.RETRY_DELAYS_SECONDS) - 1)
            retry_at = now + timedelta(seconds=self.RETRY_DELAYS_SECONDS[delay_index])

        updated = IAMAuthorizationGrant.objects.filter(
            pk=grant.pk,
            state=IAMAuthorizationGrant.State.PROCESSING,
            lease_owner=lease_owner,
            lease_until__gte=now,
        ).update(
            state=final_state,
            next_retry_at=retry_at,
            lease_owner="",
            lease_until=None,
            last_error_type=type(error).__name__[:64],
            last_error_code=str(error_code or "")[:64],
            last_error_message=sanitize_error_summary(error),
            updated_at=now,
        )
        return bool(updated), final_state

    @staticmethod
    def recover_expired_leases() -> int:
        """Recover stale processing records without allowing attempts beyond the configured limit."""

        now = timezone.now()
        expired = IAMAuthorizationGrant.objects.filter(
            state=IAMAuthorizationGrant.State.PROCESSING,
            lease_until__lt=now,
        )
        finalized = expired.filter(attempts__gte=settings.BK_IAM_GRANT_MAX_ATTEMPTS).update(
            state=IAMAuthorizationGrant.State.FAILED_FINAL,
            next_retry_at=None,
            lease_owner="",
            lease_until=None,
            last_error_type="LeaseExpiredMaxAttempts",
            last_error_message="processing lease expired at the maximum attempt limit",
            updated_at=now,
        )
        recovered = expired.filter(attempts__lt=settings.BK_IAM_GRANT_MAX_ATTEMPTS).update(
            state=IAMAuthorizationGrant.State.UNKNOWN,
            next_retry_at=now,
            lease_owner="",
            lease_until=None,
            last_error_type="LeaseExpired",
            last_error_message="processing lease expired before a result was persisted",
            updated_at=now,
        )
        return finalized + recovered

    @staticmethod
    def due_ids(*, limit: int) -> list[int]:
        now = timezone.now()
        return list(
            IAMAuthorizationGrant.objects.filter(
                Q(state=IAMAuthorizationGrant.State.PENDING)
                | Q(
                    state__in=(IAMAuthorizationGrant.State.RETRY_WAIT, IAMAuthorizationGrant.State.UNKNOWN),
                    next_retry_at__lte=now,
                )
            )
            .order_by("next_retry_at", "pk")
            .values_list("pk", flat=True)[:limit]
        )

    @staticmethod
    def requeue_failed(grant_ids: list[int]) -> int:
        now = timezone.now()
        return IAMAuthorizationGrant.objects.filter(
            pk__in=grant_ids,
            state=IAMAuthorizationGrant.State.FAILED_FINAL,
        ).update(
            state=IAMAuthorizationGrant.State.PENDING,
            attempts=0,
            next_retry_at=None,
            lease_owner="",
            lease_until=None,
            updated_at=now,
        )
