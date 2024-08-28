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
import calendar
import logging
import typing
from collections import defaultdict
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta, timezone
from itertools import groupby
from operator import attrgetter

from dateutil.relativedelta import relativedelta
from django.db.models import Q

from bkmonitor.models import DutyPlan, DutyRule, DutyRuleSnap, UserGroup
from bkmonitor.models.strategy import DutyPlanSendRecord
from bkmonitor.utils import time_tools
from bkmonitor.utils.send import Sender
from constants.action import NoticeWay
from constants.common import DutyGroupType, RotationType, WorkTimeType

logger = logging.getLogger("fta_action.run")


class DutyCalendar:
    @classmethod
    def get_end_time(cls, end_date, handover_time):
        """
        获取结束时间
        """
        try:
            [hour, minute] = handover_time.split(":")
            hour = int(hour)
            minute = int(minute)
        except BaseException as error:
            logger.exception("[get_handover_time] split handover_time(%s) error, %s", handover_time, str(error))
            hour, minute = 0, 0
        end_time = datetime(year=end_date.year, month=end_date.month, day=end_date.day, hour=hour, minute=minute)
        return datetime.fromtimestamp(end_time.timestamp(), tz=timezone.utc)

    @staticmethod
    def get_daily_rotation_end_time(begin_time: datetime, handoff_time):
        """
        获取按天轮转的结束时间
        """
        begin_time = time_tools.localtime(begin_time)
        handover_time = handoff_time["time"]
        if handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            end_date = (begin_time + timedelta(days=1)).date()
        return DutyCalendar.get_end_time(end_date, handover_time)

    @staticmethod
    def get_weekly_rotation_end_time(begin_time: datetime, handoff_time):
        """
        获取按周轮转的结束时间
        """
        begin_time = time_tools.localtime(begin_time)
        begin_week_day = begin_time.isoweekday()
        handover_date = handoff_time["date"]
        handover_time = handoff_time["time"]
        if handover_date > begin_week_day:
            end_date = (begin_time + timedelta(days=handover_date - begin_week_day)).date()
        elif handover_date == begin_week_day and handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            end_date = (begin_time + timedelta(days=handover_date + 7 - begin_week_day)).date()
        return DutyCalendar.get_end_time(end_date, handover_time)

    @staticmethod
    def get_monthly_rotation_end_time(begin_time: datetime, handoff_time):
        """
        获取按月进行轮转的结束时间
        """
        begin_time = time_tools.localtime(begin_time)
        begin_month_day = begin_time.day
        handover_date = handoff_time["date"]
        handover_time = handoff_time["time"]
        _, max_current_month_day = calendar.monthrange(begin_time.year, begin_time.month)

        if max_current_month_day >= handover_date > begin_month_day:
            handover_date = min(handover_date, max_current_month_day)
            end_date = (begin_time + timedelta(days=(handover_date - begin_month_day))).date()
        elif handover_date == begin_month_day and handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            next_month = begin_time.date() + relativedelta(months=1)
            _, max_month_day = calendar.monthrange(next_month.year, next_month.month)
            handover_date = min(handover_date, max_month_day)
            end_date = datetime(next_month.year, next_month.month, handover_date)
        return DutyCalendar.get_end_time(end_date, handover_time)


