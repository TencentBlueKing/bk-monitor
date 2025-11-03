"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import bisect
import logging
from datetime import datetime, timedelta

import pytz
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from pypinyin import lazy_pinyin
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.time_tools import timestamp_to_tz_datetime
from calendars.constants import (
    CHANGE_TYPE_LIST,
    DELETE_TYPE_LIST,
    TIME_ZONE_DICT,
    ItemFreq,
)
from calendars.models import CalendarItemModel, CalendarModel
from calendars.serializers import RepeatSerializer
from core.drf_resource import Resource

"""
时间的计算规则（以week为例）：
    1. 根据给定的time获取对应的weekday，拿这个weekday在every中找到能插入的位置。
    2. 利用这个能插入的位置获取到next_weekday,将weekday和next_weekday进行比较：
        如果weekday小于next_weekday，则将time的day加上next_weekday-weekday的相隔天数。
        如果weekday大于等于next_weekday，则time需要加上 interval*7 + every[0] - weekday（即寻找下interval个星期的第一个符合时间）。

    总体的思路就是上面这样，先获取当前的一个标签，然后拿这个标签去every中找到对应的位置，接着去通过比对两个值的大小来决定时间是如何漂移的。
    需要注意按月计算逻辑，如果下一个interval月的第every[0]天还报错，应该继续找下下个interval月。every中是有序的数字，
    如果第一个都出错了，后面的天数（29或30或31）肯定不满足当前月的计算规则，所以直接到下下个interval月重新计算即可。
"""

logger = logging.getLogger("calendars")


def get_offset(time_zone):
    """
    获取时间漂移
    :param time_zone: 时区
    :return: 时间漂移数值
    """
    offset = datetime.now(pytz.timezone(time_zone)).utcoffset().seconds // 3600
    if offset > 12:
        offset -= 24
    return offset


def get_day(time, time_zone, day_start=True):
    """
    根据时间戳或datetime计算出当天的年月日时间戳
    :param time: 时间戳或者datetime
    :param time_zone: 时区
    :param day_start: 返回这天的开始时间还是结束时间，True为开始时间则是0:0:0
    :return: 对应时间的时间戳
    """
    offset = get_offset(time_zone)
    if isinstance(time, int):
        time = timestamp_to_tz_datetime(time, offset)
    time = datetime.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d")
    if not day_start:
        time = time.replace(hour=23, minute=59, second=59)
    return int(time.timestamp())


def find_time_by_week(time, every, interval):
    """
    按照给定的time，根据week频率和规则计算出下一个符合条件的time
    :param time: 当前时间
    :param every: 循环规则
    :param interval: 周期
    :return: 返回下一个符合规则的时间
    """
    now_weekday = (time.weekday() + 1) % 7
    insert_position = bisect.bisect(every, now_weekday)
    try:
        next_weekday = every[insert_position]
    except Exception:
        next_weekday = every[-1]
    if now_weekday < next_weekday:
        time += timedelta(days=next_weekday - now_weekday)
    else:
        time += timedelta(days=every[0] + 7 * interval - now_weekday)
    return time


def get_replace_day_and_month(count):
    """
    根据当前月和周期计算出需要转换的年和月
    :param count: 当前月+按月循环周期
    :return: 返回需要转换的年和月
    """
    replace_years = count // 12
    replace_months = count % 12
    if not replace_months:
        replace_months = 12
        replace_years -= 1
    return replace_years, replace_months


def find_next_month(time, interval, replace_years, replace_months, replace_days):
    """
    按照给定的time，根据month频率和规则计算出下一个符合条件的time（是find_time_by_month的下一层）
    :param time: 当前时间
    :param interval: 周期
    :param replace_years: 需要转换的年
    :param replace_months: 需要转换的月
    :param replace_days: 需要转换的日
    :return: 返回下一个符合规则的时间
    """
    try:
        return time.replace(year=time.year + replace_years, month=replace_months, day=replace_days)
    except Exception:
        now = interval + replace_months + replace_years * 12
        replace_years, replace_months = get_replace_day_and_month(now)
        return find_next_month(time, interval, replace_years, replace_months, replace_days)


