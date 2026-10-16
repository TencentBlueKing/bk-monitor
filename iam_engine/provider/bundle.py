from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Iterator, Mapping
from threading import RLock

from iam_engine.core.config import AuthMode

from iam_engine.provider.base import PermissionProvider
from iam_engine.provider.capabilities import (
    AuthorizationWriter,
    AuthorizedScopeProvider,
    PermissionApplicationProvider,
)


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    """按 IAM 版本聚合一组可选能力。

    四个槽位可以指向同一个对象（V3/V4 Provider 同时实现鉴权、申请和范围查询），
    也可以单独缺省：被选中的能力缺失时明确报告不可用，不改选另一协议。

    空间范围走 ``scope``，不要对 ``auth`` 做鸭子调用。某一侧还不会查范围时
    把 ``scope`` 留空，Router 会返回错误范围，而不是 AttributeError。
    """

    auth: PermissionProvider | None = None
    application: PermissionApplicationProvider | None = None
    writer: AuthorizationWriter | None = None
    scope: AuthorizedScopeProvider | None = None


class LazyProviderBundles(Mapping[AuthMode, ProviderBundle]):
    """Cache capabilities, never the active mode; build only a selected protocol."""

    def __init__(self, factories: Mapping[AuthMode, Callable[[], ProviderBundle]]):
        self._factories = dict(factories)
        self._bundles: dict[AuthMode, ProviderBundle] = {}
        self._lock = RLock()

    def __getitem__(self, key: AuthMode) -> ProviderBundle:
        with self._lock:
            if key not in self._bundles:
                self._bundles[key] = self._factories[key]()
            return self._bundles[key]

    def __iter__(self) -> Iterator[AuthMode]:
        return iter(self._factories)

    def __len__(self) -> int:
        return len(self._factories)
