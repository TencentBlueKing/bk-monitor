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

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel

__all__ = ["IssueSourceAnalysisConfig", "IssueSourceAnalysisRule"]


class IssueSourceAnalysisConfig(AbstractRecordModel):
    """业务级源码分析代码库配置。"""

    class Meta:
        db_table = "bkmonitor_issue_source_analysis_config"
        verbose_name = "Issue 源码分析配置"

    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField(unique=True, verbose_name="业务 ID")
    bkci_project_id = models.CharField(max_length=128, verbose_name="蓝盾项目 ID")
    repository_alias = models.CharField(max_length=255, verbose_name="蓝盾代码库别名")


class IssueSourceAnalysisRule(AbstractRecordModel):
    """业务级源码分析规则及每次执行所需的资源参数。"""

    class Meta:
        db_table = "bkmonitor_issue_source_analysis_rule"
        verbose_name = "Issue 源码分析规则"
        ordering = ["-priority", "id"]
        indexes = [
            models.Index(
                fields=["bk_biz_id", "is_deleted", "is_enabled", "priority"],
                name="idx_isar_biz_enabled_pri",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bk_biz_id", "priority"],
                name="uniq_issue_src_rule_priority",
            ),
            # 自定义规则按优先级从高到低匹配，-1 固定留给最后兜底的默认规则。
            models.CheckConstraint(
                check=(models.Q(is_default=True, priority=-1) | models.Q(is_default=False, priority__gte=0)),
                name="ck_issue_src_rule_priority",
            ),
        ]

    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField(db_index=True, verbose_name="业务 ID")
    name = models.CharField(max_length=128, verbose_name="规则名称")
    priority = models.IntegerField(verbose_name="优先级")
    is_enabled = models.BooleanField(default=False, verbose_name="是否启用")
    is_default = models.BooleanField(default=False, verbose_name="是否默认规则")
    # 条件项沿用告警分派结构：
    # {"field": str, "value": list[str], "method": str, "condition": str}
    # method 取 eq/neq/include/exclude/reg/nreg/issuperset；condition 取 and/or/""，最后一项固定为 ""。
    conditions = JsonField(default=list, blank=True, verbose_name="匹配条件")
    repository_alias = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default=None,
        verbose_name="蓝盾代码库别名快照",
    )
    agent_ids = JsonField(default=list, blank=True, verbose_name="智能体 ID")
    skill_ids = JsonField(default=list, blank=True, verbose_name="Skill ID")
    knowledge_base_ids = JsonField(default=list, blank=True, verbose_name="知识库 ID")
