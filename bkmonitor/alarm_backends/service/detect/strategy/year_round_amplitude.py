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
同比振幅算法
当前值-前一时刻值{comp}过去{days}天内任一天同时刻差值*{ratio}+{shock}
"""


from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from six.moves import range

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.service.detect.strategy import (
    ExprDetectAlgorithms,
    RangeRatioAlgorithmsCollection,
)
from bkmonitor.strategy.serializers import YearRoundAmplitudeSerializer, allowed_method


class YearRoundAmplitude(RangeRatioAlgorithmsCollection):
    config_serializer = YearRoundAmplitudeSerializer
    expr_op = "or"

    def gen_expr(self):
        comp = allowed_method[self.validated_config["method"]]
        # 任意一天满足即可
        for i in range(1, self.validated_config["days"] + 1):
            yield ExprDetectAlgorithms(
                "unit_convert_min(abs(diffs[0][0].value - diffs[0][1].value), unit) {comp} "
                "(unit_convert_min(abs(diffs[{day}][0].value - diffs[{day}][1].value), unit) "
                "* ratio + unit_convert_min(shock, unit, algorithm_unit))".format(day=i, comp=comp),
                # 这里用字符串的format渲染django template，因此变量双花括号变成四个花括号
                _(
                    "{} - 前一时刻值{{{{pre_val|auto_unit:unit}}}} {{{{method_desc}}}} "
                    "{}天前的同一时刻差值{{{{diffs.{}.0.value |diff:diffs.{}.1.value|auto_unit:unit}}}} "
                    "* {{{{ratio}}}} + {{{{shock}}}}{{{{unit|unit_suffix:algorithm_unit}}}}"
                ).format("{% load math_filters %}{% load unit %}", i, i, i),
            )

    def extra_context(self, context):
        env = dict()
        comp = allowed_method[self.validated_config["method"]]
        method_desc = comp.replace("==", "=")
        diffs = self.history_point_fetcher(context.data_point)
        env.update(dict(pre_val=diffs[0][1].value, diffs=diffs, comp=comp, method_desc=mark_safe(method_desc)))
        env.update(self.validated_config)
        return env

    def get_history_offsets(self, item):
        agg_interval = item.query_configs[0]["agg_interval"]
        return [(i * CONST_ONE_DAY, i * CONST_ONE_DAY + agg_interval) for i in range(self.validated_config["days"] + 1)]

    def history_point_fetcher(self, data_point, **kwargs):
        """
        :return: -> list(tuple)
        """
        offsets = self.get_history_offsets(data_point.item)
        diffs = []
        for pre, suf in offsets:
            diffs.append(
                (
                    self.fetch_history_point(data_point.item, data_point, data_point.timestamp - pre),
                    self.fetch_history_point(data_point.item, data_point, data_point.timestamp - suf),
                )
            )
        return diffs
