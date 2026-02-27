"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bk_monitor_base.uptime_check import UptimeCheckTaskStatus


def mock_switch_uptime_check_task(mocker):
    """Mock uptime_check_operation.switch_uptime_check_task"""
    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.switch_uptime_check_task",
        return_value=None,
    )


def mock_get_uptime_check_task(mocker):
    """Mock uptime_check_operation.get_task_by_pk"""
    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.get_task_by_pk",
    )


@pytest.mark.django_db(databases="__all__")
class TestTaskChangeStatus:
    def test_change_status_start(self, mocker):
        """测试启动任务状态"""
        from bk_monitor_base.uptime_check import UptimeCheckTaskModel

        # 创建一个测试任务
        task_model = UptimeCheckTaskModel(
            bk_biz_id=2,
            name="test_task",
            protocol="HTTP",
            status=UptimeCheckTaskStatus.STOPED.value,
        )

        mock_get = mock_get_uptime_check_task(mocker)
        mock_get.return_value = task_model
        mock_switch = mock_switch_uptime_check_task(mocker)

        # 模拟更新后的任务状态
        updated_task = UptimeCheckTaskModel(
            bk_biz_id=2,
            name="test_task",
            protocol="HTTP",
            status=UptimeCheckTaskStatus.RUNNING.value,
        )
        mock_get.return_value = updated_task

        # 调用切换状态（由 views.py 中的 change_status 方法调用）
        from bk_monitor_base.uptime_check import control_task

        control_task(bk_tenant_id="default", bk_biz_id=2, task_id=1, action="start", operator="admin")

        mock_switch.assert_called_once()
        assert mock_get.call_count == 1

    def test_change_status_stop(self, mocker):
        """测试停止任务状态"""
        from bk_monitor_base.uptime_check import UptimeCheckTaskModel

        task_model = UptimeCheckTaskModel(
            bk_biz_id=2,
            name="test_task",
            protocol="HTTP",
            status=UptimeCheckTaskStatus.RUNNING.value,
        )

        mock_get = mock_get_uptime_check_task(mocker)
        mock_get.return_value = task_model
        mock_switch = mock_switch_uptime_check_task(mocker)

        # 模拟更新后的任务状态
        updated_task = UptimeCheckTaskModel(
            bk_biz_id=2,
            name="test_task",
            protocol="HTTP",
            status=UptimeCheckTaskStatus.STOPED.value,
        )
        mock_get.return_value = updated_task

        from monitor_web.uptime_check.resources import uptime_check_operation

        uptime_check_operation.switch_uptime_check_task(
            bk_tenant_id="default", bk_biz_id=2, task_id=1, action="stop", operator="admin"
        )

        mock_switch.assert_called_once()
        assert mock_get.call_count == 1
