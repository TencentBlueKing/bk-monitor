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

import datetime
import re
import time
from typing import Union

import arrow
import six
from django.conf import settings
from django.utils import timezone

DEFAULT_FORMAT = "%Y-%m-%d %H:%M:%S"


def now():
    return timezone.now()


def now_str(_format="%Y-%m-%d %H:%M:%S"):
    return timezone.now().strftime(_format)


def datetime_today():
    return datetime.datetime.today()


def localtime(value):
    """
    to local time
    :param value: datetime obj
    :return: 返回带本地(业务)时区的datetime对象
    """
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return timezone.make_aware(value)


def utc2localtime(utc_time):
    """
    to local time
    :param utc_time: 时间戳
    :return: 返回带本地(业务)时区的datetime对象
    """
    datetime_value = datetime.datetime.fromtimestamp(utc_time)
    return localtime(datetime_value)


def timestamp2datetime(timestamp):
    """
    to datetime obj
    :param timestamp: 时间戳
    :return: 返回datetime对象
    """
    return datetime.datetime.fromtimestamp(timestamp)


def mysql_time(value):
    """
    to mysql time
    :param value: datetime obj
    :return: 返回带本地(业务)时区的datetime对象
    """
    if settings.USE_TZ:
        if timezone.is_aware(value):
            return value
        else:
            return arrow.get(value).replace(tzinfo=timezone.get_current_timezone_name()).datetime
    else:
        if timezone.is_aware(value):
            return arrow.get(value).to(timezone.get_current_timezone_name()).naive
        else:
            return value


def biz_time_zone_offset():
    """
    获取业务的时区偏移
    """
    offset = arrow.now().replace(tzinfo=timezone.get_current_timezone().zone).format("Z")
    return str(offset[0]) + str(int(offset[1:3]))  # 转成小时的精度, 而不是分钟


def strftime_local(value, _format="%Y-%m-%d %H:%M:%S%z"):
    """
    转成业务时区字符串
    :param value: datetime obj
    """
    return localtime(value).strftime(_format)


def biz2utc_str(local_time, _format="%Y-%m-%d %H:%M:%S"):
    """
    功能: 业务时间字符串 转换成 零时区字符串
    场景: 界面传过来的时间需要转换成零时区去查询db或调用API
    """
    return arrow.get(local_time).replace(tzinfo=timezone.get_current_timezone().zone).to("utc").strftime(_format)


def utc2biz_str(utc_time, _format="%Y-%m-%d %H:%M:%S"):
    """
    功能: 零时区字符串 转换成 业务时间字符串
    场景: 从DB或调用API传回来的时间(utc时间)需要转换成业务时间再给到前端显示
    """
    return arrow.get(utc_time).to(timezone.get_current_timezone().zone).strftime(_format)


def utc2_str(utc_time, _format="%Y-%m-%d %H:%M:%S"):
    """
    将utc时间戳转换为utc时间格式
    :param utc_time: 时间戳
    :param _format:转换格式
    :return:
    """
    return arrow.get(utc_time).strftime("%Y-%m-%d %H:%M:%S")


def get_timestamp_range_by_biz_date(date):
    """
    功能: 解析从浏览器传过来的日期格式字符串, 转成时间戳timestamp格式
    @return tuple(timestamp(unit: s), timestamp(unit: s))
    """
    start_timestamp = arrow.get(date).replace(tzinfo=timezone.get_current_timezone().zone).timestamp
    end_timestamp = start_timestamp + 86400  # 24 * 3600
    return start_timestamp, end_timestamp


def gen_default_time_range(days=1, offset=0):
    """
    功能: 生成默认的业务时间日期范围
    """
    biz_today = timezone.localtime(timezone.now()).date()
    if days + offset < 1:
        return (biz_today, biz_today + datetime.timedelta(1))
    return (biz_today - datetime.timedelta(days + offset - 1), biz_today + datetime.timedelta(1 - offset))


