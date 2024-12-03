# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.db import models

from apm_web.constants import ServiceRelationLogTypeChoices
from bkmonitor.utils.db import JsonField


class ServiceBase(models.Model):
    """服务基础信息"""

    bk_biz_id = models.BigIntegerField("业务ID")
    app_name = models.CharField("应用名称", max_length=50)
    service_name = models.CharField("服务名称", max_length=512)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    created_by = models.CharField("创建人", max_length=128, null=True)
    updated_by = models.CharField("更新人", max_length=128, null=True)

    class Meta:
        abstract = True
        index_together = [["bk_biz_id", "app_name", "service_name"]]


class CMDBServiceRelation(ServiceBase):
    template_id = models.BigIntegerField("服务模板ID")


class LogServiceRelation(ServiceBase):
    log_type = models.CharField("日志类型", max_length=50, choices=ServiceRelationLogTypeChoices.choices())
    related_bk_biz_id = models.IntegerField("关联的业务id", null=True)
    value = models.CharField("日志值", max_length=512)


class AppServiceRelation(ServiceBase):
    relate_bk_biz_id = models.BigIntegerField("关联业务ID")
    relate_app_name = models.CharField("关联应用名称", max_length=50)


class UriServiceRelation(ServiceBase):
    uri = models.CharField("Uri", max_length=512)
    rank = models.IntegerField("排序")


class ApdexServiceRelation(ServiceBase):
    """服务的apdex只能设置此服务类型的apdex"""

    apdex_key = models.CharField(max_length=32, verbose_name="apdex类型")
    apdex_value = models.IntegerField("apdex值")


class CodeRedefinedConfigRelation(ServiceBase):
    ret_code_as_exception = models.BooleanField("非 0 返回码是否当成异常", default=False)
    rules = JsonField(verbose_name="匹配规则", null=True, blank=True)
