from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apps.iam.iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from apps.iam.iam_engine.provider.bundle import ProviderBundle
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter, PermissionApplicationProvider


@dataclass(frozen=True, slots=True)
class ApplicationResolution:
    """迁移策略选定的无权限申请能力与来源版本。

    source_mode 告诉门面这次申请单是哪一代生成的，便于 UNION 下 current 失败时
    决定能不能再回退 legacy，以及纯 current 失败时该不该继续降级。
    """

    source_mode: AuthMode
    provider: PermissionApplicationProvider


class ApplicationProviderNotConfiguredError(RuntimeError):
    """Bundle 中缺少可用的无权限申请能力。"""


class MigrationPolicy:
    """跨双栈迁移期的共用编排策略，平台侧只负责注入 Bundle 与拓扑。

    申请和双写故意不跟当前鉴权模式完全绑定：
    - 申请：current / union 优先新协议申请页，避免用户点到即将下线的旧申请单。
    - 双写：只要 Writer 在 Bundle 里，legacy 与 current 都写，与当时是不是 V3 模式无关。
    """

    @staticmethod
    def resolve_application(
        mode: AuthMode,
        bundles: Mapping[AuthMode, ProviderBundle],
        *,
        stack: DualStackSpec | None = None,
    ) -> ApplicationResolution:
        """按拓扑给出的候选顺序选出第一个可用的申请 Provider。"""

        topology = stack or DEFAULT_DUAL_STACK
        for candidate in topology.application_candidates(mode):
            bundle = bundles.get(candidate)
            if bundle is not None and bundle.application is not None:
                return ApplicationResolution(candidate, bundle.application)

        raise ApplicationProviderNotConfiguredError("no permission application provider configured in bundles")

    @staticmethod
    def resolve_authorization_writers(
        bundles: Mapping[AuthMode, ProviderBundle],
        *,
        stack: DualStackSpec | None = None,
    ) -> tuple[tuple[str, AuthorizationWriter], ...]:
        """按 legacy → current 收集已注入的 Writer；缺 current 时只双写一侧。"""

        topology = stack or DEFAULT_DUAL_STACK
        writers: list[tuple[str, AuthorizationWriter]] = []
        for mode in topology.writer_modes:
            bundle = bundles.get(mode)
            if bundle is not None and bundle.writer is not None:
                writers.append((mode.value, bundle.writer))

        return tuple(writers)
