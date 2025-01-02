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
同比区间算法
当前值{comp}过去{days}天内同一时刻绝对值*{ratio}+{shock}
"""


from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from six.moves import range

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.service.detect.strategy import ExprDetectAlgorithms
from alarm_backends.service.detect.strategy.advanced_year_round import AdvancedYearRound
from bkmonitor.strategy.serializers import YearRoundRangeSerializer, allowed_method


class YearRoundRange(AdvancedYearRound):
    config_serializer = YearRoundRangeSerializer
    expr_op = "or"

    def gen_expr(self):
        comp = allowed_method[self.validated_config["method"]]
        # 任意一天满足即可, i从0开始, 表达式history_points也从0开始，索引[0]表示第一天
        for i in range(0, self.validated_config["days"]):
            yield ExprDetectAlgorithms(
                "abs(unit_convert_min(value, unit)) {comp} "
                "(abs(unit_convert_min(history_points[{day}].value, unit)) "
                "* ratio + unit_convert_min(shock, unit, algorithm_unit))".format(day=i, comp=comp),
                # 这里用字符串的format渲染django template，因此变量双花括号变成四个花括号
                _(
                    "{} {{{{method_desc}}}} {}天前的同一时刻绝对值"
                    "{{{{history_points.{}.value|auto_unit:unit}}}} "
                    "* {{{{ratio}}}} + {{{{shock}}}}{{{{unit|unit_suffix:algorithm_unit}}}}"
                ).format("{% load math_filters %}{% load unit %}", i + 1, i),
            )

    def extra_context(self, context):
        env = dict()
        comp = allowed_method[self.validated_config["method"]]
        method_desc = comp.replace("==", "=")
        history_points = self.history_point_fetcher(context.data_point, days=self.validated_config["days"])
        env.update(dict(history_points=history_points, comp=comp, method_desc=mark_safe(method_desc)))
        env.update(self.validated_config)
        return env

    def get_history_offsets(self, item):
        history_points = [i * CONST_ONE_DAY for i in range(1, self.validated_config["days"] + 1)]
        return history_points
