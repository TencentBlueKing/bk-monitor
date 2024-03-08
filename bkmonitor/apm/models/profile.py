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


class ProfileService(models.Model):
    bk_biz_id = models.IntegerField("业务id", db_index=True)
    app_name = models.CharField("应用名称", max_length=255, db_index=True)
    name = models.CharField("服务名称", max_length=528, db_index=True)
    period = models.CharField("采样周期", null=True, max_length=128)
    period_type = models.CharField("周期类型", null=True, max_length=128)
    frequency = models.DecimalField("采样频率", null=True, max_digits=10, decimal_places=2)
    data_type = models.CharField("数据类型", max_length=128, null=True)
    last_check_time = models.DateTimeField("最近检查时间")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", blank=True, null=True, auto_now=True)

    class Meta:
        verbose_name = "Profile服务实例表"
