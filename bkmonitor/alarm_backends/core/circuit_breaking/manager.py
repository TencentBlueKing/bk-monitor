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

from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager
from alarm_backends.core.circuit_breaking.matcher import gen_circuit_breaking_matcher

logger = logging.getLogger("circuit_breaking")


class BaseCircuitBreakingManager:
    module = ""

    def __init__(self):
        self.config = CircuitBreakingCacheManager.get_config(self.module)
        self.matcher = gen_circuit_breaking_matcher(self.config)

    def __bool__(self) -> bool:
        return bool(self.matcher)

    def is_cb(self, target_instance: dict) -> bool:
        """
        判断是否需要熔断
        :param target_instance: 目标实例数据
        :return: 是否需要熔断
        """
        if not self.matcher:
            return False

        # 清理目标实例维度
        clean_instance = self.clean_cb_dimension(**target_instance)

        # 使用统一匹配器进行匹配
        is_match = self.matcher.is_match(clean_instance)

        if is_match:
            # 获取匹配的具体规则用于日志记录
            matched_rules = self.matcher.config_rules
            logger.debug(
                f"[circuit breaking] [{self.module}] circuit breaking triggered for module {self.module}, "
                f"matched_rules: {matched_rules}, instance: {clean_instance}"
            )

        return is_match

    @classmethod
    def clean_cb_dimension(
        cls, strategy_id=None, bk_biz_id=None, data_source_label=None, data_type_label=None, **kwargs
    ) -> dict:
        """
        清理Access Data模块的熔断维度
        :param strategy_id: 策略ID
        :param bk_biz_id: 业务ID
        :param data_source_label: 数据源标签
        :param data_type_label: 数据类型标签
        :param kwargs: 其他参数
        :return: 清理后的维度数据
        """
        dimension = {}

        if strategy_id is not None:
            dimension["strategy_id"] = str(strategy_id)
        if bk_biz_id is not None:
            dimension["bk_biz_id"] = str(bk_biz_id)
        if data_source_label:
            dimension["data_source_label"] = str(data_source_label)
        if data_type_label:
            dimension["data_type_label"] = str(data_type_label)
        if all([data_source_label, data_type_label]):
            dimension["strategy_source"] = f"{data_source_label}:{data_type_label}"
        # todo labels 支持
        # if "labels" in kwargs:
        #     dimension["labels"] = kwargs["labels"]
        return dimension

    def is_circuit_breaking(self, **kwargs) -> bool:
        """
        检查数据源是否需要熔断（不包括策略级别的熔断）
        :param bk_biz_id: 业务ID
        :param data_source_label: 数据源标签
        :param data_type_label: 数据类型标签
        :param strategy_id: 策略ID
        :return: 是否需要熔断
        """
        if not kwargs:
            return False
        try:
            target_instance = {}
            target_instance.update(kwargs)
            return self.is_cb(target_instance)
        except Exception as e:
            logger.exception(
                f"[circuit breaking] [access.data] data source circuit breaking check failed for kwargs {kwargs}: {e}"
            )
            return False

    def is_strategy_only_circuit_breaking(self, strategy_id: int, labels: list = None) -> bool:
        """
        检查策略是否熔断（只检查策略ID维度）
        用于在processor中判断策略级别的熔断
        :param strategy_id: 策略ID
        :param labels: 标签
        :return: 策略是否熔断
        """
        try:
            # 只检查策略ID维度的熔断
            dimensions = {"strategy_id": str(strategy_id)}
            if labels is not None:
                dimensions["labels"] = labels
            return self.is_cb(dimensions)
        except Exception as e:
            logger.exception(
                f"[circuit breaking] [access.data] strategy circuit breaking check failed for strategy_id {strategy_id}: {e}"
            )
            return False


class AccessDataCircuitBreakingManager(BaseCircuitBreakingManager):
    """
    Access Data 模块熔断管理器
    """

    module = "access.data"


class AlertBuilderCircuitBreakingManager(BaseCircuitBreakingManager):
    """
    Alert Builder 模块熔断管理器
    """

    module = "alert.builder"


class AlertManagerCircuitBreakingManager(BaseCircuitBreakingManager):
    """
    Alert Manager 模块熔断管理器
    alert.manager 模块同步应用熔断规则, 规则模块尝试从alert.manager获取, 如果未配置, 则复用alert.builder中的熔断规则
    """

    module = "alert.manager"

    def __init__(self):
        super().__init__()
        if self.matcher is None:
            self.config = CircuitBreakingCacheManager.get_config("alert.builder")
            self.matcher = gen_circuit_breaking_matcher(self.config)


class ActionCircuitBreakingManager(BaseCircuitBreakingManager):
    """
    Action 模块熔断管理器
    用于 FTA Action 模块的熔断控制
    plugin_type: config 支持基于处理套餐类型的细化熔
    """

    module = "action"
