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
from django.conf import settings
from mock import Mock

from monitor_web.collecting.constant import CollectStatus
from monitor_web.models.uptime_check import UptimeCheckTask

pytestmark = pytest.mark.django_db


def mock_create_flow():
    # 不提供订阅id
    task = UptimeCheckTask(pk=123, bk_biz_id=123, subscription_id=0)
    task.save = Mock()
    # 走新增流程
    task.create_subscription = Mock()
    task.create_subscription.return_value = {"subscription_id": 3}
    return task


def mock_update_flow():
    # 提供订阅id
    task = UptimeCheckTask(pk=123, bk_biz_id=123, subscription_id=123)
    task.save = Mock()
    # 走更新流程
    task.switch_off_subscription = Mock()
    task.update_subscription = Mock()
    task.switch_on_subscription = Mock()

    return task


def mock_others(mocker):
    strategy_func = mocker.patch("monitor_web.uptime_check.resources.SwitchStrategyByTaskIDResource.perform_request")
    append_metric_list_cache = mocker.patch("monitor_web.tasks.append_metric_list_cache.delay")
    subscription_instance_status = mocker.patch(
        "api.node_man.default.SubscriptionInstanceStatusResource.perform_request"
    )
    subscription_instance_status.return_value = [{"status": CollectStatus.SUCCESS}]
    return strategy_func, append_metric_list_cache, subscription_instance_status


# @pytest.mark.django_db
# class TestTaskDeploy(object):
#     # 测试插件测试流程是否正常执行
# def test_create(self, mocker):
#     settings.CELERY_ALWAYS_EAGER = True
#     task = mock_create_flow()
#     strategy_func, append_metric_list_cache, subscription_instance_status = mock_others(mocker)
#
#     strategy_func.start()
#     append_metric_list_cache.start()
#     subscription_instance_status.start()
#     result = task.deploy()
#     assert result == "success"
#     strategy_func.assert_called_once()
#     append_metric_list_cache.assert_called_once()
#     assert task.save.call_count == 2
#     task.create_subscription.assert_called_once()
#
#     strategy_func.stop()
#     append_metric_list_cache.stop()
#     subscription_instance_status.stop()
#
# # 测试部署流程是否正常执行
# def test_update(self, mocker):
#     settings.CELERY_ALWAYS_EAGER = True
#     task = mock_update_flow()
#     strategy_func, append_metric_list_cache, subscription_instance_status = mock_others(mocker)
#
#     strategy_func.start()
#     append_metric_list_cache.start()
#     subscription_instance_status.start()
#     result = task.deploy()
#     assert result == "success"
#     strategy_func.assert_called_once()
#     append_metric_list_cache.assert_called_once()
#     assert task.save.call_count == 2
#     task.switch_off_subscription.assert_called_once()
#     task.switch_on_subscription.assert_called_once()
#     task.update_subscription.assert_called_once()
#
#     strategy_func.stop()
#     append_metric_list_cache.stop()
#     subscription_instance_status.stop()
