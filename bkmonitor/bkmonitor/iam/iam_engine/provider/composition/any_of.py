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
# AnyOfPolicy —— 任一 Provider allow 即 allow
#
# 典型场景：v3 → v4 双写迁移过渡期，宽松放行避免误伤。
# 语义：
#   * is_allowed：短路求值，第一个返回 True 即返回 True
#   * batch_by_resource / batch_by_action：对每个 Provider 分别求，取并集
#
# options:
#   max_workers: int = 1     —— 并发度；>1 时用线程池并发调各 Provider
#   strict_errors: bool = False —— False: 跳过异常 Provider 继续（宽松，默认）
#                                 True: 任一 Provider 异常即上抛
# ---------------------------------------------------------------------------

from typing import Any

from ...core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
    VisibleResult,
    to_resource_type_id,
)
from ...provider.composition.base import CompositionPolicy


class AnyOfPolicy(CompositionPolicy):
    """任一 Provider allow 即 allow（宽松组合）。"""

    def __init__(self, providers: list[Any], **options: Any) -> None:
        super().__init__(providers, **options)

    @property
    def _strict_errors(self) -> bool:
        return bool(self.options.get("strict_errors", False))

    # ---- is_allowed ----

    def is_allowed(self, request: AuthRequest) -> bool:
        last_error: BaseException | None = None
        succeeded = 0
        for result, is_error in self._call_all("is_allowed", request):
            if is_error:
                last_error = result
                if self._strict_errors:
                    raise result
                continue
            succeeded += 1
            if result:
                return True
        if succeeded == 0 and last_error is not None:
            raise last_error
        return False

    # ---- batch_by_resource ----

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        allowed_keys: set[tuple[str, str]] = set()
        for result, is_error in self._call_all("batch_by_resource", request):
            if is_error:
                if self._strict_errors:
                    raise result
                continue
            for item in result.items:
                if item.allowed:
                    allowed_keys.add((item.action_id, item.resource_id))
        return BatchAuthResult(
            items=tuple(
                ResourceAuthResult(
                    action_id=request.action_id,
                    resource_type=to_resource_type_id(r.type),
                    resource_id=r.id,
                    allowed=(request.action_id, r.id) in allowed_keys,
                )
                for r in request.resources
            )
        )

    # ---- batch_by_action ----

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        allowed_actions: set[str] = set()
        for result, is_error in self._call_all("batch_by_action", request):
            if is_error:
                if self._strict_errors:
                    raise result
                continue
            for item in result.items:
                if item.allowed:
                    allowed_actions.add(item.action_id)
        resource_id = request.resource.id if request.resource else ""
        resource_type = to_resource_type_id(request.resource.type) if request.resource else ""
        return BatchAuthResult(
            items=tuple(
                ResourceAuthResult(
                    action_id=aid,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    allowed=aid in allowed_actions,
                )
                for aid in request.action_ids
            )
        )

    # ---- filter_visible_resources ----

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: Any,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """AnyOf 语义：任一 Provider 命中即命中，异常侧按 strict_errors 决定是否上抛。

        非 strict 模式（默认）：
          * 跳过抛异常的 Provider（保留其它 Provider 已有的可见性）
          * 合并成功侧：all_granted 取 OR，visible_ids 取并集
          * 所有 Provider 都失败时抛最后一次异常，避免"上层降级为空"这种静默错误

        strict 模式：任一 Provider 抛异常即上抛（对齐 is_allowed 的行为契约）。
        """
        all_granted = False
        ids: set[str] = set()
        succeeded = 0
        last_error: BaseException | None = None
        for result, is_error in self._call_all("filter_visible_resources", subject, action_id, candidates):
            if is_error:
                last_error = result
                if self._strict_errors:
                    raise result
                continue
            succeeded += 1
            all_granted = all_granted or result.all_granted
            ids.update(result.visible_ids)
        if succeeded == 0 and last_error is not None:
            raise last_error
        return VisibleResult(all_granted=all_granted, visible_ids=tuple(ids))
