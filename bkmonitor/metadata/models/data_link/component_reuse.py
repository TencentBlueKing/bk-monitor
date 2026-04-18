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

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, TypeVar

from metadata.models.data_link.data_link_configs import (
    ConditionalSinkConfig,
    DataBusConfig,
    DataLinkResourceConfigBase,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)

if TYPE_CHECKING:
    from metadata.models.data_link.data_link import DataLink

logger = logging.getLogger("metadata")


ALL_DATA_LINK_COMPONENT_KINDS: list[type[DataLinkResourceConfigBase]] = [
    ResultTableConfig,
    VMStorageBindingConfig,
    ESStorageBindingConfig,
    DorisStorageBindingConfig,
    ConditionalSinkConfig,
    DataBusConfig,
]


LeftoverPolicy = Literal["strict", "keep"]


T = TypeVar("T", bound=DataLinkResourceConfigBase)


class ComponentReuseError(Exception):
    """DataLink 组件复用校验失败。

    当 apply_data_link 在 compose 完成后检测到当前 datalink 下仍存在未被 compose 认领、
    且对应 (strategy, kind) 的策略为 ``strict`` 的既有组件时抛出。

    该错误表示当前 datalink 已偏离预期状态（典型场景为脏数据），不应继续下发到 BKBase。
    """

    def __init__(
        self,
        data_link_name: str,
        strategy: str,
        violations: dict[type[DataLinkResourceConfigBase], list[DataLinkResourceConfigBase]],
    ) -> None:
        self.data_link_name = data_link_name
        self.strategy = strategy
        self.violations = violations
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [
            f"unexpected leftover components for data_link_name={self.data_link_name!r} strategy={self.strategy!r}:"
        ]
        for kind, components in self.violations.items():
            names = [c.name for c in components]
            lines.append(f"  - {kind.__name__} ({len(components)}): {names}")
        return "\n".join(lines)


class ExistingComponentContext:
    """当前 datalink 下已有组件的可消费上下文。

    设计意图：把"查询现有组件 + 逐 slot 认领 + 未被认领组件收尾检查"这件事从 compose
    分支中解耦出来。compose 分支只关心"我这个 slot 能不能认领一条既有组件"，认领规则
    完全由 compose 通过 ``predicate`` 自行表达。

    使用模式：

    1. ``apply_data_link`` 入口一次性通过 :meth:`from_datalink` 构造；
    2. compose 分支对每个将要生成的组件调用 :meth:`claim` 尝试复用；
    3. ``apply_data_link`` 在 compose 结束后、BKBase 下发前通过 :meth:`leftover`
       与 ``DataLink.REUSE_LEFTOVER_POLICY`` 做一次"未消费组件"检查。

    命名约定：

    - "claim"：从 pool 中按 predicate 取走一条既有组件，用于复用。
    - "leftover"：compose 跑完之后，pool 中未被 claim 的剩余组件。
    """

    def __init__(
        self,
        data_link_name: str,
        components_by_kind: dict[type[DataLinkResourceConfigBase], list[DataLinkResourceConfigBase]],
    ) -> None:
        self._data_link_name = data_link_name
        self._components_by_kind = components_by_kind

    @classmethod
    def from_datalink(cls, datalink: DataLink) -> ExistingComponentContext:
        """按 ALL_DATA_LINK_COMPONENT_KINDS 遍历并加载当前 datalink 下所有现有组件。

        加载条件：``bk_tenant_id + namespace + data_link_name`` 完全命中当前 datalink。
        不按 ``data_link_strategy`` 过滤，这样历史上由其它 strategy 创建的同名组件也
        会被纳入复用/leftover 检查范围，避免脏数据被静默忽略。
        """
        components_by_kind: dict[type[DataLinkResourceConfigBase], list[DataLinkResourceConfigBase]] = {}
        for kind in ALL_DATA_LINK_COMPONENT_KINDS:
            components_by_kind[kind] = list(
                kind.objects.filter(
                    bk_tenant_id=datalink.bk_tenant_id,
                    namespace=datalink.namespace,
                    data_link_name=datalink.data_link_name,
                )
            )
        logger.info(
            "ExistingComponentContext.from_datalink: data_link_name=%s loaded=%s",
            datalink.data_link_name,
            {kind.__name__: len(items) for kind, items in components_by_kind.items()},
        )
        return cls(data_link_name=datalink.data_link_name, components_by_kind=components_by_kind)

    def claim(
        self,
        kind: type[T],
        predicate: Callable[[T], bool],
    ) -> T | None:
        """按 predicate 从 pool 中认领一条既有组件。

        行为约定：

        - 恰好 1 条匹配：从 pool 中移除并返回该组件；
        - 0 条匹配：返回 ``None``，pool 不变；
        - ≥2 条匹配：返回 ``None``，pool 不变（歧义放弃复用，避免随机命中）。

        传入未在 ALL_DATA_LINK_COMPONENT_KINDS 中注册的 kind 会直接 :class:`ValueError`，
        以便在开发阶段及时暴露 compose 侧的编程错误，而不是静默返回 ``None``。
        """
        if kind not in self._components_by_kind:
            raise ValueError(
                f"ExistingComponentContext.claim: unsupported kind {kind.__name__!r}; "
                f"must be one of {[k.__name__ for k in ALL_DATA_LINK_COMPONENT_KINDS]}"
            )

        pool = self._components_by_kind[kind]
        matched = [item for item in pool if predicate(item)]
        if len(matched) != 1:
            logger.info(
                "ExistingComponentContext.claim: data_link_name=%s kind=%s matched=%d -> no reuse",
                self._data_link_name,
                kind.__name__,
                len(matched),
            )
            return None

        target = matched[0]
        pool.remove(target)
        logger.info(
            "ExistingComponentContext.claim: data_link_name=%s kind=%s claimed name=%s",
            self._data_link_name,
            kind.__name__,
            target.name,
        )
        return target  # type: ignore[return-value]

    def leftover(self) -> dict[type[DataLinkResourceConfigBase], list[DataLinkResourceConfigBase]]:
        """返回 pool 中未被 claim 的剩余组件，只包含非空 kind。"""
        return {kind: items for kind, items in self._components_by_kind.items() if items}
