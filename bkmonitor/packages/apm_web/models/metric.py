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
from constants.data_source import METRIC_TYPE_CHOICES, MetricType


class MetricField(models.Model):
    """
    Metric 字段（指标字段 + 维度字段缓存）
    """

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)

    service_name = models.CharField("服务名称", max_length=255)

    # 监控项分组，数据来源（从上报数据中发现），默认值"default"
    scope_name = models.CharField("监控项分组名称", max_length=2048, default="default")

    type = models.CharField("字段类型", max_length=16, choices=METRIC_TYPE_CHOICES, default=MetricType.METRIC)
    name = models.CharField("字段名称", max_length=128)
    alias = models.CharField("字段别名", max_length=128, default="")

    is_disabled = models.BooleanField("是否禁用", default=False)

    config = models.JSONField("字段配置", default=dict)


class MetricCustomGroup(models.Model):
    """
    Metric 分组（指标自定义分组），仅针对未分组的指标，即 scope_name 为 default 的指标字段）
    """

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=50)

    service_name = models.CharField("服务名称", max_length=2048)

    name = models.CharField("分组名称", max_length=128)

    manual_list = JsonField("手动分组的指标列表", default=[])
    auto_rules = JsonField("自动分组的匹配规则列表", default=[])
