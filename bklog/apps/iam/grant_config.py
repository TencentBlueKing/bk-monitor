from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings


# add_authorization 生产 Schema（2026-08-12 核对）要求 expired_at 必填且最长 365 天，
# 当前不支持永久授权或更远期哨兵值，因此默认值与真实上限相同。
DEFAULT_V4_GRANT_EXPIRE_DAYS = 365
MAX_V4_GRANT_EXPIRE_DAYS = 365
DEFAULT_GRANT_MAX_ATTEMPTS = 12
DEFAULT_GRANT_LEASE_SECONDS = 120
MIN_GRANT_LEASE_SECONDS = 30
DEFAULT_GRANT_COMPENSATION_BATCH_SIZE = 100
MAX_GRANT_COMPENSATION_BATCH_SIZE = 1000
DEFAULT_GRANT_COMPENSATION_TIME_BUDGET_SECONDS = 50
MAX_GRANT_COMPENSATION_TIME_BUDGET_SECONDS = 55

logger = logging.getLogger("iam.grant.config")


def _normalize_bounded_int(
    value: int | str | None,
    *,
    setting_name: str,
    default: int,
    minimum: int,
    maximum: int | None = None,
) -> int:
    """把授权配置归一化为指定范围内的整数，非法值回退默认值。"""

    try:
        configured = int(value) if value is not None else default
    except (TypeError, ValueError):
        logger.warning("invalid %s=%r, falling back to %s", setting_name, value, default)
        return default

    if configured < minimum:
        logger.warning("%s=%s is below minimum %s, using %s", setting_name, configured, minimum, minimum)
        return minimum
    if maximum is not None and configured > maximum:
        logger.warning("%s=%s exceeds maximum %s, using %s", setting_name, configured, maximum, maximum)
        return maximum
    return configured


@dataclass(frozen=True, slots=True)
class AuthorizationGrantConfig:
    """授权双写及补偿状态机的运行参数。"""

    v4_expire_days: int
    max_attempts: int
    lease_seconds: int
    compensation_batch_size: int
    compensation_time_budget_seconds: int

    @classmethod
    def from_settings(cls) -> AuthorizationGrantConfig:
        return cls(
            v4_expire_days=_normalize_bounded_int(
                getattr(settings, "BK_IAM_V4_GRANT_EXPIRE_DAYS", DEFAULT_V4_GRANT_EXPIRE_DAYS),
                setting_name="BK_IAM_V4_GRANT_EXPIRE_DAYS",
                default=DEFAULT_V4_GRANT_EXPIRE_DAYS,
                minimum=1,
                maximum=MAX_V4_GRANT_EXPIRE_DAYS,
            ),
            max_attempts=_normalize_bounded_int(
                getattr(settings, "BK_IAM_GRANT_MAX_ATTEMPTS", DEFAULT_GRANT_MAX_ATTEMPTS),
                setting_name="BK_IAM_GRANT_MAX_ATTEMPTS",
                default=DEFAULT_GRANT_MAX_ATTEMPTS,
                minimum=1,
            ),
            lease_seconds=_normalize_bounded_int(
                getattr(settings, "BK_IAM_GRANT_LEASE_SECONDS", DEFAULT_GRANT_LEASE_SECONDS),
                setting_name="BK_IAM_GRANT_LEASE_SECONDS",
                default=DEFAULT_GRANT_LEASE_SECONDS,
                minimum=MIN_GRANT_LEASE_SECONDS,
            ),
            compensation_batch_size=_normalize_bounded_int(
                getattr(
                    settings,
                    "BK_IAM_GRANT_COMPENSATION_BATCH_SIZE",
                    DEFAULT_GRANT_COMPENSATION_BATCH_SIZE,
                ),
                setting_name="BK_IAM_GRANT_COMPENSATION_BATCH_SIZE",
                default=DEFAULT_GRANT_COMPENSATION_BATCH_SIZE,
                minimum=1,
                maximum=MAX_GRANT_COMPENSATION_BATCH_SIZE,
            ),
            compensation_time_budget_seconds=_normalize_bounded_int(
                getattr(
                    settings,
                    "BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS",
                    DEFAULT_GRANT_COMPENSATION_TIME_BUDGET_SECONDS,
                ),
                setting_name="BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS",
                default=DEFAULT_GRANT_COMPENSATION_TIME_BUDGET_SECONDS,
                minimum=1,
                maximum=MAX_GRANT_COMPENSATION_TIME_BUDGET_SECONDS,
            ),
        )
