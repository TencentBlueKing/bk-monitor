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
# 当前提供：
#   * ChunkedBatchMixin       —— 批量鉴权自动分片（默认 20 一批）
#
# 使用规则：
#   * mixin 要放在继承链的**左侧**：
#         class V4PermissionProvider(ChunkedBatchMixin, PermissionProvider): ...
#   * mixin 内部不实例化任何东西；假定子类已经通过 PermissionProvider.__init__
#     初始化了 self.ctx / self.options
# ---------------------------------------------------------------------------

from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
)
from bkmonitor.iam.iam_engine.core.utils import chunked


class ChunkedBatchMixin:
    """为不支持无限批量的 Provider 提供分片能力。

    子类必须实现：
        _batch_by_resource_page(subject, action_id, batch) -> list[ResourceAuthResult]

    子类可覆盖：
        CHUNK_SIZE          —— 每批大小
    """

    #: 单次批量调用的最大条目数。
    CHUNK_SIZE: int = 20

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """自动分片调用 _batch_by_resource_page，合并结果保序。"""
        all_items: list[ResourceAuthResult] = []
        for batch in chunked(request.resources, self.CHUNK_SIZE):
            page = self._batch_by_resource_page(request.subject, request.action_id, list(batch))
            all_items.extend(page)
        return BatchAuthResult(items=tuple(all_items))

    def _batch_by_resource_page(
        self,
        subject: Subject,
        action_id: str,
        batch: list[ResourceInstance],
    ) -> list[ResourceAuthResult]:
        """处理单批（<= CHUNK_SIZE）的鉴权。子类必须实现。"""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 便捷 helper：把单次 AuthRequest 转成"单元素批量"以复用批量路径
# 上层用不到；仅供 Provider 内部实现 is_allowed 时避免重复代码使用
# ---------------------------------------------------------------------------


def auth_request_to_batch(request: AuthRequest) -> BatchByResourceRequest:
    """把单条 AuthRequest 转成"单元素批量"请求。"""
    return BatchByResourceRequest(
        subject=request.subject,
        action_id=request.action_id,
        resources=request.resources,
        environment=request.environment,
    )
