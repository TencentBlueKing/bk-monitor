"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone, translation

from alarm_backends.core.cache.cmdb import BusinessManager, HostManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.mixins.double_check import DoubleCheckStrategy
from api.cmdb.define import Business
from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.models import ActionInstance, GlobalConfig
from bkmonitor.utils.sms import format_sms_time, render_standard_sms, sms_utf16_length
from constants.action import ActionStatus, NoticeWay
from fta_web.action import tasks, utils
from fta_web.action.resources import backend_resources, frontend_resources

ASSIGN_TIME = int(datetime(2026, 1, 2, 3, 4, tzinfo=datetime_timezone.utc).timestamp())
NOTICE_WAYS = [NoticeWay.SMS, NoticeWay.MAIL, NoticeWay.WX_BOT]


def make_alert(alert_id="alert-1", name="测试告警", bk_biz_id=2):
    return AlertDocument(
        id=alert_id,
        alert_name=name,
        severity=2,
        strategy_id=0,
        begin_time=ASSIGN_TIME - 60,
        latest_time=ASSIGN_TIME - 60,
        create_time=ASSIGN_TIME - 60,
        status="ABNORMAL",
        appointee=["responder"],
        assignee=["responder"],
        event=EventDocument(
            bk_biz_id=bk_biz_id,
            bk_tenant_id="tenant-a",
            time=ASSIGN_TIME - 60,
            description="原始告警内容",
            category="application",
            severity=2,
            alert_name=name,
            tags=[{"key": DoubleCheckStrategy.DOUBLE_CHECK_CONTEXT_KEY, "value": "SUSPECTED_MISSING_POINTS"}],
        ),
    )


def make_data(count=1, name="测试告警"):
    return {
        "bk_biz_id": "2",
        "operator": "operator",
        "appointees": ["responder"],
        "notice_receivers": ["responder"],
        "alert_ids": [f"alert-{index + 1}" for index in range(count)],
        "reason": "请协助处理",
        "notice_ways": list(NOTICE_WAYS),
        "current_time": ASSIGN_TIME,
        "sms_assign_time": format_sms_time(ASSIGN_TIME, tz=ZoneInfo("Asia/Shanghai"), language="zh-hans"),
        "sms_assign_alert": {"name": name, "severity": 2, "count": count},
    }


