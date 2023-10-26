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
from monitor_web.models.base import OperateRecordModelBase


class AlertSolution(OperateRecordModelBase):
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0)
    # 指标id，时序类：使用表名 + 字段名，事件类：使用事件类型标识
    metric_id = models.CharField(max_length=128, verbose_name="指标ID")
    content = models.TextField(verbose_name="处理建议")

    class Meta:
        unique_together = ("bk_biz_id", "metric_id")