def find_time_by_month(time, every, interval):
    """
    按照给定的time，根据month频率和规则计算出下一个符合条件的time
    :param time: 当前时间
    :param every: 循环规则
    :param interval: 周期
    :return: 返回下一个符合规则的时间
    """
    now_day = time.day
    insert_position = bisect.bisect(every, now_day)
    try:
        next_day = every[insert_position]
    except Exception:
        next_day = every[-1]
    if now_day < next_day:
        try:
            time = time.replace(day=every[insert_position])
        except Exception:
            replace_years, replace_months = get_replace_day_and_month(time.month + interval)
            time = find_next_month(time, interval, replace_years, replace_months, every[0])
    else:
        replace_years, replace_months = get_replace_day_and_month(time.month + interval)
        time = find_next_month(time, interval, replace_years, replace_months, every[0])
    return time


def add_year(time, every, interval, insert_position):
    """
    年的循环计算事项
    :param time: 当前的时间
    :param every: 循环规则
    :param interval: 周期
    :param insert_position: 当前的月在every中对应的位置
    :return: 返回下一个符合规则的时间
    """
    for month in every[insert_position:]:
        try:
            time = time.replace(month=month)
            return time
        except Exception:
            continue
    else:
        time = time.replace(year=time.year + interval)
        return add_year(time, every, interval, 0)


def find_time_by_year(time, every, interval):
    """
    按照给定的time，根据year频率和规则计算出下一个符合条件的time
    :param time: 当前时间
    :param every: 循环规则
    :param interval: 周期
    :return: 返回下一个符合规则的时间
    """
    now_month = time.month
    insert_position = bisect.bisect(every, now_month)
    try:
        next_month = every[insert_position]
    except Exception:
        next_month = every[-1]
    if now_month < next_month:
        time = add_year(time, every, interval, insert_position)
    else:
        time = time.replace(year=time.year + interval, month=every[0])
        time = add_year(time, every, interval, 0)
    return time


def find_next_start_time(freq, time, every, interval):
    """
    根据相应的规则，查找到下一个time
    :param freq: 频率，决定使用哪种计算规则
    :param time: 当前时间
    :param every: 循环规则
    :param interval: 周期
    :return: 返回下一个符合规则的时间
    """
    if freq == ItemFreq.DAY:
        time += timedelta(days=interval)
    elif freq == ItemFreq.WEEK:
        time = find_time_by_week(time, every, interval)
    elif freq == ItemFreq.MONTH:
        time = find_time_by_month(time, every, interval)
    else:
        time = find_time_by_year(time, every, interval)
    return time


def item_add_status(item_dict, now):
    """
    为返回数据添加状态
    """
    item_dict["status"] = item_dict["end_time"] >= now
    return item_dict


class SaveItemResource(Resource):
    """
    保存日历事项
    """

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(label="日历事项名称", max_length=15)
        calendar_id = serializers.IntegerField(label="所属日历ID")
        start_time = serializers.IntegerField(label="事项开始时间")
        end_time = serializers.IntegerField(label="事项结束时间")
        repeat = RepeatSerializer(required=False, label="重复事项配置信息", default={})
        time_zone = serializers.CharField(label="时区信息", max_length=35)

        def validate_time_zone(self, value):
            if value and value not in pytz.all_timezones_set:
                raise ValidationError(_("所选时区错误，请修改后再次尝试"))
            return value

        def validate_calendar_id(self, value):
            if value:
                calendar = CalendarModel.objects.filter(id=value, bk_tenant_id=get_request_tenant_id()).first()
                if not calendar:
                    raise ValidationError(_("日历不存在"))
                if calendar.classify == "default":
                    raise ValidationError(_("这是内置日历，不能进行任何操作"))
            return value

    def perform_request(self, params: dict):
        params["bk_tenant_id"] = get_request_tenant_id()
        return {"id": CalendarItemModel.objects.create(**params).id}