@pytest.fixture
def assignment(mocker, settings):
    settings.DEFAULT_LOCALE = "zh-hans"
    settings.NOTICE_MESSAGE_MAX_LENGTH = {}
    settings.SMS_CONTENT_LENGTH = 0
    settings.MD_SUPPORTED_NOTICE_WAYS = [NoticeWay.WX_BOT]
    settings.WXWORK_BOT_WEBHOOK_URL = "https://example.com/webhook"
    settings.WXWORK_BOT_SEND_IMAGE = False
    mode = mocker.patch.object(tasks, "get_sms_template_mode", return_value="standard")
    compile_mode = mocker.patch.object(utils, "get_sms_template_mode", side_effect=AssertionError("mode read twice"))
    tenant = mocker.patch.object(tasks, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(
        GlobalConfig, "get", side_effect=lambda key, default=None: "蓝鲸监控" if key == "NOTICE_TITLE" else default
    )
    mocker.patch.object(StrategyCacheManager, "get_strategy_by_id", return_value={})
    mocker.patch.object(BusinessManager, "get", return_value=Business(bk_biz_id=2, bk_biz_name="测试业务"))
    mocker.patch.object(HostManager, "get", return_value=None)
    mget = mocker.patch.object(AlertDocument, "mget", return_value=[make_alert()])
    save = mocker.patch.object(ActionInstance, "save")
    created = []

    def create_action(**kwargs):
        action = ActionInstance(id=301, **kwargs)
        created.append(action)
        return action

    mocker.patch.object(ActionInstance.objects, "create", side_effect=create_action)
    mocker.patch.object(ActionInstance.objects, "get", side_effect=lambda **kwargs: created[-1])
    rendered = []

    def render_params(data):
        # Exercise the existing API renderer without adding fields to its context contract.
        result = backend_resources.GetActionParamsByConfigResource().perform_request(data)
        rendered.append(copy.deepcopy(result))
        return result

    params_api = mocker.patch.object(tasks.api.monitor, "get_action_params_backend", side_effect=render_params)
    result = {"username_check": {"invalid": []}, "message": "OK"}
    sms = mocker.patch("bkmonitor.utils.send.api.cmsi.send_sms", return_value=result)
    mail = mocker.patch("bkmonitor.utils.send.api.cmsi.send_mail", return_value=result)
    post = mocker.patch("bkmonitor.utils.send.requests.post")
    post.return_value.json.return_value = {"errcode": 0, "errmsg": "ok"}
    yield SimpleNamespace(
        mode=mode,
        compile_mode=compile_mode,
        tenant=tenant,
        mget=mget,
        created=created,
        rendered=rendered,
        params_api=params_api,
        sms=sms,
        mail=mail,
        post=post,
        save=save,
    )


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("sms_limit", [50, 70, 100])
def test_standard_assignment_uses_event_snapshot_and_real_send(assignment, settings, count, sms_limit):
    settings.SMS_CONTENT_LENGTH = sms_limit
    data = make_data(count)
    assignment.mget.return_value = [make_alert(f"alert-{index + 1}") for index in range(count)]

    with translation.override("en"):
        tasks.notify_to_appointee(data)

    expected = render_standard_sms(
        "assign/converge" if count > 1 else "assign/action",
        {"time": data["sms_assign_time"], "level": "预警", "count": count, "name": "测试告警"},
        language="zh-hans",
    )
    assert assignment.sms.call_args.kwargs["content"] == expected
    assert data["sms_assign_time"] in expected
    assert "预警" in expected
    assert "疑似异常" not in expected
    assert sms_utf16_length(expected) <= 70
    assert assignment.sms.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assert assignment.mail.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assignment.tenant.assert_called_once_with("2")
    assignment.mode.assert_called_once_with()
    assignment.compile_mode.assert_not_called()
    assert assignment.created[-1].status == ActionStatus.SUCCESS
    assert list(assignment.created[-1].outputs["notice_results"]) == NOTICE_WAYS
    assert len(assignment.rendered[-1]["action_configs"]) == len(NOTICE_WAYS)
    assert set(assignment.params_api.call_args.args[0]) == {"action_configs", "alert_ids", "action_id", "bk_biz_id"}
    for config in assignment.rendered[-1]["action_configs"]:
        way = config["execute_config"]["context_inputs"]["notice_way"]
        message = config["execute_config"]["template_detail"]["message"]
        if way == NoticeWay.SMS:
            assert message == assignment.sms.call_args.kwargs["content"]
        elif way == NoticeWay.MAIL:
            assert message == assignment.mail.call_args.kwargs["content"]
        else:
            assert assignment.post.call_args.kwargs["json"]["markdown"]["content"] == message


@pytest.mark.parametrize("name", ['A{{7*7}}"\\', "{% endraw %}{{7*7}}"])
def test_assignment_literal_is_safe_with_existing_api_renderer(assignment, name):
    data = make_data(name=name)
    assignment.mget.return_value = [make_alert(name=name)]

    tasks.notify_to_appointee(data)

    body = assignment.sms.call_args.kwargs["content"]
    assert name in body
    assert "49" not in body
    assert "{{ content.standard_assign_sms }}" not in body
    assert assignment.rendered[-1]["action_configs"][0]["execute_config"]["template_detail"]["message"] == body


@pytest.mark.parametrize("count", [1, 2])
def test_assignment_preserves_legacy_and_other_channel_content(assignment, count):
    data = make_data(count)
    assignment.mget.return_value = [make_alert(f"alert-{index + 1}") for index in range(count)]

    with translation.override("zh-hans"):
        tasks.notify_to_appointee(copy.deepcopy(data))
        standard_mail = assignment.mail.call_args.kwargs.copy()
        standard_bot = assignment.post.call_args.kwargs["json"].copy()
        assignment.mode.return_value = "legacy"
        tasks.notify_to_appointee(copy.deepcopy(data))

    assert assignment.mail.call_args.kwargs == standard_mail
    assert assignment.post.call_args.kwargs["json"] == standard_bot
    legacy_message = assignment.rendered[-1]["action_configs"][0]["execute_config"]["template_detail"]["message"]
    assert assignment.sms.call_args.kwargs["content"] == legacy_message
    expected_content = "内容: 已持续1m, 原始告警内容\n所属空间: [2]测试业务 (业务)\n目标: \n告警ID: alert-1"
    if count == 1:
        expected_legacy = (
            "蓝鲸监控通知，operator给您分派了告警【{alarm.name}({alarm.id})】\n"
            "分派原因: 请协助处理\n负责人: responder\n"
            "operator给您分派了告警【{alarm.name}({alarm.id})】\n" + expected_content
        )
    else:
        expected_legacy = (
            "分派原因: 请协助处理\n负责人: responder\n代表：--\n"
            "operator给您分派了【测试告警】等2个告警\n" + expected_content
        )
    assert legacy_message == expected_legacy
    assert data["sms_assign_time"] not in legacy_message
    assert assignment.sms.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assert assignment.mail.call_args.kwargs["bk_tenant_id"] == "tenant-a"


def test_old_assignment_task_loads_only_effective_business_alerts(assignment):
    data = make_data(count=3)
    data.pop("sms_assign_alert")
    data.pop("sms_assign_time")
    assignment.mget.return_value = [make_alert("other", name="其他业务", bk_biz_id=3), make_alert()]

    tasks.notify_to_appointee(data)

    assert data["sms_assign_alert"] == {"name": "测试告警", "severity": 2, "count": 1}
    body = assignment.sms.call_args.kwargs["content"]
    assert "时间未知" in body
    assert "测试告警" in body
    assert "其他业务" not in body


def test_old_assignment_task_without_effective_alerts_does_not_make_up_content(assignment):
    data = make_data()
    data.pop("sms_assign_alert")
    assignment.mget.return_value = [make_alert(bk_biz_id=3)]

    tasks.notify_to_appointee(data)

    assert assignment.created == []
    assignment.params_api.assert_not_called()
    assignment.sms.assert_not_called()


def test_assign_entry_captures_time_and_effective_alert_snapshot(mocker, settings):
    settings.DEFAULT_LOCALE = "zh-hans"
    data = make_data()
    for key in ("sms_assign_alert", "sms_assign_time", "current_time"):
        data.pop(key)
    data["alert_ids"] = ["other", "alert-1"]
    alert = make_alert()
    alert.appointee = []
    alert.assignee = []
    mocker.patch.object(frontend_resources, "get_request_username", return_value="operator")
    mocker.patch.object(frontend_resources, "get_user_display_name", side_effect=lambda name: name)
    mocker.patch.object(AlertDocument, "mget", return_value=[make_alert("other", bk_biz_id=3), alert])
    mocker.patch.object(AlertDocument, "bulk_create")
    logs = mocker.patch.object(frontend_resources.AlertLog, "bulk_create")
    mocker.patch.object(frontend_resources.time, "time", return_value=ASSIGN_TIME)
    queued = mocker.patch.object(tasks.notify_to_appointee, "delay")

    with timezone.override(ZoneInfo("America/New_York")):
        frontend_resources.AssignAlertResource().perform_request(data)

    queued_data = queued.call_args.args[0]
    assert queued_data["current_time"] == ASSIGN_TIME
    assert queued_data["sms_assign_time"] == "2026年1月1日 22:04分"
    assert queued_data["sms_assign_alert"] == {"name": "测试告警", "severity": 2, "count": 1}
    assert queued_data["alert_ids"] == ["alert-1"]
    assert logs.call_args.args[0][0].create_time == ASSIGN_TIME
