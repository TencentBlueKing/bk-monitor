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
# 框架内部通用工具
#
# 规则：
#   1. 不 import django、iam SDK、requests 等外部依赖
#   2. 每个函数保持无状态、纯函数
#   3. 只放"跨 3 个以上模块被复用"的东西，避免 utils 膨胀
# ---------------------------------------------------------------------------

from collections.abc import Iterator, Sequence
from typing import TypeVar

_T = TypeVar("_T")


def chunked(items: Sequence[_T], size: int) -> Iterator[Sequence[_T]]:
    """把序列按固定大小切片。

    典型使用场景：v4 Provider 内部把批量鉴权拆成 <=100 条一批。

    Args:
        items: 待切分的序列
        size: 每片大小；必须 > 0

    Yields:
        序列切片；最后一片可能不满

    Example:
        >>> list(chunked([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError(f"chunk size must be positive, got {size}")
    for i in range(0, len(items), size):
        yield items[i : i + size]
