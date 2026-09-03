from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings


# add_authorization 生产 Schema（2026-08-12 核对）要求 expired_at 必填且最长 365 天，
# 当前不支持永久授权或更远期哨兵值，因此默认值与真实上限相同。
DEFAULT_V4_GRANT_EXPIRE_DAYS = 365
MAX_V4_GRANT_EXPIRE_DAYS = 365
DEFAULT_GRANT_MAX_ATTEMPTS = 12
# 重试退避：首次等待 BASE 秒并逐次翻倍，封顶 MAX 秒，避免长时间故障时把队列打满。
GRANT_RETRY_BASE_COUNTDOWN_SECONDS = 30
GRANT_RETRY_MAX_COUNTDOWN_SECONDS = 600

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


def retry_countdown_seconds(retries: int) -> int:
    """按已重试次数计算下一次投递的等待秒数。"""

    # 先夹住指数再乘，避免 max_attempts 配得很大时算出天文数字。
    exponent = min(max(0, retries), 16)
    return min(GRANT_RETRY_BASE_COUNTDOWN_SECONDS * 2**exponent, GRANT_RETRY_MAX_COUNTDOWN_SECONDS)


@dataclass(frozen=True, slots=True)
class AuthorizationGrantConfig:
    """创建者授权双写的运行参数。"""

    v4_expire_days: int
    max_attempts: int

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
        )
