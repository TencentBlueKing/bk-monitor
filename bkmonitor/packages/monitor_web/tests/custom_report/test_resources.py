# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import json

import mock
import pytest
from django.test import TestCase, override_settings

from core.drf_resource import APIResource
from core.errors.custom_report import CustomEventValidationError, CustomTSValidationError
from monitor_web.custom_report.resources import (
    CreateCustomEventGroup,
    DeleteCustomEventGroup,
    GetCustomEventGroup,
    ModifyCustomEventGroup,
    QueryCustomEventGroup,
    ValidateCustomEventGroupName,
    CreateCustomTimeSeries,
)
from monitor_web.models import CustomEventGroup, CustomEventItem, CustomTSItem, CustomTSTable

pytestmark = pytest.mark.django_db

RESULT_TABLE_LABELS = [
    {
        "index": 1,
        "label_type": "result_table_label",
        "level": 1,
        "parent_label": None,
        "label_name": "用户体验",
        "label_id": "applications",
    },
    {
        "index": 2,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "applications",
        "label_name": "业务应用",
        "label_id": "application_check",
    },
    {
        "index": 2,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "services",
        "label_name": "组件",
        "label_id": "component",
    },
    {
        "index": 3,
        "label_type": "result_table_label",
        "level": 1,
        "parent_label": None,
        "label_name": "主机",
        "label_id": "hosts",
    },
    {
        "index": 1,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "hosts",
        "label_name": "进程",
        "label_id": "host_process",
    },
    {
        "index": 2,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "hosts",
        "label_name": "操作系统",
        "label_id": "os",
    },
    {
        "index": 4,
        "label_type": "result_table_label",
        "level": 1,
        "parent_label": None,
        "label_name": "其他",
        "label_id": "others",
    },
    {
        "index": 2,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "others",
        "label_name": "其他",
        "label_id": "other_rt",
    },
    {
        "index": 2,
        "label_type": "result_table_label",
        "level": 1,
        "parent_label": None,
        "label_name": "服务",
        "label_id": "services",
    },
    {
        "index": 1,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "services",
        "label_name": "服务模块",
        "label_id": "service_module",
    },
    {
        "index": 1,
        "label_type": "result_table_label",
        "level": 2,
        "parent_label": "applications",
        "label_name": "服务拨测",
        "label_id": "uptimecheck",
    },
]

EVENT_INFO_LIST = [
    {
        "custom_event_id": 10010,
        "custom_event_name": "event_1",
        "dimension_list": [
            {"dimension_name": "field_name1"},
            {
                "dimension_name": "bk_target",
            },
        ],
    },
    {
        "custom_event_id": 10011,
        "custom_event_name": "event_2",
        "dimension_list": [
            {"dimension_name": "field_name2"},
            {
                "dimension_name": "bk_target",
            },
        ],
    },
]

EVENT_GROUP_RETURN_VALUE = {
    "event_group_id": 1001,
    "bk_data_id": 1234,
    "bk_biz_id": 2,
    "label": "uptimecheck",
    "event_group_name": "test custom event",
    "is_enable": True,
    "creator": "admin",
    "create_time": "2019-10-10 10:10:10",
    "last_modify_user": "admin",
    "last_modify_time": "2020-10-10 10:10:10",
    "event_info_list": EVENT_INFO_LIST,
    "table_id": "2_bkmonitor_test",
}
TS_GROUP_RETURN_VALUE = {
    "time_series_group_id": 1002,
    "bk_data_id": 1234,
    "bk_biz_id": 2,
    "label": "uptimecheck",
    "time_series_group_name": "test custom event",
    "is_enable": True,
    "creator": "admin",
    "create_time": "2019-10-10 10:10:10",
    "last_modify_user": "admin",
    "last_modify_time": "2020-10-10 10:10:10",
    "metric_info_list": EVENT_INFO_LIST,
    "table_id": "2_bkmonitor_test_1500489.base",
}


