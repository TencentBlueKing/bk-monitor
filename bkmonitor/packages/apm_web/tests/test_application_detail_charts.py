"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

import pytest
from pytest_mock import MockerFixture

from apm_web.constants import AlertLevel, AlertStatus, Apdex, DataStatus
from apm_web.meta.resources import ApplicationInfoByAppNameResource
from apm_web.metric.resources import AlertQueryResource, ApdexQueryResource
from apm_web.models import Application, ApplicationRelationInfo

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "demo"
START_TIME = 1_700_000_000
END_TIME = START_TIME + 1800


@pytest.fixture
def application() -> Application:
    return Application.objects.create(
        application_id=1,
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        trace_data_status=DataStatus.NO_DATA,
        metric_result_table_id="demo.bk_apm_count",
    )


@pytest.fixture(autouse=True)
def forbid_data_probe(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "apm_web.metric_handler.RequestCountInstance.query_instance",
        side_effect=AssertionError("请求侧不应执行应用数据探测"),
    )


@pytest.mark.parametrize("data_status", [DataStatus.NORMAL, DataStatus.NO_DATA, DataStatus.DISABLED])
@pytest.mark.parametrize("with_time_range", [False, True])
def test_application_info_returns_persisted_status(
    application: Application,
    mocker: MockerFixture,
    forbid_data_probe: mock.Mock,
    data_status: str,
    with_time_range: bool,
) -> None:
    application.trace_data_status = data_status
    application.save(update_fields=["trace_data_status"])
    application.set_init_apdex_config()
    application.set_init_instance_name_config()
    application.set_init_sampler_config()
    application.set_init_event_config()
    ApplicationRelationInfo.add_relation(application.application_id, Application.PLUGING_KEY, "opentelemetry")
    mocker.patch("apm_web.meta.resources.SpanHandler.get_lastly_span", return_value={})
    request_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME}
    if with_time_range:
        request_data.update(start_time=START_TIME, end_time=END_TIME)

    response = ApplicationInfoByAppNameResource().request(request_data)

    assert response["trace_data_status"] == data_status
    assert response["application_id"] == application.application_id
    application.refresh_from_db()
    assert application.trace_data_status == data_status
    forbid_data_probe.assert_not_called()


@pytest.mark.parametrize("with_data", [False, True])
def test_apdex_queries_selected_range_without_data_probe(
    application: Application, mocker: MockerFixture, forbid_data_probe: mock.Mock, with_data: bool
) -> None:
    timestamp = (START_TIME + 60) * 1000
    backend_response = {
        "series": [
            {"dimensions": {Apdex.DIMENSION_KEY: apdex_type}, "datapoints": [[count, timestamp]]}
            for apdex_type, count in ((Apdex.SATISFIED, 3), (Apdex.FRUSTRATED, 1))
        ]
        if with_data
        else []
    }
    graph_query = mocker.patch(
        "apm_web.metric_handler.resource.grafana.graph_unify_query", return_value=backend_response
    )

    response = ApdexQueryResource().request(
        {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "start_time": START_TIME, "end_time": END_TIME}
    )

    assert response["metrics"] == []
    series = response["series"]
    assert len(series) == 1
    assert series[0]["target"] == "apdex"
    assert len(series[0]["datapoints"]) == 30
    assert [point for point in series[0]["datapoints"] if point[0] is not None] == (
        [[0.75, timestamp]] if with_data else []
    )
    graph_query.assert_called_once()
    query_params = graph_query.call_args.args[0]
    assert (query_params["start_time"], query_params["end_time"]) == (START_TIME, END_TIME)
    assert query_params["query_configs"][0]["metrics"][0]["field"] == "bk_apm_count"
    forbid_data_probe.assert_not_called()


@pytest.mark.parametrize("with_data", [False, True])
@pytest.mark.parametrize("strategy_id", [None, 7])
def test_alert_queries_selected_range_and_strategy_without_data_probe(
    application: Application,
    mocker: MockerFixture,
    forbid_data_probe: mock.Mock,
    with_data: bool,
    strategy_id: int | None,
) -> None:
    timestamps = [START_TIME * 1000, (START_TIME + 60) * 1000, END_TIME * 1000]

    def alert_histogram(params: dict) -> dict:
        severity = params["conditions"][0]["value"][0]
        values = (
            {AlertLevel.ERROR: [2, 0, 0], AlertLevel.WARN: [1, 3, 0], AlertLevel.INFO: [0, 0, 0]}[severity]
            if with_data
            else [0, 0, 0]
        )
        return {
            "series": [
                {"name": AlertStatus.ABNORMAL, "data": list(zip(timestamps, values))},
                {"name": AlertStatus.RECOVERED, "data": [[timestamp, 0] for timestamp in timestamps]},
            ]
        }

    histogram_query = mocker.patch(
        "apm_web.metric.resources.resource.fta_web.alert.alert_date_histogram", side_effect=alert_histogram
    )
    request_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "start_time": START_TIME, "end_time": END_TIME}
    if strategy_id is not None:
        request_data["strategy_id"] = strategy_id

    response = AlertQueryResource().request(request_data)

    assert response == {
        "metrics": [],
        "series": [
            {
                "datapoints": (
                    [[[1, 2], timestamps[0]], [[2, 3], timestamps[1]]]
                    if with_data
                    else [[[4, 0], timestamp] for timestamp in timestamps[:-1]]
                ),
                "dimensions": {},
                "target": "alert",
                "type": "bar",
                "unit": "",
            }
        ],
    }
    assert histogram_query.call_count == 3
    for call, severity in zip(histogram_query.call_args_list, (AlertLevel.ERROR, AlertLevel.WARN, AlertLevel.INFO)):
        query_params = call.args[0]
        assert (query_params["start_time"], query_params["end_time"]) == (START_TIME, END_TIME)
        assert query_params["bk_biz_ids"] == [BK_BIZ_ID]
        assert query_params["query_string"] == f"metric: custom.{application.metric_result_table_id}.*"
        assert query_params["conditions"] == [
            {"key": "severity", "value": [severity]},
            *([{"key": "strategy_id", "value": [strategy_id]}] if strategy_id is not None else []),
        ]
    forbid_data_probe.assert_not_called()
