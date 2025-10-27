"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock

import pytest
from django.utils.translation import gettext as _

from core.drf_resource.exceptions import CustomException
from monitor_web.models.uptime_check import UptimeCheckTask


def mock_strategy_func(mocker):
    # 起停策略
    strategy_func = mocker.patch("monitor_web.uptime_check.resources.SwitchStrategyByTaskIDResource.perform_request")
    return strategy_func


def mock_change_status_flow():
    # 不提供订阅id
    task = UptimeCheckTask(pk=123, bk_biz_id=123, status=UptimeCheckTask.Status.STOPED)
    task.save = Mock()

    # 起停订阅
    task.switch_off_subscription = Mock()
    task.start_subscription = Mock()
    task.stop_subscription = Mock()
    task.switch_on_subscription = Mock()

    return task


@pytest.mark.django_db(databases="__all__")
class TestTaskChangeStatus:
    def test_change_status(self, mocker):
        task = mock_change_status_flow()
        strategy_func = mock_strategy_func(mocker)
        strategy_func.start()
        assert task.status == UptimeCheckTask.Status.STOPED
        result = task.change_status(UptimeCheckTask.Status.RUNNING)
        assert result == "success"
        assert task.status == UptimeCheckTask.Status.RUNNING
        result = task.change_status(UptimeCheckTask.Status.STOPED)
        assert result == "success"
        assert task.status == UptimeCheckTask.Status.STOPED
        assert task.save.call_count == 4
        task.switch_off_subscription.assert_called_once()
        task.switch_on_subscription.assert_called_once()
        task.start_subscription.assert_called_once()
        task.stop_subscription.assert_called_once()
        assert strategy_func.call_count == 2
        strategy_func.stop()

    def test_wrong_change(self, mocker):
        wrong_status = "wrong"
        with pytest.raises(CustomException) as e:
            task = mock_change_status_flow()
            task.change_status(wrong_status)
        assert e.value.message == _("更改拨测任务状态：无效的目标状态：%s") % wrong_status

    def test_empty_status(self, mocker):
        with pytest.raises(CustomException) as e:
            task = mock_change_status_flow()
            task.change_status("")
        assert e.value.message == _("更改拨测任务状态：目标状态为空")