class TestResource(TestCase):
    def setUp(self):
        CustomEventGroup.origin_objects.all().delete()
        CustomEventItem.objects.all().delete()

    def tearDown(self):
        CustomEventGroup.origin_objects.all().delete()
        CustomEventItem.objects.all().delete()

    @mock.patch("monitor_web.custom_report.resources.CreateCustomEventGroup.get_custom_event_data_id")
    @mock.patch("monitor_web.custom_report.resources.api.metadata.create_event_group")
    def test_create_custom_event_group(self, create_event_group, get_custom_event_data_id):
        get_custom_event_data_id.return_value = 1234
        create_event_group.return_value = EVENT_GROUP_RETURN_VALUE
        resource = CreateCustomEventGroup()
        result = resource.request(
            bk_biz_id=2,
            name="test custom event",
            event_info_list=[],
            scenario="uptimecheck",
        )
        self.assertEqual(result["bk_event_group_id"], 1001)
        group = CustomEventGroup.objects.get(bk_event_group_id=result["bk_event_group_id"])
        self.assertEqual(group.bk_data_id, 1234)
        self.assertEqual(group.bk_biz_id, 2)
        self.assertEqual(group.bk_event_group_id, 1001)
        self.assertEqual(group.is_enable, True)
        self.assertEqual(group.scenario, "uptimecheck")

    def insert_event_group(self):
        group = CustomEventGroup.objects.create(
            bk_biz_id=EVENT_GROUP_RETURN_VALUE["bk_biz_id"],
            bk_event_group_id=EVENT_GROUP_RETURN_VALUE["event_group_id"],
            scenario=EVENT_GROUP_RETURN_VALUE["label"],
            name=EVENT_GROUP_RETURN_VALUE["event_group_name"],
            bk_data_id=1234,
            table_id=EVENT_GROUP_RETURN_VALUE["table_id"],
        )
        event_items = []
        for event in EVENT_GROUP_RETURN_VALUE["event_info_list"]:
            event_items.append(
                CustomEventItem(
                    custom_event_id=event["custom_event_id"],
                    bk_event_group_id=EVENT_GROUP_RETURN_VALUE["event_group_id"],
                    custom_event_name=event["custom_event_name"],
                    dimension_list=event["dimension_list"],
                )
            )
        CustomEventItem.objects.bulk_create(event_items)
        return group

    @mock.patch.object(APIResource, "perform_request")
    def test_get_custom_event_group(self, mock_api):
        def mock_request(*args, **kwargs):
            if "bk_data_id" in args[0]:
                return {"token": "123"}
            elif "event_group_id" in args[0]:
                return {
                    "event_group_id": 1001,
                    "bk_data_id": 1234,
                    "bk_biz_id": 2,
                    "label": "uptimecheck",
                    "event_group_name": "modified group name",
                    "is_enable": False,
                    "creator": "admin",
                    "create_time": "2019-10-10 10:10:10",
                    "last_modify_user": "admin",
                    "last_modify_time": "2020-10-10 10:10:10",
                    "event_info_list": [
                        {
                            "event_id": 10010,
                            "event_name": "event_1",
                            "dimension_list": [
                                {"dimension_name": "field_name1"},
                                {
                                    "dimension_name": "bk_target",
                                },
                            ],
                        },
                        {
                            "event_id": 10012,
                            "event_name": "event_3",
                            "dimension_list": [
                                {"dimension_name": "field_name3"},
                                {
                                    "dimension_name": "bk_target",
                                },
                            ],
                        },
                    ],
                }
            elif "label_type" in args[0]:
                return {"result_table_label": RESULT_TABLE_LABELS}
            return {
                "hits": {
                    "hits": [
                        {
                            "sort": [1582795460000],
                            "_type": "test_type",
                            "_source": {
                                "event_name": "login",
                                "dimensions": {"log_path": "/data/net/access.log", "set": "jiangsu", "module": "db"},
                                "bk_target": "1:10.0.0.1",
                                "event": {"event_content": "user login success", "_bk_count": 30},
                                "time": 1582795460000,
                            },
                            "_score": None,
                            "_index": "rhj_test",
                            "_id": "AXDTg0sZ_Fzwj0QKtn45",
                        }
                    ],
                    "total": {"value": 4},
                    "max_score": None,
                },
                "_shards": {"successful": 5, "failed": 0, "total": 5},
                "took": 56,
                "aggregations": {
                    "target": {
                        "buckets": [
                            {"count": {"value": 2}, "key": "guangdong", "doc_count": 2},
                            {"count": {"value": 2}, "key": "jiangsu", "doc_count": 2},
                        ],
                        "sum_other_doc_count": 0,
                        "doc_count_error_upper_bound": 0,
                    }
                },
                "timed_out": False,
            }

        mock_api.side_effect = mock_request
        self.insert_event_group()
        resource = GetCustomEventGroup()
        result = resource.request(bk_event_group_id=1001, time_range="2020-03-16 16:20:18 -- 2020-03-16 17:20:18")
        assert result["bk_event_group_id"] == 1001
        assert result["bk_data_id"] == 1234
        assert result["name"] == "test custom event"
        assert result["scenario"] == "uptimecheck"
        assert result["is_enable"] is True
        assert result["scenario_display"] == ["用户体验", "服务拨测"]
        assert result["access_token"] == "123"

    @mock.patch.object(APIResource, "perform_request")
    def test_query_custom_event_group(self, get_label):
        get_label.return_value = {"result_table_label": RESULT_TABLE_LABELS}
        self.insert_event_group()
        resource = QueryCustomEventGroup()
        result = resource.request(bk_biz_id=2, search_key="test")
        assert result["total"] == 1
        assert result["list"][0]["bk_event_group_id"] == 1001
        assert result["list"][0]["bk_data_id"] == 1234
        assert result["list"][0]["scenario_display"] == ["用户体验", "服务拨测"]
        assert "related_strategy_count" in result["list"][0]
        assert "event_info_list" not in result["list"][0]

        result = resource.request(bk_biz_id=2, search_key="100")
        assert result["total"] == 0

        result = resource.request(bk_biz_id=2, search_key="1001")
        assert result["total"] == 1

    @mock.patch("monitor_web.custom_report.resources.api.metadata.modify_event_group")
    def test_modify_custom_event_group(self, modify_event_group):
        modify_event_group.return_value = {
            "event_group_id": 1001,
            "bk_data_id": 1234,
            "bk_biz_id": 2,
            "label": "uptimecheck",
            "event_group_name": "modified group name",
            "is_enable": False,
            "creator": "admin",
            "create_time": "2019-10-10 10:10:10",
            "last_modify_user": "admin",
            "last_modify_time": "2020-10-10 10:10:10",
            "event_info_list": [
                {
                    "event_id": 10010,
                    "event_name": "event_1",
                    "dimension_list": [
                        {"dimension_name": "field_name1"},
                        {
                            "dimension_name": "bk_target",
                        },
                    ],
                },
                {
                    "event_id": 10012,
                    "event_name": "event_3",
                    "dimension_list": [
                        {"dimension_name": "field_name3"},
                        {
                            "dimension_name": "bk_target",
                        },
                    ],
                },
            ],
        }
        self.insert_event_group()
        resource = ModifyCustomEventGroup()
        result = resource.request(bk_event_group_id=1001, name="modified group name", event_info_list=[])
        assert "bk_event_group_id" in result
        group = CustomEventGroup.objects.get(bk_event_group_id=result["bk_event_group_id"])
        assert group.bk_biz_id == 2
        assert group.bk_event_group_id == 1001
        assert group.is_enable is False
        assert group.scenario == "uptimecheck"

    @mock.patch("monitor_web.custom_report.resources.api.metadata.delete_event_group")
    def test_delete_custom_event_group(self, delete_event_group):
        group = self.insert_event_group()
        resource = DeleteCustomEventGroup()
        resource.request(bk_event_group_id=group.bk_event_group_id)
        assert not CustomEventGroup.objects.filter(bk_event_group_id=group.bk_event_group_id).exists()
        assert not CustomEventItem.objects.filter(bk_event_group_id=group.bk_event_group_id).exists()

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_1(self, query_event_group):
        query_event_group.return_value = [EVENT_GROUP_RETURN_VALUE]
        resource = ValidateCustomEventGroupName()
        with pytest.raises(CustomEventValidationError):
            resource.request(name="test custom event")

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_2(self, query_event_group):
        def raise_exception():
            raise Exception

        query_event_group.side_effect = raise_exception
        self.insert_event_group()
        resource = ValidateCustomEventGroupName()
        with pytest.raises(CustomEventValidationError):
            resource.request(name="test custom event")

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_3(self, query_event_group):
        query_event_group.return_value = []
        resource = ValidateCustomEventGroupName()
        assert resource.request(name="test custom event")

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_4(self, query_event_group):
        def raise_exception():
            raise Exception

        query_event_group.side_effect = raise_exception
        resource = ValidateCustomEventGroupName()
        assert resource.request(name="test custom event")

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_5(self, query_event_group):
        query_event_group.return_value = [EVENT_GROUP_RETURN_VALUE]
        self.insert_event_group()
        resource = ValidateCustomEventGroupName()
        assert resource.request(name="test custom event", bk_event_group_id=1001)

    @mock.patch("monitor_web.custom_report.resources.api.metadata.query_event_group")
    def test_validate_custom_event_group_name_6(self, query_event_group):
        query_event_group.return_value = [EVENT_GROUP_RETURN_VALUE]
        self.insert_event_group()
        resource = ValidateCustomEventGroupName()
        with pytest.raises(CustomEventValidationError):
            resource.request(name="test custom event", bk_event_group_id=1002)


