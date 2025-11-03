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
from bkmonitor.utils.model_manager import AbstractRecordModel

from django.utils.translation import gettext as _

from constants.query_template import DEFAULT_NAMESPACE, GLOBAL_BIZ_ID


class QueryTemplate(AbstractRecordModel):
    name = models.CharField(verbose_name=_("模板名称"), max_length=128, db_index=True)
    alias = models.CharField(verbose_name=_("模板别名"), max_length=256, default="", blank=True)
    bk_biz_id = models.IntegerField(verbose_name=_("业务 ID"), default=GLOBAL_BIZ_ID, db_index=True)
    space_scope = models.JSONField(verbose_name=_("生效范围"), default=list)
    namespace = models.CharField(verbose_name=_("命名空间"), max_length=128, default=DEFAULT_NAMESPACE, db_index=True)
    description = models.TextField(verbose_name=_("模板说明"), default="", blank=True)
    expression = models.TextField(verbose_name=_("计算公式"))
    functions = models.JSONField(verbose_name=_("计算函数"), default=list)
    query_configs = models.JSONField(verbose_name=_("查询配置"), default=list)
    variables = models.JSONField(verbose_name=_("模板变量"), default=list)

    class Meta:
        verbose_name = _("查询模板")
        verbose_name_plural = _("查询模板")
        index_together = [["bk_biz_id", "name"], ["bk_biz_id", "namespace", "name"]]
        unique_together = ["bk_biz_id", "name"]
