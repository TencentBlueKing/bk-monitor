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
from types import SimpleNamespace
from unittest import TestCase, mock

from constants.action import GLOBAL_BIZ_ID
from fta_web.action.resources.backend_resources import (
    BatchCreateActionResource,
    GetActionParamsByConfigResource,
)
from fta_web.action.resources.frontend_resources import AssignAlertResource
from fta_web.action.utils import filter_alerts_by_biz


def _alert(bk_biz_id, alert_id="a"):
    return SimpleNamespace(
        id=alert_id,
        event=SimpleNamespace(bk_biz_id=bk_biz_id),
        strategy_id=1,
        severity=2,
        appointee=[],
        assignee=[],
    )


class TestActionParamsBizIsolation(TestCase):
    """按 ID 取套餐与告警时必须限定在请求业务内"""

    def test_config_query_limited_to_request_and_global_biz(self):
        resource = GetActionParamsByConfigResource()
        request_data = {"config_ids": [7], "alert_ids": [], "bk_biz_id": "2", "action_id": 0}

        with mock.patch(
            "fta_web.action.resources.backend_resources.ActionConfig.objects.filter"
        ) as config_filter, mock.patch(
            "fta_web.action.resources.backend_resources.ActionConfigDetailSlz"
        ) as slz, mock.patch(
            "fta_web.action.resources.backend_resources.AlertDocument.mget", return_value=[]
        ):
            slz.return_value.data = []
            resource.perform_request(request_data)

        config_filter.assert_called_once_with(id__in=[7], bk_biz_id__in=[GLOBAL_BIZ_ID, "2"])

    def test_context_built_with_request_biz_alerts(self):
        own, foreign = _alert("2"), _alert("9002")
        request_data = {
            "action_configs": [{"execute_config": {"template_detail": {}}}],
            "alert_ids": ["a", "b"],
            "bk_biz_id": "2",
            "action_id": 0,
        }

        with mock.patch(
            "fta_web.action.resources.backend_resources.AlertDocument.mget", return_value=[own, foreign]
        ), mock.patch(
            "fta_web.action.resources.backend_resources.ActionContext", create=True
        ) as context_cls, mock.patch(
            "fta_web.action.resources.backend_resources.CustomTemplateRenderer"
        ):
            context_cls.return_value.get_dictionary.return_value = {}
            GetActionParamsByConfigResource().perform_request(request_data)

        self.assertEqual(context_cls.call_args[1]["alerts"], [own])

    def test_action_instance_limited_to_request_biz(self):
        request_data = {"action_configs": [], "alert_ids": [], "bk_biz_id": "2", "action_id": 5}
        with mock.patch("fta_web.action.resources.backend_resources.AlertDocument.mget", return_value=[]), mock.patch(
            "fta_web.action.resources.backend_resources.ActionInstance.objects.get"
        ) as action_get:
            GetActionParamsByConfigResource().perform_request(request_data)
        action_get.assert_called_once_with(id=5, bk_biz_id="2")

    def test_alerts_from_other_biz_are_dropped(self):
        own, foreign = _alert("2"), _alert("9002")
        self.assertEqual(
            filter_alerts_by_biz([own, foreign], "2"),
            [own],
        )

    def test_alert_without_biz_is_dropped(self):
        self.assertEqual(
            filter_alerts_by_biz([SimpleNamespace(event=SimpleNamespace())], "2"),
            [],
        )

    def test_int_and_str_biz_id_match(self):
        self.assertEqual(
            len(filter_alerts_by_biz([_alert(2)], "2")),
            1,
        )
        self.assertEqual(len(filter_alerts_by_biz([_alert("2")], 2)), 1)


class TestActionCreateBizIsolation(TestCase):
    """创建处理任务与分派时仅处理请求业务下的告警"""

    @mock.patch("fta_web.action.resources.backend_resources.PushActionProcessor", create=True)
    @mock.patch("fta_web.action.resources.backend_resources.AlertLog")
    @mock.patch("fta_web.action.resources.backend_resources.ActionPluginSlz")
    @mock.patch("fta_web.action.resources.backend_resources.ActionPlugin")
    @mock.patch("fta_web.action.resources.backend_resources.ActionInstance")
    @mock.patch("fta_web.action.resources.backend_resources.AlertDocument")
    def test_batch_create_only_handles_request_biz_alerts(
        self, alert_document, action_instance, _plugin, plugin_slz, _alert_log, push_processor
    ):
        own, foreign = _alert("2", "own"), _alert("9002", "foreign")
        alert_document.mget.return_value = [own, foreign]
        plugin_slz.return_value.data = []
        BatchCreateActionResource().perform_request(
            {
                "operate_data_list": [
                    {"alert_ids": ["own", "foreign"], "action_configs": [{"config_id": 1, "plugin_id": 1}]}
                ],
                "creator": "alice",
                "bk_biz_id": "2",
            }
        )
        self.assertEqual(action_instance.objects.create.call_args[1]["alerts"], ["own"])
        self.assertEqual([call[1]["id"] for call in alert_document.call_args_list], ["own"])
        push_processor.push_actions_to_queue.assert_called_once_with(mock.ANY, [own])

    @mock.patch("fta_web.action.resources.frontend_resources.notify_to_appointee")
    @mock.patch("fta_web.action.resources.frontend_resources.AlertLog")
    @mock.patch("fta_web.action.resources.frontend_resources.get_request_username", return_value="alice")
    @mock.patch("fta_web.action.resources.frontend_resources.AlertDocument")
    def test_assign_only_handles_request_biz_alerts(self, alert_document, _username, _alert_log, notify):
        own, foreign = _alert("2", "own"), _alert("9002", "foreign")
        alert_document.mget.return_value = [own, foreign]
        result = AssignAlertResource().perform_request(
            {
                "appointees": ["bob"],
                "alert_ids": ["own", "foreign"],
                "reason": "handover",
                "notice_ways": ["mail"],
                "bk_biz_id": "2",
            }
        )
        self.assertEqual(result["assigned_alerts"], ["own"])
        self.assertEqual(notify.delay.call_args[0][0]["alert_ids"], ["own"])
        self.assertEqual([call[1]["id"] for call in alert_document.call_args_list], ["own"])
