"""迁移期编排：申请选边与创建者双写。

鉴权合并在 provider.composition.union；本包只管「写」和「去哪申请」。
两者都只认 DualStackSpec，不认具体的 v3/v4 名字。
"""

from apps.iam.iam_engine.migration.policy import (
    ApplicationProviderNotConfiguredError,
    ApplicationResolution,
    MigrationPolicy,
)

__all__ = [
    "ApplicationProviderNotConfiguredError",
    "ApplicationResolution",
    "MigrationPolicy",
]
