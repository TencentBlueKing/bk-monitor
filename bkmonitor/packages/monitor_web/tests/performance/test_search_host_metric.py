import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.cmdb.mock import HOSTS
from core.drf_resource import resource
from core.errors.share import InvalidParamsError
from monitor_web.cc.resources.cmdb import _build_host_target_filter
from monitor_web.constants import AGENT_STATUS
from monitor_web.performance.resources import HostPerformanceResource, SearchHostMetricResource
from monitor_web.performance.views import SearchHostMetricViewSet


def mock_other_sections(mocker, failed_section: str | None = None):
    for section in ("agent_status", "performance_data", "process_status", "alarm_count"):
        method = mocker.patch.object(SearchHostMetricResource, f"get_{section}")
        if section == failed_section:
            method.side_effect = RuntimeError(f"{section} failed")


def _capture_filter_dicts(mocker):
    captured = []

    def data_source_factory(**kwargs):
        captured.append(kwargs.get("filter_dict"))
        return Mock()

    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=data_source_factory)
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)
    mocker.patch("monitor_web.cc.resources.cmdb.api.cmdb.get_process", return_value=[])
    return captured


def test_build_host_target_filter_skips_linear_terms_when_push_disabled(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.is_ipv6_biz", return_value=False)
    assert _build_host_target_filter(2, HOSTS[:3], push_host_target=False) == {}
    pushed = _build_host_target_filter(2, HOSTS[:1], push_host_target=True)
    assert "targets" in pushed
    assert pushed["targets"][0]["bk_target_ip"] == [HOSTS[0].bk_host_innerip]


def test_search_host_metric_omitted_ids_uses_cmdb_hosts_without_target(mocker):
    get_topo = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=HOSTS[:2])
    get_by_id = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id")
    captured = {}

    def capture_agent(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        captured["hosts"] = hosts
        captured["push_host_target"] = push_host_target
        captured["data_keys"] = set(data)

    mocker.patch.object(SearchHostMetricResource, "get_agent_status", side_effect=capture_agent)
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2})

    get_topo.assert_called_once_with(bk_biz_id=2)
    get_by_id.assert_not_called()
    assert captured["push_host_target"] is False
    assert captured["hosts"] == HOSTS[:2]
    assert set(result) == {HOSTS[0].bk_host_id, HOSTS[1].bk_host_id}


def test_search_host_metric_omitted_ids_unify_query_filter_is_empty(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    captured = _capture_filter_dicts(mocker)

    SearchHostMetricResource().perform_request({"bk_biz_id": 2})

    assert captured
    assert all(item == {} for item in captured)


def test_search_host_metric_omitted_ids_skips_target_above_two_thousand_hosts(mocker):
    many_hosts = HOSTS[:1] * 2500
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=many_hosts)
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    captured = _capture_filter_dicts(mocker)

    SearchHostMetricResource().perform_request({"bk_biz_id": 2})

    assert captured
    assert all(item == {} for item in captured)


