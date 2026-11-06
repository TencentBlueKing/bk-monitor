"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from unittest import mock

import arrow
import pytest

from monitor_web.grafana.resources.log import LogQueryResource


@pytest.mark.parametrize(
    ("time_value", "expected"),
    [
        pytest.param(0, 0, id="zero"),
        pytest.param(1791877020, 1791877020, id="seconds"),
        pytest.param("1791877020", 1791877020, id="seconds_string"),
        pytest.param("1791877020.128", 1791877020, id="fractional_seconds_string"),
        pytest.param(1791877020128, 1791877020, id="milliseconds"),
        pytest.param("1791877020128", 1791877020, id="milliseconds_string"),
        pytest.param("2026-10-13T07:37:00.128000000Z", 1791877020, id="iso_utc"),
        pytest.param(" 2026-10-13T07:37:00Z ", 1791877020, id="iso_surrounding_whitespace"),
        pytest.param("2026-10-13T15:37:00.128000000+08:00", 1791877020, id="iso_timezone_nanoseconds"),
        pytest.param("2026-10-13T07:37:00", 1791877020, id="iso_without_timezone"),
        pytest.param("2026-10-13", 1791849600, id="date_only"),
    ],
)
def test_log_time_parsing_preserves_other_record_fields(time_value: Any, expected: int) -> None:
    record = {"event_time": time_value, "message": "original log", "dimensions": {"service": "demo"}}
    with mock.patch("monitor_web.grafana.resources.log.arrow.now", return_value=arrow.get(1791877449)):
        timestamp = LogQueryResource.get_time(record, "event_time")

    assert type(timestamp) is int
    assert timestamp == expected
    assert record == {"message": "original log", "dimensions": {"service": "demo"}}


@pytest.mark.parametrize("time_value", ["invalid-time", {}])
def test_log_time_parsing_failure_falls_back_to_now(time_value: Any) -> None:
    record = {"event_time": time_value, "message": "original log"}
    with mock.patch("monitor_web.grafana.resources.log.arrow.now", return_value=arrow.get(1791877449)):
        timestamp = LogQueryResource.get_time(record, "event_time")

    assert timestamp == 1791877449
    assert record == {"message": "original log"}
