import json

import pytest

from alarm_backends.core.context.alarm import Alarm


def test_reads_full_log_record():
    alarm = Alarm(parent=None)
    record = {"log": "x" * 2048, "bklog_link": "/retrieve/example"}
    alarm.log_raw_related_info = json.dumps(record)
    assert alarm.log_related_fields == record


@pytest.mark.parametrize("raw", ["", "plain text", "[]"])
def test_missing_log_record(raw):
    alarm = Alarm(parent=None)
    alarm.log_raw_related_info = raw
    assert alarm.log_related_fields == {}
