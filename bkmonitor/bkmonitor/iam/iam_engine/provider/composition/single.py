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
# SinglePolicy —— 单 Provider 直通
#
# 唯一存在的场景：项目只配置了一个 Provider（例如生产环境只跑 v4）。
# 所有方法直接委托给 self.providers[0]，无组合逻辑。
# ---------------------------------------------------------------------------

from bkmonitor.iam.iam_engine.core.exceptions import ConfigError
from bkmonitor.iam.iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
)
from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy


class SinglePolicy(CompositionPolicy):
    """单 Provider 直通策略。

    要求 providers 恰好含 1 个元素；多元素时 ConfigError。
    """

    def __init__(self, providers, **options) -> None:
        super().__init__(providers, **options)
        if len(self.providers) != 1:
            raise ConfigError(f"SinglePolicy requires exactly 1 provider, got {len(self.providers)}")

    def is_allowed(self, request: AuthRequest) -> bool:
        return self.providers[0].is_allowed(request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        return self.providers[0].batch_by_resource(request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        return self.providers[0].batch_by_action(request)
