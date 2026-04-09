"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from django.test import SimpleTestCase

from bkmonitor.aiops.incident.operation import IncidentOperationManager
from constants.incident import IncidentOperationType


class TestIncidentOperationManager(SimpleTestCase):
    def test_get_display_incident_name_should_map_merged_anonymous_incident(self):
        display_name = IncidentOperationManager.get_display_incident_name("new_incident_1002", status="merged")

        self.assertEqual(display_name, "已合并匿名故障")

    def test_get_display_incident_name_should_keep_non_merged_or_named_incident(self):
        self.assertEqual(
            IncidentOperationManager.get_display_incident_name("new_incident_1002", status="abnormal"),
            "new_incident_1002",
        )
        self.assertEqual(IncidentOperationManager.get_display_incident_name("故障A", status="merged"), "故障A")

    def test_record_merge_incident_should_send_notice_for_real_incident_merge(self):
        merge_info = {
            "origin_incident_id": 1001,
            "origin_incident_name": "故障A",
            "origin_created_at": 1710000000,
            "target_incident_id": 2001,
            "target_incident_name": "故障B",
            "target_created_at": 1710000100,
        }

        with mock.patch.object(IncidentOperationManager, "record_operation") as mock_record_operation:
            IncidentOperationManager.record_merge_incident(
                operate_time=1710000200, merge_info=merge_info, alert_count=3
            )

        self.assertEqual(mock_record_operation.call_count, 2)
        self.assertEqual(mock_record_operation.call_args_list[0].args[1], IncidentOperationType.MERGE_TO)
        self.assertTrue(mock_record_operation.call_args_list[0].kwargs["send_notice"])
        self.assertEqual(mock_record_operation.call_args_list[1].args[1], IncidentOperationType.MERGE)
        self.assertTrue(mock_record_operation.call_args_list[1].kwargs["send_notice"])

    def test_record_merge_incident_should_not_send_notice_for_anonymous_source_merge(self):
        merge_info = {
            "origin_incident_id": 1002,
            "origin_incident_name": "new_incident_1002",
            "origin_created_at": 1710000000,
            "target_incident_id": 2002,
            "target_incident_name": "故障B",
            "target_created_at": 1710000100,
        }

        with mock.patch.object(IncidentOperationManager, "record_operation") as mock_record_operation:
            IncidentOperationManager.record_merge_incident(
                operate_time=1710000200, merge_info=merge_info, alert_count=5
            )

        self.assertEqual(mock_record_operation.call_count, 2)
        self.assertEqual(mock_record_operation.call_args_list[0].args[1], IncidentOperationType.MERGE_TO)
        self.assertFalse(mock_record_operation.call_args_list[0].kwargs["send_notice"])
        self.assertEqual(mock_record_operation.call_args_list[1].args[1], IncidentOperationType.MERGE)
        self.assertFalse(mock_record_operation.call_args_list[1].kwargs["send_notice"])
