from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings


# add_authorization 生产 Schema（2026-08-12 核对）要求 expired_at 必填且最长 365 天，
# 当前不支持永久授权或更远期哨兵值，因此默认值与真实上限相同。
DEFAULT_V4_GRANT_EXPIRE_DAYS = 365
MAX_V4_GRANT_EXPIRE_DAYS = 365

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
    """创建者授权双写的运行参数。"""

    v4_expire_days: int

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
        )
