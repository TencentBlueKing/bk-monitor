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


from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.i18n import TranslateDict


def enum(**enums):
    return type(str("Enum"), (), enums)


# 进程端口状态
PROC_PORT_STATUS = enum(
    UNKNOWN=-1,
    LISTEN=0,
    NONLISTEN=1,
    NOT_ACCURATE_LISTEN=2,
)

# Agent状态
AGENT_STATUS = enum(UNKNOWN=-1, ON=0, OFF=1, NOT_EXIST=2, NO_DATA=3)

# sql查询条件映射
CONDITION_CONFIG = {"lt": "<", "gt": ">", "lte": "<=", "gte": ">=", "in": " in ", "like": " like ", "!=": "!="}


# 告警策略
STRATEGY_CHOICES = TranslateDict(
    {
        1000: _lazy("静态阈值"),
        1001: _lazy("同比策略（简易）"),
        1002: _lazy("环比策略（简易）"),
        1003: _lazy("同比策略（高级）"),
        1004: _lazy("环比策略（高级）"),
        1005: _lazy("同比振幅"),
        1006: _lazy("同比区间"),
        1007: _lazy("环比振幅"),
        4000: _lazy("关键字匹配"),
        5000: _lazy("进程端口监控检测策略"),
        5001: _lazy("系统重新启动监控策略"),
        6000: _lazy("自定义字符型告警"),
    }
)


SHELL_COLLECTOR_DB = "selfscript"
UPTIME_CHECK_DB = "uptimecheck"
STRUCTURED_LOG_DB = "slog"

# exporter监听地址参数名称
EXPORTER_LISTEN_ADDRESS_PARAM_NAME = "_exporter_url_"


class UptimeCheckProtocol(object):
    HTTP = "HTTP"
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