def test_search_host_metric_share_host_without_ids_stays_scoped(mocker):
    get_by_id = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    get_topo = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")
    captured = {}

    def capture_agent(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        captured["push_host_target"] = push_host_target

    mocker.patch.object(SearchHostMetricResource, "get_agent_status", side_effect=capture_agent)
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_id": HOSTS[0].bk_host_id})

    get_by_id.assert_called_once_with(bk_biz_id=2, bk_host_ids=[HOSTS[0].bk_host_id])
    get_topo.assert_not_called()
    assert captured["push_host_target"] is True
    assert set(result) == {HOSTS[0].bk_host_id}


def test_search_host_metric_topo_share_without_ids_stays_scoped(mocker):
    get_topo = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=HOSTS[:1])
    captured = {}

    def capture_perf(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        captured["push_host_target"] = push_host_target

    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_performance_data", side_effect=capture_perf)
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")

    SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_obj_id": "module", "bk_inst_id": 8})

    get_topo.assert_called_once_with(bk_biz_id=2, topo_nodes={"module": [8]})
    assert captured["push_host_target"] is True


def test_search_host_metric_nonempty_ids_still_push_host_target(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")
    captured = {}

    def capture_perf(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        captured["push_host_target"] = push_host_target
        captured["hosts"] = hosts

    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_performance_data", side_effect=capture_perf)
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert captured["push_host_target"] is True
    assert captured["hosts"] == HOSTS[:1]
    assert set(result) == {HOSTS[0].bk_host_id}


def test_search_host_metric_unknown_ids_do_not_scan_all_business_processes(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=[])
    get_process = mocker.patch("monitor_web.cc.resources.cmdb.api.cmdb.get_process")
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")

    SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [999]})

    get_process.assert_not_called()


def test_search_host_metric_nonempty_ids_unify_query_keeps_host_terms(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.is_ipv6_biz", return_value=False)
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    captured = _capture_filter_dicts(mocker)

    SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert captured
    assert all(item.get("targets") for item in captured)


def test_search_host_metric_empty_ids_are_not_full_business(mocker):
    get_topo = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")
    get_by_id = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id")
    get_agent = mocker.patch.object(SearchHostMetricResource, "get_agent_status")

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": []})

    assert result == {}
    get_topo.assert_not_called()
    get_by_id.assert_not_called()
    get_agent.assert_not_called()


@pytest.mark.parametrize("scope", [{"bk_obj_id": "module"}, {"bk_inst_id": 8}])
def test_search_host_metric_rejects_incomplete_topology_scope(mocker, scope):
    get_topo = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node")

    with pytest.raises(InvalidParamsError):
        SearchHostMetricResource().perform_request({"bk_biz_id": 2, **scope})

    get_topo.assert_not_called()


def test_host_performance_list_skips_linear_host_target(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_topo_node", return_value=HOSTS[:2])
    mocker.patch(
        "monitor_web.performance.resources.api.cmdb.get_topo_tree",
        return_value=SimpleNamespace(convert_to_topo_link=lambda: {}),
    )
    mocker.patch("monitor_web.performance.resources.SearchHostInfoResource.get_module_info", return_value=[])
    captured = {}

    def capture_agent(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        captured["push_host_target"] = push_host_target
        captured["hosts"] = hosts

    mocker.patch.object(SearchHostMetricResource, "get_agent_status", side_effect=capture_agent)
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(HostPerformanceResource, "get_process_status")
    mocker.patch.object(HostPerformanceResource, "get_alarm_count")

    result = HostPerformanceResource().perform_request({"bk_biz_id": 2})

    assert captured["push_host_target"] is False
    assert captured["hosts"] == HOSTS[:2]
    assert {item["bk_host_id"] for item in result["hosts"]} == {HOSTS[0].bk_host_id, HOSTS[1].bk_host_id}


def test_get_host_performance_data_empty_filter_when_push_disabled(mocker):
    captured = _capture_filter_dicts(mocker)

    result = resource.cc.get_host_performance_data(bk_biz_id=2, hosts=HOSTS[:2], push_host_target=False)

    assert captured
    assert all(item == {} for item in captured)
    assert HOSTS[0].bk_host_id in result
    assert HOSTS[1].bk_host_id in result


@pytest.mark.parametrize("failed_section", ["agent_status", "performance_data", "process_status", "alarm_count"])
def test_search_host_metric_keeps_successful_sections_when_one_fails(mocker, failed_section):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mock_other_sections(mocker, failed_section=failed_section)

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    host_id = HOSTS[0].bk_host_id
    assert host_id in result
    assert result[host_id]["status"] == AGENT_STATUS.UNKNOWN
    assert result[host_id]["cpu_usage"] is None
    assert result[host_id]["component"] is None
    assert result[host_id]["alarm_count"] is None


def test_search_host_metric_alarm_failure_does_not_drop_other_sections(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])

    def fill_agent(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        data[HOSTS[0].bk_host_id]["status"] = AGENT_STATUS.ON

    mocker.patch.object(SearchHostMetricResource, "get_agent_status", side_effect=fill_agent)
    mocker.patch.object(SearchHostMetricResource, "get_performance_data")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch(
        "monitor_web.performance.resources.resource.cc.get_host_alarm_count",
        side_effect=RuntimeError("alarm query failed"),
    )

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert result[HOSTS[0].bk_host_id]["status"] == AGENT_STATUS.ON
    assert result[HOSTS[0].bk_host_id]["alarm_count"] is None


def test_search_host_metric_successful_empty_process_and_alarm_are_not_failures(mocker):
    host_id = HOSTS[0].bk_host_id
    data = {host_id: SearchHostMetricResource._empty_host_metric()}
    mocker.patch("monitor_web.performance.resources.resource.cc.get_process_info", return_value={})
    mocker.patch("monitor_web.performance.resources.resource.cc.get_host_alarm_count", return_value={host_id: {}})

    SearchHostMetricResource.get_process_status(2, HOSTS[:1], data)
    SearchHostMetricResource.get_alarm_count(2, HOSTS[:1], data)

    assert data[host_id]["component"] == []
    assert data[host_id]["alarm_count"] == []


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


def test_search_host_metric_partial_performance_query_keeps_other_sections(mocker):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])

    def fill_agent(
        bk_biz_id, hosts, data, start_time=None, end_time=None, fail_on_incomplete=False, push_host_target=True
    ):
        data[HOSTS[0].bk_host_id]["status"] = AGENT_STATUS.ON

    mocker.patch.object(SearchHostMetricResource, "get_agent_status", side_effect=fill_agent)
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id]})

    assert result[HOSTS[0].bk_host_id]["status"] == AGENT_STATUS.ON
    assert result[HOSTS[0].bk_host_id]["cpu_usage"] is None


