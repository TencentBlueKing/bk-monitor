from types import SimpleNamespace

import pytest
from elasticsearch_dsl import AttrDict

from alarm_backends.core.context.alarm import Alarm
from bkmonitor.utils.template import CustomTemplateRenderer, Jinja2Renderer
from bkmonitor.utils.template_ref_values import RefValueTemplateError
from monitor_web.strategies.constant import ValueableList
from constants.alert import EventStatus


class AlertStub:
    def __init__(self, status=EventStatus.ABNORMAL, no_data=False):
        self.status = status
        self._no_data = no_data
        self.strategy = {
            "items": [{"query_output_config": {"output_list": [{"reference_name": "A"}, {"reference_name": "C"}]}}]
        }

    def is_no_data(self):
        return self._no_data


def build_alarm(*, status=EventStatus.ABNORMAL, no_data=False):
    ref_values = {"A": {"value": 42, "state": "SUCCESS"}, "C": {"value": 4.2, "state": "SUCCESS"}}
    parent = SimpleNamespace(
        alert=AlertStub(status=status, no_data=no_data),
        anomaly_record=SimpleNamespace(
            extra_info=AttrDict({"origin_alarm": {"data": {"value": 4.2, "ref_values": ref_values}}})
        ),
        action=None,
    )
    return Alarm(parent), ref_values


def test_alarm_ref_values_reads_same_anomaly_snapshot_as_current_value():
    alarm, ref_values = build_alarm()

    assert alarm.current_value == 4.2
    assert alarm.ref_values == ref_values


def test_alarm_ref_values_is_empty_for_recovery_and_nodata():
    recovered, _ = build_alarm(status=EventStatus.RECOVERED)
    no_data, _ = build_alarm(no_data=True)

    assert recovered.ref_values == {}
    assert no_data.ref_values == {}


def test_alarm_ref_values_is_empty_for_legacy_anomaly_without_snapshot():
    parent = SimpleNamespace(
        alert=AlertStub(),
        anomaly_record=SimpleNamespace(
            extra_info=SimpleNamespace(origin_alarm=SimpleNamespace(data=SimpleNamespace(value=4.2)))
        ),
        action=None,
    )

    assert Alarm(parent).ref_values == {}


def test_alarm_ref_values_can_be_rendered_with_static_case_compatible_access():
    alarm, _ = build_alarm()

    rendered = Jinja2Renderer.render(
        "{{ alarm.ref_values.a.value }}|{{ alarm.ref_values.A.state }}",
        {"alarm": alarm},
    )

    assert rendered == "42|SUCCESS"


def test_alarm_ref_values_can_be_rendered_by_custom_notice_template():
    alarm, _ = build_alarm()
    context = {
        "action": None,
        "alarm": alarm,
        "notice_way": "rtx",
        "content_template": ("A={{ alarm.ref_values.a.value }}；C={{ alarm.ref_values.c.value }}"),
        "default_content_template": "fallback",
        "title_template": "",
        "default_title_template": "default title",
    }

    CustomTemplateRenderer.render("", context)

    assert context["user_content"] == "A=42；C=4.2"


def test_notice_variable_list_documents_only_static_reference_leaves():
    alarm_variables = next(group for group in ValueableList.VALUEABLELIST if group["id"] == "ALARM_VAR")

    ids = {item["id"] for item in alarm_variables["items"]}
    assert "alarm.ref_values.a.value" in ids
    assert "alarm.ref_values.a.state" in ids
    assert not any("ref_values.get" in name or name == "alarm.ref_values" for name in ids)


def test_runtime_whitelist_uses_evaluated_strategy_instead_of_latest_definition():
    alarm, _ = build_alarm()
    alarm.parent.anomaly_record.extra_info.strategy = {
        "items": [{"query_output_config": {"output_list": [{"reference_name": "C"}]}}]
    }
    assert Jinja2Renderer.render("{{alarm.ref_values.c.value}}", {"alarm": alarm}) == "4.2"
    with pytest.raises(RefValueTemplateError, match="unconfigured"):
        Jinja2Renderer.render("{{alarm.ref_values.A.value}}", {"alarm": alarm})


def test_runtime_reuses_matching_persisted_snapshot_after_cache_expiry(mocker):
    from alarm_backends.core.control.strategy import Strategy

    alarm, _ = build_alarm()
    alarm.parent.alert.origin_alarm = {"strategy_snapshot_key": "same-snapshot"}
    alarm.parent.anomaly_record.extra_info.origin_alarm.strategy_snapshot_key = "same-snapshot"
    lookup = mocker.patch.object(Strategy, "get_strategy_snapshot_by_key", return_value=None)
    assert Jinja2Renderer.render("{{alarm.ref_values.a.value}}", {"alarm": alarm}) == "42"
    lookup.assert_not_called()


def test_runtime_does_not_bind_a_different_expired_snapshot_to_alert_config(mocker):
    from alarm_backends.core.control.strategy import Strategy

    alarm, _ = build_alarm()
    alarm.parent.alert.origin_alarm = {"strategy_snapshot_key": "old-snapshot"}
    alarm.parent.anomaly_record.strategy_id = 1
    alarm.parent.anomaly_record.extra_info.origin_alarm.strategy_snapshot_key = "new-snapshot"
    mocker.patch.object(Strategy, "get_strategy_snapshot_by_key", return_value=None)
    with pytest.raises(RefValueTemplateError, match="unconfigured"):
        Jinja2Renderer.render("{{alarm.ref_values.a.value}}", {"alarm": alarm})


def test_internal_alarm_parent_is_not_a_template_escape_path():
    alarm, _ = build_alarm()
    with pytest.raises(RefValueTemplateError, match="internal"):
        Jinja2Renderer.render("{{alarm.parent.anomaly_record.extra_info.origin_alarm.data}}", {"alarm": alarm})
