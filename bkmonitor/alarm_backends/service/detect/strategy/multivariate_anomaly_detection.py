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
import json
import logging

from django.conf import settings

from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)
from core.unit import load_unit

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
                "主机场景智能检测发现{{ anomaly_sort | length }}个指标异常："
                "{% for item in anomaly_sort %}{{ item.4 }}({{ item.0 }})={{ item.3 }}(异常得分:{{ item.2 }});{% endfor %}"
            ),
        )

    def get_context(self, data_point):
        context = super(MultivariateAnomalyDetection, self).get_context(data_point)
        anomaly_sort = parse_anomaly(data_point.values["anomaly_sort"], self.config)
        context.update({"anomaly_sort": anomaly_sort})
        return context

    def anomaly_message_template_tuple(self, data_point):
        prefix, suffix = super(MultivariateAnomalyDetection, self).anomaly_message_template_tuple(data_point)
        return prefix, ""


def parse_anomaly(anomaly_str, config):
    """
    解析异常数据，数据源格式：
    [[指标名, 数值, 异常得分]]
    [["system__net__speed_recv", 2812154.0, 0.979932],...]
    """

    def setup_metric_info(metric_name):
        return {"name": metric_name, "metric_id": metric_name, "unit": ""}

    anomalies = json.loads(anomaly_str)
    # 策略配置信息转字典
    metric_map = {m["metric_name"]: m for m in config["metrics"]} if config and "metrics" in config else {}
    result = []
    # 获取指标中文名称
    for item in anomalies:
        metric_name = item[0].replace("__", ".")
        metric_info = metric_map[metric_name] if metric_name in metric_map else setup_metric_info(metric_name)
        # 转为标准metric_id
        item[0] = metric_info["metric_id"]
        # 异常得分只保留标准小数位
        item[2] = round(item[2], settings.POINT_PRECISION)
        # 数据单位转化
        unit = load_unit(metric_info["unit"])
        value, suffix = unit.fn.auto_convert(item[1], decimal=settings.POINT_PRECISION)
        item.append(f"{value}{suffix}")
        # 添加指标名
        item.append(metric_info["name"])
        """
        转化后格式：
        [[指标名, 数值, 异常得分, 带单位的数值, 指标中文名]]
        [["bk_monitor.system.net.speed_recv", 2812154.0, 0.9799, "2812154.0Kbs", "网卡入流量"],...]
        """
        result.append(item)
    return result
