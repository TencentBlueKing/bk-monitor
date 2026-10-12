"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib
import sys
import types
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def rabbitmq_story_module():
    package_name = "alarm_backends.management.story"
    module_names = [package_name, f"{package_name}.base", f"{package_name}.rabbitmq_story"]
    missing = object()
    previous_modules = {name: sys.modules.get(name, missing) for name in module_names}
    management_package = importlib.import_module("alarm_backends.management")
    previous_story_attribute = getattr(management_package, "story", missing)

    package = types.ModuleType(package_name)
    package.__path__ = [str(Path(__file__).parents[1] / "management" / "story")]
    sys.modules[package_name] = package
    try:
        yield importlib.import_module(f"{package_name}.rabbitmq_story")
    finally:
        for name, previous_module in previous_modules.items():
            if previous_module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module
        if previous_story_attribute is missing:
            vars(management_package).pop("story", None)
        else:
            management_package.story = previous_story_attribute


def build_queue(name, messages, messages_ready, messages_unacknowledged):
    return {
        "name": name,
        "messages": messages,
        "messages_details": {"rate": 0},
        "messages_ready": messages_ready,
        "messages_ready_details": {"rate": 0},
        "messages_unacknowledged": messages_unacknowledged,
        "messages_unacknowledged_details": {"rate": 0},
        "message_stats": {"publish_details": {"rate": 0}},
    }


@pytest.mark.parametrize("queue_name", ["celery_running_action", "custom-celery_running_action"])
def test_running_action_high_unack_does_not_report_blocking(rabbitmq_story_module, queue_name):
    step = rabbitmq_story_module.TableSpace(mock.Mock())
    queue = build_queue(
        name=queue_name,
        messages=20_001,
        messages_ready=0,
        messages_unacknowledged=20_001,
    )

    assert step._check_queue(queue, water_level=10_000) is None


def test_running_action_high_ready_reports_ready_blocking(rabbitmq_story_module):
    step = rabbitmq_story_module.TableSpace(mock.Mock())
    queue = build_queue(
        name="celery_running_action",
        messages=20_001,
        messages_ready=20_001,
        messages_unacknowledged=0,
    )

    problem = step._check_queue(queue, water_level=10_000)

    assert isinstance(problem, rabbitmq_story_module.Blocking)
    assert str(problem) == "queue[celery_running_action] maybe blocking: message ready: 20001"


def test_other_queue_keeps_total_blocking_rule(rabbitmq_story_module):
    step = rabbitmq_story_module.TableSpace(mock.Mock())
    queue = build_queue(
        name="celery_service",
        messages=20_001,
        messages_ready=0,
        messages_unacknowledged=20_001,
    )

    problem = step._check_queue(queue, water_level=10_000)

    assert isinstance(problem, rabbitmq_story_module.Blocking)
    assert str(problem) == "queue[celery_service] maybe blocking: message total: 20001"


def test_get_rabbitmq_management_host_falls_back_to_amqp_host(monkeypatch):
    from config.tools.rabbitmq import get_rabbitmq_management_host

    monkeypatch.delenv("BK_MONITOR_RABBITMQ_MANAGEMENT_HOST", raising=False)
    monkeypatch.delenv("RABBITMQ_MANAGEMENT_HOST", raising=False)

    assert get_rabbitmq_management_host("amqp.example.com", backend=True) == "amqp.example.com"


def test_get_rabbitmq_management_host_uses_backend_env(monkeypatch):
    from config.tools.rabbitmq import get_rabbitmq_management_host

    monkeypatch.setenv("BK_MONITOR_RABBITMQ_MANAGEMENT_HOST", "mgmt.example.com")
    monkeypatch.setenv("RABBITMQ_MANAGEMENT_HOST", "other.example.com")

    assert get_rabbitmq_management_host("amqp.example.com", backend=True) == "mgmt.example.com"


def test_get_rabbitmq_management_host_backend_falls_back_to_shared_env(monkeypatch):
    from config.tools.rabbitmq import get_rabbitmq_management_host

    monkeypatch.delenv("BK_MONITOR_RABBITMQ_MANAGEMENT_HOST", raising=False)
    monkeypatch.setenv("RABBITMQ_MANAGEMENT_HOST", "mgmt.example.com")

    assert get_rabbitmq_management_host("amqp.example.com", backend=True) == "mgmt.example.com"


def test_healthz_uses_management_host_for_queues_url(rabbitmq_story_module):
    step = rabbitmq_story_module.TableSpace(mock.Mock())
    story = mock.Mock()
    step.story = story
    response = mock.Mock()
    response.status_code = 200
    response.json.return_value = []

    with mock.patch.object(
        rabbitmq_story_module,
        "settings",
        mock.Mock(
            RABBITMQ_HOST="amqp.example.com",
            RABBITMQ_MANAGEMENT_HOST="mgmt.example.com",
            RABBITMQ_VHOST="bkmonitor",
            RABBITMQ_USER="user",
            RABBITMQ_PASS="pass",
            IS_CONTAINER_MODE=True,
        ),
    ), mock.patch.object(rabbitmq_story_module.requests, "get", return_value=response) as get_mock, mock.patch.object(
        rabbitmq_story_module.StrategyCacheManager, "get_strategy_ids", return_value=[]
    ):
        step.check()

    get_mock.assert_called_once()
    assert get_mock.call_args[0][0] == "http://mgmt.example.com:15672/api/queues/bkmonitor"