class DutyRuleManager:
    """
    轮值规则管理模块
    """

    def __init__(
        self,
        duty_rule,
        begin_time: str = None,
        days=0,
        last_user_index=0,
        last_time_index=0,
        end_time: str = None,
        snap_end_time: str = "",
    ):
        self.duty_arranges = duty_rule["duty_arranges"]
        self.category = duty_rule.get("category")
        begin_time = begin_time or ""
        self.begin_time = time_tools.str2datetime(max(begin_time, duty_rule["effective_time"]))
        self.enabled = bool(duty_rule.get("enabled"))
        self.last_user_index = last_user_index
        self.last_time_index = last_time_index
        # end_time 可视为预览/当次排班结束时间，不包括最后一天
        if end_time:
            self.end_time = time_tools.str2datetime(end_time)
        else:
            # 如果本来没有设置结束时间，和预览天数，默认用30天
            days = days or 30
            self.end_time = self.begin_time + timedelta(days=days)

        # end_date 为规则/快照的结束日期，包括这天
        self.end_date = self._calculate_end_date(duty_rule.get("end_time"), snap_end_time)
        self._last_duty_plans = []

    def get_last_duty_plans(self):
        """
        缓存上一次排班的结果
        """
        return self._last_duty_plans

    @staticmethod
    def _calculate_end_date(rule_end_time: typing.Optional[str], snap_end_time: typing.Optional[str]) -> datetime.date:
        """结束日期，包括这一天，除非是一天的开始。"""
        rule_end_datetime = end_time_to_datetime(rule_end_time)
        snap_end_datetime = end_time_to_datetime(snap_end_time)
        final_end_datetime = min(rule_end_datetime, snap_end_datetime)

        if final_end_datetime.time() == dt_time.min:
            final_end_datetime -= timedelta(microseconds=1)

        return final_end_datetime.date()

    def get_duty_plan(self):
        """
        获取轮值计算排班入口
        """
        if not self.enabled:
            return []
        if self.category == "regular":
            return self.get_regular_duty_plan()
        return self.get_rotation_duty_plan()

    def get_duty_dates(self, duty_time, special_rotation=False, period_interval=0):
        """
        根据一个轮班设置获取指定时间范围内的有效日期（按天获取）
        """
        date_ranges = []
        weekdays = []
        days = []
        duty_dates = []
        work_days = self.get_work_days(duty_time)
        if duty_time["work_type"] == RotationType.DATE_RANGE:
            # 如果是根据时间返回来获取的, 则根据时间范围来获取
            for item in duty_time["work_date_range"]:
                # 如果开始至结束期间，只要当前日期满足日期范围，就符合条件
                [begin_date, end_date] = item.split("--")
                date_ranges.append((begin_date, end_date))
        elif duty_time["work_type"] in RotationType.WEEK_MODE:
            # 按照周来处理的
            weekdays = work_days
        elif duty_time["work_type"] == RotationType.MONTHLY:
            # 按照月来轮班的情况
            days = work_days
        begin_time = (
            time_tools.str2datetime(duty_time["begin_time"]) if duty_time.get("begin_time") else self.begin_time
        )
        # 只有按周，按月才有对应的交接工作日，就是页面配置的起始日期

        handoff_date = work_days[0] if work_days else None
        period_dates = []
        # 标记最近一次交接时间
        last_handoff_time = self.end_time - timedelta(days=1)
        # 只比较日期，包括结束日期
        while begin_time.date() <= min(last_handoff_time.date(), self.end_date):
            # 在有效的时间范围内，获取有效的排期
            is_valid = False
            # 如果是指定
            begin_date = begin_time.strftime("%Y-%m-%d")
            next_day_time = begin_time + timedelta(days=1)

            # 是否为新的周期，只有那种需要指定班次轮值的情况下才生效，所以其他场景默认都为新的周期就好
            new_period = (
                self.is_new_period(duty_time["work_type"], handoff_date, next_day_time) if special_rotation else True
            )

            if (
                duty_time["work_type"] == RotationType.DAILY
                or begin_time.isoweekday() in weekdays
                or begin_time.day in days
            ):
                # 如果是每天都轮班，则一定生效
                # 如果是按周轮班，当天在工作日内
                # 如果按月轮班，当天在工作日内
                is_valid = True
            else:
                for date_range in date_ranges:
                    if date_range[0] <= begin_date <= date_range[1]:
                        is_valid = True
                        break

            if is_valid:
                period_dates.append(begin_time.date())

            if period_interval and len(period_dates) % period_interval:
                # 如果是通过系统自动排班日期的，则以是否能够整除为准
                new_period = False

            if special_rotation and new_period and period_dates:
                # 如果是一个新的周期，原来的安排归档，开始一个新的周期计算
                duty_dates.append(period_dates)
                period_dates = []

            if new_period is False and last_handoff_time < next_day_time:
                # 如果不是一个新的周期，表示要继续
                last_handoff_time = next_day_time

            begin_time = next_day_time
        if special_rotation and period_dates:
            # 如果需要轮转并且最后一个周期日期还没有合入，添加到结果中， 这种情况一般是最后一次循环跳出没有合入
            duty_dates.append(period_dates)
        # 更新当前时间段的下一次排班交接时间
        duty_time["begin_time"] = time_tools.datetime2str(last_handoff_time + timedelta(days=1))
        return duty_dates if special_rotation else period_dates

    @staticmethod
    def get_work_days(duty_time):
        """
        获取轮值的有效工作日
        """
        if duty_time.get("work_time_type") != WorkTimeType.DATETIME_RANGE:
            return duty_time.get("work_days", [])

        # 定义时间范围的一个最大日期
        max_work_day = 7 if duty_time["work_type"] in RotationType.WEEK_MODE else 31
        for work_time in duty_time["work_time"]:
            # 起止时间的场景下，只有一个工作时间段
            [start_time, end_time] = work_time.split("--")
            start_work_day = int(start_time[:2])
            end_work_day = int(end_time[:2])
            if start_work_day < end_work_day:
                # 如果开始小于结束，则表示是一周范围之内的
                work_days = list(range(start_work_day, end_work_day + 1))
            else:
                # 如果是大于于，需要分成两段
                # 第一段 是开始时间至最大结束时间
                first_stage = list(range(start_work_day, max_work_day + 1))
                second_stage = list(range(1, end_work_day + 1))
                work_days = first_stage + second_stage
            #  只有一个时间范围，直接返回
            return work_days

    @staticmethod
    def is_new_period(work_type, handoff_date, next_day_time: datetime):
        """
        判断是否为新的周期，只有那种需要指定班次轮值的情况下才生效，所以其他场景默认都为新的周期就好
        """
        new_period = False
        if work_type == RotationType.DAILY:
            new_period = True
        elif work_type in RotationType.WEEK_MODE and next_day_time.isoweekday() == handoff_date:
            # 按周轮转，如果下一天为交接日期，表示将会开启一个新的交接
            new_period = True
        elif work_type == RotationType.MONTHLY and next_day_time.day == handoff_date:
            # 按月轮转，如果下一天为交接日期，表示将会开启一个新的交接
            new_period = True
        return new_period

    def get_auto_hour_periods(self, duty_time):
        # TODO 获取根据小时轮转的周期
        return []

    def get_regular_duty_plan(self):
        """
        获取常规轮值的排班计划
        """
        duty_plans = []
        for index, duty_arrange in enumerate(self.duty_arranges):
            work_time = []
            for duty_time in duty_arrange["duty_time"]:
                duty_dates = self.get_duty_dates(duty_time)
                for work_date in duty_dates:
                    # 获取到有效的日期，进行排班
                    work_time.extend(self.get_time_range_work_time(work_date, duty_time["work_time"]))

            if work_time:
                duty_plans.append(
                    {
                        "users": duty_arrange["duty_users"][0],
                        "order": index,
                        "user_index": index,
                        "work_times": work_time,
                    }
                )
        return duty_plans

    def get_rotation_duty_plan(self):
        """
        获取轮值周期排班
        """
        duty_plans = []
        if not self.duty_arranges:
            return []
        # 轮值情况下只有一个
        for order, duty_arrange in enumerate(self.duty_arranges):
            self.get_one_handoff_duty_plan(duty_arrange, order, duty_plans)
        return duty_plans

    def get_one_handoff_duty_plan(self, duty_arrange, order, duty_plans: list):
        """
        获取单个安排的计划
        """
        duty_users = duty_arrange["duty_users"]
        duty_times = duty_arrange["duty_time"]
        last_user_index = duty_arrange.get("last_user_index") or self.last_user_index
        group_user_number = 1
        period_interval = 1
        group_type = duty_arrange.get("group_type", DutyGroupType.SPECIFIED)
        if group_type == DutyGroupType.AUTO:
            # 如果人员信息为自动
            group_user_number = duty_arrange["group_number"]
            duty_users = duty_users[0]
        duty_date_times = []
        special_rotation = True
        for duty_time in duty_times:
            period_settings = duty_time.get("period_settings")
            if period_settings:
                # 如果有进行自动按照天数或者小时轮值的，计算出来有效的轮值天数
                special_rotation = False
                period_interval = period_settings["duration"]
                duty_date_times.extend(
                    [
                        {"date": one_date, "work_time_list": duty_time["work_time"]}
                        for one_date in self.get_duty_dates(duty_time, period_interval=period_interval)
                    ]
                )
                break
            # 没有进行自动计算的情况，需要做轮值获取
            # 一般来说一个需要轮转的规则里，轮值类型都是一样的
            period_duty_dates = self.get_duty_dates(duty_time, special_rotation=True)

            period_duty_date_times = []
            for one_period_dates in period_duty_dates:
                period_duty_date_times.append(
                    [
                        {
                            "date": one_date,
                            "work_time_type": duty_time["work_time_type"],
                            "work_type": duty_time["work_type"],
                            "work_time_list": duty_time["work_time"],
                        }
                        for one_date in one_period_dates
                    ]
                )

            duty_date_times.append(period_duty_date_times)

        if special_rotation:
            # 如果是进行轮转的，需要做轮值时间周期打平
            duty_date_times = self.flat_rotation_duty_dates(duty_date_times)
        date_index = 0
        while date_index < len(duty_date_times):
            # 根据配置的有效时间进行轮转
            current_duty_dates = duty_date_times[date_index : date_index + period_interval]
            date_index = date_index + period_interval
            # 根据设置的用户数量进行轮转
            current_user_index = last_user_index
            users, last_user_index = self.get_group_duty_users(
                duty_users, last_user_index, group_user_number, group_type
            )
            duty_work_time = []
            for one_period_dates in current_duty_dates:
                if not isinstance(one_period_dates, list):
                    one_period_dates = [one_period_dates]
                for day in one_period_dates:
                    if day.get("work_time_type") == WorkTimeType.DATETIME_RANGE:
                        duty_work_time.extend(
                            self.get_datetime_range_work_time(day["date"], day["work_time_list"], day["work_type"])
                        )

                        continue

                    duty_work_time.extend(self.get_time_range_work_time(day["date"], day["work_time_list"]))

            duty_plans.append(
                {"users": users, "user_index": current_user_index, "order": order, "work_times": duty_work_time}
            )
        duty_arrange["last_user_index"] = last_user_index
        return duty_plans

    @staticmethod
    def flat_rotation_duty_dates(duty_dates):
        """
        将有效的排班日期打平
        """
        max_column_len = max(len(period_column) for period_column in duty_dates)
        new_duty_dates = []
        for column in range(0, max_column_len):
            for row in range(0, len(duty_dates)):
                if len(duty_dates[row]) <= column:
                    # 如果当前的列数已经小于轮询的列
                    break
                new_duty_dates.append(duty_dates[row][column])
        return new_duty_dates

    @staticmethod
    def get_group_duty_users(duty_users, user_index, group_user_number, group_type=DutyGroupType.SPECIFIED):
        """
        获取自动分组的下一个小组成员
        """
        if len(duty_users) < group_user_number or len(duty_users) <= user_index:
            # 如果配置的用户比自动分组的用户还少，直接返回
            return duty_users, 0
        next_user_index = user_index + group_user_number
        if group_type == DutyGroupType.AUTO:
            users = duty_users[user_index:next_user_index]
        else:
            users = duty_users[user_index]
        if next_user_index >= len(duty_users):
            # 重置user_index 为 0
            next_user_index = user_index = 0
            if group_type == DutyGroupType.AUTO:
                # 如果自动分组，需要补齐人数
                next_user_index = group_user_number - len(users)
                users.extend(duty_users[user_index:next_user_index])
        return users, next_user_index

    @staticmethod
    def get_time_range_work_time(work_date, work_time_list: list):
        """
        获取时间范围的工作时间
        """
        duty_work_time = []
        for time_range in work_time_list:
            [start_time, end_time] = time_range.split("--")
            start_date = end_date = work_date

            if start_time >= end_time:
                # 如果开始时间段 大于或者等于的情况下 结束时间段表示有跨天
                end_date += timedelta(days=1)

            duty_work_time.append(
                dict(
                    start_time="{date} {start_time}".format(
                        date=start_date.strftime("%Y-%m-%d"), start_time=start_time
                    ),
                    end_time="{date} {end_time}".format(date=end_date.strftime("%Y-%m-%d"), end_time=end_time),
                )
            )
        return duty_work_time

    @staticmethod
    def get_datetime_range_work_time(work_date: datetime, work_time_list: list, work_type):
        """
        根据日期时间范围的类型获取工作时间
        """
        duty_work_time = []
        time_range = work_time_list[0]
        [start_time, finished_time] = time_range.split("--")
        begin_time = "00:00"
        end_time = "23:59"
        weekday = day = 0
        begin_date = int(start_time[:2])
        end_day = int(finished_time[:2])
        cross_day = False
        if begin_date == end_day:
            # 如果开始日期==结束日期，表示最后一天存在跨天的场景，为前一天至截止时间
            cross_day = True
            end_day -= 1

        #     计算出当前工作日的时间
        if work_type in RotationType.WEEK_MODE:
            weekday = work_date.isoweekday()
            max_work_day = 7
        else:
            day = work_date.day
            _, max_work_day = calendar.monthrange(work_date.year, work_date.month)

        if end_day == 0:
            # 如果当前结束时间为0，对应前一天为最后一天
            end_date = max_work_day

        if weekday == begin_date or day == begin_date:
            # 当前为第一天的时候，起点时间以配置时间为准
            begin_time = start_time[3:].strip()

        is_last_day = False
        if weekday == end_day or day == end_day:
            # 当前为最后一天的时候，结束时间以配置时间为准
            end_time = finished_time[3:].strip()
            is_last_day = True

        begin_date = end_date = work_date
        if cross_day and is_last_day:
            # 如果开始时间段 大于 结束时间段表示有跨天
            end_date += timedelta(days=1)

        duty_work_time.append(
            dict(
                start_time="{date} {start_time}".format(date=begin_date.strftime("%Y-%m-%d"), start_time=begin_time),
                end_time="{date} {end_time}".format(date=end_date.strftime("%Y-%m-%d"), end_time=end_time),
            )
        )
        return duty_work_time

    @classmethod
    def refresh_duty_rule_from_any_begin_time(
        cls, duty_rule: typing.Dict[str, typing.Any], begin_time: str
    ) -> typing.Optional["DutyRuleManager"]:
        """
        从任何起点刷新 duty_rule 排班

        背景：新创建的轮值快照以「创建/任务时间」作为起始时间进行排班，和规则「生效时间」脱钩
        导致问题：告警组关联轮值在新建、轮值规则变更等场景下，基于「创建/任务时间（begin_time）」重新排班会导致
        思路：交替排班是基于「生效时间」生成的连续排班规则，
             每次新建排班快照，都要预计算生效时间到 begin_time，把 duty_rule_snap 的 index 和 begin_time 刷对

        :param duty_rule:
        :param begin_time:
        :return:
        """
        is_handoff: bool = duty_rule.get("category") == "handoff"
        if begin_time > duty_rule["effective_time"] and is_handoff:
            duty_manager = cls(duty_rule, end_time=begin_time)
            # 排班会刷新 rule_snap 中 duty_time["begin_time"] 和 duty_arrange["last_user_index"]
            duty_manager._last_duty_plans = duty_manager.get_duty_plan()
            return duty_manager
        return None


