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
高级同比算法
"""

import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from six.moves import range

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.service.detect.strategy import RangeRatioAlgorithmsCollection
from bkmonitor.strategy.serializers import AdvancedYearRoundSerializer
from bkmonitor.utils.common_utils import safe_int
from core.errors.alarm_backends.detect import InvalidDataPoint

logger = logging.getLogger("detect")


class AdvancedYearRound(RangeRatioAlgorithmsCollection):
    config_serializer = AdvancedYearRoundSerializer
    expr_op = "or"

    floor_desc_tpl = _(
        "{% load unit %}较前{{floor_interval}}天内同一时刻绝对值的{{fetch_desc}}"
        "({{floor_history_value|auto_unit:unit}})下降超过{{floor}}%"
    )
    ceil_desc_tpl = _(
        "{% load unit %}较前{{ceil_interval}}天内同一时刻绝对值的{{fetch_desc}}"
        "({{ceil_history_value|auto_unit:unit}})上升超过{{ceil}}%"
    )

    def extra_context(self, context):
        env = {
            "fetch_desc": {
                "avg": _("均值"),
                "last": _("瞬间值"),
            }[self.validated_config["fetch_type"]]
        }
        floor_history_data_points = self.history_point_fetcher(
            context.data_point, days=self.validated_config["floor_interval"] or 0
        )
        if not isinstance(floor_history_data_points, list):
            raise InvalidDataPoint(data_point=floor_history_data_points)
        # 新增瞬时值获取，瞬时值取倒数第一个数据点（因为数据拉取按照时间倒序）
        if floor_history_data_points:
            env["floor_history_value"] = (
                round(
                    sum([abs(p.value) for p in floor_history_data_points]) * 1.0 / len(floor_history_data_points),
                    settings.POINT_PRECISION,
                )
                if self.validated_config["fetch_type"] == "avg"
                else abs(floor_history_data_points[-1].value)
            )

        ceil_history_data_points = self.history_point_fetcher(
            context.data_point, days=self.validated_config["ceil_interval"] or 0
        )
        if ceil_history_data_points:
            env["ceil_history_value"] = (
                round(
                    sum([abs(p.value) for p in ceil_history_data_points]) * 1.0 / len(ceil_history_data_points),
                    settings.POINT_PRECISION,
                )
                if self.validated_config["fetch_type"] == "avg"
                else abs(ceil_history_data_points[-1].value)
            )

        env.update(self.validated_config)
        return env

    def get_history_offsets(self, item):
        return [
            CONST_ONE_DAY * i
            for i in range(
                1,
                max(map(safe_int, [self.validated_config["ceil_interval"], self.validated_config["floor_interval"]]))
                + 1,
            )
        ]

    def history_point_fetcher(self, data_point, **kwargs):
        """
        :return: list(data_point)
        """
        # 前 n 天 同一时刻的data points
        days = kwargs["days"]
        offsets = self.get_history_offsets(data_point.item)
        target_offsets = offsets[:days]
        points = []
        for offset in target_offsets:
            history_timestamp = data_point.timestamp - offset
            point = self.fetch_history_point(data_point.item, data_point, history_timestamp)
            if point:
                points.append(point)
        return points