def test_search_host_metric_partial_performance_query_keeps_returned_records(mocker):
    host_id = HOSTS[0].bk_host_id
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    mocker.patch.object(SearchHostMetricResource, "get_agent_status")
    mocker.patch.object(SearchHostMetricResource, "get_process_status")
    mocker.patch.object(SearchHostMetricResource, "get_alarm_count")
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = [{"_result_": 12.5, "bk_host_id": str(host_id)}]
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    result = SearchHostMetricResource().perform_request({"bk_biz_id": 2, "bk_host_ids": [host_id]})

    assert result[host_id]["cpu_usage"] == 12.5


@pytest.mark.parametrize("partial_section", ["agent_status", "process_status"])
def test_search_host_metric_partial_agent_and_process_query_keeps_host_row(mocker, partial_section):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    for section in ("agent_status", "performance_data", "process_status", "alarm_count"):
        if section != partial_section:
            mocker.patch.object(SearchHostMetricResource, f"get_{section}")

    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)
    mocker.patch("monitor_web.cc.resources.cmdb.api.cmdb.get_process", return_value=[])

    result = SearchHostMetricResource().perform_request(
        {
            "bk_biz_id": 2,
            "bk_host_ids": [HOSTS[0].bk_host_id],
            "start_time": 100,
            "end_time": 200,
        }
    )

    assert HOSTS[0].bk_host_id in result


def test_reused_agent_and_process_helpers_keep_partial_degradation_by_default(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    agent_status = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:1], start_time=100, end_time=200)
    process_status = resource.cc.get_process_status(bk_biz_id=2, hosts=HOSTS[:1], start_time=100, end_time=200)

    assert agent_status
    assert process_status == {}


def test_historical_partial_agent_query_keeps_missing_hosts_unknown(mocker):
    first_host_id = HOSTS[0].bk_host_id
    second_host_id = HOSTS[1].bk_host_id
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = [{"_result_": 1, "bk_host_id": str(first_host_id)}]
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)

    result = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:2], start_time=100, end_time=200)

    assert result[first_host_id] == AGENT_STATUS.ON
    assert result[second_host_id] == AGENT_STATUS.UNKNOWN


def test_realtime_partial_agent_query_does_not_claim_alive_host_has_no_data(mocker):
    first_host_id = HOSTS[0].bk_host_id
    second_host_id = HOSTS[1].bk_host_id
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    partial_query = Mock(is_partial=True)
    partial_query.query_data.return_value = [{"_result_": 1, "bk_host_id": str(first_host_id)}]
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=partial_query)
    mocker.patch(
        "monitor_web.cc.resources.cmdb.api.node_man.ipchooser_host_detail",
        return_value=[{"alive": 1, "host_id": second_host_id}],
    )

    result = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:2])

    assert result[first_host_id] == AGENT_STATUS.ON
    assert result[second_host_id] == AGENT_STATUS.UNKNOWN


def test_realtime_agent_query_keeps_failed_nodeman_batch_unknown(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock())
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)
    mocker.patch(
        "monitor_web.cc.resources.cmdb.api.node_man.ipchooser_host_detail",
        side_effect=RuntimeError("nodeman failed"),
    )

    result = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:2])

    assert result == {
        HOSTS[0].bk_host_id: AGENT_STATUS.UNKNOWN,
        HOSTS[1].bk_host_id: AGENT_STATUS.UNKNOWN,
    }


def test_search_host_metric_response_uses_gzip():
    assert SearchHostMetricViewSet.resource_routes[0].content_encoding == "gzip"


def test_search_host_metric_alarm_count_only_constrained_by_end_time(mocker):
    """未恢复告警是存量状态语义：透传 end_time，但不透传窗口起点 start_time"""
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:1])
    for section in ("agent_status", "performance_data", "process_status"):
        mocker.patch.object(SearchHostMetricResource, f"get_{section}")
    alarm_count = mocker.patch(
        "monitor_web.performance.resources.resource.cc.get_host_alarm_count",
        return_value={HOSTS[0].bk_host_id: {}},
    )

    SearchHostMetricResource().perform_request(
        {"bk_biz_id": 2, "bk_host_ids": [HOSTS[0].bk_host_id], "start_time": 100, "end_time": 200}
    )

    assert alarm_count.call_args.kwargs["end_time"] == 200
    assert "start_time" not in alarm_count.call_args.kwargs


