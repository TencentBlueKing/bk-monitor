"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.db.fields import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel

logger = logging.getLogger("bkmonitor")


class StrategyIssueConfig(AbstractRecordModel):
    """策略 Issue 聚合配置

    每条 Strategy 至多一条配置（unique_together = strategy_id）。
    格式校验在 clean() 中完成。
    跨模型校验（aggregate_dimensions 子集、conditions.key 有效性、bk_biz_id 回填）
    由同文件的 StrategyIssueConfigManager 完成，不在 Model 层做跨模型查询。
    """

    class Meta:
        db_table = "bkmonitor_strategy_issue_config"
        verbose_name = _("策略 Issue 聚合配置")
        verbose_name_plural = _("策略 Issue 聚合配置")

    strategy_id = models.IntegerField(unique=True, db_index=True, verbose_name=_("策略 ID"))
    bk_biz_id = models.IntegerField(db_index=True, verbose_name=_("业务 ID"))

    # aggregate_dimensions: 当前策略公共维度子集（空列表表示使用 Strategy.public_dimensions 全量）
    # 格式: ["bk_target_ip", "service"]
    aggregate_dimensions = JsonField(default=list, verbose_name=_("聚合维度"))

    # conditions: 过滤条件列表，key 必须属于生效维度集合
    # 格式: [{"key": "service", "method": "eq", "value": ["order"]}]
    # method 支持: eq / neq / include / exclude / reg / nreg
    conditions = JsonField(default=list, verbose_name=_("过滤条件"))

    # alert_levels: 生效告警级别子集（1=致命, 2=预警, 3=提醒）
    # 格式: [1, 2, 3]
    alert_levels = JsonField(default=list, verbose_name=_("生效告警级别"))

    def clean(self):
        """配置字段格式校验（不做跨模型维度校验，跨模型校验由 StrategyIssueConfigManager 完成）"""
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError(_("alert_levels 必须为 [1,2,3] 的非空子集"))

        valid_methods = {"eq", "neq", "include", "exclude", "reg", "nreg"}
        for cond in self.conditions:
            if cond.get("method") not in valid_methods:
                raise ValidationError(_("不支持的 method: {}").format(cond.get("method")))
            if self.aggregate_dimensions and cond.get("key") not in self.aggregate_dimensions:
                raise ValidationError(
                    _("conditions.key={} 不在 aggregate_dimensions 中").format(cond.get("key"))
                )

    def __str__(self):
        return f"StrategyIssueConfig(strategy_id={self.strategy_id}, bk_biz_id={self.bk_biz_id})"


# ── 缓存失效信号 ──────────────────────────────────────────────────────────────


@receiver(post_save, sender=StrategyIssueConfig)
@receiver(post_delete, sender=StrategyIssueConfig)
def invalidate_strategy_issue_config_cache(sender, instance, **kwargs):
    """配置写入/删除后主动失效 Redis 缓存"""
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCacheManager

        StrategyIssueConfigCacheManager.invalidate(instance.strategy_id)
    except Exception:  # NOCC:broad-except(避免信号异常影响主流程)
        pass


# ── 业务逻辑 Manager ──────────────────────────────────────────────────────────


