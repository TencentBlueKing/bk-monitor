from types import SimpleNamespace

from alarm_backends.core.context.alarm import Alarm
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
                origin_alarm=SimpleNamespace(data=SimpleNamespace(value=4.2, ref_values=ref_values))
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