def test_get_host_alarm_count_only_limits_begin_time_by_end_time(mocker):
    """begin_time 只受 end_time 上界约束（文档级过滤），不限制触发起点；end_time 不参与索引选择"""
    search = mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search")
    search.return_value.filter.return_value = search.return_value
    search.return_value.source.return_value = search.return_value
    search.return_value.scan.return_value = []

    resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=HOSTS[:1], end_time=100)

    assert search.call_args.kwargs["days"] == 7
    assert "end_time" not in search.call_args.kwargs
    range_calls = [c for c in search.return_value.filter.call_args_list if c.args and c.args[0] == "range"]
    assert len(range_calls) == 1
    assert range_calls[0].kwargs == {"begin_time": {"lte": 100}}


def test_get_host_alarm_count_default_looks_back_by_days_without_end_time(mocker):
    """不传 end_time 时保持旧版口径：按 days 回溯索引窗口，不加 begin_time range 过滤"""
    search = mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search")
    search.return_value.filter.return_value = search.return_value
    search.return_value.source.return_value = search.return_value
    search.return_value.scan.return_value = []

    resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=HOSTS[:1])

    assert search.call_args.kwargs["days"] == 7
    assert "end_time" not in search.call_args.kwargs
    range_calls = [c for c in search.return_value.filter.call_args_list if c.args and c.args[0] == "range"]
    assert range_calls == []


def test_get_host_alarm_count_old_end_time_keeps_current_index_window(mocker):
    """历史 end_time 不收窄索引窗口：search 不收 end_time、days 不变，上界保持 now（覆盖当天索引）"""
    search = mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search")
    search.return_value.filter.return_value = search.return_value
    search.return_value.source.return_value = search.return_value
    search.return_value.scan.return_value = []

    old_end_time = time.time() - 30 * 86400
    resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=HOSTS[:1], end_time=old_end_time)

    assert search.call_args.kwargs["days"] == 7
    assert "end_time" not in search.call_args.kwargs


def _make_alert(ip=None, bk_cloud_id=0, severity=1, dimensions=None, alert_id=None):
    return SimpleNamespace(
        event=SimpleNamespace(ip=ip, bk_cloud_id=bk_cloud_id),
        severity=severity,
        dimensions=dimensions or [],
        meta=SimpleNamespace(id=alert_id or f"alert-{ip}-{bk_cloud_id}-{severity}"),
    )


def _mock_alert_search(mocker, alerts):
    search = mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search")
    search.return_value.filter.return_value = search.return_value
    search.return_value.source.return_value = search.return_value
    search.return_value.scan.return_value = alerts
    return search


def test_get_host_alarm_count_multi_ip_host_matches_each_ip(mocker):
    """多 IP 主机：event.ip 命中任一拆分 IP 即可归属到该主机"""
    host = SimpleNamespace(bk_host_id=111, bk_cloud_id=0, bk_host_innerip="127.0.0.1,127.0.0.2")
    _mock_alert_search(mocker, [_make_alert(ip="127.0.0.2", bk_cloud_id=0, severity=2)])

    result = resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=[host])

    assert result == {111: {1: 0, 2: 1, 3: 0}}


def test_get_host_alarm_count_invalid_severity_skipped_without_breaking_section(mocker):
    """severity 缺失/越界的脏数据告警跳过计数，不影响其余告警统计（不炸分区）"""
    host = SimpleNamespace(bk_host_id=111, bk_cloud_id=0, bk_host_innerip="127.0.0.1")
    _mock_alert_search(
        mocker,
        [
            _make_alert(ip="127.0.0.1", bk_cloud_id=0, severity=1),
            _make_alert(ip="127.0.0.1", bk_cloud_id=0, severity=None),
            _make_alert(ip="127.0.0.1", bk_cloud_id=0, severity=9),
        ],
    )

    result = resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=[host])

    assert result == {111: {1: 1, 2: 0, 3: 0}}


def test_get_host_alarm_count_dedups_same_alert_during_reindex(mocker):
    """reindex 过渡期同一告警在新旧索引各存一份：按 alert id 去重，不重复计数"""
    host = SimpleNamespace(bk_host_id=111, bk_cloud_id=0, bk_host_innerip="127.0.0.1")
    duplicated_alert = _make_alert(ip="127.0.0.1", bk_cloud_id=0, severity=2, alert_id="alert-dup")
    _mock_alert_search(mocker, [duplicated_alert, duplicated_alert])

    result = resource.cc.get_host_alarm_count(bk_biz_id=2, hosts=[host])

    assert result == {111: {1: 0, 2: 1, 3: 0}}
