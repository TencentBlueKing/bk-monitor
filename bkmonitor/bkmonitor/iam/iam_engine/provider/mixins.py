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
# Provider Mixins —— 通用实现片段，防止各 Provider 重复造轮子
#
# 提供：
#   * BatchMixin              —— 批量鉴权自动分片（batch_by_resource + batch_by_action）
#                               通过 MAX_WORKERS 控制串/并行：
#                                   MAX_WORKERS = 1 (默认) → 串行
#                                   MAX_WORKERS > 1        → ThreadPoolExecutor 并行
#   * auth_request_to_batch() —— 单次 AuthRequest → 单元素批量请求
#
# 使用规则：
#   * mixin 要放在继承链的**左侧**：
#         class V4PermissionProvider(BatchMixin, PermissionProvider): ...
#   * mixin 内部不实例化任何东西；假定子类已经通过 PermissionProvider.__init__
#     初始化了 self.ctx / self.options
# ---------------------------------------------------------------------------

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from ..core.exceptions import ProviderUnavailable
from ..core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
    to_action_id,
)
from ..core.utils import chunked

if TYPE_CHECKING:
    from ..schema.definitions import ActionDef


class BatchMixin:
    """批量鉴权通用 Mixin。提供 batch_by_resource + batch_by_action 两项能力。

    子类实现两个 page-hook：
        _batch_by_resource_page(subject, action_id, batch) -> list[ResourceAuthResult]
        _batch_by_action_page(subject, action_ids, resource) -> list[ResourceAuthResult]

    子类可覆盖：
        CHUNK_SIZE      —— 每批大小（默认 20）
        MAX_WORKERS     —— 并发度（默认 1 = 串行；>1 = ThreadPoolExecutor 并行）
    """

    #: 单次批量调用的最大条目数。
    CHUNK_SIZE: int = 20
    #: 并发 worker 数。1 = 串行，>1 = ThreadPoolExecutor 并行。
    MAX_WORKERS: int = 1

    # ------------------------------------------------------------------
    # batch_by_resource
    # ------------------------------------------------------------------

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """自动分片 + 串/并行调用 _batch_by_resource_page，合并结果保序。"""
        action_id = to_action_id(request.action_id)
        chunks = [list(c) for c in chunked(request.resources, self.CHUNK_SIZE)]
        if not chunks:
            return BatchAuthResult(items=())

        if self.MAX_WORKERS <= 1 or len(chunks) <= 1:
            items: list[ResourceAuthResult] = []
            for chunk in chunks:
                items.extend(self._batch_by_resource_page(request.subject, action_id, chunk))
        else:
            items = self._parallel_batch(
                chunks,
                lambda c: self._batch_by_resource_page(request.subject, action_id, c),
            )
        return BatchAuthResult(items=tuple(items))

    def _batch_by_resource_page(
        self,
        subject: Subject,
        action_id: ActionDef | str,
        batch: list[ResourceInstance],
    ) -> list[ResourceAuthResult]:
        """处理单批（<= CHUNK_SIZE）资源的鉴权。子类必须实现。"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # batch_by_action
    # ------------------------------------------------------------------

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """自动分片 + 串/并行调用 _batch_by_action_page，合并结果保序。"""
        action_ids = [to_action_id(a) for a in request.action_ids]
        chunks = [list(c) for c in chunked(action_ids, self.CHUNK_SIZE)]
        if not chunks:
            return BatchAuthResult(items=())

        if self.MAX_WORKERS <= 1 or len(chunks) <= 1:
            items: list[ResourceAuthResult] = []
            for chunk in chunks:
                items.extend(self._batch_by_action_page(request.subject, chunk, request.resource))
        else:
            items = self._parallel_batch(
                chunks,
                lambda c: self._batch_by_action_page(request.subject, c, request.resource),
            )
        return BatchAuthResult(items=tuple(items))

    def _batch_by_action_page(
        self,
        subject: Subject,
        action_ids: list[str],
        resource: ResourceInstance | None,
    ) -> list[ResourceAuthResult]:
        """处理单批（<= CHUNK_SIZE）action 的鉴权。子类必须实现。"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 内部：并行执行
    # ------------------------------------------------------------------

    def _parallel_batch(
        self,
        chunks: list[list],
        fn: Callable[[list], list[ResourceAuthResult]],
    ) -> list[ResourceAuthResult]:
        """ThreadPoolExecutor 并行执行分片，按 chunk 原始顺序合并结果。

        fn 接收单个 chunk，返回 list[ResourceAuthResult]。
        部分 chunk 失败时聚合所有异常并抛出 ProviderUnavailable。
        """
        items: list[ResourceAuthResult] = []
        max_workers = min(self.MAX_WORKERS, len(chunks))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fn, chunk): i for i, chunk in enumerate(chunks)}
            results_by_idx: dict[int, list[ResourceAuthResult]] = {}
            errors: list[tuple[int, Exception]] = []
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results_by_idx[idx] = future.result()
                except Exception as e:
                    errors.append((idx, e))
            if errors:
                raise ProviderUnavailable(
                    f"BatchMixin: {len(errors)}/{len(chunks)} chunks failed: "
                    + "; ".join(f"[{i}] {e}" for i, e in errors[:3])
                )
            for idx in sorted(results_by_idx):
                items.extend(results_by_idx[idx])
        return items


#: 向后兼容别名
ChunkedBatchMixin = BatchMixin


# ---------------------------------------------------------------------------
# 便捷 helper：把单次 AuthRequest 转成"单元素批量"以复用批量路径
# ---------------------------------------------------------------------------


def auth_request_to_batch(request: AuthRequest) -> BatchByResourceRequest:
    """把单条 AuthRequest 转成"单元素批量"请求。"""
    return BatchByResourceRequest(
        subject=request.subject,
        action_id=request.action_id,
        resources=(request.resource,) if request.resource else (),
        environment=request.environment,
    )
