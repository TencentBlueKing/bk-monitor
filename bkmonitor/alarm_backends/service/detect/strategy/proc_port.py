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
进程端口存活检测：基于时序数据 system.env.uptime 进行判断。
uptime表示主机运行时长。
该检测算法依赖bkmonitorbeat采集器被gse agent托管(机器重启后bkmonitorbeat自动拉起)否则无数据上报会导致该检测算法失效。
"""


from django.utils.translation import gettext as _

from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)


class ProcPort(BasicAlgorithmsCollection):
    expr_op = "or"
    config_serializer = None

    def gen_expr(self):
        factory = [
            ("int(data_point.value) != 1", _("当前进程({{data_point.dimensions.display_name | safe}})不存在")),
            (
                "data_point.dimensions.get('nonlisten', '[]') not in ['[]', 'null']",
                _(
                    "{% load port_range %}当前进程({{data_point.dimensions.display_name | safe}})"
                    "存在，端口({{data_point.dimensions.nonlisten | port_range}})不存在"
                ),
            ),
            (
                "data_point.dimensions.get('not_accurate_listen', '[]') not in ['[]', 'null']",
                _(
                    "当前进程({{data_point.dimensions.display_name | safe}})"
                    "和监听端口({{data_point.dimensions.not_accurate_listen | safe}})存在，"
                    "监听的IP与CMDB中配置的({{data_point.dimensions.bind_ip | safe}})不符"
                ),
            ),
        ]
        for args in factory:
            yield ExprDetectAlgorithms(*args)

    def anomaly_message_template_tuple(self, data_point):
        return "", ""
