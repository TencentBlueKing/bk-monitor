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
from bkmonitor.utils.enum import ChoicesEnum


class StaffEnum(ChoicesEnum):
    """
    人员选择
    """

    USER = "user"
    GROUP = "group"

    _choices_labels = ((USER, "用户"), (GROUP, "用户组"))


class ChannelEnum(ChoicesEnum):
    # 订阅渠道
    EMAIL = "email"
    WXBOT = "wxbot"
    USER = "user"

    _choices_labels = ((EMAIL, "外部邮件"), (WXBOT, "企业微信机器人"), (USER, "内部用户"))


class ScenarioEnum(ChoicesEnum):
    # 订阅场景
    CLUSTERING = "clustering"
    DASHBOARD = "dashboard"
    SCENE = "scene"

    _choices_labels = ((CLUSTERING, "日志聚类"), (DASHBOARD, "仪表盘"), (SCENE, "观测场景"))


class SendStatusEnum(ChoicesEnum):
    # 订阅发送状态
    NO_STATUS = "no_status"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_FAILED = "partial_failed"

    _choices_labels = (
        (SUCCESS, "成功"),
        (FAILED, "失败"),
        (PARTIAL_FAILED, "部分失败"),
        (NO_STATUS, "无"),
    )


class SendModeEnum(ChoicesEnum):
    # 订阅模式
    PERIODIC = "periodic"
    ONE_TIME = "one_time"

    _choices_labels = ((PERIODIC, "周期发送"), (ONE_TIME, "只发一次"))


class SubscriberTypeEnum(ChoicesEnum):
    # 订阅人类型
    SELF = "self"
    OTHERS = "others"

    _choices_labels = ((SELF, "仅自己"), (OTHERS, "其他人"))


class HourFrequencyTime:
    HALF_HOUR = {"minutes": ["00", "30"]}
    HOUR = {"minutes": ["00"]}
    HOUR_2 = {"hours": ["00", "02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22"]}
    HOUR_6 = {"hours": ["00", "06", "12", "18"]}
    HOUR_12 = {"hours": ["09", "21"]}

    TIME_CONFIG = {"0.5": HALF_HOUR, "1": HOUR, "2": HOUR_2, "6": HOUR_6, "12": HOUR_12}


class YearOnYearEnum(ChoicesEnum):
    NOT = 0
    ONE_HOUR = 1
    TWO_HOUR = 2
    THREE_HOUR = 3
    SIX_HOUR = 6
    HALF_DAY = 12
    ONE_DAY = 24

    _choices_labels = (
        (NOT, "不比对"),
        (ONE_HOUR, "1小时前"),
        (TWO_HOUR, "2小时前"),
        (THREE_HOUR, "3小时前"),
        (SIX_HOUR, "6小时前"),
        (HALF_DAY, "12小时前"),
        (ONE_DAY, "24小时前"),
    )


class YearOnYearChangeEnum(ChoicesEnum):
    ALL = "all"
    RISE = "rise"
    DECLINE = "decline"

    _choices_labels = (
        (ALL, "所有"),
        (RISE, "上升"),
        (DECLINE, "下降"),
    )


class LogColShowTypeEnum(ChoicesEnum):
    PATTERN = "pattern"
    LOG = "log"

    _choices_labels = (
        (PATTERN, "PATTERN模式"),
        (LOG, "采样日志"),
    )


class ReportCreateTypeEnum(ChoicesEnum):
    MANAGER = "manager"
    SELF = "self"

    _choices_labels = (
        (MANAGER, "管理员"),
        (SELF, "自己"),
    )


class ReportQueryTypeEnum(ChoicesEnum):
    INVALID = "invalid"
    CANCELLED = "cancelled"
    AVAILABLE = "available"
    ALL = "all"

    _choices_labels = (
        (INVALID, "失效"),
        (CANCELLED, "已取消"),
        (AVAILABLE, "生效"),
        (ALL, "全部"),
    )


class ApplyRecordQueryTypeEnum(ChoicesEnum):
    USER = "user"
    BIZ = "biz"

    _choices_labels = (
        (USER, "用户"),
        (BIZ, "业务"),
    )


CLUSTERING_VARIABLES = [
    {"name": "time", "description": "系统时间", "example": "2023-12-12 22:00"},
    {"name": "index_set_name", "description": "索引集名称", "example": "apm_demo_app_1111"},
    {"name": "business_name", "description": "业务名称", "example": "测试业务"},
]

SUBSCRIPTION_VARIABLES_MAP = {ScenarioEnum.CLUSTERING.value: CLUSTERING_VARIABLES}
