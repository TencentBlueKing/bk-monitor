"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Tuple, Type

from django.utils.module_loading import import_string
from typing_extensions import Protocol

if TYPE_CHECKING:
    from alarm_backends.core.control.item import Item
    from alarm_backends.service.detect import DataPoint  # noqa

logger = logging.getLogger("core.control")


@dataclass
class DoubleCheckStrategy(Protocol):
    """二次确认策略

    不同于 detect 算法，该模型聚焦于对数据的二次检验
    """

    DOUBLE_CHECK_CONTEXT_KEY: ClassVar[str] = "__double_check_result"
    DOUBLE_CHECK_CONTEXT_VALUE: ClassVar[str] = ""

    name: ClassVar[str]
    item: "Item"

    # 策略 ID 限定，若策略 ID 为空，则意味着不进行灰度匹配
    # Q: 为什么不和其他限定一样，使用 ClassVar？
    # A: 因为策略ID限定可能从 DB 配置中获取，ClassVar 进程唯一，无法动态修改
    match_strategy_ids: List[int]

    # scope 限定: [(source, type),]，当不需要限定时，请手动指定为 []
    data_scopes: ClassVar[List[Tuple[str, str]]]

    # 聚合方法限定，不需要限定时为 None
    match_agg_method: ClassVar[Optional[str]]

    # 检测算法匹配序列，越靠前的优先级越高
    match_algorithms_type_sequence: ClassVar[List[str]]

    def _check_data_scopes(self) -> bool:
        """检查数据范围"""
        # 当不需要限定时，直接放过
        if not bool(self.data_scopes):
            return True

        for scope in self.data_scopes:
            source_scope, type_scope = scope
            for source_ in self.item.data_source_labels:
                if source_ != source_scope:
                    continue

                for type_ in self.item.data_type_labels:
                    # 当且仅当两个 label 均相等时命中
                    if type_ == type_scope:
                        return True

        return False

    def _check_agg_method(self) -> bool:
        """检查聚合方法"""
        if self.match_agg_method is None:
            return True

        return self.match_agg_method in self.item.agg_methods

    def get_algorithm_type_by_level(self, level: str) -> str:
        """通过告警等级获取目标算法类型"""

        for algorithms_info in self.item.algorithms:
            if algorithms_info.get("level") == int(level):
                return algorithms_info["type"]

        raise ValueError("No matched algorithm")

    def get_best_match_algorithm(self) -> str:
        """获取最佳匹配算法"""

        best_index: Optional[int] = None
        for type_ in self.item.algorithm_types:
            try:
                index = self.match_algorithms_type_sequence.index(type_)
                if best_index is None:
                    best_index = index

                # 找到优先级最高的算法
                if index < best_index:
                    best_index = index

            except ValueError:
                continue

        if best_index is None:
            raise ValueError("No matched algorithm")

        return self.match_algorithms_type_sequence[best_index]

    def _check_algorithms_type(self) -> bool:
        """检查检测算法"""
        if not self.match_algorithms_type_sequence:
            return True

        try:
            self.get_best_match_algorithm()
        except ValueError:
            return False
        else:
            return True

    def _check_strategy_ids(self) -> bool:
        """检查策略ID白名单"""
        # 当策略白名单为空时，即表示不灰度
        if not bool(self.match_strategy_ids):
            return True

        return int(self.item.strategy.id) in self.match_strategy_ids

    def check_extra(self) -> bool:
        """额外检查，当存在一些非通用的过滤方法时，可以覆盖该方法"""
        return True

    def check_hit(self) -> bool:
        """检查是否命中

        当前判断机制比较简单，耗时较短，能保证策略快照的时效性
        """
        if not self._check_data_scopes():
            return False

        if not self._check_agg_method():
            return False

        if not self._check_algorithms_type():
            return False

        return self.check_extra()

    def double_check(self, outputs: List[dict]):
        """[NotImplemented]二次确认
        当检测存在异常状况时返回 False，正常返回 True
        """
        raise NotImplementedError


_strategies: Dict[str, Type[DoubleCheckStrategy]] = {}


def register_double_check_strategy(strategy: Type[DoubleCheckStrategy]):
    """注册二次确认策略"""
    if strategy.name in _strategies:
        logger.debug("DoubleCheckStrategy<%s> already registered", strategy.name)
        return

    _strategies[strategy.name] = strategy


def load_all_strategies():
    """加载所有二次确认策略"""
    strategies_path = "alarm_backends.service.detect.double_check_strategies.all_strategies"
    for s in import_string(strategies_path):
        register_double_check_strategy(s)


def pick_double_check_strategy(item: "Item") -> Optional[DoubleCheckStrategy]:
    """拣选二次确认策略"""
    # TODO: 当前仅返回第一个匹配成功的策略，后续不满足的场景按需调整
    for _, strategy_cls in _strategies.items():
        ins = strategy_cls.__call__(item)
        if ins.check_hit():
            return ins

    logger.debug("无可用二次确认逻辑，跳过")
    return None


class DoubleCheckMixin:
    def double_check(self: "Item", outputs: List[dict]):
        """二次确认"""
        load_all_strategies()
        strategy = pick_double_check_strategy(item=self)

        if strategy is None:
            return

        strategy.double_check(outputs=outputs)
