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


import copy

import pytest
from django.db.models import QuerySet
from monitor_web.tests.utils import equal_value
from monitor_web.uptime_check.resources import (
    UptimeCheckCardResource,
    UptimeCheckTaskListResource,
)


class MockUptimeCheckTask(object):
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

    def get_period(self):
        """
        获取采集周期
        """
        return 1


class MockUptimeCheckGroup(object):
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)


TASK_DATA = [
    MockUptimeCheckTask(
        id=10001,
        bk_biz_id=2,
        name="test1",
        protocol="HTTP",
        check_interval=1,
        nodes=[10001],
        status="running",
        create_time="2020-03-16 23:52:06+0800",
        update_time="2020-03-18 14:58:22+0800",
        create_user="admin",
        update_user="admin",
        is_deleted=False,
        config={
            "timeout": 5005,
            "response_code": "200",
            "period": 60,
            "response_format": "nin",
            "response": None,
            "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "query_params": [],
            "headers": [],
            "urls": "http://www.baiidu.com",
            "method": "GET",
        },
        location={"bk_state_name": "", "bk_province_name": ""},
        subscription_id=1325,
    ),
    MockUptimeCheckTask(
        id=10002,
        bk_biz_id=2,
        name="test2",
        protocol="HTTP",
        check_interval=1,
        nodes=[10001, 10002],
        status="running",
        create_time="2020-03-19 22:35:40+0800",
        update_time="2020-03-19 22:35:43+0800",
        create_user="admin",
        update_user="admin",
        is_deleted=False,
        config={
            "timeout": 3000,
            "response_code": "",
            "period": 60,
            "response_format": "nin",
            "response": None,
            "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "query_params": [],
            "headers": [],
            "urls": "http://www.qq.com",
            "method": "GET",
        },
        location={"bk_state_name": "", "bk_province_name": ""},
        subscription_id=1354,
    ),
]

NODE_MAP = {
    10001: {
        "bk_biz_id": 2,
        "is_deleted": False,
        "is_common": False,
        "ip": "10.0.1.11",
        "carrieroperator": "\\u8054\\u901a",
        "create_user": "admin",
        "location": {"country": "\\u4e2d\\u56fd", "city": "\\u5e7f\\u4e1c"},
        "update_user": "admin",
        "plat_id": 0,
        "id": 10001,
        "name": "\\u4e2d\\u56fd\\u5e7f\\u4e1c\\u8054\\u901a",
    },
    10002: {
        "bk_biz_id": 2,
        "is_deleted": False,
        "is_common": False,
        "ip": "10.0.1.10",
        "carrieroperator": "\\u7535\\u4fe1",
        "create_user": "admin",
        "location": {"country": "\\u4e2d\\u56fd", "city": "\\u5e7f\\u4e1c"},
        "update_user": "admin",
        "plat_id": 0,
        "id": 10002,
        "name": "\\u4e2d\\u56fd\\u5e7f\\u4e1c\\u7535\\u4fe1",
    },
}

