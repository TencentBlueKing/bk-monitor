"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import date, datetime, timedelta

import requests
from django.core.management.base import BaseCommand
from pydantic import BaseModel

from calendars.models import DEFAULT_TENANT_ID, CalendarItemModel, CalendarModel


class CalendarItemCreate(BaseModel):
    name: str
    start_time: datetime
    end_time: datetime
    repeat: dict = {}
    calendar_id: int


def get_next_year() -> int:
    """
    获取下一个年份
    """
    return datetime.now().year + 1


def generate_year_days(year: int) -> list[str]:
    start_date = date(year, 1, 1)
    end_date = date(year + 1, 1, 1)

    dates = []
    current_date = start_date
    while current_date < end_date:
        dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    return dates


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

    def get_holiday_data(self, year: int) -> list[dict]:
        """
        获取节假日数据

        数据来源: https://github.com/NateScarlet/holiday-cn
        """
        url = f"https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"
        response = requests.get(url)

        if response.status_code == 200:
            content = response.json()
            return content["days"]

        return []

    def generate_calendar_items(self, days: list[CalendarItemCreate]) -> list[CalendarItemModel]:
        items = []

        for day in days:
            start_time = int(day.start_time.timestamp())
            end_time = int(day.end_time.replace(hour=23, minute=59, second=59, microsecond=0).timestamp())

            items.append(
                CalendarItemModel(
                    **{
                        "bk_tenant_id": DEFAULT_TENANT_ID,
                        "name": day.name,
                        "calendar_id": day.calendar_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "repeat": day.repeat,
                    }
                )
            )

        return items

    def get_days(
        self,
        holiday_data: list[dict],
        holiday_calendar_id: int,
        working_calendar_id: int,
    ) -> list[CalendarItemModel]:
        calendar_item_create_list = []
        for day_item in holiday_data:
            day_name = day_item["name"]
            day_date = datetime.strptime(day_item["date"], "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            is_off_day: bool = day_item["isOffDay"]

            day_name = day_name if is_off_day else "调休"
            calendar_id = holiday_calendar_id if is_off_day else working_calendar_id
            calendar_item_create_list.append(
                CalendarItemCreate(
                    name=day_name,
                    start_time=day_date,
                    end_time=day_date.replace(hour=23, minute=59, second=59),
                    repeat={},
                    calendar_id=calendar_id,
                )
            )

        calendar_items: list[CalendarItemModel] = self.generate_calendar_items(calendar_item_create_list)

        return calendar_items

    def create_calendar_item(self, year: int, holiday_calendar_id: int, working_calendar_id: int):
        holiday_data = self.get_holiday_data(year)

        # 获取节假日和周末调休的日期
        holiday_items: list[CalendarItemModel] = self.get_days(holiday_data, holiday_calendar_id, working_calendar_id)
        holiday_map = {}
        for day in holiday_items:
            if day.start_time is None:
                print(day)
            start_date = datetime.fromtimestamp(day.start_time).strftime("%Y-%m-%d")
            holiday_map[start_date] = day

        # 获取剩余工作日
        working_items: list[CalendarItemModel] = []
        working_items_create: list[CalendarItemCreate] = []
        # 计算方式: 常规工作日 = 全年 - (节假日 + 调休日) - 周末
        # 所有工作日 = 常规工作日 + 调休日
        for current_date in generate_year_days(year):
            # 跳过节假日和因节假日调休的周末
            if holiday_map.get(current_date):
                continue

            current_date = datetime.strptime(current_date, "%Y-%m-%d")

            # 排除周末
            if current_date.weekday() + 1 in [6, 7]:
                continue

            working_items_create.append(
                CalendarItemCreate(
                    name="工作日", start_time=current_date, end_time=current_date, calendar_id=working_calendar_id
                )
            )

        working_items = self.generate_calendar_items(working_items_create)

        # 批量创建
        calendar_items = working_items + holiday_items

        # CalendarItemModel.objects.bulk_create(calendar_items)
        for item in calendar_items:
            item.save()

        print("添加完成")
        print(f"total len:{len(calendar_items)}")
        print(f"工作日 len:{len(working_items)}")
        print(f"节假日 len:{len([i for i in holiday_items if i.name != '调休'])}")
        print(f"调休日 len:{len([i for i in holiday_items if i.name == '调休'])}")

    def list_system_calendars(self):
        system_calendars = (
            CalendarModel.objects.filter(
                classify="default",
                bk_tenant_id=DEFAULT_TENANT_ID,
            )
            .order_by("id")
            .values_list("id", "name")
        )
        for cal_id, cal_name in system_calendars:
            print(f"ID: {cal_id} - 名称: {cal_name}")

    def create_calendar(self, name, light_color, deep_color, classify):
        """添加日历"""
        # 校验字段
        # required_fields = ["name", "light_color", "deep_color"]
        # if not all(options[field] for field in required_fields):
        #     missing = [field for field in required_fields if not options[field]]
        #     self.stdout.write(self.style.ERROR(f"缺少必填参数: {', '.join(missing)}"))
        #     return

        # 校验是否存在同名
        if self._cheack_calendar_exist(name=name):
            return

        # 添加日历
        calendar = CalendarModel.objects.create(
            name=name,
            light_color=f"#{light_color}",
            deep_color=f"#{deep_color}",
            classify=classify,
            bk_tenant_id=DEFAULT_TENANT_ID,
        )

        return calendar.to_json()

    def _cheack_calendar_exist(self, name: str = None, id: int = None) -> bool:
        if name:
            calendar = CalendarModel.objects.filter(name=name).first()
        elif id:
            calendar = CalendarModel.objects.filter(id=id).first()

        if calendar:
            print(f"日历保存失败，日历({calendar.name} -- ID： {calendar.id})已存在")
            return True

        return False


class Command(BaseCommand):
    """
    日历同步工具

    使用频率： 每年一次
    目的: 维护内置两个日历事项: 法定节假日和工作日

    使用方法:
    - 查看日历列表 `python manage.py default_calendar_sync list`
    - 添加日历 `python manage.py default_calendar_sync create_calendar --name test2 --deep_color 3A84FF  --light_color E1ECFF`
    - 添加日历事项 `python manage.py default_calendar_sync create_calendar_items`
    """

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")
        calendar_manager = CalendarManager()
        match subcommand:
            case "list":
                calendar_manager.list_system_calendars()
            case "create_calendar":
                name = options["name"]
                light_color = options["light_color"]
                deep_color = options["deep_color"]
                classify = options["classify"]
                calendar_manager.create_calendar(name, light_color, deep_color, classify)
                print("添加成功")
                calendar_manager.list_system_calendars()
            case "create_calendar_item":
                year = options["year"]
                holiday_calendar_id = options["holiday_calendar_id"]
                working_calendar_id = options["working_calendar_id"]
                calendar_manager.create_calendar_item(year, holiday_calendar_id, working_calendar_id)
            # case _:
            #     pass

    def add_arguments(self, parser):
        # 主命令参数
        subparsers = parser.add_subparsers(dest="subcommand", required=True)

        # 添加日历item
        create_calendar_item_parser = subparsers.add_parser("create_calendar_item", help="创建日历事项")
        create_calendar_item_parser.add_argument("--holiday_calendar_id", type=int, help="节假日ID", required=True)
        create_calendar_item_parser.add_argument("--working_calendar_id", type=int, help="工作日ID", required=True)
        create_calendar_item_parser.add_argument(
            "--year", type=int, help="年份", required=True, default=get_next_year()
        )

        # 查看日历
        subparsers.add_parser("list", help="查看日历")

        # 创建日历
        create_calendar_parser = subparsers.add_parser("create_calendar", help="创建日历")
        create_calendar_parser.add_argument("--name", type=str, help="日历名称", required=True)
        create_calendar_parser.add_argument("--light_color", type=str, help="日历浅色底色 e.g.: E1ECFF", required=True)
        create_calendar_parser.add_argument("--deep_color", type=str, help="日历深色底色 e.g.: 3A84FF", required=True)
        create_calendar_parser.add_argument(
            "--classify", type=str, help="日历分类", default="default", required=False, choices=["default", "custom"]
        )
