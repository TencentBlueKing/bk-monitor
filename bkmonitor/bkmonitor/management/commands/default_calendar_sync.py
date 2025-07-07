"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Generator
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

import pytz
import requests
from django.core.management.base import BaseCommand

from calendars.models import CalendarItemModel, CalendarModel
from constants.common import DEFAULT_TENANT_ID


class DateType(Enum):
    """
    日期类型
    """

    WORKDAY = "workday"
    HOLIDAY = "holiday"


class CalendarManager:
    """
        1. 爬取数据
        2. 日历有节假日和工作日
            设置节假日的开始和结束时间，因为有些节假日只有一天，有些节假日包含周末
            判断逻辑：
                遍历节假日数据
                datetime_interval

        3. 遍历所有的日子: [1月1 -- 12月31]

        注意:
        （一）元旦，放假1天（1月1日）；
    （二）春节，放假4天（农历除夕、正月初一至初三）；
    （三）清明节，放假1天（农历清明当日）；
    （四）劳动节，放假2天（5月1日、2日）；
    （五）端午节，放假1天（农历端午当日）；
    （六）中秋节，放假1天（农历中秋当日）；
    （七）国庆节，放假3天（10月1日至3日）。
    12 月份的日期可能会被下一年的文件影响，因此应检查两个文件。

    说白了其实就分为工作日和非工作日
    然后还有一个内置的双休
    全天-双休-节假日=工作日
    """

    timezone = pytz.timezone("Asia/Shanghai")

    def get_holiday_data(self, year: int) -> list[dict[str, Any]]:
        """
        获取节假日数据
        {
            "days": [
                {
                    "name": "元旦",
                    "date": "2025-01-01",
                    "isOffDay": true
                },
                {
                    "name": "春节",
                    "date": "2025-01-26",
                    "isOffDay": false
                },
                {
                    "name": "春节",
                    "date": "2025-01-28",
                    "isOffDay": true
                }
            ]
        }

        数据来源: https://github.com/NateScarlet/holiday-cn
        """
        url = f"https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"
        response = requests.get(url)
        if response.status_code == 200:
            content = response.json()
            return content["days"]
        raise ValueError(f"获取节假日数据失败，状态码: {response.status_code}, 错误信息: {response.text}")

    @staticmethod
    def is_weekend(date: date) -> bool:
        """
        判断是否为周末
        """
        return date.weekday() + 1 in [6, 7]

    @staticmethod
    def generate_year_days(year: int) -> Generator[date, None, None]:
        """
        生成一年中的所有日期
        """
        start_date = date(year, 1, 1)
        end_date = date(year + 1, 1, 1)

        current_date = start_date
        while current_date < end_date:
            yield current_date
            current_date += timedelta(days=1)

    def get_calendar_ranges(self, year: int) -> list[tuple[date, date, str, DateType]]:
        """
        获取节假日与工作日的时间分段
        :param year: 年份
        :return: 时间分段列表，包含开始日期、结束日期、范围名称、日期类型
        [
            (date(2025, 1, 1), date(2025, 1, 1), "元旦", DateType.HOLIDAY),
            (date(2025, 1, 2), date(2025, 1, 5), "元旦(补班)", DateType.WORKDAY),
            (date(2025, 1, 6), date(2025, 1, 6), "周末", DateType.HOLIDAY),
            (date(2025, 1, 7), date(2025, 1, 7), "工作日", DateType.WORKDAY),
            ...
        ]
        """

        # 获取节假日数据
        holiday_data = self.get_holiday_data(year)
        holiday_map: dict[str, dict[str, Any]] = {}
        for holiday in holiday_data:
            holiday_map[holiday["date"]] = holiday

        # 遍历一年
        calendar_ranges: list[tuple[date, date, str, DateType]] = []
        range_name: str = ""
        start_date: date | None = None
        date_type: DateType = DateType.HOLIDAY
        for today in self.generate_year_days(year):
            # 判断是否为节假日/补办/周末/工作日
            today_str = today.strftime("%Y-%m-%d")
            if today_str in holiday_map:
                # 节假日信息，包含是否为补班
                if not holiday_map[today_str]["isOffDay"]:
                    today_range_name = holiday_map[today_str]["name"] + "(补班)"
                    today_date_type = DateType.WORKDAY
                else:
                    today_range_name = holiday_map[today_str]["name"]
                    today_date_type = DateType.HOLIDAY
            elif self.is_weekend(today):
                today_range_name = "周末"
                today_date_type = DateType.HOLIDAY
            else:
                today_range_name = "工作日"
                today_date_type = DateType.WORKDAY

            # 如果是第一天，则设置开始日期和范围名称
            if start_date is None:
                start_date = today
                range_name = today_range_name
                date_type = today_date_type
                continue

            # 如果是最后一天，则直接记录
            if today == date(year, 12, 31):
                calendar_ranges.append((start_date, today, range_name, date_type))
                break

            # 如果当前日期与上一个日期相同，则不记录
            if range_name == today_range_name:
                continue

            # 如果当前日期与上一个日期不同，则进行分段记录，并重新设置开始日期和范围名称
            yesterday = today - timedelta(days=1)
            calendar_ranges.append((start_date, yesterday, range_name, date_type))
            start_date = today
            range_name = today_range_name
            date_type = today_date_type
        return calendar_ranges

    def create_or_update_calendar(self, bk_tenant_id: str, calendar_name: str) -> int:
        """
        创建或更新日历
        """
        calendar = CalendarModel.objects.filter(name=calendar_name, bk_tenant_id=bk_tenant_id).first()
        if calendar:
            return calendar.pk
        else:
            calendar = CalendarModel.objects.create(
                name=calendar_name,
                classify="default",
                bk_tenant_id=bk_tenant_id,
            )
            return calendar.pk

    def create_calendar_item(
        self,
        bk_tenant_id: str,
        year: int,
        holiday_calendar_name: str,
        working_calendar_name: str,
    ):
        # 创建日历
        holiday_calendar_id = self.create_or_update_calendar(
            bk_tenant_id=bk_tenant_id, calendar_name=holiday_calendar_name
        )
        working_calendar_id = self.create_or_update_calendar(
            bk_tenant_id=bk_tenant_id, calendar_name=working_calendar_name
        )

        # 清理重复的日历事项
        CalendarItemModel.objects.filter(
            calendar_id__in=[holiday_calendar_id, working_calendar_id],
            start_time__gte=self.timezone.localize(
                datetime.combine(
                    date=date(year, 1, 1),
                    time=datetime.min.time(),
                )
            ).timestamp(),
            end_time__lte=self.timezone.localize(
                datetime.combine(
                    date=date(year, 12, 31),
                    time=datetime.max.time(),
                )
            ).timestamp(),
            bk_tenant_id=bk_tenant_id,
        ).delete()

        # 获取节假日和工作日的时间分段
        calendar_ranges = self.get_calendar_ranges(year)

        # 遍历时间分段，生成日历事项
        calendar_items: list[CalendarItemModel] = []
        for start_date, end_date, range_name, date_type in calendar_ranges:
            calendar_items.append(
                CalendarItemModel(
                    name=range_name,
                    start_time=self.timezone.localize(
                        datetime.combine(
                            date=start_date,
                            time=datetime.min.time(),
                        )
                    ).timestamp(),
                    end_time=self.timezone.localize(
                        datetime.combine(
                            date=end_date,
                            time=datetime.max.time(),
                        )
                    ).timestamp(),
                    repeat={},
                    calendar_id=holiday_calendar_id if date_type == DateType.HOLIDAY else working_calendar_id,
                    bk_tenant_id=bk_tenant_id,
                )
            )

        # 批量创建日历事项
        CalendarItemModel.objects.bulk_create(calendar_items)

    def list_system_calendars(self, bk_tenant_id: str):
        system_calendars = (
            CalendarModel.objects.filter(
                classify="default",
                bk_tenant_id=bk_tenant_id,
            )
            .order_by("id")
            .values_list("id", "name")
        )
        for cal_id, cal_name in system_calendars:
            print(f"ID: {cal_id} - 名称: {cal_name}")


