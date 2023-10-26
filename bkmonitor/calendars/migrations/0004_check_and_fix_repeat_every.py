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

from django.db import migrations

from calendars.constants import ItemFreq
from bkmonitor.utils.time_tools import timestamp_to_tz_datetime


def check_and_fix_repeat_every(apps, schema_editor):
    """
    检查并修正为空的repeat_every
    """
    CalendarItemModel = apps.get_model("calendars", "CalendarItemModel")
    for item in CalendarItemModel.objects.all():
        if not item.repeat:
            continue
        if item.repeat["every"] != []:
            continue

        offset = datetime.datetime.now(pytz.timezone(item.time_zone)).utcoffset().seconds // 3600
        if offset > 12:
            offset -= 24
        start_time = timestamp_to_tz_datetime(item.start_time, offset)

        if item.repeat["freq"] == ItemFreq.WEEK:
            item.repeat["every"] = [(start_time.weekday() + 1) % 7]
        elif item.repeat["freq"] == ItemFreq.MONTH:
            item.repeat["every"] = [start_time.day]
        elif item.repeat["freq"] == ItemFreq.YEAR:
            item.repeat["every"] = [start_time.month]
        print(item.name, item.repeat)
        item.save()


class Migration(migrations.Migration):
    dependencies = [
        ("calendars", "0003_auto_20220415_1456"),
    ]

    operations = [migrations.RunPython(check_and_fix_repeat_every)]