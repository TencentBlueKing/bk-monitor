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
环比振幅算法
当前与前一时刻均>={threshold}且,之间差值>=前一时刻值*{ratio}+{shock}
"""


from django.utils.translation import gettext_lazy as _

from alarm_backends.service.detect.strategy import ExprDetectAlgorithms
from alarm_backends.service.detect.strategy.simple_ring_ratio import SimpleRingRatio
from bkmonitor.strategy.serializers import RingRatioAmplitudeSerializer


class RingRatioAmplitude(SimpleRingRatio):
    config_serializer = RingRatioAmplitudeSerializer
    expr_op = "and"
    desc_tpl = _(
        "{% load unit %} - 前一时刻值{{history_data_point.value|auto_unit:unit}}的绝对值 >= "
        "前一时刻值{{history_data_point.value|auto_unit:unit}} * {{ratio}} + {{shock}}{{unit|unit_suffix:algorithm_unit}}"
    )

    def gen_expr(self):
        yield ExprDetectAlgorithms(
            "unit_convert_min(data_point.value, unit) >= unit_convert_min(threshold, algorithm_unit) and"
            " unit_convert_min(history_data_point.value, unit) >= unit_convert_min(threshold, unit, algorithm_unit)",
            "",
        )
        yield ExprDetectAlgorithms(
            "unit_convert_min(abs(history_data_point.value-data_point.value), unit) >= "
            "unit_convert_min(history_data_point.value, unit) * ratio + unit_convert_min(shock, unit, algorithm_unit)",
            "",
        )

    def gen_anomaly_point(self, data_point, detect_result, level, auto_format=True):
        ap = super(RingRatioAmplitude, self).gen_anomaly_point(data_point, detect_result, level)
        if auto_format:
            anomaly_message_prefix, anomaly_message_suffix = self.anomaly_message_template_tuple(data_point)
            ap.anomaly_message = anomaly_message_prefix + self._format_message(data_point) + anomaly_message_suffix
        else:
            ap.anomaly_message = self._format_message(data_point)

        return ap
