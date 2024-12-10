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

import pytz
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.time_tools import (
    datetime_to_tz_timestamp,
    timestamp_to_tz_datetime,
)
from bkmonitor.utils.user import get_global_user
from calendars.constants import ItemFreq


class AbstractModel(models.Model):
    create_user = models.CharField(
        "创建人",
        max_length=32,
        default="",
        blank=True,
    )
    create_time = models.IntegerField("创建时间", blank=True, null=True)
    update_user = models.CharField(
        "最后修改人",
        max_length=32,
        default="",
        blank=True,
    )
    update_time = models.IntegerField("最后修改时间", blank=True, null=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        username = get_global_user() or "unknown"
        now = int(datetime.datetime.now().timestamp())
        self.update_user = username
        self.update_time = now
        if self.pk is None:
            self.create_user = username
            self.create_time = now
        return super(AbstractModel, self).save(*args, **kwargs)


class CalendarModel(AbstractModel):
    """
    日历模型
    """

    CALENDAR_CLASSIFY_CHOICES = (("default", _lazy("内置")), ("custom", _lazy("自定义")))
    name = models.CharField(
        "日历名称",
        max_length=15,
    )
    classify = models.CharField("日历分类", choices=CALENDAR_CLASSIFY_CHOICES, max_length=12)
    deep_color = models.CharField("日历深色底色", max_length=7, default="#3A84FF")
    light_color = models.CharField("日历浅色底色", max_length=7, default="#E1ECFF")

    class Meta:
        verbose_name = "日历信息"
        verbose_name_plural = verbose_name
        db_table = "calendar"

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "update_user": self.update_user,
            "update_time": self.update_time,
            "create_user": self.create_user,
            "create_time": self.create_time,
            "classify": self.classify,
            "deep_color": self.deep_color,
            "light_color": self.light_color,
        }


class CalendarItemModel(AbstractModel):
    """
    日历事项模型
    """

    name = models.CharField(
        "日历事项名称",
        max_length=15,
    )
    calendar_id = models.IntegerField("日历ID")
    start_time = models.IntegerField("事项开始时间")
    end_time = models.IntegerField("事项结束时间")
    repeat = JsonField("重复事项配置信息")
    parent_id = models.IntegerField("父事项ID", null=True, blank=True)
    time_zone = models.CharField("时区信息", default="Asia/Shanghai", max_length=35)

    class Meta:
        verbose_name = "日历事项"
        verbose_name_plural = verbose_name
        db_table = "calendar_item"

    def to_json(self, start_time=None, end_time=None, time_zone=None, is_first=True):
        calendar = CalendarModel.objects.get(id=self.calendar_id)
        time_zone = time_zone if time_zone else self.time_zone
        offset = datetime.datetime.now(pytz.timezone(time_zone)).utcoffset().seconds // 3600
        if offset > 12:
            offset -= 24
        start_time = start_time if start_time else timestamp_to_tz_datetime(self.start_time, offset)
        end_time = end_time if end_time else timestamp_to_tz_datetime(self.end_time, offset)

        return {
            "id": self.id,
            "name": self.name,
            "start_time": datetime_to_tz_timestamp(start_time, offset),
            "end_time": datetime_to_tz_timestamp(end_time, offset),
            "update_user": self.update_user,
            "update_time": self.update_time,
            "create_time": self.create_time,
            "create_user": self.create_user,
            "calendar_id": self.calendar_id,
            "calendar_name": calendar.name,
            "deep_color": calendar.deep_color,
            "light_color": calendar.light_color,
            "repeat": self.repeat,
            "parent_id": self.parent_id,
            "is_first": is_first,
        }

    def save(self, *args, **kwargs):
        if self.time_zone and self.time_zone not in pytz.all_timezones_set:
            raise ValueError(_("所选时区错误，请修改后再次尝试"))
        if self.repeat:
            # 判断every是否符合标准
            freq = self.repeat["freq"]
            # 每天的every制为[]
            if freq == ItemFreq.DAY:
                self.repeat["every"] = []
            # 如果every为空并且freq不为每天，则强制使用start_time作为循环周期
            elif not self.repeat["every"]:
                offset = datetime.datetime.now(pytz.timezone(self.time_zone)).utcoffset().seconds // 3600
                if offset > 12:
                    offset -= 24
                start_time = timestamp_to_tz_datetime(self.start_time, offset)
                if freq == ItemFreq.WEEK:
                    self.repeat["every"] = [(start_time.weekday() + 1) % 7]
                elif freq == ItemFreq.MONTH:
                    self.repeat["every"] = [start_time.day]
                else:
                    self.repeat["every"] = [start_time.month]
            # 判断循环结束时间是否大于start_time
            if self.repeat["until"] and self.repeat["until"] < self.start_time:
                raise ValueError(_("循环结束时间不能小于事项开始时间，请重新尝试"))
            # 对every进行排序
            self.repeat["every"].sort()

        return super(CalendarItemModel, self).save(*args, **kwargs)