class StrategyIssueConfigManager:
    """StrategyIssueConfig 的创建 / 更新入口，含跨模型校验

    分层设计：
    - StrategyIssueConfig（Model）：DB 持久化 + 格式校验
    - StrategyIssueConfigManager（本类）：跨模型校验 + 写入 DB（位于 bkmonitor/ 业务层）
    - StrategyIssueConfigCacheManager（alarm_backends/core/cache/）：DB → Redis 周期刷新
    - 后台 issue_processor.py 仅从 Redis 读配置，不直接访问 DB

    校验顺序：
      1. 跨模型子集校验（aggregate_dimensions ⊆ Strategy.public_dimensions）
      2. conditions.key 有效性校验（⊆ 生效维度集合）
      3. bk_biz_id 由 strategy_id 对应策略缓存回填，不接受外部指定
      4. Model.clean() 格式校验（构造临时实例，不落库）
      5. 全部通过后 update_or_create 落库（post_save 信号触发缓存失效）
    """

    @staticmethod
    def _get_strategy_public_dimensions(strategy: dict) -> set:
        """从策略缓存快照中提取公共维度集合

        - 单 Item：取 query_configs 中所有 agg_dimension 的交集
        - 多 Item：取各 Item 公共维度的再次交集
        """
        item_public_dimensions = []
        for item in strategy.get("items", []):
            query_dimensions = []
            for query in item.get("query_configs", []):
                dims = {dim for dim in query.get("agg_dimension", []) if dim}
                if dims:
                    query_dimensions.append(dims)
            if not query_dimensions:
                continue
            item_public_dimensions.append(set.intersection(*query_dimensions))

        if not item_public_dimensions:
            return set()
        return set.intersection(*item_public_dimensions)

    @classmethod
    def _get_strategy(cls, strategy_id: int) -> dict:
        """从策略缓存中获取策略快照，不存在则 raise ValueError"""
        from alarm_backends.core.cache.strategy import StrategyCacheManager

        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"strategy_id={strategy_id} 不存在或未缓存")
        return strategy

    @classmethod
    def validate_aggregate_dimensions(cls, strategy_id: int, aggregate_dimensions: list) -> None:
        """校验 aggregate_dimensions ⊆ Strategy.public_dimensions

        空列表时跳过（表示使用策略全量公共维度）。
        """
        if not aggregate_dimensions:
            return

        strategy = cls._get_strategy(strategy_id)
        strategy_dimensions = cls._get_strategy_public_dimensions(strategy)
        invalid = set(aggregate_dimensions) - strategy_dimensions
        if invalid:
            raise ValueError(
                f"aggregate_dimensions 包含策略公共维度之外的字段: {invalid}，"
                f"当前策略 public_dimensions: {strategy_dimensions}"
            )

    @classmethod
    def validate_conditions(cls, conditions: list, effective_dimensions: set) -> None:
        """校验 conditions 的 method 和 key 合法性"""
        valid_methods = {"eq", "neq", "include", "exclude", "reg", "nreg"}
        for cond in conditions:
            if cond.get("method") not in valid_methods:
                raise ValueError(f"不支持的 method: {cond.get('method')}")
            if cond.get("key") not in effective_dimensions:
                raise ValueError(
                    f"conditions.key={cond.get('key')} 不在可用维度集合中，"
                    f"当前可用维度: {effective_dimensions}"
                )

    @classmethod
    def save(cls, strategy_id: int, config_data: dict) -> "StrategyIssueConfig":
        """创建或更新 StrategyIssueConfig

        :param strategy_id: 策略 ID
        :param config_data: 配置字段，支持 key：
            aggregate_dimensions / conditions / alert_levels / is_enabled
        :return: 保存后的 StrategyIssueConfig 实例
        """
        aggregate_dimensions = config_data.get("aggregate_dimensions", [])
        conditions = config_data.get("conditions", [])

        strategy = cls._get_strategy(strategy_id)
        cls.validate_aggregate_dimensions(strategy_id, aggregate_dimensions)

        strategy_dimensions = cls._get_strategy_public_dimensions(strategy)
        effective_dimensions = set(aggregate_dimensions) if aggregate_dimensions else strategy_dimensions
        cls.validate_conditions(conditions, effective_dimensions)

        # bk_biz_id 由策略缓存回填，不接受外部指定
        config_data = dict(config_data)
        config_data["bk_biz_id"] = strategy["bk_biz_id"]

        # 格式校验：构造临时实例调用 full_clean()，不落库不触发信号
        temp = StrategyIssueConfig(strategy_id=strategy_id, **config_data)
        temp.full_clean(exclude=["create_user", "update_user"])

        # 全部校验通过，写库（post_save 信号在此触发缓存失效）
        config, _ = StrategyIssueConfig.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=config_data,
        )
        logger.info("StrategyIssueConfigManager.save: strategy_id=%s saved", strategy_id)
        return config

    @classmethod
    def get_effective_dimensions(cls, strategy_id: int, aggregate_dimensions: Optional[list] = None) -> set:
        """返回指定策略的生效维度集合

        :param aggregate_dimensions: 配置中的值；None 或空列表时取 Strategy.public_dimensions
        """
        if aggregate_dimensions:
            return set(aggregate_dimensions)

        try:
            strategy = cls._get_strategy(strategy_id)
        except ValueError:
            return set()
        return cls._get_strategy_public_dimensions(strategy)
