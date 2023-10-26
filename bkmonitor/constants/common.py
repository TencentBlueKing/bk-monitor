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
from django.utils.translation import ugettext_lazy as _lazy


class SourceApp:
    MONITOR = "monitor"
    FTA = "fta"


ALL_DAY = "00:00--23:59"


class RotationType:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALWAYS = "always"

    ROTATION_TYPE_DISPLAY_DICT = {
        DAILY: _lazy("每天"),
        WEEKLY: _lazy("每周"),
        MONTHLY: _lazy("每月"),
    }

    ROTATION_TYPE_CHOICE = [(key, display) for key, display in ROTATION_TYPE_DISPLAY_DICT.items()]


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
