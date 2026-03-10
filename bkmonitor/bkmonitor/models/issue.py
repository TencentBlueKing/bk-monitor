"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from alarm_backends.core.cache.strategy import StrategyCacheManager
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel

__all__ = ["StrategyIssueConfig", "StrategyIssueConfigService"]


class StrategyIssueConfig(AbstractRecordModel):
    """策略 Issue 聚合配置（唯一 MySQL 表）"""

    class Meta:
        db_table = "bkmonitor_strategy_issue_config"
        verbose_name = "策略 Issue 聚合配置"

    strategy_id = models.IntegerField(unique=True, db_index=True, verbose_name="策略 ID")
    bk_biz_id = models.IntegerField(db_index=True, verbose_name="业务 ID")
    aggregate_dimensions = JsonField(default=list, verbose_name="聚合维度")
    conditions = JsonField(default=list, verbose_name="过滤条件")
    alert_levels = JsonField(default=list, verbose_name="生效告警级别")

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    def clean(self):
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError({"alert_levels": "alert_levels 必须为 [1,2,3] 的非空子集"})

        for cond in self.conditions:
            if not isinstance(cond, dict):
                raise ValidationError({"conditions": f"conditions 条目必须为 dict，当前为 {type(cond)}"})
            if cond.get("method") not in self.VALID_CONDITION_METHODS:
                raise ValidationError({"conditions": f"不支持的 method: {cond.get('method')}"})
            if self.aggregate_dimensions and cond.get("key") not in self.aggregate_dimensions:
                raise ValidationError({"conditions": f"conditions.key={cond.get('key')} 不在 aggregate_dimensions 中"})


class StrategyIssueConfigService:
    """StrategyIssueConfig 的创建 / 更新入口，含跨模型校验"""

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    @staticmethod
    def _get_strategy_public_dimensions(strategy: dict) -> set:
        """
        计算策略公共维度（跨 item / query_config 取交集）。
        维度语义与 CompositeProcessor.cal_public_dimensions 一致。
        """
        public_dimensions = None
        for item in strategy.get("items", []):
            for query_config in item.get("query_configs", []):
                dimensions = {dim for dim in query_config.get("agg_dimension", []) if dim}
                if public_dimensions is None:
                    public_dimensions = dimensions
                else:
                    public_dimensions &= dimensions
        return public_dimensions or set()

    @classmethod
    def validate_aggregate_dimensions(cls, aggregate_dimensions: list, strategy_dimensions: set):
        if not aggregate_dimensions:
            return

        invalid = set(aggregate_dimensions) - strategy_dimensions
        if invalid:
            raise ValueError(
                f"aggregate_dimensions 包含当前策略公共维度之外的字段: {invalid}，"
                f"当前策略 Strategy.public_dimensions 为: {strategy_dimensions}"
            )

    @classmethod
    def validate_conditions(cls, conditions: list, effective_dimensions: set):
        for cond in conditions:
            if not isinstance(cond, dict):
                raise ValueError(f"conditions 条目必须为 dict，当前为 {type(cond)}")
            if cond.get("method") not in cls.VALID_CONDITION_METHODS:
                raise ValueError(f"不支持的 method: {cond.get('method')}")
            if cond.get("key") not in effective_dimensions:
                raise ValueError(
                    f"conditions.key={cond.get('key')} 不在可用维度集合中，当前可用维度为: {effective_dimensions}"
                )

    @classmethod
    def save(cls, strategy_id: int, config_data: dict) -> StrategyIssueConfig:
        """
        创建或更新配置。
        校验顺序：跨模型子集校验 → Model.clean() 格式校验 → 全部通过后才落库。
        """
        aggregate_dimensions = config_data.get("aggregate_dimensions", [])
        conditions = config_data.get("conditions", [])

        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"strategy_id={strategy_id} 不存在或未缓存")

        strategy_dimensions = cls._get_strategy_public_dimensions(strategy)
        cls.validate_aggregate_dimensions(aggregate_dimensions, strategy_dimensions)
        effective_dimensions = set(aggregate_dimensions) if aggregate_dimensions else strategy_dimensions
        if conditions:
            cls.validate_conditions(conditions, effective_dimensions)
        config_data["bk_biz_id"] = strategy.get("bk_biz_id", 0)

        temp = StrategyIssueConfig(strategy_id=strategy_id, **config_data)
        temp.full_clean()

        config, _ = StrategyIssueConfig.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=config_data,
        )
        return config


@receiver(post_save, sender=StrategyIssueConfig)
def upsert_strategy_issue_config_cache(sender, instance, **kwargs):
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        StrategyIssueConfigCache.upsert(instance)
    except Exception:
        pass


@receiver(post_delete, sender=StrategyIssueConfig)
def invalidate_strategy_issue_config_cache(sender, instance, **kwargs):
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        StrategyIssueConfigCache.invalidate(instance.strategy_id)
    except Exception:
        pass
