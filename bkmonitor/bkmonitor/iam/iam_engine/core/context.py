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
# ProviderContext —— Provider 运行时依赖注入容器
#
# 目的：解耦 Provider 与 IAMEngine 主体，让 Provider 可以在框架之外被独立测试。
#   - ctx 是"只读上下文"，Provider 只从中读取自己需要的东西
#   - 单元测试构造一个 ProviderContext 即可，不必造整个框架
#
# 规则：
#   1. ProviderContext 是 frozen，构造后不可改
#   2. 不 import django；credentials/cache 都是接口，具体实现由 django 层注入
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from dataclasses import dataclass, field
from logging import Logger, getLogger
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # 避免运行时循环 import：schema/registry 反过来不应该 import core.context
    from bkmonitor.iam.iam_engine.schema.definitions import SystemDef
    from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry


_EMPTY_MAPPING: Mapping[str, Any] = MappingProxyType({})


class CacheBackend:
    """缓存后端接口（占位）。

    真正的实现由 django 层提供（例如 Django cache 或 Redis 直连）。
    Provider 通过 ctx.cache 使用，若为 None 表示不启用缓存。
    """

    def get(self, key: str) -> Any:  # pragma: no cover - 接口占位
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int = 0) -> None:  # pragma: no cover
        raise NotImplementedError

    def delete(self, key: str) -> None:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class ProviderContext:
    """Provider 构造时接收的只读上下文。

    Args:
        schema: 冻结后的 SchemaRegistry；Provider 可查询 action/resource_type 元数据
        system: 该 Provider 的系统信息（per-Provider，非框架共享）
        credentials: 该 Provider 的凭据（app_code/secret 等，由 credentials_provider 解析后传入）
        logger: 日志器；建议每个 Provider 用自己的 logger 名
        cache: 可选缓存后端；None 表示不启用
        options: 从 settings 里透传给该 Provider 的 options 字典（不可变视图）
    """

    schema: SchemaRegistry
    system: SystemDef | None = None
    credentials: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)
    logger: Logger = field(default_factory=lambda: getLogger("iam_engine"))
    cache: CacheBackend | None = None
    options: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAPPING)