TASK_LIST_RESULT_DATA = [
    {
        "id": 10001,
        "config": {
            "method": "GET",
            "urls": "http://www.baiidu.com",
            "headers": [],
            "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "query_params": [],
            "response_code": "200",
            "period": 60,
            "response_format": "nin",
            "response": None,
            "timeout": 5005,
        },
        "location": {"bk_state_name": "", "bk_province_name": ""},
        "nodes": [
            {
                "bk_biz_id": 2,
                "is_deleted": False,
                "is_common": False,
                "ip": "10.0.1.11",
                "carrieroperator": "\\u8054\\u901a",
                "create_user": "admin",
                "location": {"country": "\\u4e2d\\u56fd", "city": "\\u5e7f\\u4e1c"},
                "update_user": "admin",
                "plat_id": 0,
                "id": 10001,
                "name": "\\u4e2d\\u56fd\\u5e7f\\u4e1c\\u8054\\u901a",
            }
        ],
        "groups": [],
        "available": 0.0,
        "task_duration": 0.0,
        "url": "http://www.baiidu.com",
        "create_time": "2020-03-16 23:52:06+0800",
        "update_time": "2020-03-18 14:58:22+0800",
        "create_user": "admin",
        "update_user": "admin",
        "is_deleted": False,
        "bk_biz_id": 2,
        "name": "test1",
        "protocol": "HTTP",
        "check_interval": 1,
        "status": "running",
        "subscription_id": 1325,
        "alarm_num": 10,
        "available_alarm": False,
        "task_duration_alarm": False,
    },
    {
        "id": 10002,
        "config": {
            "method": "GET",
            "urls": "http://www.qq.com",
            "headers": [],
            "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "query_params": [],
            "response_code": "",
            "period": 60,
            "response_format": "nin",
            "response": None,
            "timeout": 3000,
        },
        "location": {"bk_state_name": "", "bk_province_name": ""},
        "nodes": [
            {
                "bk_biz_id": 2,
                "is_deleted": False,
                "is_common": False,
                "ip": "10.0.1.11",
                "carrieroperator": "\\u8054\\u901a",
                "create_user": "admin",
                "location": {"country": "\\u4e2d\\u56fd", "city": "\\u5e7f\\u4e1c"},
                "update_user": "admin",
                "plat_id": 0,
                "id": 10001,
                "name": "\\u4e2d\\u56fd\\u5e7f\\u4e1c\\u8054\\u901a",
            },
            {
                "bk_biz_id": 2,
                "is_deleted": False,
                "is_common": False,
                "ip": "10.0.1.10",
                "carrieroperator": "\\u7535\\u4fe1",
                "create_user": "admin",
                "location": {"country": "\\u4e2d\\u56fd", "city": "\\u5e7f\\u4e1c"},
                "update_user": "admin",
                "plat_id": 0,
                "id": 10002,
                "name": "\\u4e2d\\u56fd\\u5e7f\\u4e1c\\u7535\\u4fe1",
            },
        ],
        "groups": [],
        "available": 0.0,
        "task_duration": 0.0,
        "url": "http://www.qq.com",
        "create_time": "2020-03-19 22:35:40+0800",
        "update_time": "2020-03-19 22:35:43+0800",
        "create_user": "admin",
        "update_user": "admin",
        "is_deleted": False,
        "bk_biz_id": 2,
        "name": "test2",
        "protocol": "HTTP",
        "check_interval": 1,
        "status": "running",
        "subscription_id": 1354,
        "alarm_num": 0,
        "available_alarm": False,
        "task_duration_alarm": False,
    },
]


class MockRequest(object):
    def __init__(self, method, params=None):
        params = params or {}
        if method.upper() == "GET":
            self.query_params = params

        if method.upper() == "POST":
            self.data = params


class MockUptimeCheckCardQuerySet(object):
    def filter(self):
        pass


