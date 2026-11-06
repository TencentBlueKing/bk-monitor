from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK, DualStackSpec
from iam_engine.provider.bundle import ProviderBundle
from iam_engine.provider.capabilities import AuthorizationWriter, PermissionApplicationProvider


@dataclass(frozen=True, slots=True)
class ApplicationResolution:
    """迁移策略选定的无权限申请能力与来源版本。

    source_mode 标识申请版本；生成失败只标记不可用，不能跨版本回退。
    """

    source_mode: AuthMode
    provider: PermissionApplicationProvider


class ApplicationProviderNotConfiguredError(RuntimeError):
    """Bundle 中缺少可用的无权限申请能力。"""


class MigrationPolicy:
    """跨双栈迁移期的共用编排策略，平台侧只负责注入 Bundle 与拓扑。

    所有能力使用同一次操作的模式快照：
    - 申请：current / union 固定新协议申请页，不回退旧协议。
    - 授权及模型同步：单栈只选自身，Union 才选择两侧。
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
        mode: AuthMode,
        bundles: Mapping[AuthMode, ProviderBundle],
        *,
        stack: DualStackSpec | None = None,
    ) -> tuple[tuple[str, AuthorizationWriter], ...]:
        """只选择模式指定的授权目标；缺少目标能力不能静默跳过。"""

        topology = stack or DEFAULT_DUAL_STACK
        writers: list[tuple[str, AuthorizationWriter]] = []
        for target in topology.modes_for(mode):
            bundle = bundles.get(target)
            if bundle is None or bundle.writer is None:
                raise RuntimeError(f"IAM {target.value} authorization writer is not configured")
            writers.append((target.value, bundle.writer))

        return tuple(writers)
