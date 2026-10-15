from copy import deepcopy

import pytest
from django.utils import translation

from bkmonitor.utils.template import Jinja2Renderer
from constants.action import DEMO_CONTEXT
from fta_web.action.resources import frontend_resources


def test_notice_variable_catalog_exposes_query_reference_values():
    groups = frontend_resources.GetVariablesResource().perform_request({})
    variables = next(group["items"] for group in groups if group["group"] == "ALARM_VAR")
    by_name = {variable["name"]: variable for variable in variables}

    assert by_name["alarm.ref_values"]["example"] == DEMO_CONTEXT["alarm"]["ref_values"]
    for field, default in (("value", "--"), ("state", "MISSING")):
        name = f'alarm.ref_values.get("A", {{}}).get("{field}", "{default}")'
        variable = by_name[name]
        assert Jinja2Renderer.render("{{ " + name + " }}", DEMO_CONTEXT) == str(variable["example"])


@pytest.fixture
def preview(monkeypatch):
    notice_ways = ("weixin", "qy_weixin", "mail", "sms", "voice", "wxwork-bot")
    monkeypatch.setattr(
        frontend_resources.api.cmsi,
        "get_msg_type",
        lambda: [{"type": way, "label": way, "is_active": True} for way in notice_ways],
    )

    def render(template):
        with translation.override("zh-hans"):
            result = frontend_resources.RenderNoticeTemplate().perform_request({"template": template})
        assert len(result) == len(notice_ways)
        assert all(len(channel["messages"]) == 2 for channel in result)
        return [{"channel": channel["type"], **message} for channel in result for message in channel["messages"]]

    return render


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ alarm.ref_values }}", "SUCCESS"),
        (
            'A={{ alarm.ref_values.get("A", {}).get("value", "--") }};'
            'B={{ alarm.ref_values.get("B", {}).get("value", "--") }};'
            'C={{ alarm.ref_values.get("C", {}).get("value", "--") }};'
            'RESULT={{ alarm.ref_values.get("RESULT", {}).get("value", "--") }}',
            "A=4;B=6;C=9;RESULT=10",
        ),
        ('{{ alarm.ref_values.get("A", {}).get("state", "MISSING") }}', "SUCCESS"),
        ('{{ alarm.ref_values.get("UNKNOWN", {}).get("value", "--") }}', "--"),
        ('{{ alarm.ref_values.get("UNKNOWN", {}).get("state", "MISSING") }}', "MISSING"),
        ("current={{ alarm.current_value }}", "current=10"),
        ("{{ content.level }}", "致命"),
    ],
)
def test_notice_preview_renders_reference_values_and_legacy_templates(preview, template, expected):
    for message in preview(template):
        assert not message["error"]
        if message["channel"] == "voice":
            # 语音沿用固定播报模板，不展示用户自定义正文。
            assert "致命告警" in message["message"]
        else:
            assert expected in message["message"]


def test_notice_preview_reports_invalid_template(preview):
    assert all(message["error"] for message in preview("{{ broken("))


def test_notice_preview_keeps_reference_examples_read_only(preview):
    reference_values = deepcopy(DEMO_CONTEXT["alarm"]["ref_values"])

    assert all(message["error"] for message in preview("{{ alarm.ref_values.clear() }}"))
    assert DEMO_CONTEXT["alarm"]["ref_values"] == reference_values


def test_demo_reference_values_preserve_missing_value_fallback():
    assert (
        Jinja2Renderer.render('{{ alarm.ref_values.get("A", {}).get("value", "--") }}', {"alarm": {"ref_values": {}}})
        == "--"
    )
