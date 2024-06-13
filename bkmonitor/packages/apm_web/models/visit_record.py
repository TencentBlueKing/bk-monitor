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


class UserVisitRecord(models.Model):

    bk_biz_id = models.BigIntegerField("业务 ID")
    app_name = models.CharField("应用名称", max_length=50, null=True)
    func_name = models.CharField("功能名称", max_length=128, default="")

    created_at = models.DateTimeField("访问时间", auto_now_add=True, db_index=True)
    created_by = models.CharField("访问者", max_length=32, default="", db_index=True)

    class Meta:
        verbose_name = "APM 用户访问记录"
        verbose_name_plural = "APM 用户访问记录"
