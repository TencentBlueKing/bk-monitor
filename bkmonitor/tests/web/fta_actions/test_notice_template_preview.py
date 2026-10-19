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

    assert "alarm.ref_values" not in by_name
    assert by_name["alarm.ref_values.a.value"]["example"] == "4"
    assert by_name["alarm.ref_values.a.state"]["example"] == "SUCCESS"
    assert not any("ref_values.get" in name for name in by_name)


def preview_config():
    return {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": name, "expression": expression}
            for name, expression in (("A", "a"), ("B", "b"), ("C", "c"), ("RESULT", "a + b"))
        ],
    }


@pytest.fixture
def preview(monkeypatch):
    notice_ways = ("weixin", "qy_weixin", "mail", "sms", "voice", "wxwork-bot")
    monkeypatch.setattr(
        frontend_resources.api.cmsi,
        "get_msg_type",
        lambda: [{"type": way, "label": way, "is_active": True} for way in notice_ways],
    )

    def render(template, **params):
        with translation.override("zh-hans"):
            result = frontend_resources.RenderNoticeTemplate().perform_request(
                {"template": template, "query_output_config": preview_config(), **params}
            )
        assert len(result) == len(notice_ways)
        assert all(len(channel["messages"]) == 2 for channel in result)
        return [{"channel": channel["type"], **message} for channel in result for message in channel["messages"]]

    return render


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        (
            "A={{ alarm.ref_values.a.value }};"
            "B={{ alarm.ref_values.b.value }};"
            "C={{ alarm.ref_values.c.value }};"
            "RESULT={{ alarm.ref_values.result.value }}",
            "A=4;B=6;C=9;RESULT=10",
        ),
        ("{{ alarm.ref_values.a.state }}", "SUCCESS"),
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
        Jinja2Renderer.render(
            "{{ alarm.ref_values.a.value }}",
            {"alarm": {"ref_values": {}}, "_query_output_config": preview_config()},
        )
        == "--"
    )


@pytest.mark.parametrize(
    "template", ["{{alarm.ref_values}}", "{{alarm.ref_values.UNKNOWN.value}}", '{{alarm.ref_values.get("A")}}']
)
def test_preview_rejects_unconfigured_or_non_static_references(preview, template):
    assert all(message["error"] for message in preview(template))


def test_preview_does_not_grant_fixed_demo_names_without_config(preview):
    assert all(message["error"] for message in preview("{{alarm.ref_values.A.value}}", query_output_config=None))


def test_preview_accepts_custom_configured_names(preview):
    config = preview_config()
    config["output_list"][0]["reference_name"] = "ErrorRate"
    for message in preview("{{alarm.ref_values.errorrate.state}}", query_output_config=config):
        assert not message["error"]
