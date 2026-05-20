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

from django.conf import settings

from metadata.models.data_link.data_link_configs import (
    BasereportSinkConfig,
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
    BasereportSinkConfig,
    ConditionalSinkConfig,
    DataBusConfig,
]


# 已在代码中真正接入 existing_context 参数的 data_link_strategy 白名单。
#
# 复用机制遵循"代码能力白名单 + 运行时开关"语义：
#
# - settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES：运维/灰度侧的开关，决定本次
#   部署里哪些 strategy 允许尝试复用；
# - ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE：单表开关，用于精准
#   指定某张 RT 进入复用逻辑；
# - REUSE_ENABLED_STRATEGIES：代码侧的实现声明，列出 compose_*_configs 已经改造
#   完成、可以安全接收 existing_context 参数的 strategy。
#
# 只有代码能力命中，且 strategy 灰度或单表开关任一命中，才会构造 ExistingComponentContext 并下传到
# compose 分支。这样当运维在 settings 里误配了一个尚未接入复用的 strategy 时，
# compose 层不会因为多出一个不认识的关键字参数而直接 ``TypeError``，而是带一条
# warning 日志回退到原有新建路径，保证"只会影响复用能力，不会把链路 apply 打挂"。
#
# 接入新 strategy 的 checklist：
#   1. 在对应 ``compose_*_configs`` 上加上 ``existing_context`` 形参；
#   2. 把该 strategy 对应的字符串常量加入下面的集合；
#   3. 补充 DataLink.REUSE_LEFTOVER_POLICY 中相关 (strategy, kind) 条目。
REUSE_ENABLED_STRATEGIES: set[str] = {
    "bk_exporter_time_series",
    "bk_standard_time_series",
    "bk_standard_v2_time_series",
}


def is_reuse_supported_for(strategy: str) -> bool:
    """判断某 strategy 的 compose 流程是否已接入组件复用。"""
    return strategy in REUSE_ENABLED_STRATEGIES


def _is_table_option_enabled(table_id: str | None, bk_tenant_id: str | None) -> bool:
    if not table_id or not bk_tenant_id:
        return False

    from metadata.models.result_table import ResultTableOption

    option = ResultTableOption.objects.filter(
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        name=ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE,
    ).first()
    return option is not None and option.get_value() is True


def is_reuse_enabled_for(strategy: str, table_id: str | None = None, bk_tenant_id: str | None = None) -> bool:
    """判断当前 datalink 是否应当启用组件复用。

    开关来源包含 strategy 级灰度与 RT option 级单表开关；``table_id`` 为空时不查询
    RT option，只保留原有 strategy 灰度语义。

    当 settings 中配置了该 strategy 但 :data:`REUSE_ENABLED_STRATEGIES` 未包含它时，
    打印一条 warning 提示"配了灰度但代码还没接入"，并返回 ``False`` 走老路径。
    """
    strategy_enabled = strategy in settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES
    table_enabled = _is_table_option_enabled(table_id=table_id, bk_tenant_id=bk_tenant_id)
    if not strategy_enabled and not table_enabled:
        return False
    if not is_reuse_supported_for(strategy):
        logger.warning(
            "component reuse: strategy=%s is enabled by runtime switch "
            "(strategy_enabled=%s, table_enabled=%s) but its compose pipeline has not been migrated yet "
            "(REUSE_ENABLED_STRATEGIES=%s); falling back to the legacy create path.",
            strategy,
            strategy_enabled,
            table_enabled,
            sorted(REUSE_ENABLED_STRATEGIES),
        )
        return False
    return True


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
