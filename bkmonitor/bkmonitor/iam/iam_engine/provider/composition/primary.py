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
# PrimaryPolicy —— 主决策 + 主故障时 fallback
#
# 典型场景：v4 挂了自动降级到 v3，保证服务不中断。
# 语义：
#   * 主 provider：默认 providers[0]；也可通过 options["primary_provider"]（provider.name）显式指定
#   * 备 provider：其余按 providers 顺序（不含主）
#   * 主返回结果时以主为准（无论 allow/deny）
#   * 主抛 ProviderUnavailable（**注意：不是 ProviderError**）时按顺序尝试备
#   * 全部不可用时抛最后一个异常
#
# options:
#   primary_provider: str | None = None  —— 显式指定主 provider 的 name；未指定则取 providers[0]
#   fallback_on_error: bool = True       —— False 时主故障不 fallback（直接抛）
# ---------------------------------------------------------------------------

from typing import Any

from ...core.exceptions import ProviderUnavailable
from ...core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
)
from ...provider.base import PermissionProvider
from ...provider.composition.base import CompositionPolicy


class PrimaryPolicy(CompositionPolicy):
    """主决策，主故障时按顺序 fallback 到备。

    与 AnyOfPolicy 的区别：
      * PrimaryPolicy 尊重主的 deny 决策（主返回 False 即 False）
      * AnyOfPolicy 会继续尝试备（宽松放行）
    """

    def __init__(self, providers: list[PermissionProvider], **options: Any) -> None:
        super().__init__(providers, **options)
        primary_name: str | None = options.get("primary_provider")
        if primary_name:
            match = [p for p in providers if p.name == primary_name]
            if not match:
                raise ValueError(f"primary_provider={primary_name!r} not in providers {[p.name for p in providers]}")
            self._primary: PermissionProvider = match[0]
            self._fallbacks: list[PermissionProvider] = [p for p in providers if p is not self._primary]
        else:
            self._primary = providers[0]
            self._fallbacks = list(providers[1:])
        # _chain：主在前 + 按声明顺序的备
        self._chain: list[PermissionProvider] = [self._primary, *self._fallbacks]

    def primary(self) -> PermissionProvider:
        """无法合并的操作（get_apply_url / get_apply_data）走主 Provider。"""
        return self._primary

    def _try_chain(self, fn_name: str, *args, **kwargs):
        """按 primary → fallbacks 顺序调用同名方法，遇 ProviderUnavailable 尝试下一个。"""
        fallback_on_error: bool = self.options.get("fallback_on_error", True)
        last_exc: BaseException | None = None
        for idx, provider in enumerate(self._chain):
            try:
                method = getattr(provider, fn_name)
                return method(*args, **kwargs)
            except ProviderUnavailable as exc:
                last_exc = exc
                if idx == 0 and not fallback_on_error:
                    raise
                continue
        assert last_exc is not None
        raise last_exc

    def is_allowed(self, request: AuthRequest) -> bool:
        return self._try_chain("is_allowed", request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        return self._try_chain("batch_by_resource", request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        return self._try_chain("batch_by_action", request)

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """Primary 语义：主 Provider 结果为准；主抛 ProviderUnavailable 时按顺序 fallback。"""
        return self._try_chain("filter_visible_resources", subject, action_id, candidates)
