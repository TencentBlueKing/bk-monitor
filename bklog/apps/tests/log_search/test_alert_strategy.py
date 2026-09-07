"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_search.constants import AlertStatusEnum
from apps.log_search.handlers.alert_strategy import AlertStrategyHandler
from apps.log_search.serializers import AlertRecordSerializer
from apps.utils.drf import custom_params_valid


class TestAlertRecordSerializer(SimpleTestCase):
    def test_accepts_abnormal(self):
        data = custom_params_valid(AlertRecordSerializer, {"status": AlertStatusEnum.ABNORMAL.value})
        self.assertEqual(data["status"], AlertStatusEnum.ABNORMAL.value)

    def test_accepts_not_shielded_abnormal(self):
        data = custom_params_valid(AlertRecordSerializer, {"status": AlertStatusEnum.NOT_SHIELDED_ABNORMAL.value})
        self.assertEqual(data["status"], AlertStatusEnum.NOT_SHIELDED_ABNORMAL.value)

    def test_rejects_unknown_status(self):
        serializer = AlertRecordSerializer(data={"status": "INVALID"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)


class TestAlertStrategyHandlerGetAlertRecords(SimpleTestCase):
    def setUp(self):
        self.index_set = SimpleNamespace(index_set_id=123, space_uid="bkcc__2")

    def _build_handler(self):
        with patch("apps.log_search.handlers.alert_strategy.LogIndexSet.objects.get", return_value=self.index_set):
            return AlertStrategyHandler(index_set_id=123)

    def _search_params(self, mock_search):
        return mock_search.call_args[0][0]

    @patch("apps.log_search.handlers.alert_strategy.space_uid_to_bk_biz_id", return_value=2)
    @patch("apps.log_search.handlers.alert_strategy.MonitorApi.search_alert")
    def test_abnormal_forwards_status_to_monitor(self, mock_search, _mock_space):
        mock_search.return_value = {"alerts": []}
        self._build_handler().get_alert_records(status=AlertStatusEnum.ABNORMAL.value)
        params = self._search_params(mock_search)
        self.assertEqual(params["status"], [AlertStatusEnum.ABNORMAL.value])
        self.assertEqual(params["conditions"], [{"key": "metric", "value": ["bk_log_search.index_set.123"]}])

    @patch("apps.log_search.handlers.alert_strategy.space_uid_to_bk_biz_id", return_value=2)
    @patch("apps.log_search.handlers.alert_strategy.MonitorApi.search_alert")
    def test_not_shielded_abnormal_still_forwards(self, mock_search, _mock_space):
        mock_search.return_value = {"alerts": []}
        self._build_handler().get_alert_records(status=AlertStatusEnum.NOT_SHIELDED_ABNORMAL.value)
        self.assertEqual(self._search_params(mock_search)["status"], [AlertStatusEnum.NOT_SHIELDED_ABNORMAL.value])

    @patch("apps.log_search.handlers.alert_strategy.space_uid_to_bk_biz_id", return_value=2)
    @patch("apps.log_search.handlers.alert_strategy.MonitorApi.search_alert")
    def test_all_does_not_filter_status(self, mock_search, _mock_space):
        mock_search.return_value = {"alerts": []}
        self._build_handler().get_alert_records(status=AlertStatusEnum.ALL.value)
        self.assertEqual(self._search_params(mock_search)["status"], [])

    @patch("apps.log_search.handlers.alert_strategy.get_request_username", return_value="alice")
    @patch("apps.log_search.handlers.alert_strategy.space_uid_to_bk_biz_id", return_value=2)
    @patch("apps.log_search.handlers.alert_strategy.MonitorApi.search_alert")
    def test_my_assignee_adds_assignee_condition(self, mock_search, _mock_space, _mock_username):
        mock_search.return_value = {"alerts": []}
        self._build_handler().get_alert_records(status=AlertStatusEnum.MY_ASSIGNEE.value)
        params = self._search_params(mock_search)
        self.assertEqual(params["status"], [])
        self.assertIn({"key": "assignee", "value": ["alice"]}, params["conditions"])
