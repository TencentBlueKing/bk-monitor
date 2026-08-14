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

from django.conf import settings
from django.test import SimpleTestCase

from constants.alert import EventStatus

# Web 角色不加载 worker 的定时任务配置，但告警关闭依赖链会导入任务注册模块。
for setting_name in ("DEFAULT_CRONTAB", "ACTION_TASK_CRONTAB", "LONG_TASK_CRONTAB", "EXCLUDE_WORKER_TASKS"):
    if not hasattr(settings, setting_name):
        setattr(settings, setting_name, [])

from kernel_api.views.v4 import alert as alert_view


class TestCloseAlertResourceLifecycle(SimpleTestCase):
    def test_close_rechecks_newer_alert_ownership_under_alert_lock(self):
        alert_doc = mock.Mock()
        alert_doc.id = "old-alert"
        alert_doc.status = EventStatus.ABNORMAL
        alert_doc.is_ack = False
        alert_doc.to_dict.return_value = {
            "id": alert_doc.id,
            "strategy_id": 1,
            "dedupe_md5": "dedupe-md5",
            "status": EventStatus.ABNORMAL,
            "severity": 2,
            "event": {},
            "extra_info": {},
        }
        lock = mock.Mock()
        lock.is_locked.return_value = True
        lock_context = mock.MagicMock()
        lock_context.__enter__.return_value = lock
        lock_context.__exit__.return_value = False

        with (
            mock.patch.object(alert_view.AlertDocument, "mget", return_value=[alert_doc]),
            mock.patch.object(alert_view, "multi_service_lock", return_value=lock_context),
            mock.patch.object(alert_view.CloseStatusChecker, "check_event_expired", return_value=True) as check_expired,
            mock.patch.object(alert_view.CloseStatusChecker, "close") as close,
            mock.patch.object(alert_view.AlertManager, "save_alerts"),
            mock.patch.object(alert_view.AlertManager, "save_alert_logs"),
            mock.patch.object(alert_view.AlertManager, "update_alert_cache"),
            mock.patch.object(alert_view.AlertManager, "update_alert_snapshot"),
        ):
            result = alert_view.CloseAlertResource().perform_request({"ids": [alert_doc.id], "message": "manual close"})

        check_expired.assert_called_once()
        close.assert_not_called()
        self.assertEqual(result["alerts_close_success"], [alert_doc.id])