@pytest.mark.django_db
class TestTaskList(object):
    # def test_list(self, mocker):
    #     from monitor_web.uptime_check.views import UptimeCheckTaskViewSet
    #
    #     mock_request = MockRequest("get", {"bk_biz_id": 2})
    #     result_list = {"task_data": TASK_LIST_RESULT_DATA, "group_data": [], "has_node": True}
    #     get_queryset_mock = mocker.patch("monitor_web.uptime_check.views.UptimeCheckTaskViewSet.get_queryset")
    #     filter_queryset_mock = mocker.patch(
    #         "rest_framework.generics.GenericAPIView.filter_queryset", return_value=TASK_DATA
    #     )
    #     uptime_check_task_list_mock = mocker.patch(
    #         "monitor_web.uptime_check.resources.UptimeCheckTaskListResource.request", return_value=result_list
    #     )
    #     uptime_check_task_viewset = UptimeCheckTaskViewSet()
    #     setattr(uptime_check_task_viewset, "request", mock_request)
    #     result = uptime_check_task_viewset.list(request=mock_request)
    #     assert result.data == result_list
    #     get_queryset_mock.assert_called_once()
    #     filter_queryset_mock.assert_called_once()
    #     uptime_check_task_list_mock.assert_called_once()

    def test_uptime_check_task_list(self, mocker):
        params = {"bk_biz_id": 2, "task_data": TASK_DATA, "get_available": False, "get_task_duration": False}

        def get_nodes_side_effect(task):
            return [NODE_MAP.get(node_id) for node_id in task.nodes]

        mocker.patch("monitor_web.uptime_check.resources.UptimeCheckTaskListResource.get_groups", return_value=[])
        mocker.patch(
            "monitor_web.uptime_check.resources.UptimeCheckTaskListResource.get_nodes",
            side_effect=get_nodes_side_effect,
        )

        result_data = UptimeCheckTaskListResource().request(params)
        equal_value(result_data, TASK_LIST_RESULT_DATA, ignore=["create_time", "update_time"])

    def test_uptime_check_card(self, mocker):
        task_params = copy.deepcopy(TASK_LIST_RESULT_DATA)
        [t.update(groups=[{"id": 1, "name": "group1"}]) for t in task_params]
        task_params[0]["available"] = 0.8
        params = {"bk_biz_id": 2, "task_data": task_params}
        origin_alarm = [
            {"origin_alarm": {"data": {"dimensions": {"task_id": 10001}, "values": {"available": 1}}}},
            {"origin_alarm": {"data": {"dimensions": {"task_id": 10002}, "values": {"task_duration": 1}}}},
            {"origin_alarm": {"data": {"dimensions": {"task_id": 10002}, "values": {"available": 1}}}},
        ]
        mocker.patch(
            "monitor_web.alert_events.resources.frontend_resource.QueryEventsResource.request", return_value=QuerySet()
        )
        mocker.patch("django.db.models.query.QuerySet.filter", return_value=QuerySet())
        mocker.patch("django.db.models.query.QuerySet.values", return_value=origin_alarm)
        mocker.patch("bkmonitor.utils.user.get_request_username")
        mocker.patch(
            "django.db.models.query.QuerySet.__iter__",
            return_value=iter(
                [
                    MockUptimeCheckGroup(
                        id=1,
                        name="group1",
                        logo="",
                        bk_biz_id=2,
                    )
                ]
            ),
        )
        mocker.patch("django.db.models.query.QuerySet.exists", return_value=True)
        task_data = copy.deepcopy(task_params)
        list(filter(lambda x: x["id"] == 10001, task_data))[0].update(alarm_num=1, available_alarm=True)
        list(filter(lambda x: x["id"] == 10002, task_data))[0].update(
            alarm_num=2, available_alarm=True, task_duration_alarm=True
        )
        result_data = UptimeCheckCardResource().request(params)
        assert result_data == {
            "task_data": task_data,
            "group_data": [
                {
                    "id": 1,
                    "top_three_tasks": [
                        {
                            "name": task_data[1]["name"],
                            "available": task_data[1]["available"],
                            "task_id": task_data[1]["id"],
                            "status": task_data[1]["status"],
                        },
                        {
                            "name": task_data[0]["name"],
                            "available": task_data[0]["available"],
                            "task_id": task_data[0]["id"],
                            "status": task_data[0]["status"],
                        },
                    ],
                    "protocol_num": [{"name": "HTTP", "val": 2}],
                    "logo": "",
                    "name": "group1",
                    "alarm_num": 3,
                    "all_tasks": [
                        {
                            "name": task_data[0]["name"],
                            "available": task_data[0]["available"],
                            "task_id": task_data[0]["id"],
                            "status": task_data[0]["status"],
                        },
                        {
                            "name": task_data[1]["name"],
                            "available": task_data[1]["available"],
                            "task_id": task_data[1]["id"],
                            "status": task_data[1]["status"],
                        },
                    ],
                    "bk_biz_id": 2,
                }
            ],
            "has_node": True,
        }
        equal_value(
            result_data,
            {
                "task_data": task_data,
                "group_data": [
                    {
                        "id": 1,
                        "top_three_tasks": [
                            {
                                "name": task_data[1]["name"],
                                "available": task_data[1]["available"],
                                "task_id": task_data[1]["id"],
                                "status": task_data[1]["status"],
                            },
                            {
                                "name": task_data[0]["name"],
                                "available": task_data[0]["available"],
                                "task_id": task_data[0]["id"],
                                "status": task_data[0]["status"],
                            },
                        ],
                        "protocol_num": [{"name": "HTTP", "val": 2}],
                        "logo": "",
                        "name": "group1",
                        "alarm_num": 3,
                        "all_tasks": [
                            {
                                "name": task_data[0]["name"],
                                "available": task_data[0]["available"],
                                "task_id": task_data[0]["id"],
                                "status": task_data[0]["status"],
                            },
                            {
                                "name": task_data[1]["name"],
                                "available": task_data[1]["available"],
                                "task_id": task_data[1]["id"],
                                "status": task_data[1]["status"],
                            },
                        ],
                        "bk_biz_id": 2,
                    }
                ],
                "has_node": True,
            },
        )
