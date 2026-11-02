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
import time
from typing import Any

from alarm_backends.core.cache.circuit_breaking import CircuitBreakingCacheManager
from alarm_backends.core.circuit_breaking.groups import CircuitBreakingRuleGroupStore
from alarm_backends.core.circuit_breaking.matcher import gen_circuit_breaking_matcher

logger = logging.getLogger("circuit_breaking")


class BaseCircuitBreakingManager:
    module = ""
    legacy_fallback_module = None

    def __init__(self):
        self.config, self.matcher = self._load_legacy(self.module)
        if self.matcher is None and self.legacy_fallback_module:
            self.config, self.matcher = self._load_legacy(self.legacy_fallback_module)
        self.group_matchers = []
        self._group_snapshot_time = 0
        self._group_server_time_ms = 0
        try:
            snapshot = CircuitBreakingRuleGroupStore().snapshot(self.module)
            # Pair Redis TIME with receipt, excluding pre-sample request delays.
            # Transit/decoding after the server sample conservatively delays
            # local expiry; matcher construction and later elapsed time count.
            self._group_snapshot_time = time.monotonic()
            self._group_server_time_ms = snapshot["server_time_ms"]
            for group in snapshot["groups"]:
                matcher = gen_circuit_breaking_matcher(group["conditions"])
                self.group_matchers.append((group["expires_at_ms"], matcher))
        except Exception:
            logger.exception("[circuit breaking] [%s] failed to load rule groups", self.module)

    @staticmethod
    def _load_legacy(module):
        try:
            config = CircuitBreakingCacheManager.get_config(module)
            return config, gen_circuit_breaking_matcher(config)
        except Exception:
            logger.exception("[circuit breaking] [%s] failed to load legacy rules", module)
            return [], None

    def _active_group_matchers(self):
        # Monotonic elapsed time preserves independent deadlines for a manager
        # reused across many targets without another Redis call per target.
        now_ms = self._group_server_time_ms + (time.monotonic() - self._group_snapshot_time) * 1000
        return (matcher for expires_at_ms, matcher in self.group_matchers if expires_at_ms > now_ms)

    def __bool__(self) -> bool:
        return bool(self.matcher) or any(self._active_group_matchers())

    def is_cb(self, target_instance: dict) -> bool:
        """
        判断是否需要熔断
        :param target_instance: 目标实例数据
        :return: 是否需要熔断
        """
        matchers = ([self.matcher] if self.matcher else []) + list(self._active_group_matchers())
        if not matchers:
            return False

        # 清理目标实例维度
        clean_instance = self.clean_cb_dimension(**target_instance)

        # 使用统一匹配器进行匹配
        matched_rules = []
        for matcher in matchers:
            if matcher.is_match(clean_instance):
                matched_rules = matcher.config_rules
                break
        is_match = bool(matched_rules)

        if is_match:
            # 获取匹配的具体规则用于日志记录
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

    def is_strategy_only_circuit_breaking(self, strategy_id: int, labels: list | None = None) -> bool:
        """
        检查策略是否熔断（只检查策略ID维度）
        用于在processor中判断策略级别的熔断
        :param strategy_id: 策略ID
        :param labels: 标签
        :return: 策略是否熔断
        """
        try:
            # 只检查策略ID维度的熔断
            dimensions: dict[str, Any] = {"strategy_id": str(strategy_id)}
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
    legacy_fallback_module = "alert.builder"


class ActionCircuitBreakingManager(BaseCircuitBreakingManager):
    """
    Action 模块熔断管理器
    用于 FTA Action 模块的熔断控制
    plugin_type: config 支持基于处理套餐类型的细化熔
    """

    module = "action"

    @classmethod
    def clean_cb_dimension(
        cls, strategy_id=None, bk_biz_id=None, data_source_label=None, data_type_label=None, plugin_type=None, **kwargs
    ) -> dict:
        """
        清理Action模块的熔断维度
        :param strategy_id: 策略ID
        :param bk_biz_id: 业务ID
        :param data_source_label: 数据源标签
        :param data_type_label: 数据类型标签
        :param plugin_type: 插件类型（Action模块特有）
        :param kwargs: 其他参数
        :return: 清理后的维度数据
        """
        # 先调用父类方法处理基础字段
        dimension = super().clean_cb_dimension(
            strategy_id=strategy_id,
            bk_biz_id=bk_biz_id,
            data_source_label=data_source_label,
            data_type_label=data_type_label,
            **kwargs,
        )
        # 添加 plugin_type 处理（Action模块特有）
        if plugin_type is not None:
            dimension["plugin_type"] = str(plugin_type)
        return dimension
