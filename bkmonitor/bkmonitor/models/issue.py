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
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.db.fields import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel


class StrategyIssueConfig(AbstractRecordModel):
    """策略 Issue 聚合配置

    每条 Strategy 至多一条配置（unique_together = strategy_id）。
    跨模型字段校验（aggregate_dimensions 子集、conditions.key 有效性、bk_biz_id 回填）
    由 StrategyIssueConfigService 完成，不在 Model 层做跨模型查询。
    """

    class Meta:
        db_table = "bkmonitor_strategy_issue_config"
        verbose_name = _("策略 Issue 聚合配置")
        verbose_name_plural = _("策略 Issue 聚合配置")

    strategy_id = models.IntegerField(unique=True, db_index=True, verbose_name=_("策略 ID"))
    bk_biz_id = models.IntegerField(db_index=True, verbose_name=_("业务 ID"))

    # aggregate_dimensions: 当前策略公共维度子集（空列表表示使用 Strategy.public_dimensions）
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
        """配置字段格式校验（不做跨模型维度校验，跨模型校验由 Service 层完成）"""
        # alert_levels 非空且为 [1,2,3] 子集
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError(_("alert_levels 必须为 [1,2,3] 的非空子集"))

        valid_methods = {"eq", "neq", "include", "exclude", "reg", "nreg"}
        for cond in self.conditions:
            if cond.get("method") not in valid_methods:
                raise ValidationError(_("不支持的 method: {}").format(cond.get("method")))
            # 仅在 aggregate_dimensions 非空时做本地 key 一致性校验
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
