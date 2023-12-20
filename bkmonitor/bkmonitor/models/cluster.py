# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _


class AlarmClusterMatchRule(models.Model):
    """
    目标空间关系
    """

    cluster_name = models.CharField(_("集群名称"), max_length=32, db_index=True, blank=True)
    target_type = models.CharField(_("目标类型"), max_length=32)
    # 匹配类型, regex: 正则匹配, exact: 精确匹配, 精确匹配的优先级高于正则匹配
    match_type = models.CharField(_("匹配类型"), max_length=32, choices=(("regex", _("正则")), ("exact", _("精确"))))
    match_rules = models.JSONField(_("匹配规则"), max_length=64, default=list)

    class Meta:
        verbose_name = _("集群目标关系")
        verbose_name_plural = _("集群目标关系")
        db_table = "alarm_cluster_match_rule"
        unique_together = ("cluster_name", "target_type", "match_type")
