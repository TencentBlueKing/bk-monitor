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
import json
import logging

from django.utils.translation import gettext as _

from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)

"""
AbnormalCluster：离群检测算法基于计算平台的计算结果，再基于结果表的is_anomaly数量来进行判断。
"""

logger = logging.getLogger("detect")


class AbnormalCluster(BasicAlgorithmsCollection):
    def gen_expr(self):
        expr = "value > 0"
        yield ExprDetectAlgorithms(
            expr,
            (
                _(
                    "{% if value == 1 %} {{ abnormal_clusters }} 维度值发生离群{% endif %}"
                    "{% if value > 1 %} {{ abnormal_clusters }} 等{{ value }}组维度值发生离群{% endif %}"
                )
            ),
        )

    def get_context(self, data_point):
        context = super(AbnormalCluster, self).get_context(data_point)
        abnormal_clusters = parse_cluster(data_point.values["cluster"])
        context.update({"abnormal_clusters": abnormal_clusters})
        return context

    def anomaly_message_template_tuple(self, data_point):
        prefix, suffix = super(AbnormalCluster, self).anomaly_message_template_tuple(data_point)
        return prefix, ""


def parse_cluster(cluster_str):
    clusters = json.loads(f"[{cluster_str}]")
    result = []
    for key, value in clusters[0].items():
        result.append("{}({})".format(key, value))
    result = "[{}]".format("-".join(result))
    return result
