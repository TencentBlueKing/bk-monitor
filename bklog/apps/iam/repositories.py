from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.iam.error_summary import sanitize_error_summary
from apps.iam.grant_config import AuthorizationGrantConfig
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

    @staticmethod
    def get(grant_id: int) -> IAMAuthorizationGrant:
        return IAMAuthorizationGrant.objects.get(pk=grant_id)

    @staticmethod
    def mark_preparation_failed(grant: IAMAuthorizationGrant, *, error: Exception) -> bool:
        """记录无法生成冻结请求的确定性失败，不覆盖已经存在的执行状态。"""

        now = timezone.now()
        return bool(
            IAMAuthorizationGrant.objects.filter(
                pk=grant.pk,
                state=IAMAuthorizationGrant.State.PENDING,
                attempts=0,
                payload={},
            ).update(
                state=IAMAuthorizationGrant.State.FAILED_FINAL,
                next_retry_at=None,
                last_error_type=type(error).__name__[:64],
                last_error_message=sanitize_error_summary(error),
                updated_at=now,
            )
        )

    def claim(self, grant_id: int, *, lease_owner: str) -> IAMAuthorizationGrant | None:
        now = timezone.now()
        grant_config = AuthorizationGrantConfig.from_settings()
        due = Q(state=IAMAuthorizationGrant.State.PENDING) | Q(
            state__in=(IAMAuthorizationGrant.State.RETRY_WAIT, IAMAuthorizationGrant.State.UNKNOWN),
            next_retry_at__lte=now,
        )
        updated = (
            IAMAuthorizationGrant.objects.filter(pk=grant_id)
            .filter(due, attempts__lt=grant_config.max_attempts)
            .update(
                state=IAMAuthorizationGrant.State.PROCESSING,
                attempts=F("attempts") + 1,
                lease_owner=lease_owner,
                lease_until=now + timedelta(seconds=grant_config.lease_seconds),
                updated_at=now,
            )
        )
        if not updated:
            # 历史数据或租约恢复路径也必须服从统一的最大尝试次数。
            IAMAuthorizationGrant.objects.filter(
                pk=grant_id,
                attempts__gte=grant_config.max_attempts,
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
        """仅在调用方仍持有处理租约时持久化成功状态。"""

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
        """持久化归类后的失败，并返回调用方是否仍持有处理租约。"""

        now = timezone.now()
        grant_config = AuthorizationGrantConfig.from_settings()
        final_state = state
        if grant.attempts >= grant_config.max_attempts:
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
        """恢复过期的处理记录，同时禁止尝试次数超过配置上限。"""

        now = timezone.now()
        grant_config = AuthorizationGrantConfig.from_settings()
        expired = IAMAuthorizationGrant.objects.filter(
            state=IAMAuthorizationGrant.State.PROCESSING,
            lease_until__lt=now,
        )
        finalized = expired.filter(attempts__gte=grant_config.max_attempts).update(
            state=IAMAuthorizationGrant.State.FAILED_FINAL,
            next_retry_at=None,
            lease_owner="",
            lease_until=None,
            last_error_type="LeaseExpiredMaxAttempts",
            last_error_message="processing lease expired at the maximum attempt limit",
            updated_at=now,
        )
        recovered = expired.filter(attempts__lt=grant_config.max_attempts).update(
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
            last_error_type="",
            last_error_code="",
            last_error_message="",
            updated_at=now,
        )
