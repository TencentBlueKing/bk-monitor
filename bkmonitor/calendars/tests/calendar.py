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
import pytest
import logging

from calendars import models
from calendars.resources.calendar import (
    SaveCalendarResource,
    ListCalendarResource,
    EditCalendarResource,
    DeleteCalendarResource,
    GetCalendarResource,
)

logger = logging.getLogger("calendars")


@pytest.mark.django_db
class TestCalendar:
    def test_save_calendar(self, mocker):
        """
        测试添加日历
        """
        # 1. 添加日历成功
        calendar1 = SaveCalendarResource().request(name="日历1", deep_color="#111111", light_color="#111111")
        assert calendar1["id"] == 2

        # 2. 添加日历失败：名字重复
        with pytest.raises(ValueError) as e:
            SaveCalendarResource().request(name="日历1", deep_color="#111113", light_color="#111113")
        exec_msg = e.value.args[0]
        assert exec_msg == "日历保存失败，日历名称(日历1)已存在"

    def test_edit_calendar(self, mocker):
        """
        测试编辑日历
        """
        calendar_id = SaveCalendarResource().request(name="日历2", deep_color="#111111", light_color="#111111")["id"]
        # 1. 编辑日历成功
        calendar = EditCalendarResource().request(id=calendar_id, name="修改日历")
        assert calendar["name"] == "修改日历"

        # 2. 编辑日历失败：名称已经存在
        with pytest.raises(ValueError) as e:
            EditCalendarResource().request(id=calendar_id, name="日历1")
        exec_msg = e.value.args[0]
        assert exec_msg == "日历编辑失败，日历名称(日历1)已存在"

        # 3. 日历编辑失败：id不存在
        with pytest.raises(models.CalendarModel.DoesNotExist) as e:
            EditCalendarResource().request(id=7, name="日历2")
        exec_msg = e.value.args[0]
        assert exec_msg == "CalendarModel matching query does not exist."

        # 4. 编辑日历颜色
        calendar = EditCalendarResource().request(id=calendar_id, deep_color="#111114", light_color="#111114")
        assert calendar["deep_color"] == "#111114"
        assert calendar["light_color"] == "#111114"

    def test_get_calendar(self, mocker):
        """
        获取单个日历
        """

        # 1. 获取单个日历成功: 通过id查询
        calendar = GetCalendarResource().request(id=2)
        logger.info("日历获取成功: id")
        assert calendar["id"] == 2
        assert calendar["name"] == "日历1"
        assert calendar["deep_color"] == "#111111"
        assert calendar["light_color"] == "#111111"

        # 2. 获取单个日历成功： 通过name查询
        calendar = GetCalendarResource().request(name="修改日历")
        logger.info("日历获取成功: name")
        assert calendar["name"] == "修改日历"
        assert calendar["deep_color"] == "#111114"
        assert calendar["light_color"] == "#111114"

        # 3. 获取单个日历失败：id不存在
        with pytest.raises(models.CalendarModel.DoesNotExist) as e:
            GetCalendarResource().request(id=9)
        exec_msg = e.value.args[0]
        assert exec_msg == "CalendarModel matching query does not exist."

    def test_list_calendar(self, mocker):
        """
        批量获取日历
        """
        return_data = ListCalendarResource().request()
        assert return_data["count"] == 3

    def test_delete_calendar(self, mocker):
        """
        删除日历
        """
        # 1. 删除日历成功
        DeleteCalendarResource().request(id=2)
        logger.info("删除日历成功")

        # 2. 删除日历失败
        with pytest.raises(models.CalendarModel.DoesNotExist) as e:
            DeleteCalendarResource().request(id=99)
        exec_msg = e.value.args[0]
        assert exec_msg == "CalendarModel matching query does not exist."
