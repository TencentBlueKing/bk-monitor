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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.framework import IAMFramework

_framework: IAMFramework | None = None


def _set_framework(fw: IAMFramework) -> None:
    """存入模块级单例（由 conf.load_framework() 调用）。"""
    global _framework
    _framework = fw


def get_framework() -> IAMFramework:
    """获取 IAMFramework 单例。

    Raises:
        RuntimeError: 框架尚未初始化（IAMEngineConfig.ready() 未执行）
    """
    if _framework is None:
        raise RuntimeError(f"IAMFramework has not been initialized. Ensure {__package__!r} is in INSTALLED_APPS.")
    return _framework