class Command(BaseCommand):
    """
    日历同步工具

    使用频率： 每年一次
    目的: 维护内置两个日历事项: 法定节假日和工作日

    使用方法:
    - python manage.py default_calendar_sync list
    - python manage.py default_calendar_sync create_calendar_item --holiday_calendar "节假日(不告警)" --working_calendar "工作日(不告警)" --year 2025
    """

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")
        calendar_manager = CalendarManager()
        match subcommand:
            case "list":
                calendar_manager.list_system_calendars(bk_tenant_id=options["bk_tenant_id"])
            case "create_calendar_item":
                calendar_manager.create_calendar_item(
                    bk_tenant_id=options["bk_tenant_id"],
                    year=options["year"],
                    holiday_calendar_name=options["holiday_calendar"],
                    working_calendar_name=options["working_calendar"],
                )
            case _:
                raise ValueError(f"无效的子命令: {subcommand}")

    def add_arguments(self, parser):
        # 主命令参数
        subparsers = parser.add_subparsers(dest="subcommand", required=True)

        # 添加日历item
        create_calendar_item_parser = subparsers.add_parser("create_calendar_item", help="创建日历事项")
        create_calendar_item_parser.add_argument("--bk_tenant_id", type=str, help="租户ID", default=DEFAULT_TENANT_ID)
        create_calendar_item_parser.add_argument("--holiday_calendar", type=str, help="节假日日历名称", required=True)
        create_calendar_item_parser.add_argument("--working_calendar", type=str, help="工作日日历名称", required=True)
        create_calendar_item_parser.add_argument("--year", type=int, help="年份", required=True)

        # 查看日历
        subparsers.add_parser("list", help="查看内置日历")
