"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from datetime import datetime

import pytest

from calendars.models import CalendarItemModel
from calendars.resources import (
    DeleteItemResource,
    EditItemResource,
    ItemDetailResource,
    ItemListResource,
    SaveCalendarResource,
    SaveItemResource,
)
from core.drf_resource.exceptions import CustomException

logger = logging.getLogger("calendars")


def delete_items(fun):
    def warp(self, mocker):
        fun(self, mocker)
        CalendarItemModel.objects.all().delete()

    return warp


@pytest.mark.django_db(databases="__all__")
class TestItem:
    """
    测试日历事项
    1。 添加事项：
        1-1 添加单天的事项
        1-2 测试重复事项的范围限定（day的every为[]，week的every在0-6，month的every在1-31，year的every在1-31）
    2。 编辑事项：
        2-1 编辑全部事项
        2-2 编辑当前事项
        2-3 编辑当前及未来全部事项
    3。 删除事项：
        3-1 删除全部事项
        3-2 删除当前事项
        3-3 删除当前及未来全部事项
    """

    def test_add_item(self, mocker):
        # 为事项先添加一个日历
        calendar_id = SaveCalendarResource().request(name="日历1", deep_color="#111111", light_color="#111111")["id"]
        request_data = {
            "name": "事项1",
            "calendar_id": calendar_id,
            "start_time": 1646870400,
            "end_time": 1646884800,
            "time_zone": "Asia/Shanghai",
        }
        logger.info("开始添加测试添加日历事项")
        # 1。 添加单天事项
        item_1 = SaveItemResource().request(**request_data)
        item_1 = CalendarItemModel.objects.get(id=item_1["id"])
        assert item_1.repeat == {}
        # 2。 每天
        request_data["repeat"] = {"freq": "day", "interval": 1, "until": 1647359999, "every": [], "exclude_date": []}
        item_2 = SaveItemResource().request(**request_data)
        item_2 = CalendarItemModel.objects.get(id=item_2["id"])
        assert item_2.repeat["freq"] == "day"
        assert item_2.repeat["interval"] == 1
        assert item_2.repeat["until"] == int(datetime(2022, 3, 15, 23, 59, 59).timestamp())
        # 3。每周不停止
        request_data.update({"repeat": {"freq": "week", "interval": 1, "until": None, "every": [], "exclude_date": []}})
        item_3 = SaveItemResource().request(**request_data)
        item_3 = CalendarItemModel.objects.get(id=item_3["id"])
        assert item_3.repeat["freq"] == "week"
        assert item_3.repeat["interval"] == 1
        assert not item_3.repeat["until"]
        # 4。 每两个月,永不停止
        request_data.update(
            {"repeat": {"freq": "month", "interval": 2, "until": None, "every": [], "exclude_date": []}}
        )
        item_4 = SaveItemResource().request(**request_data)
        item_4 = CalendarItemModel.objects.get(id=item_4["id"])
        assert item_4.repeat["freq"] == "month"
        assert item_4.repeat["interval"] == 2
        assert not item_4.repeat["until"]
        # 5。 每两周，每周3，4，5重复, 3.15停止，排除3.11日期
        request_data.update(
            {
                "repeat": {
                    "freq": "week",
                    "interval": 2,
                    "until": 1647359999,
                    "every": [3, 4, 5],
                    "exclude_date": [1646928000],
                }
            }
        )
        item_5 = SaveItemResource().request(**request_data)
        item_5 = CalendarItemModel.objects.get(id=item_5["id"])
        assert item_5.repeat["freq"] == "week"
        assert item_5.repeat["interval"] == 2
        assert item_5.repeat["until"] == int(datetime(2022, 3, 15, 23, 59, 59).timestamp())
        assert item_5.repeat["every"] == [3, 4, 5]
        assert item_5.repeat["exclude_date"] == [int(datetime(2022, 3, 11).timestamp())]
        # 6。 重复区间出错
        request_data.update(
            {"repeat": {"freq": "day", "interval": 2, "until": None, "every": [1, 2], "exclude_date": []}}
        )
        with pytest.raises(CustomException) as e:
            SaveItemResource().request(**request_data)
        exec_msg = e.value.args[0]
        assert exec_msg == "Resource[SaveItem] 请求参数格式错误：(重复事项配置信息) 当重复频率为day时，重复区间必须为[]"
        request_data.update(
            {"repeat": {"freq": "week", "interval": 1, "until": None, "every": [8, 9], "exclude_date": []}}
        )
        with pytest.raises(CustomException) as e:
            SaveItemResource().request(**request_data)
        exec_msg = e.value.args[0]
        assert (
            exec_msg
            == "Resource[SaveItem] 请求参数格式错误：(重复事项配置信息) 当重复频率为week时，重复区间里的值应该在0-6之间"
        )

        logger.info("添加事项测试完成")

    def test_edit_item(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历2", deep_color="#111111", light_color="#111111")["id"]
        # 添加一个新的事项从3-10 8:00到3-10 12:00结束的一个每天不结束的事项
        item_id = SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1646870400,
            end_time=1646884800,
            time_zone="Asia/Shanghai",
            repeat={"freq": "day", "interval": 1, "until": None, "every": [], "exclude_date": []},
        )["id"]
        logger.info("开始测试编辑事项")
        # 1. 修改全部事项
        item_1 = EditItemResource().request(id=item_id, name="测试编辑事项_1", change_type=0)
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 1
        assert item_1["name"] == "测试编辑事项_1"

        # 2. 编辑当前事项
        item_2 = EditItemResource().request(
            id=item_id, name="测试编辑事项_2", start_time=1647043200, end_time=1647050400, change_type=1
        )
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 2
        assert item_2["parent_id"] == item_id
        assert item_2["start_time"] == int(datetime(2022, 3, 12, 8).timestamp())
        assert item_2["end_time"] == int(datetime(2022, 3, 12, 10).timestamp())
        assert CalendarItemModel.objects.get(id=item_id).repeat["exclude_date"] == [
            int(datetime(2022, 3, 12).timestamp())
        ]

        # 3。编辑当前及未来所有
        item_3 = EditItemResource().request(
            id=item_id, name="测试编辑事项_3", start_time=1646956800, end_time=1646964000, change_type=2
        )
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 3
        assert not CalendarItemModel.objects.get(id=item_2["id"]).parent_id
        assert item_3["start_time"] == int(datetime(2022, 3, 11, 8).timestamp())
        assert item_3["end_time"] == int(datetime(2022, 3, 11, 10).timestamp())
        assert CalendarItemModel.objects.get(id=item_id).repeat["exclude_date"] == [
            int(datetime(2022, 3, 11).timestamp())
        ]
        assert CalendarItemModel.objects.get(id=item_id).repeat["until"] == int(
            datetime(2022, 3, 11, 23, 59, 59).timestamp()
        )

        # 4。处理一个复杂的事项
        item_id = SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1645923600,
            end_time=1646015400,
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "week",
                "interval": 1,
                "until": None,
                "every": [2, 4, 6],
                "exclude_date": [1647273600, 1647446400, 1646841600, 1648483200],
            },
        )["id"]
        EditItemResource().request(
            id=item_id, name="测试编辑事项_3", start_time=1646701200, end_time=1646793000, change_type=2
        )
        item = CalendarItemModel.objects.get(id=item_id)
        assert item.repeat["until"] == int(datetime(2022, 3, 8, 23, 59, 59).timestamp())
        assert int(datetime(2022, 3, 8).timestamp()) in item.repeat["exclude_date"]
        assert not CalendarItemModel.objects.filter(parent_id=item_id)

    def test_delete_item(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历3", deep_color="#111111", light_color="#111111")["id"]
        # 主事项
        item_id = SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1645923600,
            end_time=1646015400,
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "week",
                "interval": 1,
                "until": None,
                "every": [2, 4, 6],
                "exclude_date": [1647273600, 1647446400, 1646841600, 1648483200],  # 3.15   3.17   3.10  3.29
            },
        )["id"]

        # 子事项
        sun_item = EditItemResource().request(
            id=item_id,
            name="测试编辑事项_2",
            start_time=1648080000,
            end_time=1648175400,
            change_type=1,  # 3.24
        )

        # 1。删除当前事项
        DeleteItemResource().request(id=item_id, start_time=1647043200, end_time=1647138600, delete_type=1)  # 3.12
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 2
        assert CalendarItemModel.objects.get(id=item_id).repeat["exclude_date"] == sorted(
            [
                1646841600,
                1647273600,
                1647446400,
                1648483200,
                int(datetime(2022, 3, 12).timestamp()),
                int(datetime(2022, 3, 24).timestamp()),
            ]
        )

        # 2。 删除当前及未来所有事项
        DeleteItemResource().request(id=item_id, start_time=1647907200, end_time=1648002600, delete_type=2)  # 3.22
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 2
        assert CalendarItemModel.objects.get(id=item_id).repeat["until"] == int(
            datetime(2022, 3, 22, 23, 59, 59).timestamp()
        )
        assert CalendarItemModel.objects.get(id=item_id).repeat["exclude_date"] == sorted(
            [
                1646841600,
                1647273600,
                1647446400,
                int(datetime(2022, 3, 22).timestamp()),
                int(datetime(2022, 3, 12).timestamp()),
            ]
        )

        # 3。 删除全部（错误情况）
        with pytest.raises(ValueError) as e:
            DeleteItemResource().request(id=item_id, start_time=1647907200, end_time=1648002600, delete_type=0)
        exec_msg = e.value.args[0]
        assert exec_msg == "当前事项不是第一项，无法删除全部"
        # 4。 删除全部正确情况
        DeleteItemResource().request(id=item_id, start_time=1645923600, end_time=1646015400, delete_type=0)
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id).count() == 1
        assert CalendarItemModel.objects.filter(calendar_id=calendar_id)[0].id == sun_item["id"]

    def test_item_detail(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历4", deep_color="#111111", light_color="#111111")["id"]
        # 主事项1
        item_1_id = SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1645923600,  # 2.27, 9
            end_time=1646015400,  # 2.28 10.30
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "week",
                "interval": 1,
                "until": 1649260799,  # 4.5
                "every": [2, 4, 6],
                "exclude_date": [1647273600],  # 3.15
            },
        )["id"]
        # 主事项2
        SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1647907200,  # 3.22 8
            end_time=1647936000,  # 3.22 16
            time_zone="Asia/Shanghai",
            repeat={},
        )

        all_items_of_day = ItemDetailResource().request(
            calendar_ids=[calendar_id], time=1647924000, start_time=1646928000
        )  # 3.22 12.40 开始时间3.11
        assert len(all_items_of_day) == 2

        #  修改主事项，将其频率改为两周一次
        EditItemResource().request(
            id=item_1_id,
            repeat={
                "freq": "week",
                "interval": 2,
                "until": 1649260799,  # 4.5
                "every": [2, 4, 6],
                "exclude_date": [1647273600],  # 3.15
            },
            change_type=0,
        )
        all_items_of_day = ItemDetailResource().request(
            calendar_ids=[calendar_id], time=1647924000, start_time=1646928000
        )  # 3.22 12.40
        assert len(all_items_of_day) == 1

    def test_item_list_week(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历5", deep_color="#111111", light_color="#111111")["id"]
        SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1645923600,  # 2.27 9
            end_time=1646015400,  # 2.28 10.30
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "week",
                "interval": 1,
                "until": 1649260799,  # 4.5
                "every": [2, 4, 6],
                "exclude_date": [1647273600, 1647446400, 1646841600],
            },
        )
        all_item_list = ItemListResource().request(
            calendar_ids=[calendar_id],
            start_time=1645891200,
            end_time=1649174400,  # 2.27
        )  # 4.6
        assert len(all_item_list) == 13
        item_1 = all_item_list[0]["list"][0]
        assert item_1["start_time"] == datetime(2022, 3, 1, 9).timestamp()
        assert item_1["end_time"] == datetime(2022, 3, 2, 10, 30).timestamp()

    def test_item_list_month(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历6", deep_color="#111111", light_color="#111111")["id"]
        SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1641690000,  # 1,9 9
            end_time=1641693600,  # 1,9 10
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "month",
                "interval": 1,
                "until": 1648742399,  # 3.31
                "every": [9, 10, 11, 12, 13, 15, 18, 25, 31],
                "exclude_date": [],
            },
        )
        all_item_list = ItemListResource().request(
            calendar_ids=[calendar_id],
            start_time=1642089600,
            end_time=1648828800,  # 1.14
        )  # 4.2
        assert len(all_item_list) == 21

    def test_item_list_year(self, mocker):
        calendar_id = SaveCalendarResource().request(name="日历7", deep_color="#111111", light_color="#111111")["id"]
        item_id = SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1641690000,  # 2022,1,9 9
            end_time=1641693600,  # 2022,1,9 10
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "year",
                "interval": 1,
                "until": 1772207999,  # 2026,2,27
                "every": [1, 2, 3, 4, 5, 6, 7],
                "exclude_date": [],
            },
        )["id"]
        all_item_list = ItemListResource().request(
            calendar_ids=[calendar_id], start_time=1640966400, end_time=1788537600
        )
        assert len(all_item_list) == 30

        EditItemResource().request(
            id=item_id,
            start_time=1667178000,  # 2022,10,31 9
            end_time=1667268000,  # 2022,11,1 10
            repeat={
                "freq": "year",
                "interval": 2,
                "until": 1820419199,  # 2027,9,8
                "every": [1, 2, 3, 4, 5, 6, 7],
                "exclude_date": [],
            },
            change_type=0,
        )

        all_item_list = ItemListResource().request(
            calendar_ids=[calendar_id],
            start_time=1641347400,
            end_time=1812160200,  # 2022,1,5 9.50
        )  # 2027,6,5 9.50
        assert len(all_item_list) == 8

    def test_item_year_12_to1(self, mocker):
        """
        测试跨年的按月循环（12月份是否正确）
        """
        calendar_id = SaveCalendarResource().request(name="日历8", deep_color="#111111", light_color="#111111")["id"]
        SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1664069400,  # 2022,9,25 9,30
            end_time=1664073000,  # 2022,9,25 10,30
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "month",
                "interval": 1,
                "until": 1672761600,  # 2023,1,4
                "every": [25, 26, 27, 28, 29, 30],
                "exclude_date": [],
            },
        )
        all_item_list = ItemListResource().request(
            calendar_ids=[calendar_id], start_time=1664035200, end_time=1672502400
        )
        assert len(all_item_list) == 24

    def test_item_detail_now(self, mocker):
        """
        测试事项详情
        :param mocker:
        :return:
        """
        calendar_id = SaveCalendarResource().request(name="日历9", deep_color="#111111", light_color="#111111")["id"]
        SaveItemResource().request(
            name="测试编辑事项",
            calendar_id=calendar_id,
            start_time=1640995200,  # 2022,1,1 8:00
            end_time=1641002400,  # 2022,1,1 10:00
            time_zone="Asia/Shanghai",
            repeat={
                "freq": "day",
                "interval": 1,
                "until": 1643644800,  # 2022 2,1
                "every": [],
                "exclude_date": [],
            },
        )
        # 测试查找的开始时间大于日日历开始时间和小于结束时间
        all_items = ItemDetailResource().request(
            calendar_ids=[calendar_id],
            time=1641776400,
            start_time=1641657600,  # 1,10 9:00
        )
        assert len(all_items) == 1
        # 测试查询开始时间为当前时间（大于until的情况）
        all_items = ItemDetailResource().request(calendar_ids=[calendar_id], time=1641776400)  # 1,10 9:00
        assert len(all_items) == 0
