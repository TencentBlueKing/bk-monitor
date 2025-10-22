"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.db.models import Q

from bkmonitor.utils.model_manager import AbstractRecordModel

from django.utils.translation import gettext as _

from apm_web.strategy.constants import (
    StrategyTemplateType,
    StrategyTemplateCategory,
    StrategyTemplateMonitorType,
    DEFAULT_ROOT_ID,
)


class StrategyTemplate(AbstractRecordModel):
    # 应用元信息
    bk_biz_id = models.IntegerField(verbose_name=_("业务 ID"), db_index=True)
    app_name = models.CharField(verbose_name=_("应用名称"), max_length=50, db_index=True)

    code = models.CharField(verbose_name=_("模板代号"), max_length=128)
    name = models.CharField(verbose_name=_("模板名称"), max_length=128, db_index=True)
    type = models.CharField(verbose_name=_("模板类型"), max_length=32, default=StrategyTemplateType.APP_TEMPLATE.value)

    # 功能启用信息
    is_enabled = models.BooleanField(verbose_name=_("是否启用"), default=True)
    is_auto_apply = models.BooleanField(verbose_name=_("是否自动下发到新服务"), default=False)
    auto_applied_at = models.DateTimeField(verbose_name=_("最后一次自动下发时间"), null=True, blank=True)

    # 继承关系
    root_id = models.IntegerField(verbose_name=_("根模板 ID"), default=DEFAULT_ROOT_ID, db_index=True)
    parent_id = models.IntegerField(verbose_name=_("父模板 ID"), default=DEFAULT_ROOT_ID, db_index=True)

    # 告警模板类别
    system = models.CharField(verbose_name=_("模板类型"), max_length=64, db_index=True)
    category = models.CharField(
        verbose_name=_("模板分类"), max_length=64, db_index=True, default=StrategyTemplateCategory.DEFAULT.value
    )
    monitor_type = models.CharField(
        verbose_name=_("监控类型"), max_length=64, default=StrategyTemplateMonitorType.DEFAULT.value
    )

    # 检测 & 通知
    detect = models.JSONField(verbose_name=_("触发条件"), default=list)
    algorithms = models.JSONField(verbose_name=_("检测算法"), default=list)
    user_group_ids = models.JSONField(verbose_name=_("告警用户组 ID"), default=list)

    # 关联查询模板：bk_biz_id & name
    query_template = models.JSONField(verbose_name=_("查询模板"), default=dict)
    context = models.JSONField(verbose_name=_("策略模板上下文"), default=dict)

    class Meta:
        verbose_name = _("告警策略模板")
        verbose_name_plural = _("告警策略模板")
        index_together = [["bk_biz_id", "app_name", "type"]]

    @classmethod
    def filter_same_origin_templates(
        cls, qs: models.QuerySet["StrategyTemplate"], ids: list[int], root_ids: list[int]
    ) -> models.QuerySet["StrategyTemplate"]:
        """列出同源的模板"""

        strategy_template_ids: list[int] = list(filter(lambda x: x != DEFAULT_ROOT_ID, ids + root_ids))
        return qs.filter(Q(id__in=strategy_template_ids) | Q(root_id__in=strategy_template_ids))


class StrategyInstance(models.Model):
    # 服务元信息
    bk_biz_id = models.IntegerField(verbose_name=_("业务 ID"), db_index=True)
    app_name = models.CharField(verbose_name=_("应用名称"), max_length=50, db_index=True)
    service_name = models.CharField(verbose_name=_("服务名称"), max_length=512, db_index=True)

    # 实例
    strategy_id = models.IntegerField(verbose_name=_("策略实例 ID"), db_index=True)
    # 为什么模板不记录 md5？
    # 模板的 md5 可能会跟随模板内容变更而变更，实例的 md5 只跟创建时的内容有关。
    # [(detects, algorithms, user_group_ids), (query_template, context)]
    md5 = models.CharField(verbose_name=_("策略实例 MD5"), max_length=32, default="", db_index=True)

    # 模板
    strategy_template_id = models.IntegerField(verbose_name=_("策略模板 ID"), db_index=True)
    root_strategy_template_id = models.IntegerField(verbose_name=_("根模板 ID"), default=0, db_index=True)

    # 检测 & 通知
    detect = models.JSONField(verbose_name=_("触发条件"), default=list)
    algorithms = models.JSONField(verbose_name=_("检测算法"), default=list)
    user_group_ids = models.JSONField(verbose_name=_("告警用户组 ID"), default=list)

    # 模板上下文
    context = models.JSONField(verbose_name=_("策略模板上下文"), default=dict)

    class Meta:
        verbose_name = _("告警策略实例")
        verbose_name_plural = _("告警策略实例")
        index_together = [["bk_biz_id", "app_name", "service_name"]]
        unique_together = ["bk_biz_id", "app_name", "service_name", "strategy_template_id"]

    @classmethod
    def filter_same_origin_instances(
        cls, qs: models.QuerySet["StrategyInstance"], strategy_template_id: int, root_strategy_template_id: int
    ) -> models.QuerySet["StrategyInstance"]:
        """列出同源的策略实例"""

        # 过滤出模板自身下发的实例。
        q: Q = Q(strategy_template_id=strategy_template_id)
        if root_strategy_template_id == DEFAULT_ROOT_ID:
            # 内置模板，同源模板的 root id 即为内置模板 ID。
            q |= Q(root_strategy_template_id=strategy_template_id)
        else:
            # 克隆模板，同源模板为内置模板，或其他具有相同 root id 的克隆模板。
            q |= Q(root_strategy_template_id=root_strategy_template_id) | Q(
                strategy_template_id=root_strategy_template_id
            )

        return qs.filter(q)