def parse_time_range(time_range=None, days=1, offset=0, _time_format="%Y-%m-%d %H:%M"):
    """
    功能: 解析从浏览器传过来的time_range, 转成UTC时区, 再返回timestamp
    场景: 获取图表数据
    @return tuple(timestamp(unit: s), timestamp(unit: s))
    """
    if not time_range:
        # 默认取业务时区当天的数据
        start, end = gen_default_time_range(days, offset)
    else:
        time_range = time_range.replace("&nbsp;", " ")
        start, end = [i.strip() for i in time_range.split("--")]
        # start = date_convert(start, 'datetime', _time_format)
        # end = date_convert(end, 'datetime', _time_format)
    tzinfo = timezone.get_current_timezone().zone
    start = arrow.get(start)
    end = arrow.get(end)

    # 没有时区信息时，使用业务时区补全
    if not hasattr(start.tzinfo, "_offset"):
        start = start.replace(tzinfo=tzinfo)
    if not hasattr(end.tzinfo, "_offset"):
        end = end.replace(tzinfo=tzinfo)
    return start.timestamp, end.timestamp


def date_convert(_date, _format, _time_format="%Y-%m-%d %H:%M:%S"):
    try:
        if isinstance(_date, datetime.date):
            if _format == "utc":
                return datetime2utc(_date, _time_format)

        elif isinstance(_date, six.string_types):
            if _format == "datetime":
                return str2datetime(_date, _time_format)
            elif _format == "date":
                return str2date(_date, "%Y-%m-%d")
            elif _format == "utc":
                return str2utc(_date, _time_format)

        elif isinstance(_date, six.integer_types):
            if _format == "datetime":
                return utc2datetime(_date, _time_format)
            elif _format == "date":
                return utc2date(_date, _time_format)

        return _date
    except Exception:
        return ""


