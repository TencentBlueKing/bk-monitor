from __future__ import annotations

from dataclasses import dataclass

from apps.iam.iam_engine.provider.base import PermissionProvider
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter, PermissionApplicationProvider


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    """按 IAM 版本聚合鉴权、无权限申请与授权写入能力。"""

    auth: PermissionProvider | None = None
    application: PermissionApplicationProvider | None = None
    writer: AuthorizationWriter | None = None
