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
多指标异常检测算法
"""
import logging

from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)
from bkmonitor.aiops.alert.utils import parse_anomaly

"""
MultivariateAnomalyDetection：多指标异常检测算法基于计算平台的计算结果，再基于结果表的is_anomaly值来进行判断。
"""

logger = logging.getLogger("detect")


class MultivariateAnomalyDetection(BasicAlgorithmsCollection):
    def gen_expr(self):
        expr = "value > 0"
        yield ExprDetectAlgorithms(
            expr,
            (
                "主机智能异常检测 发现 {{ anomaly_sort | length }} 个指标异常："
                "{% for item in anomaly_sort %}{{ item.4 }}({{ item.0 }})={{ item.3 }}"
                "(异常得分: {{ item.2 }}); {% endfor %}"
            ),
        )

    def get_context(self, data_point):
        context = super(MultivariateAnomalyDetection, self).get_context(data_point)
        anomaly_sort = parse_anomaly(data_point.values["anomaly_sort"], self.config)
        context.update({"anomaly_sort": anomaly_sort})
        return context

    def anomaly_message_template_tuple(self, data_point):
        return "", ""
