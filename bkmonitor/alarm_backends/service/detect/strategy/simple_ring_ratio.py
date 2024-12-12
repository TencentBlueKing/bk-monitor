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
"""
简易环比算法
"""


import logging

from django.utils.translation import gettext_lazy as _

from alarm_backends.service.detect.strategy import RangeRatioAlgorithmsCollection
from bkmonitor.strategy.serializers import SimpleRingRatioSerializer

logger = logging.getLogger("detect")


class SimpleRingRatio(RangeRatioAlgorithmsCollection):
    config_serializer = SimpleRingRatioSerializer

    floor_desc_tpl = _("{% load unit %}较前一时刻({{history_data_point.value|auto_unit:unit}})下降超过{{floor}}%")
    ceil_desc_tpl = _("{% load unit %}较前一时刻({{history_data_point.value|auto_unit:unit}})上升超过{{ceil}}%")

    def get_history_offsets(self, item):
        return [item.query_configs[0]["agg_interval"]]
