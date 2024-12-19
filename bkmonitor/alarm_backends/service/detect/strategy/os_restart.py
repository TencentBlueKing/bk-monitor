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
系统重启算法：基于时序数据 system.env.uptime 进行判断。
uptime表示主机运行时长。
该检测算法依赖bkmonitorbeat采集器被gse agent托管(机器重启后bkmonitorbeat自动拉起)否则无数据上报会导致该检测算法失效。
"""


from django.utils.translation import gettext_lazy as _

from alarm_backends.service.detect.strategy import ExprDetectAlgorithms
from alarm_backends.service.detect.strategy.simple_ring_ratio import SimpleRingRatio
from alarm_backends.service.detect.strategy.threshold import Threshold


class OsRestart(SimpleRingRatio):
    expr_op = "and"
    desc_tpl = _("当前服务器在{{data_point.value}}秒前发生系统重启事件")
    config_serializer = None

    def gen_expr(self):
        # 主机运行时长在0到600秒之间
        yield Threshold(config=[[{"threshold": 0, "method": "gt"}, {"threshold": 600, "method": "lte"}]])
        # 主机当前运行时长比前一个周期值小，或者前一个周期值为空
        yield ExprDetectAlgorithms(
            "(previous is None or (value < previous)) and (is_ok_10minute_ago or is_ok_25minute_ago)",
            "{value} < {previous}",
        )
        # 系统重启的检测原理：
        #
        # 检查采集器上报的机器运行时长数据：
        #
        # 1. 主机运行时长在0到600秒之间（10分钟内有开机行为）
        # 2. 主机当前运行时长比前一个周期值小，或者前一个周期值为空（上一分钟未上报数据，或者上一分钟运行时长大于当前时刻）
        # 3. 判断主机10分钟前及25分钟前是否有时长数据上报。
        # 4. 如果有，则表明是重启，如果没有上报说明有4种情况： 1. 机器一直未开机。 2. 机器开机，但是数据未上报。3. 机器重启耗时超过至少25分钟。
        # 这种情况通过ping不可达和agent失联进行补充。 4. 机器一直未开机，开机后在10-25分钟内发生了重新启动事件也能检测出重启。
        # 5. ！！！机器一直未开机，开机后10分钟内发生重启事件，此极端情况无法告警！！！

    def extra_context(self, context):
        env = dict(previous=None, ip="")
        history_data_points = self.history_point_fetcher(context.data_point, greed=True)
        if history_data_points[1]:
            env["previous"] = history_data_points[1].value

        env["is_ok_10minute_ago"] = history_data_points[2] is not None
        env["is_ok_25minute_ago"] = history_data_points[3] is not None
        env["ip"] = context.data_point.dimensions.get("ip", "")

        return env

    def get_history_offsets(self, item):
        # 获取上一个周期，和10分钟前的数据，这类offset加入0，利用query_history_points的特性，
        # 将当前由access模块拉取的数据直接缓存到history_point队列中。这样由于时间窗口的推移，
        # 前一个周期的数据可以不用再获取了（在缓存生效（HISTORY_DATA_KEY.ttl）范围内）
        agg_interval = item.query_configs[0]["agg_interval"]
        return [0, agg_interval, 60 * 10, 60 * 25]

    def gen_anomaly_point(self, data_point, detect_result, level, auto_format=True):
        ap = super(OsRestart, self).gen_anomaly_point(data_point, detect_result, level)
        ap.anomaly_message = self._format_message(data_point)
        return ap
