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
#   * providers[0] 是主，其余是备
#   * 主返回结果时以主为准（无论 allow/deny）
#   * 主抛 ProviderUnavailable（**注意：不是 ProviderError**）时按顺序尝试备
#   * 全部不可用时抛最后一个异常
#
# options:
#   fallback_on_error: bool = True   —— False 时主故障不 fallback（直接抛）
# ---------------------------------------------------------------------------

from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
)
from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy


class PrimaryPolicy(CompositionPolicy):
    """主决策，主故障时按顺序 fallback 到备。

    与 AnyOfPolicy 的区别：
      * PrimaryPolicy 尊重主的 deny 决策（主返回 False 即 False）
      * AnyOfPolicy 会继续尝试备（宽松放行）
    """

    def _try_chain(self, fn_name: str, *args, **kwargs):
        """按 providers 顺序调用同名方法，遇 ProviderUnavailable 尝试下一个。"""
        fallback_on_error: bool = self.options.get("fallback_on_error", True)
        last_exc: BaseException | None = None
        for idx, provider in enumerate(self.providers):
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