class DeleteItemResource(Resource):
    """
    删除日历事项
        1。 如果是不重复事项和子事项，则不管传入的delete_type是何种，都是全部删除（就一个事项）
        2。 如果传入的是删除全部事项，则根据传入的id去查找对应的id和parend_id将其删除
        3。 如果是仅删除当前事项，直接在excluede_date中添加当前日期
        4。 如果是删除当前和以后，则将当前事项到原先until所有挂载的子事项解除挂载，删除exclue_date中额外的date，然后将父事项的until提前
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="日历事项ID")
        start_time = serializers.IntegerField(label="事项开始时间")
        end_time = serializers.IntegerField(label="事项结束时间")
        repeat = RepeatSerializer(required=False, label="重复事项配置信息", default={})
        delete_type = serializers.ChoiceField(label="删除类型", choices=DELETE_TYPE_LIST)

        def validate_id(self, value):
            if value:
                item = CalendarItemModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=value)
                calendar = CalendarModel.objects.filter(
                    id=item.calendar_id, bk_tenant_id=get_request_tenant_id()
                ).first()
                if not calendar:
                    raise ValidationError(_("日历不存在"))
                if calendar.classify == "default":
                    raise ValidationError(_("该事项属于内置日历事项，不能进行任何操作"))
            return value

    def perform_request(self, params: dict):
        delete_type = params["delete_type"]
        item_id = params["id"]
        item = CalendarItemModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=item_id)
        start_time = params["start_time"]

        if not item.repeat or item.parent_id:
            item.delete()
        elif delete_type == DELETE_TYPE_LIST[0]:
            if start_time == item.start_time:
                CalendarItemModel.objects.filter(
                    Q(parent_id=item_id) | Q(id=item_id), bk_tenant_id=get_request_tenant_id()
                ).delete()
            else:
                raise ValueError(_("当前事项不是第一项，无法删除全部"))
        elif delete_type == DELETE_TYPE_LIST[1]:
            exclude_date = item.repeat["exclude_date"]
            exclude_date.append(get_day(start_time, item.time_zone))
            exclude_date.sort()
            item.save()
        else:
            # 将item.start_time大于start_time并且挂在在当前事项的子事项解除挂载
            CalendarItemModel.objects.filter(
                start_time__gte=start_time, parent_id=item_id, bk_tenant_id=get_request_tenant_id()
            ).update(parent_id=None)
            exclude_date = item.repeat["exclude_date"]
            exclude_date.append(get_day(start_time, item.time_zone))
            for time in exclude_date.copy():
                if time > get_day(start_time, item.time_zone):
                    exclude_date.remove(time)
            exclude_date.sort()
            item.repeat["until"] = get_day(time=start_time, time_zone=item.time_zone, day_start=False)
            item.save()


class EditItemResource(Resource):
    """
    修改日历事项
        1。 如果是不重复事项和子事项，则不管传入的change_type是何种，和全部修改等同（就一个事项）
        2。 如果传入的是修改全部事项，则直接修改id对应的事项
        3。 如果是仅修改当前事项，则创建一个子事项，将其挂载到父事项，并在父事项中添加excluede_date
        4。 如果是修改当前和以后，则新建一个事项，将当前事项到原先until所有挂载的子事项解除挂载，删除exclue_date中额外的date，然后将父事项的until提前
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="日历事项ID")
        name = serializers.CharField(required=False, label="日历事项名称", max_length=15)
        calendar_id = serializers.IntegerField(required=False, label="所属日历ID")
        start_time = serializers.IntegerField(required=False, label="事项开始时间")
        end_time = serializers.IntegerField(required=False, label="事项结束时间")
        repeat = RepeatSerializer(required=False, label="重复事项配置信息", default={})
        change_type = serializers.ChoiceField(label="修改类型", choices=CHANGE_TYPE_LIST)

        def validate_calendar_id(self, value):
            if value:
                calendar = CalendarModel.objects.filter(id=value, bk_tenant_id=get_request_tenant_id()).first()
                if not calendar:
                    raise ValidationError(_("日历不存在"))

                if calendar.classify == "default":
                    raise ValidationError(_("这是内置日历，不能进行任何操作"))
            return value

        def validate_id(self, value):
            if value:
                item = CalendarItemModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=value)
                calendar = CalendarModel.objects.get(id=item.calendar_id, bk_tenant_id=get_request_tenant_id())
                if calendar.classify == "default":
                    raise ValidationError(_("该事项属于内置日历事项，不能进行任何操作"))
            return value

    def perform_request(self, params: dict):
        change_type = params["change_type"]
        item_id = params["id"]
        item = CalendarItemModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=item_id)
        name = params.get("name", item.name)
        calendar_id = params.get("calendar_id", item.calendar_id)
        start_time = params.get("start_time", item.start_time)
        end_time = params.get("end_time", item.end_time)
        repeat = params.get("repeat")
        repeat = repeat if repeat else item.repeat

        if not item.repeat or item.parent_id or change_type == CHANGE_TYPE_LIST[0]:
            # 修改全部
            item.name = name
            item.calendar_id = calendar_id
            item.start_time = start_time
            item.end_time = end_time
            item.repeat = {} if item.parent_id else repeat
            item.save()
        elif change_type == CHANGE_TYPE_LIST[1]:
            # 仅改变当前时间的日历事项
            # 1. 将该事项设置为新事项，并且将该新事项挂载到item上
            new_item = CalendarItemModel.objects.create(
                bk_tenant_id=get_request_tenant_id(),
                name=name,
                calendar_id=calendar_id,
                start_time=start_time,
                end_time=end_time,
                repeat={},
                time_zone=item.time_zone,
                parent_id=item.parent_id if item.parent_id else item_id,
            )
            # 2. 将当天日期放入item的exclude_data中
            item.repeat["exclude_date"].append(get_day(start_time, item.time_zone))
            item.save()
            item = new_item
        else:
            # 改变当前事项及未来所有事项
            # 1. 根据相关配置生成新的事项
            new_item = CalendarItemModel.objects.create(
                bk_tenant_id=get_request_tenant_id(),
                name=name,
                calendar_id=calendar_id,
                start_time=start_time,
                end_time=end_time,
                repeat=repeat,
                time_zone=item.time_zone,
            )
            # 2. 根据start_time去将子表解除关联
            CalendarItemModel.objects.filter(
                parent_id=item_id, start_time__gte=start_time, bk_tenant_id=get_request_tenant_id()
            ).update(parent_id=None)
            # 3. 删除exclude_date中
            exclude_date = item.repeat["exclude_date"]
            exclude_date.append(get_day(start_time, item.time_zone))
            for time in exclude_date.copy():
                if time > get_day(start_time, item.time_zone):
                    exclude_date.remove(time)
            exclude_date.sort()

            # 4. 将repeat.until设置为可用的start_time
            item.repeat["until"] = get_day(time=start_time, time_zone=item.time_zone, day_start=False)
            item.save()
            item = new_item

        return item.to_json()


