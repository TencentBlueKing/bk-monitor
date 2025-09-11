# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from enum import Enum

from django.utils.translation import gettext_lazy as _lazy


class SourceApp:
    MONITOR = "monitor"
    FTA = "fta"


ALL_DAY = "00:00--23:59"


class DutyCategory:
    """
    轮值规则模式
    """

    REGULAR = "regular"
    HANDOFF = "handoff"
    DutyCategory_DISPLAY_DICT = {REGULAR: "常规", HANDOFF: "交替"}


class RotationType:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALWAYS = "always"
    WORK_DAY = "work_day"
    WEEKEND = "weekend"
    DATE_RANGE = "date_range"

    ROTATION_TYPE_DISPLAY_DICT = {
        DAILY: _lazy("每天"),
        WEEKLY: _lazy("每周"),
        MONTHLY: _lazy("每月"),
        WORK_DAY: _lazy("工作日"),
        WEEKEND: _lazy("周末"),
        DATE_RANGE: _lazy("日期范围"),
    }

    WEEK_MODE = [WEEKLY, WORK_DAY, WEEKEND]

    ROTATION_TYPE_CHOICE = [(key, display) for key, display in ROTATION_TYPE_DISPLAY_DICT.items()]


class WorkTimeType:
    TIME_RANGE = "time_range"
    DATETIME_RANGE = "datetime_range"

    WORK_TYME_TYPE_DISPLAY_DICT = {TIME_RANGE: _lazy("时间范围"), DATETIME_RANGE: _lazy("起止时间")}

    WORK_TYME_TYPE_CHOICE = [(key, display) for key, display in WORK_TYME_TYPE_DISPLAY_DICT.items()]


class DutyType:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    SINGLE = "single"

    DUTY_TYPE_DISPLAY_DICT = {
        SINGLE: _lazy("单次"),
        DAILY: _lazy("每天"),
        WEEKLY: _lazy("每周"),
        MONTHLY: _lazy("每月"),
    }

    DUTY_TYPE_CHOICE = [(key, display) for key, display in DUTY_TYPE_DISPLAY_DICT.items()]


class DutyGroupType:
    """ """

    SPECIFIED = "specified"
    AUTO = "auto"

    DISPLAY_DICT = {SPECIFIED: _lazy("手动指定"), AUTO: _lazy("自动")}

    CHOICE = [(key, display) for key, display in DISPLAY_DICT.items()]


class IsoWeekDay:
    MON = 1
    TUES = 2
    WED = 3
    THUR = 4
    FRI = 5
    SAT = 6
    SUN = 7

    WEEK_DAY_RANGE = [MON, TUES, WED, THUR, FRI, SAT, SUN]


class MonthDay:
    MONTH_DAY_RANGE = list(range(1, 32))


# 暂时不设置过期时间
LOGO_IMAGE_TIMEOUT = None


class CustomEnum(Enum):
    @classmethod
    def get_enum_value_list(cls, excludes=None):
        if excludes is None:
            excludes = []
        return [m.value for m in cls.__members__.values() if m.value not in excludes]

    @classmethod
    def get_enum_translate_list(cls, excludes=None):
        if excludes is None:
            excludes = []
        return [(m.value, m.alias) for m in cls.__members__.values() if m.value not in excludes]


# 为了统一多租户和非多租户场景的逻辑，默认使用system租户
DEFAULT_TENANT_ID = "system"
