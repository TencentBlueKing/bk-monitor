from unittest.mock import Mock

import pytest

from api.cmdb.mock import HOSTS
from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from monitor_web.performance.resources import SearchHostMetricResource


def mock_other_sections(mocker, failed_section: str | None = None):
    for section in ("agent_status", "performance_data", "process_status", "alarm_count"):
        method = mocker.patch.object(SearchHostMetricResource, f"get_{section}")
        if section == failed_section:
            method.side_effect = RuntimeError(f"{section} failed")


@pytest.mark.parametrize("failed_section", ["agent_status", "performance_data", "process_status", "alarm_count"])
def test_search_host_metric_surfaces_thread_failure(mocker, failed_section):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mock_other_sections(mocker, failed_section=failed_section)

    with pytest.raises(CustomException) as exc_info:
        SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert exc_info.value.data == {"failed_sections": [failed_section]}


def test_search_host_metric_does_not_degrade_alarm_failure_to_empty(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch(
        "monitor_web.performance.resources.resource.cc.get_host_alarm_count",
        side_effect=RuntimeError("alarm query failed"),
    )

    with pytest.raises(CustomException) as exc_info:
        SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert exc_info.value.data == {"failed_sections": ["alarm_count"]}


def test_reused_performance_section_keeps_partial_degradation_by_default(mocker):
    get_performance_data = mocker.patch(
        "monitor_web.performance.resources.resource.cc.get_host_performance_data", return_value={}
    )

    SearchHostMetricResource.get_performance_data(2, HOSTS[:1], {})

    assert get_performance_data.call_args.kwargs["fail_on_incomplete"] is False


def test_host_performance_helper_keeps_partial_result_as_degraded_defaults(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    result = resource.cc.get_host_performance_data(bk_biz_id=2, hosts=HOSTS[:1])

    assert result[HOSTS[0].bk_host_id] == {
        "cpu_load": None,
        "cpu_usage": None,
        "disk_in_use": None,
        "io_util": None,
        "mem_usage": None,
        "psc_mem_usage": None,
    }


def test_search_host_metric_rejects_partial_performance_query(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    with pytest.raises(CustomException) as exc_info:
        SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert exc_info.value.data == {"failed_sections": ["performance_data"]}


@pytest.mark.parametrize("partial_section", ["agent_status", "process_status"])
def test_search_host_metric_rejects_partial_agent_and_process_query(mocker, partial_section):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    for section in ("agent_status", "performance_data", "process_status", "alarm_count"):
        if section != partial_section:
            mocker.patch.object(SearchHostMetricResource, f"get_{section}")

    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)
    mocker.patch("monitor_web.cc.resources.cmdb.api.cmdb.get_process", return_value=[])

    with pytest.raises(CustomException) as exc_info:
        SearchHostMetricResource().perform_request(
            {
                "bk_biz_id": 2,
                "bk_host_ids": [HOSTS[0].bk_host_id],
                "start_time": 100,
                "end_time": 200,
            }
        )

    assert exc_info.value.data == {"failed_sections": [partial_section]}


def test_reused_agent_and_process_helpers_keep_partial_degradation_by_default(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    agent_status = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:1], start_time=100, end_time=200)
    process_status = resource.cc.get_process_status(bk_biz_id=2, hosts=HOSTS[:1], start_time=100, end_time=200)

    assert agent_status
    assert process_status == {}
