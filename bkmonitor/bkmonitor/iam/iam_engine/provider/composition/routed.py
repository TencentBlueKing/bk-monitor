"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# RoutedPolicy —— 按 action_id 路由到不同 Provider
#
# 典型场景：v3 → v4 分批迁移期，部分 action 已迁 v4，其余仍在 v3。
# 语义：
#   * 通过 action_routes 字典配置：{action_id: provider_name}
#   * 命中路由的 action 走对应 Provider
#   * 未命中的 action 走 default_provider_name（默认 providers[0]）
#   * 批量请求会按路由分组 → 分别调用各 Provider → 合并结果保序
#
# options:
#   action_routes: dict[str, str]       —— action_id -> provider name
#   default_provider: str = providers[0].name
# ---------------------------------------------------------------------------

from bkmonitor.iam.iam_engine.core.exceptions import ConfigError
from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
)
from bkmonitor.iam.iam_engine.provider.base import PermissionProvider
from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy


class RoutedPolicy(CompositionPolicy):
    """按 action_id 路由到指定 Provider。"""

    def __init__(self, providers, **options) -> None:
        super().__init__(providers, **options)
        self._by_name: dict[str, PermissionProvider] = {p.name: p for p in providers}
        if len(self._by_name) != len(providers):
            raise ConfigError(
                f"RoutedPolicy requires providers to have unique names; got names={[p.name for p in providers]}"
            )

        self._routes: dict[str, str] = dict(options.get("action_routes", {}))
        # 校验路由目标存在
        unknown = set(self._routes.values()) - set(self._by_name)
        if unknown:
            raise ConfigError(f"RoutedPolicy action_routes references unknown provider(s): {sorted(unknown)}")

        default_name = options.get("default_provider", providers[0].name)
        if default_name not in self._by_name:
            raise ConfigError(
                f"RoutedPolicy default_provider {default_name!r} not in providers {sorted(self._by_name)}"
            )
        self._default_name = default_name

    def _resolve_provider(self, action_id: str) -> PermissionProvider:
        """按 action_id 找到对应 Provider；未配置路由走 default。"""
        name = self._routes.get(action_id, self._default_name)
        return self._by_name[name]

    def primary(self) -> PermissionProvider:
        """default_provider 作为 primary，用于 apply_url 等无法合并的操作。"""
        return self._by_name[self._default_name]

    # ---- 鉴权组合 ----

    def is_allowed(self, request: AuthRequest) -> bool:
        return self._resolve_provider(request.action_id).is_allowed(request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        # 单 action 请求直接路由
        return self._resolve_provider(request.action_id).batch_by_resource(request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """多 action：按 provider 分组，分别调用后合并保序。"""
        # 分组：provider_name -> [action_id, ...]
        grouped: dict[str, list[str]] = {}
        for aid in request.action_ids:
            provider_name = self._routes.get(aid, self._default_name)
            grouped.setdefault(provider_name, []).append(aid)

        # 每组调用一次
        allowed_actions: set[str] = set()
        for provider_name, aids in grouped.items():
            sub_req = BatchByActionRequest(
                subject=request.subject,
                action_ids=tuple(aids),
                resource=request.resource,
                environment=request.environment,
            )
            result = self._by_name[provider_name].batch_by_action(sub_req)
            for item in result.items:
                if item.allowed:
                    allowed_actions.add(item.action_id)

        # 保序：按原 action_ids 顺序返回
        resource_id = request.resource.id if request.resource else ""
        resource_type = request.resource.type if request.resource else ""
        merged = [
            ResourceAuthResult(
                action_id=aid,
                resource_type=resource_type,
                resource_id=resource_id,
                allowed=aid in allowed_actions,
            )
            for aid in request.action_ids
        ]
        return BatchAuthResult(items=tuple(merged))
