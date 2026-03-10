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

__all__ = ["StrategyIssueConfig"]


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


@receiver(post_save, sender=StrategyIssueConfig)
@receiver(post_delete, sender=StrategyIssueConfig)
def invalidate_strategy_issue_config_cache(sender, instance, **kwargs):
    try:
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        StrategyIssueConfigCache.invalidate(instance.strategy_id)
    except Exception:
        pass
