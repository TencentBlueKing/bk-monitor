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
Ping不可达算法：基于时序数据 pingserver.base.loss_percent 进行判断。
loss_percent表示丢包率
该检测算法依赖bkmonitorproxy采集器, 否则无数据上报会导致该检测算法失效。
"""


from django.utils.translation import gettext_lazy as _

from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)


class PingUnreachable(BasicAlgorithmsCollection):
    expr_op = "and"
    desc_tpl = _("Ping不可达")
    config_serializer = None

    def gen_expr(self):
        """
        Ping不可达检测原理，当丢包率大于等于100%，即1.0时(0~1)，则告警
        """
        factory = [
            ("data_point.value >= 1", _("Ping不可达")),
        ]
        for args in factory:
            yield ExprDetectAlgorithms(*args)

    def anomaly_message_template_tuple(self, data_point):
        return "", ""
