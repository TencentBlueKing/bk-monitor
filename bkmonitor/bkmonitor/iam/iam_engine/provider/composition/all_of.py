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
# AllOfPolicy —— 所有 Provider 都 allow 才 allow
#
# 典型场景：敏感操作需双重验证（例如既过 v4 主鉴权，又过内部黑名单 Provider）。
# 语义：
#   * is_allowed：短路求值，第一个返回 False 即返回 False
#   * batch_by_resource / batch_by_action：对每个 Provider 分别求，取交集
#
# options:
#   max_workers: int = 1    —— 并发度；>1 时用线程池并发调各 Provider
#   strict_errors: bool = True —— True: 任一 Provider 异常即上抛（严格，默认）
#                                 False: 跳过异常 Provider，仅基于成功的决策
# ---------------------------------------------------------------------------

from typing import Any

from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
)
from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy


class AllOfPolicy(CompositionPolicy):
    """所有 Provider 都 allow 才 allow（严格组合）。"""

    def __init__(self, providers: list[Any], **options: Any) -> None:
        super().__init__(providers, **options)

    @property
    def _strict_errors(self) -> bool:
        return bool(self.options.get("strict_errors", True))

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
            if not result:
                return False
        if succeeded == 0 and last_error is not None:
            raise last_error
        return True

    # ---- batch_by_resource ----

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        allowed_sets: list[set[tuple[str, str]]] = []
        for result, is_error in self._call_all("batch_by_resource", request):
            if is_error:
                if self._strict_errors:
                    raise result
                continue
            allowed_sets.append({(item.action_id, item.resource_id) for item in result.items if item.allowed})
        allowed_keys = set.intersection(*allowed_sets) if allowed_sets else set()
        return BatchAuthResult(
            items=tuple(
                ResourceAuthResult(
                    action_id=request.action_id,
                    resource_type=r.type,
                    resource_id=r.id,
                    allowed=(request.action_id, r.id) in allowed_keys,
                )
                for r in request.resources
            )
        )

    # ---- batch_by_action ----

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        allowed_sets: list[set[str]] = []
        for result, is_error in self._call_all("batch_by_action", request):
            if is_error:
                if self._strict_errors:
                    raise result
                continue
            allowed_sets.append({item.action_id for item in result.items if item.allowed})
        allowed_actions = set.intersection(*allowed_sets) if allowed_sets else set()
        resource_id = request.resource.id if request.resource else ""
        resource_type = request.resource.type if request.resource else ""
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
