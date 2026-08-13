from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter, PermissionApplicationProvider


@dataclass(frozen=True, slots=True)
class ApplicationResolution:
    """迁移策略选定的无权限申请能力与来源版本。"""

    source_mode: AuthMode
    provider: PermissionApplicationProvider


class ApplicationProviderNotConfiguredError(RuntimeError):
    """Bundle 中缺少可用的无权限申请能力。"""


class MigrationPolicy:
    """跨 V3/V4 迁移期的共用编排策略，平台侧只负责注入 Provider Bundle。"""

    @staticmethod
    def resolve_application(
        mode: AuthMode,
        bundles: Mapping[AuthMode, ProviderBundle],
    ) -> ApplicationResolution:
        """V4 / Union 优先 V4 申请；否则统一回退 V3 Bundle 的申请能力。"""

        if mode in (AuthMode.V4, AuthMode.UNION):
            v4_bundle = bundles.get(AuthMode.V4)
            if v4_bundle is not None and v4_bundle.application is not None:
                return ApplicationResolution(AuthMode.V4, v4_bundle.application)

        v3_bundle = bundles.get(AuthMode.V3)
        if v3_bundle is not None and v3_bundle.application is not None:
            return ApplicationResolution(AuthMode.V3, v3_bundle.application)

        raise ApplicationProviderNotConfiguredError("no permission application provider configured in bundles")

    @staticmethod
    def resolve_authorization_writers(
        bundles: Mapping[AuthMode, ProviderBundle],
    ) -> tuple[tuple[str, AuthorizationWriter], ...]:
        """创建者授权按版本双写；V3 始终保留，V4 在注入 Writer 时追加。"""

        writers: list[tuple[str, AuthorizationWriter]] = []
        v3_bundle = bundles.get(AuthMode.V3)
        if v3_bundle is not None and v3_bundle.writer is not None:
            writers.append((AuthMode.V3.value, v3_bundle.writer))

        v4_bundle = bundles.get(AuthMode.V4)
        if v4_bundle is not None and v4_bundle.writer is not None:
            writers.append((AuthMode.V4.value, v4_bundle.writer))

        return tuple(writers)