class ItemDetailResource(Resource):
    """
    获取某些日历下某个时间点的所有事项
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        calendar_ids = serializers.ListField(label="所属日历ID列表")
        time = serializers.IntegerField(label="查询时间")
        start_time = serializers.IntegerField(required=False, label="日历详情开始时间")

    def perform_request(self, params: dict):
        return ItemListResource()(
            bk_tenant_id=params["bk_tenant_id"],
            calendar_ids=params["calendar_ids"],
            start_time=params["time"],
            end_time=params["time"],
            time_zone=settings.TIME_ZONE,
        )


class ItemListResource(Resource):
    """
    查询规定日期内的所有日历事项列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        calendar_ids = serializers.ListField(label="所属日历ID列表")
        start_time = serializers.IntegerField(label="日历查询范围开始时间")
        end_time = serializers.IntegerField(label="日历查询范围结束时间")
        time_zone = serializers.CharField(required=False, label="时区信息", max_length=35)
        search_key = serializers.CharField(required=False, label="搜索关键词", default="")

        def validate_time_zone(self, value):
            if value and value not in pytz.all_timezones_set:
                raise ValidationError(_("所选时区错误，请修改后再次尝试"))
            return value

    def perform_request(self, params: dict):
        calendar_ids = params["calendar_ids"]
        search_key = params["search_key"]
        validated_data = {}
        if 0 not in calendar_ids:
            validated_data["calendar_id__in"] = calendar_ids
        if search_key:
            validated_data["name__icontains"] = search_key

        item_dict = {}
        items = CalendarItemModel.objects.filter(bk_tenant_id=params["bk_tenant_id"], **validated_data)

        calendar_ids = {item.calendar_id for item in items}

        calendars = CalendarModel.objects.filter(id__in=calendar_ids).only("id", "name", "deep_color", "light_color")

        calendars_mapping = {calendar.id: calendar for calendar in calendars}

        for item in items:
            time_zone = params.get("time_zone", item.time_zone)
            offset = get_offset(time_zone)
            repeat = item.repeat
            item_start_time = timestamp_to_tz_datetime(item.start_time, offset)  # 事项单次开始时间
            item_end_time = timestamp_to_tz_datetime(item.end_time, offset)  # 事项单次结束时间
            start_time = timestamp_to_tz_datetime(params["start_time"], offset)  # 查询范围开始时间
            end_time = timestamp_to_tz_datetime(params["end_time"], offset)  # 查询范围结束时间
            now = datetime.now().timestamp()  # 此刻的时间，用来计算该事项的状态

            # 对于一次性的可以直接存入
            if not repeat:
                if not (end_time < item_start_time or start_time > item_end_time):
                    item_list = item_dict.get(get_day(item_start_time, time_zone), [])
                    item_list.append(
                        item_add_status(item.to_json(time_zone=time_zone, calendars_mapping=calendars_mapping), now)
                    )
                    item_dict.update({get_day(item_start_time, time_zone): item_list})
                continue
            freq = repeat["freq"]
            until = repeat["until"] if repeat["until"] else end_time
            interval = repeat["interval"]
            every = repeat["every"]
            exclude_date = repeat["exclude_date"]
            until = timestamp_to_tz_datetime(timestamp=until, offset=offset)  # 事项结束时间
            old_time = item_start_time
            if (
                (freq == ItemFreq.WEEK and (item_start_time.weekday() + 1) % 7 not in every)
                or (freq == ItemFreq.MONTH and item_start_time.day not in every)
                or (freq == ItemFreq.YEAR and item_start_time.month not in every)
            ):
                item_start_time = find_next_start_time(freq, item_start_time, every, interval)

            end_time = min(end_time, until)
            # 1. 如果查询范围的开始时间大于事项的结束时间，则需要找到找下一个循环事项，直到查找到的事项的结束时间大于查询范围的开始时间
            while start_time > item_end_time:
                item_start_time = find_next_start_time(freq, item_start_time, every, interval)
                item_end_time += item_start_time - old_time
                old_time = item_start_time
            item_end_time += item_start_time - old_time

            # 2. 只要当前事项的开始时间小于查询范围的结束时间，就可以存入事项列表，并且更新当前事项
            while item_start_time <= end_time:
                if get_day(item_start_time, time_zone) not in exclude_date:
                    item_list = item_dict.get(get_day(item_start_time, time_zone), [])
                    if item_start_time == timestamp_to_tz_datetime(item.start_time, offset):
                        item_list.append(
                            item_add_status(
                                item.to_json(
                                    item_start_time, item_end_time, time_zone, calendars_mapping=calendars_mapping
                                ),
                                now,
                            )
                        )
                    else:
                        item_list.append(
                            item_add_status(
                                item.to_json(
                                    item_start_time,
                                    item_end_time,
                                    time_zone,
                                    is_first=False,
                                    calendars_mapping=calendars_mapping,
                                ),
                                now,
                            )
                        )
                    item_dict.update({get_day(item_start_time, time_zone): item_list})
                old_time = item_start_time
                item_start_time = find_next_start_time(freq, item_start_time, every, interval)
                item_end_time += item_start_time - old_time
        item_list = []
        for timestamp in sorted(list(item_dict.keys())):
            item_list.append(
                {"today": timestamp, "list": sorted(item_dict[timestamp], key=lambda item: item["start_time"])}
            )
        return item_list


class GetTimeZoneResource(Resource):
    """
    获取默认时区
    """

    def perform_request(self, validated_request_data):
        return sorted(
            [{"name": f"{name}({time_zone})", "time_zone": time_zone} for name, time_zone in TIME_ZONE_DICT.items()],
            key=lambda time_zone: lazy_pinyin(time_zone["name"]),
        )


class GetParentItemListResource(Resource):
    """
    获取所属日历下所有父类事项列表
    """

    class RequestSerializer(serializers.Serializer):
        calendar_ids = serializers.ListField(label="所属日历ID列表", child=serializers.IntegerField())

    def perform_request(self, params: dict):
        calendar_ids = params["calendar_ids"]
        items = CalendarItemModel.objects.filter(bk_tenant_id=get_request_tenant_id())
        if 0 not in calendar_ids:
            items = items.filter(calendar_id__in=calendar_ids)
        item_list = []
        for item in items:
            item_list.append(item.to_json())
        return {
            "total": len(item_list),
            "list": item_list,
        }
