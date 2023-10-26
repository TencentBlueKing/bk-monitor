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
静态阈值算法
"""


import ast
import logging

from django.utils.safestring import mark_safe
from six.moves import zip

from alarm_backends.service.detect.strategy import BasicAlgorithmsCollection, ExprDetectAlgorithms
from bkmonitor.strategy.serializers import ThresholdSerializer, allowed_threshold_method
from core.errors.alarm_backends.detect import InvalidThresholdConfig

logger = logging.getLogger("detect")


class AlgorithmsAST(ast.NodeTransformer):
    """
    todo check safety expr
    """

    pass


class AndThreshold(BasicAlgorithmsCollection):
    config_serializer = ThresholdSerializer.AndSerializer
    expr_op = "and"

    desc_tpl = "{{% load unit %}} {method_desc} {threshold}{{{{unit|unit_suffix:algorithm_unit}}}}"

    def gen_expr(self):
        expr_list = []
        tpl_list = []
        for t_config in self.validated_config:
            method = t_config["method"]
            threshold = t_config["threshold"]
            comp = allowed_threshold_method[method]
            expr_list.append(
                "unit_convert_min(value, unit) {comp} unit_convert_min({threshold}, unit, algorithm_unit)".format(
                    comp=comp, threshold=threshold
                )
            )
            tpl_list.append(self.desc_tpl.format(method_desc=mark_safe(comp.replace("==", "=")), threshold=threshold))

        # no more effect
        if not expr_list:
            raise InvalidThresholdConfig(dict(config=self.validated_config))

        for args in zip(expr_list, tpl_list):
            yield ExprDetectAlgorithms(*args)


class Threshold(AndThreshold):
    config_serializer = ThresholdSerializer
    expr_op = "or"

    def gen_expr(self):
        for t_config in self.validated_config:
            yield AndThreshold(t_config, self.unit)
