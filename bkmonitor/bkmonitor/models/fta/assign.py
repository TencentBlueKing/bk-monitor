# -*- coding: utf-8 -*-
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
from django.utils.translation import gettext as _

from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.action import UserGroupType


class AlertAssignGroup(AbstractRecordModel):
    """
    告警分派规则组
    """

    id = models.BigAutoField(primary_key=True)

    priority = models.IntegerField("优先级", default=-1, db_index=True)
    name = models.CharField("规则组名", max_length=128, blank=False)
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)

    is_builtin = models.BooleanField("是否内置", default=False)
    is_enabled = models.BooleanField("是否启用", default=True)
    settings = models.JSONField("其他属性", default=dict)

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)
    source = models.CharField("来源系统", default=get_source_app_code, max_length=32, null=True, blank=True)

    def __str__(self):
        return f"{self.name}-{self.priority}"

    class Meta:
        verbose_name = _("告警分派规则组")
        verbose_name_plural = _("告警分派规则组")

    @property
    def rules(self):
        return AlertAssignRule.objects.filter(assign_group_id=self.id)


class AlertAssignRule(models.Model):
    """
    告警分派规则
    """

    id = models.BigAutoField(primary_key=True)
    assign_group_id = models.BigIntegerField("关联组", db_index=True)
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)
    event_source = models.JSONField("告警来源", default=list)
    scenario = models.JSONField("监控对象", default=list)
    user_groups = models.JSONField("负责人用户组", default=list)
    user_type = models.CharField("人员类型", default=UserGroupType.MAIN, choices=UserGroupType.CHOICE, max_length=32)
    conditions = models.JSONField("条件组", default=list)
    actions = models.JSONField("处理事件", default=list)
    is_enabled = models.BooleanField("是否启用", default=False)

    # 告警级别重置，如果为空，表示保留
    alert_severity = models.IntegerField("告警级别", choices=[(1, "致命"), (2, "预警"), (3, "提醒"), (0, "保持")], default=0)
    additional_tags = models.JSONField("标签", default=list)

    def __str__(self):
        return f"{self.assign_group.name}({self.assign_group_id})-{self.assign_group.priority}"

    @property
    def assign_group(self):
        return AlertAssignGroup.objects.get(id=self.assign_group_id)
