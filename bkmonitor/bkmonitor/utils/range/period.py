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


import time
from datetime import datetime, timedelta

import arrow

from bkmonitor.utils import time_tools


class TimeMatch(object):
    """
    时间屏蔽/订阅基类
    """

    def __init__(self, cycle, begin_datetime=None, end_datetime=None):
        self.cycle = cycle
        self.begin_datetime = begin_datetime
        self.end_datetime = end_datetime

        self.start_time = self.cycle.get("begin_time")
        self.end_time = self.cycle.get("end_time")

    def is_match(self, data_time):
        raise NotImplementedError("you must implement this method")

    def shield_left_time(self, current_time):
        return int(self.time_match_left_time(current_time))

    def is_datetime_match(self, data_time):
        """
        判断是否在时间范围内
        """
        if self.begin_datetime and data_time.timestamp < self.begin_datetime.timestamp:
            return False

        if self.end_datetime and data_time.timestamp > self.end_datetime.timestamp:
            return False

        return True

    def datetime_match_left_time(self, current_time):
        return self.end_datetime.timestamp - current_time.timestamp

    def is_time_match(self, data_time):
        """
        判断是否在周期内
        """
        # 1. 获取当前时间小时/分钟/秒
        now_time = time_tools.localtime(data_time).replace(microsecond=0).time()

        start_time = datetime.strptime(self.start_time, "%H:%M:%S").time()
        end_time = datetime.strptime(self.end_time, "%H:%M:%S").time()

        if start_time <= end_time:
            return start_time <= now_time <= end_time
        else:
            return start_time <= now_time or now_time <= end_time

    def time_match_left_time(self, current_time):

        # 1. 获取当前时间小时/分钟/秒
        now_time = time_tools.localtime(current_time).replace(microsecond=0).time()

        start_time = datetime.strptime(self.start_time, "%H:%M:%S").time()
        end_time = datetime.strptime(self.end_time, "%H:%M:%S").time()

        today_str = current_time.strftime("%Y-%m-%d")
        if start_time <= end_time or end_time > now_time:
            end_time = time_tools.str2datetime(end_time.strftime("{} %H:%M:%S".format(today_str)))
        elif start_time <= now_time:
            # 需要跨天计算
            tomorrow_str = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")
            end_time = time_tools.str2datetime(end_time.strftime("{} %H:%M:%S".format(tomorrow_str)))
        return end_time.timestamp() - current_time.timestamp

    @staticmethod
    def convert_datetime_to_arrow(t):
        """
        对 datetime 进行时区转换,将utc时间转换为本地时间
        :param t: 2019-08-15 11:32:11
        :return: arrow.arrow.Arrow
        """
        return arrow.get(time_tools.localtime(t))


class TimeMatchBySingle(TimeMatch):
    """
    单次屏蔽/订阅，判断时间是否匹配
    """

    def is_match(self, data_time):
        return self.is_datetime_match(data_time)

    def shield_left_time(self, current_time):
        return self.datetime_match_left_time(current_time)


class TimeMatchByDay(TimeMatch):
    """
    按天屏蔽/订阅，判断时间+week_list是否匹配
    """

    def __init__(self, cycle, begin_datetime=None, end_datetime=None):
        super(TimeMatchByDay, self).__init__(cycle, begin_datetime, end_datetime)
        self.week_list = self.cycle.get("week_list")

    def is_match(self, data_time):
        """
        根据week_list进行判断
        若为空，则进行屏蔽操作，否则进行订阅操作
        """
        if not self.week_list:
            return self.is_datetime_match(data_time) and self.is_time_match(data_time)
        else:
            return self.is_datetime_match(data_time) and self.is_time_match(data_time) and self.is_week_match(data_time)

    def is_week_match(self, data_time):
        """
        按week_list屏蔽/订阅
        :return: bool
        """
        if isinstance(self.week_list, list):
            # 这里获取到的天数会少一
            day_of_week = time.localtime(data_time.timestamp).tm_wday + 1
            return day_of_week in self.week_list
        return False


class TimeMatchByWeek(TimeMatch):
    """
    按周屏蔽/订阅，判断时间+week_list是否匹配
    """

    def __init__(self, cycle, begin_datetime=None, end_datetime=None):
        super(TimeMatchByWeek, self).__init__(cycle, begin_datetime, end_datetime)
        self.week_list = self.cycle.get("week_list")

    def is_match(self, data_time):
        return self.is_datetime_match(data_time) and self.is_time_match(data_time) and self.is_week_match(data_time)

    def is_week_match(self, data_time):
        """
        按周屏蔽/订阅
        :return: bool
        """
        if isinstance(self.week_list, list):
            # 这里获取到的天数会少一
            day_of_week = time.localtime(data_time.timestamp).tm_wday + 1
            return day_of_week in self.week_list
        return False


class TimeMatchByMonth(TimeMatch):
    """
    按月屏蔽/订阅，判断时间+day_list是否匹配
    """

    def __init__(self, cycle, begin_datetime=None, end_datetime=None):
        super(TimeMatchByMonth, self).__init__(cycle, begin_datetime, end_datetime)
        self.day_list = self.cycle.get("day_list")

    def is_match(self, data_time):
        return self.is_datetime_match(data_time) and self.is_time_match(data_time) and self.is_month_match(data_time)

    def is_month_match(self, data_time):
        if isinstance(self.day_list, list):
            day_of_month = time.localtime(data_time.timestamp).tm_mday
            return day_of_month in self.day_list
        return False
