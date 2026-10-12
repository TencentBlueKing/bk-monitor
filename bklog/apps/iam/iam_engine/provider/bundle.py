from __future__ import annotations

from dataclasses import dataclass

from apps.iam.iam_engine.provider.base import PermissionProvider
from apps.iam.iam_engine.provider.capabilities import (
    AuthorizationWriter,
    AuthorizedScopeProvider,
    PermissionApplicationProvider,
)


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    """按 IAM 版本聚合一组可选能力。

    四个槽位可以指向同一个对象（V3/V4 Provider 同时实现鉴权、申请和范围查询），
    也可以单独缺省：current Writer 未配置时双写只落 legacy，申请则回退到下一候选。

    空间范围走 ``scope``，不要对 ``auth`` 做鸭子调用。某一侧还不会查范围时
    把 ``scope`` 留空，Router 会返回错误范围，而不是 AttributeError。
    """

    auth: PermissionProvider | None = None
    application: PermissionApplicationProvider | None = None
    writer: AuthorizationWriter | None = None
    scope: AuthorizedScopeProvider | None = None
