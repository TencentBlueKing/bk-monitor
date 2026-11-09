"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget
from bkmonitor.data_source.unify_query.builder import QueryHelper
from rum_web.handlers.builder.timeline import SESSION_MAX_DURATION_US, session_summary
from rum_web.handlers.level.span import SpanLevelHandler


START = 1_800_000_000_000_000


@pytest.mark.parametrize(
    "start,end,observed_start,observed_end,age,status,duration",
    [
        (START, START + 1_500_000, START - 1000, START + 2_000_000, 5 * 3600, "ended", 1500),
        (START, None, START, START + 459_000_000, 3600, "active", 459000),
        (START, None, START, START + 459_000_000, 4 * 3600 - 0.001, "active", 459000),
        (START, None, START, START + 459_000_000, 4 * 3600, "expired", 459000),
        (None, None, START, START + 1000, 4 * 3600, "expired", 1),
        (None, None, START, START + 1000, 1200, "active", 1),
        (None, START + 1000, START, START + 2000, 3600, "ended", 2),
        (START, START, START, START, 0, "ended", 0),
        (START, START - 1, START, START + 1000, 0, "ended", None),
        (START, None, START, START - 1, 0, "active", None),
        (None, None, None, None, 3600, None, None),
        (None, None, START, None, 3600, "active", None),
    ],
)
def test_session_status_and_duration(mocker, start, end, observed_start, observed_end, age, status, duration):
    mocker.patch("rum_web.handlers.builder.timeline.time.time", return_value=START / 1_000_000 + age)

    result = session_summary(
        {"start_time": start, "end_time": end, "observed_start": observed_start, "observed_end": observed_end}
    )

    assert result == {"start_time": start, "end_time": end, "duration": duration, "session_status": status}


def _handler():
    return SpanLevelHandler(
        [TraceDatasourceTarget.build(bk_biz_id=2, app_name="rum-demo", table_id="bk_rum.demo.span")]
    )


def test_expiration_uses_lifecycle_start_and_late_end_corrects_summary(mocker):
    mocker.patch("rum_web.handlers.builder.timeline.time.time", return_value=(START + SESSION_MAX_DURATION_US) / 1e6)
    period = {"start_time": START, "end_time": None, "observed_start": START - 10_000_000, "observed_end": START}

    assert session_summary(period)["session_status"] == "expired"
    period["end_time"] = START + 60_000_000
    assert session_summary(period)["session_status"] == "ended"
    assert session_summary(period)["duration"] == 60000


def test_summary_retrieves_global_boundaries_outside_node_limit(mocker):
    handler = _handler()
    mocker.patch("rum_web.handlers.builder.timeline.time.time", return_value=(START + 10_000_000) / 1e6)
    query = mocker.patch.object(
        handler.query,
        "query_list",
        side_effect=[
            [],  # 时间线节点已截断或不满足 View 组装条件，不参与摘要。
            [{"start_time": START}],
            [{"end_time": START + 459_000_000}],
            [{"start_time": START - 1000}],
            [{"end_time": START + 460_000_000}],
        ],
    )

    result = handler.timeline(session_id="session-1")

    assert result == {
        "start_time": START,
        "end_time": START + 459_000_000,
        "duration": 459000,
        "session_status": "ended",
        "tree": [],
        "records": [],
    }
    calls = [call.kwargs for call in query.call_args_list]
    assert [call["limit"] for call in calls] == [10000, 1, 1, 1, 1]
    assert [call["sort"] for call in calls[1:]] == [
        ["start_time", "span_id"],
        ["-end_time", "span_id"],
        ["start_time", "span_id"],
        ["-end_time", "span_id"],
    ]
    scope = {"key": "attributes.session.id", "value": ["session-1"], "operator": FilterOperator.EQUAL}
    for call in calls:
        assert call["start_time"] is None and call["end_time"] is None
        assert scope in call["filters"]
    assert calls[1]["filters"][-2]["value"] == ["start", "rotate"]
    assert calls[2]["filters"][-2]["value"] == ["end"]
    for call, field in zip(calls[1:], ["start_time", "end_time", "start_time", "end_time"]):
        assert call["filters"][-1] == {"key": field, "value": [""], "operator": FilterOperator.EXISTS}


@pytest.mark.parametrize("value", [None, "invalid", "nan", float("inf"), float("-inf")])
def test_invalid_boundaries_remain_null(mocker, value):
    handler = _handler()
    mocker.patch.object(handler.query, "query_list", return_value=[{"start_time": value, "end_time": value}])

    result = handler.query.query_session_time_range("session-1")

    assert result == {"start_time": None, "end_time": None, "observed_start": None, "observed_end": None}


def test_summary_queries_preserve_application_table_scope_and_retention(mocker):
    query = _handler().query
    mocker.patch.object(query, "_get_time_range", return_value=(1000, 2000))
    execute = mocker.patch.object(QueryHelper, "query", return_value=[])

    assert query.query_session_time_range("session-1") == {
        "start_time": None,
        "end_time": None,
        "observed_start": None,
        "observed_end": None,
    }

    bodies = [call.kwargs["query_body"] for call in execute.call_args_list]
    assert len(bodies) == 4
    for body in bodies:
        assert body["bk_biz_id"] == 2
        assert body["start_time"] == 1000 and body["end_time"] == 2000
        assert body["offset"] == 0 and body["limit"] == 1
        assert len(body["query_configs"]) == 1
        config = body["query_configs"][0]
        assert config["table"] == "bk_rum.demo.span"
        assert config["filter_dict"]["attributes.session.id__eq"] == ["session-1"]
    assert bodies[0]["query_configs"][0]["filter_dict"]["attributes.session.phase__eq"] == ["start", "rotate"]
    assert bodies[1]["query_configs"][0]["filter_dict"]["attributes.session.phase__eq"] == ["end"]
