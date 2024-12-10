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
IntelligentDetect：智能异常检测算法基于计算平台的计算结果，再基于结果表的is_anomaly{1,2,3}来进行判断。
"""
import copy
import json
import logging

from django.conf import settings
from django.utils.translation import ugettext as _

from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy import (
    ExprDetectAlgorithms,
    RangeRatioAlgorithmsCollection,
)
from constants.aiops import SDKDetectStatus
from core.drf_resource import api

logger = logging.getLogger("detect")


class DetectDirect(object):
    CEIL = "ceil"
    FLOOR = "floor"
    ALL = "all"


class IntelligentDetect(RangeRatioAlgorithmsCollection):
    """
    智能异常检测（动态阈值算法）
    """

    def detect(self, data_point):
        if data_point.item.query_configs[0]["intelligent_detect"].get("use_sdk", False):
            # 历史依赖准备就绪才开始检测
            if data_point.item.query_configs[0]["intelligent_detect"]["status"] == SDKDetectStatus.PREPARING:
                raise Exception("Strategy history dependency data not ready")

            return self.detect_by_sdk(data_point)
        else:
            return super().detect(data_point)

    def detect_by_sdk(self, data_point):
        dimensions = copy.deepcopy(data_point.dimensions)
        dimensions["strategy_id"] = data_point.item.strategy.id
        predict_params = {
            "data": [{"value": data_point.value, "timestamp": data_point.timestamp * 1000}],
            "dimensions": dimensions,
            "interval": data_point.item.query_configs[0]["agg_interval"],
            "predict_args": {
                "alert_up": self.validated_config["args"].get("$alert_up"),
                "alert_down": self.validated_config["args"].get("$alert_down"),
                "sensitivity": self.validated_config["args"].get("$sensitivity"),
            },
            "extra_data": {
                "history_anomaly": [],
            },
        }

        predict_result = api.aiops_sdk.kpi_predict(**predict_params)

        return super().detect(
            DataPoint(
                accessed_data={
                    "record_id": data_point.record_id,
                    "value": data_point.value,
                    "values": predict_result[0],
                    "time": int(predict_result[0]["timestamp"] / 1000),
                    "dimensions": data_point.dimensions,
                },
                item=data_point.item,
            )
        )

    def gen_expr(self):
        expr = "is_anomaly > 0"
        yield ExprDetectAlgorithms(
            expr,
            _(
                "{% load unit %}智能模型检测到异常"
                "{% if alert_msg is not None %}, 异常类型: {{ alert_msg }}{% endif %}"
                "{% if anomaly_score is not None %}, 异常分值: {{ anomaly_score }}{% endif %}"
                "{% if previous_point is not None %}, 前一时刻值{{ previous_point.value | auto_unit:unit }}{% endif %}"
            ),
        )

    def extra_context(self, context):
        values = getattr(context.data_point, "values", {})
        env = copy.deepcopy(values)
        if "extra_info" in env:
            try:
                env["extra_info"] = json.loads(env["extra_info"])
            except Exception as e:
                logger.info("[IntelligentDetect] get extra context error: %s, origin data: %s", e, env["extra_info"])
        else:
            env["extra_info"] = {}

        if "anomaly_score" in env["extra_info"]:
            env["anomaly_score"] = env["extra_info"]["anomaly_score"]

        if "anomaly_score" in env:
            env["anomaly_score"] = round(env["anomaly_score"], settings.POINT_PRECISION)

        if "alert_msg" in env["extra_info"]:
            env["alert_msg"] = env["extra_info"]["alert_msg"]

        # 获取前一时刻的数据
        env["previous_point"] = self.history_point_fetcher(context.data_point)

        return env

    def get_history_offsets(self, item):
        return [item.query_configs[0]["agg_interval"]]