class GroupDutyRuleManager:
    """
    告警组的轮值规则管理
    """

    def __init__(self, user_group: UserGroup, duty_rules):
        self.user_group = user_group
        self.duty_rules = duty_rules

    def manage_duty_rule_snap(self, task_time):
        """
        :param task_time:
        :return:
        """
        # task_time需要提前定义, 这个可以是七天以后的一个时间

        logger.info("[manage_duty_rule_snap] begin to manage duty snap for current_time(%s)", task_time)

        snaps = DutyRuleSnap.objects.filter(
            duty_rule_id__in=self.user_group.duty_rules, user_group_id=self.user_group.id, enabled=True
        ).order_by("duty_rule_id")
        rule_id_to_snaps = {rule_id: list(snaps) for rule_id, snaps in groupby(snaps, key=attrgetter("duty_rule_id"))}

        rules_for_snap_creation = []
        updated_rule_snaps = []
        expired_snaps = []
        for duty_rule in self.duty_rules:
            if not duty_rule["enabled"]:
                continue

            # 规则为新关联的，创建快照
            rule_id = duty_rule["id"]
            if rule_id not in rule_id_to_snaps:
                rules_for_snap_creation.append(duty_rule)
                continue

            old_snaps: typing.List[DutyRuleSnap] = rule_id_to_snaps[rule_id]

            # 规则没有变化，跳过
            old_hashes = {snap.rule_snap["hash"] for snap in old_snaps}
            if duty_rule["hash"] in old_hashes:
                continue

            # 规则被修改，创建新快照，处理旧快照，更新旧计划
            new_snap_start_time = max(duty_rule["effective_time"], task_time)
            self.update_outdated_plans_by_rule(rule_id, new_snap_start_time)
            rules_for_snap_creation.append(duty_rule)

            for old_snap in old_snaps:
                if old_snap.end_time and old_snap.end_time <= new_snap_start_time:
                    # 如果新快照在旧快照结束后生效，啥也不做
                    pass
                elif old_snap.next_plan_time >= new_snap_start_time:
                    # 否则，如果已排完班，直接删除
                    expired_snaps.append(old_snap.id)
                else:
                    # 否则，修改旧快照的 end_time，让它们负责的时间段不重叠
                    old_snap.end_time = new_snap_start_time
                    updated_rule_snaps.append(old_snap)

        # 禁用规则管理：删除快照、禁用计划
        self.manage_disabled_rules()

        # step1 先创建一波新的snap
        new_group_rule_snaps = []
        for duty_rule in rules_for_snap_creation:
            first_effective_time = max(duty_rule["effective_time"], task_time)
            new_group_rule_snaps.append(
                DutyRuleSnap(
                    enabled=duty_rule["enabled"],
                    next_plan_time=first_effective_time,
                    next_user_index=0,
                    end_time=duty_rule["end_time"],
                    user_group_id=self.user_group.id,
                    first_effective_time=first_effective_time,
                    duty_rule_id=duty_rule["id"],
                    rule_snap=duty_rule,
                )
            )
        if new_group_rule_snaps:
            # Q：为什么不在上方 DutyRuleSnap 初始化时就执行 effective_time ~ task_time 的刷新？
            # A：只有「新建 / 快照变更」场景需要根据 effective_time 刷对顺序，如果 DutyRuleSnap 已存在，排班顺序是有保障的
            # Q：为什么 DutyRuleSnap 存在时，排班顺序有保障？
            # A：DutyRuleManager.get_duty_plan 每次都会迭代 snap 里的 begin_time 和 user_index
            for new_group_rule_snap in new_group_rule_snaps:
                refresh_duty_manager: typing.Optional[
                    DutyRuleManager
                ] = DutyRuleManager.refresh_duty_rule_from_any_begin_time(
                    new_group_rule_snap.rule_snap, begin_time=task_time
                )
                if refresh_duty_manager:
                    # 更新对应的rule_snap的下一次管理计划任务时间
                    new_group_rule_snap.next_plan_time = refresh_duty_manager.end_time
                    new_group_rule_snap.next_user_index = refresh_duty_manager.last_user_index

            DutyRuleSnap.objects.bulk_create(new_group_rule_snaps)

        # step2 然后再来一波更新
        if updated_rule_snaps:
            DutyRuleSnap.objects.bulk_update(updated_rule_snaps, fields=["end_time"])

        # step 3 删除掉过期的
        if expired_snaps:
            DutyRuleSnap.objects.filter(id__in=expired_snaps).delete()

        # 排班的时候提前7天造好数据
        plan_time = time_tools.str2datetime(task_time) + timedelta(days=7)
        for rule_snap in DutyRuleSnap.objects.filter(
            next_plan_time__lte=time_tools.datetime2str(plan_time), user_group_id=self.user_group.id, enabled=True
        ):
            self.manage_duty_plan(rule_snap=rule_snap)

    def update_outdated_plans_by_rule(self, rule_id: int, new_start_time: str) -> None:
        """规则修改后，更新旧计划。"""
        duty_plan_queryset = DutyPlan.objects.filter(
            duty_rule_id=rule_id, user_group_id=self.user_group.id, is_effective=1
        )
        # 在指定日期之前生效的需要取消
        duty_plan_queryset.filter(Q(start_time__gte=new_start_time)).update(is_effective=0)
        # 在开始时间之后还生效的部分，设置结束时间为开始时间
        duty_plan_queryset.filter(
            Q(finished_time__gt=new_start_time) | Q(finished_time=None) | Q(finished_time="")
        ).update(finished_time=new_start_time)

    def manage_disabled_rules(self) -> None:
        """被禁用规则处理。

        只关注当前用户组关联的，解除关联的已在用户组保存接口处理（直接删除快照和计划）
        增：如果规则在关联前已经是禁用状态，则快照和计划都不会创建（下面是空处理）
        改：如果规则在关联后变为禁用状态，规则保存接口已经部分处理（禁用快照和计划）"""

        rule_ids = self.user_group.duty_rules
        disabled_duty_rules = DutyRule.objects.filter(id__in=rule_ids, enabled=False).values_list("id", flat=True)
        if disabled_duty_rules:
            # 如果有有禁用的，需要删除掉
            DutyRuleSnap.objects.filter(duty_rule_id__in=disabled_duty_rules, user_group_id=self.user_group.id).delete()

            # 已经设置的好的排班计划，也需要设置为不生效
            DutyPlan.objects.filter(
                duty_rule_id__in=disabled_duty_rules, user_group_id=self.user_group.id, is_effective=1
            ).update(is_effective=0)

    def manage_duty_plan(self, rule_snap: DutyRuleSnap):
        """
        排班计划生成
        """
        # step 1 当前分组的原计划都设置为False
        if not rule_snap:
            logger.warning("[manage_duty_plan] snap of user group(%s) not existed", self.user_group.id)
            return

        snap_id = rule_snap.id
        logger.info("[manage_duty_plan] begin to manage duty(%s) plan for group(%s)", snap_id, self.user_group.id)

        if not rule_snap.rule_snap["enabled"]:
            # 如果当前规则不生效，则不生成计划
            logger.info("[manage_duty_plan] duty rule (%s) of group(%s) is disabled", snap_id, self.user_group.id)
            return
        # step 2 根据当前的轮值模式生成新的计划
        begin_time = rule_snap.next_plan_time

        duty_manager = DutyRuleManager(rule_snap.rule_snap, begin_time=begin_time, snap_end_time=rule_snap.end_time)

        duty_plans = []
        for duty_plan in duty_manager.get_duty_plan():
            duty_end_times = [f'{work_time["end_time"]}:59' for work_time in duty_plan["work_times"]]
            duty_start_times = [f'{work_time["start_time"]}:00' for work_time in duty_plan["work_times"]]
            # 结束时间获取当前有效的排班时间最后一天即可，不能大于结束时间
            rule_end_time = rule_snap.rule_snap.get("end_time") or time_tools.MAX_DATETIME_STR
            snap_end_time = rule_snap.end_time or time_tools.MAX_DATETIME_STR
            finished_time = min(max(duty_end_times), rule_end_time, snap_end_time)
            # 开始时间取当前时间取当前排班内容里的最小一位，不能小于生效时间
            start_time = max(min(duty_start_times), rule_snap.rule_snap["effective_time"])
            duty_plans.append(
                DutyPlan(
                    start_time=start_time,
                    finished_time=finished_time,
                    user_group_id=self.user_group.id,
                    duty_rule_id=rule_snap.duty_rule_id,
                    users=duty_plan["users"],
                    work_times=duty_plan["work_times"],
                    is_effective=1,
                    order=duty_plan.get("order", 0),
                    user_index=duty_plan.get("user_index", 0),
                )
            )

        # 创建排班计划
        DutyPlan.objects.bulk_create(duty_plans)

        next_plan_time = time_tools.datetime2str(duty_manager.end_time)
        if rule_snap.end_time and next_plan_time >= rule_snap.end_time:
            # 如果已生成负责的所有计划，则删除快照
            rule_snap.delete()
        else:
            # 否则保存下次排班的上下文信息
            rule_snap.next_plan_time = next_plan_time
            rule_snap.next_user_index = duty_manager.last_user_index
            rule_snap.save(update_fields=["next_plan_time", "next_user_index", "rule_snap"])

        logger.info("[manage_duty_plan] finished for user group(%s) snap(%s)", self.user_group.id, snap_id)

    def manage_duty_notice(self):
        """
        排班通知管理
        """
        duty_notice = self.user_group.duty_notice
        plan_notice = duty_notice.get("plan_notice", {})
        personal_notice = duty_notice.get("personal_notice")
        current_time = datetime.now(tz=self.user_group.tz_info)
        if plan_notice:
            self.send_plan_notice(plan_notice, current_time)
        if personal_notice:
            self.send_personal_notice(personal_notice, current_time)

    def send_plan_notice(self, plan_notice, current_time: datetime):
        """
        发送排班计划通知
        """
        if not plan_notice["enabled"]:
            # 如果没有开启直接不用判断
            logger.info("[send_plan_notice] duty plan notice  of group(%s) is disabled", self.user_group.id)
            return

        current_time_str = time_tools.datetime2str(current_time, "%H:%M")
        compare_date = plan_notice["date"]
        compare_time = plan_notice["time"]

        if plan_notice["type"] in RotationType.WEEK_MODE:
            # 如果是按周，则获取今天的日期
            current_date = current_time.isoweekday()
        else:
            _, max_month_day = calendar.monthrange(current_time.year, current_time.month)
            current_date = current_time.day
            if max_month_day < compare_date:
                # 如果一个月的最大一天都小于配置的日期，则以当月最后一天为发送日
                compare_date = max_month_day

        if compare_time > current_time_str or compare_date != current_date:
            # 如果不满足条件，直接返回
            logger.info(
                "[send_plan_notice] finished duty plan notice  of group(%s), time is not matched", self.user_group.id
            )
            return

        end_datetime = current_time + timedelta(days=plan_notice["days"])
        # 接下来开始发通知
        chat_ids = plan_notice["chat_ids"]
        if not chat_ids:
            # 如果没有配置机器人，直接返回
            logger.info(
                "[send_plan_notice] ignore notice because duty plan notice's field(chat_ids) of group(%s) is empty",
                self.user_group.id,
            )
            return

        last_record = DutyPlanSendRecord.objects.filter(user_group_id=self.user_group.id).first()
        if last_record:
            last_send_time = datetime.fromtimestamp(last_record.last_send_time, tz=self.user_group.tz_info)
            if last_send_time.day == current_time.day and last_send_time.strftime("%H:%M") >= compare_time:
                # 如果最后一次记录的时间就在今天，已经发送过并且配置时间未发生过变化（配置时间小于最后一次发送时间），忽略
                # 这里是为了兼容部分用户改了报表的时间，如果是当天的，需要立马发出
                return

        # 过滤的范围：开始时间处于两个时间范围之内的
        # 开始时间小于当前时间，但是结束时间大于当前时间的
        current_time_str = time_tools.datetime2str(current_time)
        end_time_str = time_tools.datetime2str(end_datetime)
        duty_plan_queryset = DutyPlan.objects.filter(user_group_id=self.user_group.id, is_effective=1).filter(
            Q(
                start_time__gte=current_time_str,
                start_time__lte=end_time_str,
            )
            | Q(
                Q(start_time__lte=current_time_str) & Q(finished_time__gte=current_time_str),
            )
        )
        duty_plans = [
            {
                "id": duty_plan.id,
                "users": duty_plan.users,
                "start_time": duty_plan.start_time,
                "finished_time": duty_plan.finished_time,
                "work_times": duty_plan.work_times,
            }
            for duty_plan in duty_plan_queryset
        ]

        if not duty_plans:
            # 没有生成排班计划。这可能算得上是一个告警了
            notice_content = ["\\n> No Data"]
        else:
            notice_content = []
        for duty_plan in duty_plans:
            duty_users = ",".join([f'{user["id"]}({user.get("display_name")})' for user in duty_plan["users"]])
            duty_contents = []
            for work_time in duty_plan["work_times"]:
                content = f"\\n> {work_time['start_time']} -- {work_time['end_time']}  {duty_users}"
                if work_time['start_time'] <= end_time_str and content not in duty_contents:
                    duty_contents.append(content)
            if duty_contents:
                notice_content.extend(duty_contents)
        sender = Sender(
            context={
                "bk_biz_id": self.user_group.bk_biz_id,
                "group_name": self.user_group.name,
                "days": plan_notice["days"],
                "plan_content": "".join(sorted(notice_content)) + "\\n",
                "notice_way": NoticeWay.WX_BOT,
            },
            content_template_path="duty/plan_content.jinja",
        )

        result = sender.send_wxwork_content("markdown", content=sender.content, chat_ids=chat_ids)
        is_succeed = True
        if result.get("errcode") != 0:
            is_succeed = False

        if is_succeed:
            # 凡事有记录的，都会成功
            DutyPlanSendRecord.objects.create(
                user_group_id=self.user_group.id,
                last_send_time=int(current_time.timestamp()),
                notice_config=plan_notice,
            )

        logger.info(
            "[send_plan_notice] send duty plan of group(%s) to chat_ids(%s) finished, result(%s), message(%s)",
            self.user_group.id,
            chat_ids,
            is_succeed,
            result.get("message"),
        )

    def send_personal_notice(self, personal_notice, current_time: datetime):
        """
        发送个人值班通知
        """
        if not personal_notice.get("enabled"):
            # 没有开启通知，直接返回
            logger.info("[send_personal_notice] duty personal notice of group(%s) is disabled", self.user_group.id)
            return
        start_time = current_time + timedelta(hours=personal_notice["hours_ago"])
        end_time = start_time + timedelta(seconds=60)

        # 获取当前时间内一分钟以后的数据
        # 获取指定时间以后的一段内容
        # 可能因为某些原因没有发送个人通知的，需要补齐
        duty_plan_queryset = DutyPlan.objects.filter(user_group_id=self.user_group.id, is_effective=1).filter(
            Q(start_time__gte=time_tools.datetime2str(start_time), start_time__lte=time_tools.datetime2str(end_time))
            | Q(
                last_send_time=0,
                start_time__gte=time_tools.datetime2str(current_time),
                start_time__lt=time_tools.datetime2str(start_time),
            )
        )
        if personal_notice.get("duty_rules"):
            # 指定了轮值规则，则发送对应轮值规则的内容， 没有的话，默认全部
            duty_plan_queryset = duty_plan_queryset.filter(duty_rule_id__in=personal_notice["duty_rules"])
        duty_plans = [
            {
                "id": duty_plan.id,
                "users": duty_plan.users,
                "start_time": duty_plan.start_time,
                "finished_time": duty_plan.finished_time,
                "work_times": duty_plan.work_times,
            }
            for duty_plan in duty_plan_queryset
        ]
        if not duty_plans:
            # 没有排班计划，直接返回
            logger.info(
                "[send_personal_notice] ignore duty personal notice of group(%s)  because of empty duty plan",
                self.user_group.id,
            )
            return

        # 更新一下最近范围内的发送时间
        duty_plan_ids = [d["id"] for d in duty_plans]

        # 这里的id不会很多，所以用in 问题不大
        DutyPlan.objects.filter(id__in=duty_plan_ids).update(last_send_time=int(end_time.timestamp()))

        user_duty_plans = defaultdict(list)
        for duty_plan in duty_plans:
            duty_users = ",".join([f'{user["id"]}({user.get("display_name")})' for user in duty_plan["users"]])
            duty_contents = []
            for work_time in duty_plan["work_times"]:
                duty_contents.append(f"{work_time['start_time']} -- {work_time['end_time']}  {duty_users}")
            for user in duty_plan["users"]:
                if user["type"] == "group":
                    continue
                user_duty_plans[user["id"]].extend(duty_contents)
        failed_list = []
        succeed_list = []
        if len(duty_plans) == 1:
            # 表示所有人的通知内容都是一样的
            logger.info("[send_personal_notice] send personal duty email of group(%s) to all users", self.user_group.id)
            duty_users = list(user_duty_plans.keys())
            send_content = "\n".join(sorted(list(user_duty_plans.values())[0]))
            sender = Sender(
                context={
                    "bk_biz_id": self.user_group.bk_biz_id,
                    "group_name": self.user_group.name,
                    "start_time": min([d["start_time"] for d in duty_plans]),
                    "plan_content": send_content,
                    "notice_way": NoticeWay.MAIL,
                },
                title_template_path="duty/mail_title.jinja",
                content_template_path="duty/personal_content.jinja",
            )
            result = sender.send_mail(notice_receivers=duty_users)
            for receiver in result:
                if not result[receiver]["result"]:
                    failed_list.append(result[receiver])
                else:
                    succeed_list.append(result[receiver])
            logger.info(
                "[send_personal_notice] send personal duty email of group(%s) "
                "finished:succeed_list(%s), failed_list(%s)",
                self.user_group.id,
                succeed_list,
                failed_list,
            )
            return

        logger.info(
            "[send_personal_notice] send personal duty email of group(%s) separately because users got different plans",
            self.user_group.id,
        )
        for user, duty_plan in user_duty_plans.items():
            send_content = "\n".join(sorted(duty_plan))
            sender = Sender(
                context={
                    "bk_biz_id": self.user_group.bk_biz_id,
                    "group_name": self.user_group.name,
                    "start_time": min([d["start_time"] for d in duty_plans]),
                    "plan_content": send_content,
                    "notice_way": NoticeWay.MAIL,
                },
                title_template_path="duty/mail_title.jinja",
                content_template_path="duty/personal_content.jinja",
            )
            result = sender.send_mail(notice_receivers=[user])
            for receiver in result:
                if not result[receiver]["result"]:
                    failed_list.append(result[receiver])
                else:
                    succeed_list.append(result[receiver])

        logger.info(
            "[send_personal_notice] send personal duty email of group(%s) finished:succeed_list(%s), failed_list(%s)",
            self.user_group.id,
            succeed_list,
            failed_list,
        )


def end_time_to_datetime(end_time: typing.Optional[str]) -> datetime:
    """返回 datetime 类型的结束时间。"""
    if not end_time:
        return datetime.max
    return time_tools.str2datetime(end_time)
