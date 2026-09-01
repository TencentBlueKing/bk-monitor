from types import SimpleNamespace

from elasticsearch_dsl import AttrDict

from alarm_backends.core.context.alarm import Alarm
from bkmonitor.utils.template import CustomTemplateRenderer, Jinja2Renderer
from monitor_web.strategies.constant import ValueableList
from constants.alert import EventStatus


class AlertStub:
    def __init__(self, status=EventStatus.ABNORMAL, no_data=False):
        self.status = status
        self._no_data = no_data

    def is_no_data(self):
        return self._no_data


def build_alarm(*, status=EventStatus.ABNORMAL, no_data=False):
    ref_values = {"A": {"value": 42, "state": "SUCCESS"}, "C": {"value": 4.2, "state": "SUCCESS"}}
    parent = SimpleNamespace(
        alert=AlertStub(status=status, no_data=no_data),
        anomaly_record=SimpleNamespace(
            extra_info=SimpleNamespace(
                origin_alarm=SimpleNamespace(data=SimpleNamespace(value=4.2, ref_values=AttrDict(ref_values)))
            )
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


def test_alarm_ref_values_can_be_rendered_with_safe_get_access():
    alarm, _ = build_alarm()

    rendered = Jinja2Renderer.render(
        '{{ alarm.ref_values.get("A", {}).get("value") }}|{{ alarm.ref_values.get("A", {}).get("state") }}',
        {"alarm": alarm},
    )

    assert rendered == "42|SUCCESS"


def test_alarm_ref_values_can_be_rendered_by_custom_notice_template():
    alarm, _ = build_alarm()
    context = {
        "action": None,
        "alarm": alarm,
        "notice_way": "rtx",
        "content_template": (
            'A={{ alarm.ref_values.get("A", {}).get("value", "--") }}；'
            'C={{ alarm.ref_values.get("C", {}).get("value", alarm.current_value) }}'
        ),
        "default_content_template": "fallback",
        "title_template": "",
        "default_title_template": "default title",
    }

    CustomTemplateRenderer.render("", context)

    assert context["user_content"] == "A=42；C=4.2"


def test_notice_variable_list_documents_alarm_ref_values_get_usage():
    alarm_variables = next(group for group in ValueableList.VALUEABLELIST if group["id"] == "ALARM_VAR")

    ids = {item["id"] for item in alarm_variables["items"]}
    assert 'alarm.ref_values.get("reference_name", {}).get("value")' in ids
    assert 'alarm.ref_values.get("reference_name", {}).get("state")' in ids
