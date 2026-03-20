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

    @classmethod
    def _validate_condition_item(cls, cond: dict, effective_dimensions: set | None = None):
        if not isinstance(cond, dict):
            raise ValidationError({"conditions": f"conditions 条目必须为 dict，当前为 {type(cond)}"})

        required_keys = {"key", "method", "value"}
        missing = required_keys - set(cond.keys())
        if missing:
            raise ValidationError({"conditions": f"conditions 条目缺少字段: {sorted(missing)}"})

        key = cond.get("key")
        method = cond.get("method")
        value = cond.get("value")

        if not isinstance(key, str) or not key:
            raise ValidationError({"conditions": "conditions.key 必须为非空字符串"})
        if method not in cls.VALID_CONDITION_METHODS:
            raise ValidationError({"conditions": f"不支持的 method: {method}"})
        if value is None:
            raise ValidationError({"conditions": "conditions.value 不能为空"})
        if effective_dimensions is not None and key not in effective_dimensions:
            raise ValidationError({"conditions": f"conditions.key={key} 不在可用维度集合中"})

    def clean(self):
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError({"alert_levels": "alert_levels 必须为 [1,2,3] 的非空子集"})

        for cond in self.conditions:
            self._validate_condition_item(cond, set(self.aggregate_dimensions) if self.aggregate_dimensions else None)


class StrategyIssueConfigService:
    """StrategyIssueConfig 的创建 / 更新入口，含跨模型校验"""

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

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
            try:
                StrategyIssueConfig._validate_condition_item(cond, effective_dimensions)
            except ValidationError as e:
                raise ValueError(e.message_dict.get("conditions", [str(e)])[0])

    @classmethod
    def save(cls, strategy_id: int, config_data: dict) -> StrategyIssueConfig:
        """
        创建或更新配置。
        校验顺序：跨模型子集校验 → Model.clean() 格式校验 → 全部通过后才落库。
        """
        from bkmonitor.models.strategy import StrategyModel
        from bkmonitor.strategy.new_strategy import Strategy

        strategies = Strategy.from_models(StrategyModel.objects.filter(id=strategy_id))
        if not strategies:
            raise ValueError(f"strategy_id={strategy_id} 不存在")
        strategy_obj = strategies[0]

        aggregate_dimensions = config_data.get("aggregate_dimensions", [])
        conditions = config_data.get("conditions", [])

        strategy_dimensions = set(strategy_obj.public_dimensions)
        cls.validate_aggregate_dimensions(aggregate_dimensions, strategy_dimensions)
        effective_dimensions = set(aggregate_dimensions) if aggregate_dimensions else strategy_dimensions
        if conditions:
            cls.validate_conditions(conditions, effective_dimensions)
        config_data["bk_biz_id"] = strategy_obj.bk_biz_id

        temp = StrategyIssueConfig(strategy_id=strategy_id, **config_data)
        temp.full_clean()

        config, _ = StrategyIssueConfig.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=config_data,
        )
        return config


def _has_cache_role() -> bool:
    """仅 api / worker 进程具备缓存写入能力；web 进程无缓存配置，跳过。"""
    from django.conf import settings

    return settings.ROLE in ("api", "worker")


@receiver(post_save, sender=StrategyIssueConfig)
def upsert_strategy_issue_config_cache(sender, instance, **kwargs):
    if not _has_cache_role():
        return
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        StrategyIssueConfigCache.upsert(instance)
    except Exception:
        pass


@receiver(post_delete, sender=StrategyIssueConfig)
def invalidate_strategy_issue_config_cache(sender, instance, **kwargs):
    if not _has_cache_role():
        return
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        StrategyIssueConfigCache.invalidate(instance.strategy_id)
    except Exception:
        pass