# 字符串转datetime
def str2datetime(_str, _format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strptime(_str, _format)


def str2date(_str, _format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strptime(_str, _format).date()


def str2utc(_str, _format="%Y-%m-%d %H:%M:%S"):
    """
    字符串转UTC
    """
    _datetime = datetime.datetime.strptime(_str, _format)
    return int(time.mktime(_datetime.timetuple()))


def datetime2utc(_datetime, _format="%Y-%m-%d %H:%M:%S"):
    """
    datetime转UTC
    """
    return int(time.mktime(_datetime.timetuple()))


def utc2datetime(_utc, _format="%Y-%m-%d %H:%M:%S"):
    """
    UTC转datetime
    """
    return time.strftime(_format, time.localtime(int(_utc)))


def utc2date(_utc, _format="%Y-%m-%d %H:%M"):
    """
    UTC转date
    """
    return time.strftime(_format, time.localtime(int(_utc)))


def get_datetime_range(period, distance, now=None, rounding=True):
    now = now or localtime(timezone.now())
    if period == "minute":
        begin = arrow.get(now).replace(minutes=-distance)
        end = arrow.get(now)
        if rounding:
            begin = begin.ceil("minute")
            end = end.ceil("minute")

    elif period == "day":
        begin = arrow.get(now).replace(days=-distance)
        end = arrow.get(now)
        if rounding:
            begin = begin.ceil("day")
            end = end.ceil("day")
    elif period == "hour":
        begin = arrow.get(now).replace(hours=-distance)
        end = arrow.get(now)
        if rounding:
            begin = begin.ceil("hour")
            end = end.ceil("hour")
    else:
        raise TypeError("invalid period: %r" % period)

    if settings.USE_TZ:
        return begin.datetime, end.datetime
    else:
        return begin.naive, end.naive


def get_datetime_list(begin_time, end_time, period):
    if period == "day":
        timedelta = "days"
    elif period == "hour":
        timedelta = "hours"
    else:
        raise TypeError("invalid period: %r" % period)

    datetime_list = []
    item = begin_time
    while item < end_time:
        datetime_list.append(item)
        item = item + timezone.timedelta(**{timedelta: 1})

    return datetime_list


def utcoffset_in_seconds():
    """
    获取当前时区偏移量（秒）
    """
    return localtime(now()).utcoffset().total_seconds()


def datetime2timestamp(value):
    """
    datetime转timestamp格式
    """
    return time.mktime(localtime(value).timetuple())


def hms_string(sec_elapsed, display_num=2, day_unit="d", hour_unit="h", minute_unit="m", second_unit="s", upper=False):
    """
    将秒数转化为 人类易读时间 1d 12h 3m
    """
    d = int(sec_elapsed // (60 * 60) // 24)
    h = int((sec_elapsed - d * 24 * 3600) // 3600)
    m = int((sec_elapsed - d * 24 * 3600 - h * 3600) // 60)
    s = int(sec_elapsed - d * 24 * 3600 - h * 3600 - m * 60)

    # 在上面的基本计算之外，检查是否需要向上取整
    if upper:
        if d:
            if any([h, m, s]):
                d += 1
                h = m = s = 0
        elif h:
            if any([m, s]):
                h += 1
                m = s = 0
        elif m:
            if s:
                m += 1
                s = 0

    units = [(d, day_unit), (h, hour_unit), (m, minute_unit), (s, second_unit)]
    time_str = ""
    index = 0
    for unit in units:
        if unit[0] == 0:
            continue

        index += 1
        time_str += "{}{} ".format(unit[0], unit[1])
        if index >= display_num:
            return time_str.strip()

    if not time_str:
        return "{}{}".format(s, second_unit)

    return time_str.strip()


TIME_ABBREVIATION_MATCH = re.compile(r"^[-+]?[0-9]*\.?[0-9]+[smhdwMy]")


def parse_time_compare_abbreviation(time_offset: Union[int, str]) -> int:
    """
    时间对比解析(h/d/w/M/y)
    :param time_offset: 1d / 0.5m / -5w
    :return: 返回一个整数，以秒为单位。 int (unit: s)
    """
    if isinstance(time_offset, (int, float)):
        return time_offset

    time_offset = str(time_offset).strip()

    if not time_offset or not TIME_ABBREVIATION_MATCH.match(time_offset):
        time_offset = 0
    else:
        if time_offset[-1] in "smhdw":
            time_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
            try:
                time_offset = -int(float(time_offset[:-1]) * time_unit[time_offset[-1]])
            except ValueError:
                # 降采样低于1s后， 单位为ms， 上面逻辑不适用，最低设置为1s即可。
                time_offset = -1
        else:
            current_time = arrow.now()
            if time_offset[-1] == "M":
                last_time = current_time.replace(months=-int(float(time_offset[:-1])))
            else:
                last_time = current_time.replace(years=-int(float(time_offset[:-1])))
            time_offset = int((last_time - current_time).total_seconds())

    return time_offset


def datetime_str_to_datetime(datetime_str, format, time_zone=0):
    return arrow.get(datetime.datetime.strptime(datetime_str, format)).replace(hours=time_zone).datetime


def timestamp_to_tz_datetime(timestamp, offset):
    return arrow.get(timestamp).replace(hours=offset).datetime


def datetime_to_tz_timestamp(datetime, offset):
    return arrow.get(datetime).replace(hours=-offset).timestamp


def datetime2str(date_time: datetime.datetime, format="%Y-%m-%d %H:%M:%S"):
    # datetime 转换为时间字符串
    return date_time.strftime(format)


def time_interval_align(timestamp: int, interval: int):
    """
    时间对齐函数
    :param timestamp: 时间戳(单位: s)
    :param interval: 对齐间隔(单位: s)
    """

    # 获取当前时区偏移量（秒）
    timezone_offset = int(timezone.localtime().utcoffset().total_seconds())

    # 按时区偏移量对齐
    timestamp += timezone_offset

    # 以interval为单位对齐
    timestamp = timestamp // interval * interval

    # 恢复时区偏移量
    timestamp -= timezone_offset

    return timestamp


MAX_DATETIME_STR = datetime2str(datetime.datetime.max)