class TestTSResource(TestCase):
    def setUp(self):
        CustomTSTable.origin_objects.all().delete()
        CustomTSItem.objects.all().delete()

    def tearDown(self):
        CustomTSTable.origin_objects.all().delete()
        CustomTSItem.objects.all().delete()

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    @mock.patch.object(APIResource, "perform_request")
    def test_create_custom_ts(self, mocker):
        post_data = {"bk_biz_id": 2, "name": "test_ts", "scenario": "uptimecheck", "data_label": "test_ts"}
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request",
            return_value=[{"bk_data_id": 123}, TS_GROUP_RETURN_VALUE],
        )
        data = CreateCustomTimeSeries().request(post_data)
        self.assertEqual(data["time_series_group_id"], 1002)

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    @mock.patch.object(APIResource, "perform_request")
    def test_modify_custom_ts(self, mock_api):
        table = CustomTSTable.objects.create(
            time_series_group_id=1002,
            bk_data_id=123,
            bk_biz_id=2,
            name="test_ts",
            scenario="uptimecheck",
            table_id="4567",
        )
        post_data = {
            "time_series_group_id": table.time_series_group_id,
            "name": "test_ts",
            "metric_json": [
                {
                    "fields": [
                        {
                            "name": "mem_usage",
                            "type": "double",
                            "monitor_type": "metric",
                            "unit": "M",
                            "description": "mem_usage_2",
                        },
                        {
                            "description": "test_name_2",
                            "type": "string",
                            "monitor_type": "dimension",
                            "unit": "",
                            "name": "test_name",
                        },
                    ],
                }
            ],
        }

        def mock_api_func(*args, **kwargs):
            if "field_list" in args[0]:
                return {"bk_data_id": 123}
            elif "bk_data_id" in args[0]:
                return {"token": "234"}
            elif "time_series_group_id" in args[0]:
                return {
                    "metric_info_list": [
                        {
                            "field_name": "mem_usage",
                            "metric_display_name": "mem_usage_2",
                            "unit": "M",
                            "type": "double",
                            "tag_list": [{"dimension_name": "test_name", "dimension_display_name": "test_name_2"}],
                        }
                    ]
                }
            elif "sql" in args[0]:
                return {"list": [{"mem_usage": "100", "test_name": "mem_1"}]}
            elif "label_type" in args[0]:
                return {"result_table_label": RESULT_TABLE_LABELS}

        mock_api.side_effect = mock_api_func
        path = "/rest/v2/custom_report/modify_custom_time_series/"
        response = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
        content = json.loads(response.content)
        print(content)
        self.assertEqual(content["data"]["time_series_group_id"], table.time_series_group_id)
        self.assertEqual(
            content["data"]["metric_json"],
            [
                {
                    "fields": [
                        {
                            "name": "mem_usage",
                            "monitor_type": "metric",
                            "unit": "M",
                            "description": "mem_usage_2",
                            "value": "100",
                            "type": "double",
                        },
                        {
                            "name": "test_name",
                            "monitor_type": "dimension",
                            "unit": "",
                            "description": "test_name_2",
                            "value": "mem_1",
                            "type": "string",
                        },
                    ]
                }
            ],
        )

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    @mock.patch.object(APIResource, "perform_request")
    def test_delete_custom_ts(self, mock_api):
        table = CustomTSTable.objects.create(
            time_series_group_id=1002,
            bk_data_id=123,
            bk_biz_id=2,
            name="test_ts",
            scenario="uptimecheck",
            table_id="4567",
        )
        CustomTSItem.objects.create(
            table=table,
            metric_name="mem_usage",
            unit="M",
            metric_display_name="mem_usage_1",
            dimension_list={"dimension_name": "test_name", "dimension_display_name": "test_name_1"},
        )
        post_data = {
            "time_series_group_id": table.time_series_group_id,
        }
        path = "/rest/v2/custom_report/delete_custom_time_series/"
        response = self.client.post(path=path, data=json.dumps(post_data), content_type="application/json")
        content = json.loads(response.content)
        self.assertEqual(content["data"]["time_series_group_id"], table.time_series_group_id)

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    def test_custom_ts_list(self):
        CustomTSTable.objects.create(
            time_series_group_id=1002,
            bk_data_id=123,
            bk_biz_id=2,
            name="test_ts",
            scenario="uptimecheck",
            table_id="4567",
        )
        data = {
            "bk_biz_id": 2,
        }

        path = "/rest/v2/custom_report/custom_time_series/"
        response = self.client.get(path=path, data=data)
        print(response.content)
        content = json.loads(response.content)
        self.assertEqual(content["data"]["total"], 1)

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    @mock.patch.object(APIResource, "perform_request")
    def test_custom_ts_detail(self, mock_api):
        table = CustomTSTable.objects.create(
            time_series_group_id=1002,
            bk_data_id=123,
            bk_biz_id=2,
            name="test_ts",
            scenario="uptimecheck",
            table_id="4567",
        )
        CustomTSItem.objects.create(
            table=table,
            metric_name="mem_usage",
            unit="M",
            type="double",
            metric_display_name="mem_usage_1",
            dimension_list=[{"dimension_name": "test_name", "dimension_display_name": "test_name_1"}],
        )
        post_data = {
            "time_series_group_id": table.time_series_group_id,
        }

        def mock_api_func(*args, **kwargs):
            if "bk_data_id" in args[0]:
                return {"token": "234"}
            elif "time_series_group_id" in args[0]:
                return {
                    "metric_info_list": [
                        {
                            "field_name": "mem_usage",
                            "metric_display_name": "mem_usage_2",
                            "unit": "M",
                            "type": "double",
                            "tag_list": [{"dimension_name": "test_name", "dimension_display_name": "test_name_2"}],
                        }
                    ]
                }
            elif "sql" in args[0]:
                return {"list": [{"mem_usage": "100", "test_name": "mem_1"}]}
            elif "label_type" in args[0]:
                return {"result_table_label": RESULT_TABLE_LABELS}

        mock_api.side_effect = mock_api_func
        path = "/rest/v2/custom_report/custom_time_series_detail/"
        response = self.client.get(path=path, data=post_data)
        content = json.loads(response.content)
        self.assertEqual(content["data"]["time_series_group_id"], table.time_series_group_id)
        self.assertEqual(
            content["data"]["metric_json"],
            [
                {
                    "fields": [
                        {
                            "name": "mem_usage",
                            "monitor_type": "metric",
                            "unit": "M",
                            "description": "mem_usage_1",
                            "value": "100",
                            "type": "double",
                        },
                        {
                            "name": "test_name",
                            "monitor_type": "dimension",
                            "unit": "",
                            "description": "test_name_1",
                            "value": "mem_1",
                            "type": "string",
                        },
                    ]
                }
            ],
        )

    @override_settings(MIDDLEWARE=("monitor_web.tests.middlewares.OverrideMiddleware",))
    @mock.patch.object(APIResource, "perform_request")
    def test_custom_ts_detail_no_value(self, mock_api):
        table = CustomTSTable.objects.create(
            time_series_group_id=1002,
            bk_data_id=123,
            bk_biz_id=2,
            name="test_ts",
            scenario="uptimecheck",
            table_id="4567",
        )
        post_data = {
            "time_series_group_id": table.time_series_group_id,
        }

        def mock_api_func(*args, **kwargs):
            if "bk_data_id" in args[0]:
                return {"token": "234"}
            elif "time_series_group_id" in args[0]:
                return {
                    "metric_info_list": [
                        {
                            "field_name": "mem_usage",
                            "metric_display_name": "mem_usage_2",
                            "unit": "M",
                            "type": "double",
                            "tag_list": [{"dimension_name": "test_name", "dimension_display_name": "test_name_2"}],
                        }
                    ]
                }
            elif "sql" in args[0]:
                return {
                    "list": [
                        {
                            "mem_usage": "100",
                        }
                    ]
                }
            elif "label_type" in args[0]:
                return {"result_table_label": RESULT_TABLE_LABELS}

        mock_api.side_effect = mock_api_func
        path = "/rest/v2/custom_report/custom_time_series_detail/"
        response = self.client.get(path=path, data=post_data)
        content = json.loads(response.content)
        self.assertEqual(content["data"]["time_series_group_id"], table.time_series_group_id)
        self.assertEqual(
            content["data"]["metric_json"],
            [
                {
                    "fields": [
                        {
                            "name": "mem_usage",
                            "monitor_type": "metric",
                            "unit": "M",
                            "description": "mem_usage_2",
                            "value": "100",
                            "type": "double",
                        },
                        {
                            "name": "test_name",
                            "monitor_type": "dimension",
                            "unit": "",
                            "description": "test_name_2",
                            "value": "近5分钟无数据上报",
                            "type": "string",
                        },
                    ]
                }
            ],
        )
