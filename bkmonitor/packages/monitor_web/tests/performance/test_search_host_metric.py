from types import SimpleNamespace
from unittest.mock import Mock
from importlib import import_module

import pytest

from api.cmdb.mock import HOSTS
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from monitor_web.performance.resources import SearchHostMetricResource
from monitor_web.performance.views import SearchHostMetricViewSet


def mock_other_sections(mocker, failed_section: str | None = None):
    for section in ("agent_status", "performance_data", "process_status", "alarm_count"):
        method = mocker.patch.object(SearchHostMetricResource, f"get_{section}")
        if section == failed_section:
            method.side_effect = RuntimeError(f"{section} failed")


def test_search_host_metric_response_uses_gzip():
    assert SearchHostMetricViewSet.resource_routes[0].content_encoding == "gzip"


def test_get_process_multiple_hosts_use_cmdb_host_list(mocker):
    batch_request = mocker.patch("api.cmdb.default.batch_request", return_value=[])

    result = api.cmdb.get_process(bk_biz_id=2, bk_host_ids=[1, 2])

    assert result == []
    assert batch_request.call_args.args[1] == {"bk_biz_id": 2, "bk_host_list": [1, 2]}


def test_get_process_empty_host_list_does_not_query_all_hosts(mocker):
    batch_request = mocker.patch("api.cmdb.default.batch_request")

    result = api.cmdb.get_process(bk_biz_id=2, bk_host_ids=[])

    assert result == []
    batch_request.assert_not_called()


def test_get_process_without_host_filter_keeps_business_cache(mocker):
    batch_request = mocker.patch("api.cmdb.default.batch_request")
    get_service_instance_by_biz = mocker.patch("api.cmdb.default.get_service_instance_by_biz", return_value=[])

    result = api.cmdb.get_process(bk_biz_id=2)

    assert result == []
    get_service_instance_by_biz.assert_called_once_with(2)
    batch_request.assert_not_called()


@pytest.mark.parametrize(
    ("query_mode", "host_count", "expected_valid"),
    [("page", 100, True), ("page", 101, False), ("full", 101, True)],
)
def test_search_host_metric_page_mode_limits_one_page(query_mode, host_count, expected_valid):
    serializer = SearchHostMetricResource.RequestSerializer(
        data={"bk_biz_id": 2, "bk_host_ids": list(range(host_count)), "query_mode": query_mode}
    )

    assert serializer.is_valid() is expected_valid
    assert ("bk_host_ids" in serializer.errors) is (not expected_valid)


@pytest.mark.parametrize(("query_params", "expected_filter"), [({}, False), ({"query_mode": "page"}, True)])
def test_search_host_metric_mode_controls_process_cmdb_host_filter(mocker, query_params, expected_filter):
    mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_by_id", return_value=HOSTS[:2])
    mock_other_sections(mocker)

    SearchHostMetricResource().perform_request(
        {"bk_biz_id": 2, "bk_host_ids": [host.bk_host_id for host in HOSTS[:2]], **query_params}
    )

    process_status = SearchHostMetricResource.get_process_status
    assert process_status.call_args.args[-1] is expected_filter


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


@pytest.mark.parametrize(
    "helper_name",
    ["get_agent_status", "get_host_performance_data", "get_process_status"],
)
def test_snapshot_can_explicitly_omit_uq_host_target_without_losing_host_whitelist(mocker, helper_name):
    data_source_class = Mock(return_value=Mock())
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=data_source_class)
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)
    mocker.patch("monitor_web.cc.resources.cmdb.api.node_man.ipchooser_host_detail", return_value=[])

    helper = getattr(resource.cc, helper_name)
    result = helper(bk_biz_id=2, hosts=HOSTS[:1], target_filter={})

    assert data_source_class.call_args.kwargs["filter_dict"] == {}
    assert set(result).issubset({HOSTS[0].bk_host_id})


def test_existing_host_metric_helpers_keep_builder_when_target_filter_is_unspecified(mocker):
    expected_filter = {"targets": [{"bk_host_id": [str(HOSTS[0].bk_host_id)]}]}
    build_filter = mocker.patch(
        "monitor_web.cc.resources.cmdb._build_host_target_filter",
        return_value=expected_filter,
    )
    data_source_class = Mock(return_value=Mock())
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=data_source_class)
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)

    resource.cc.get_host_performance_data(bk_biz_id=2, hosts=HOSTS[:1])

    build_filter.assert_called_once_with(2, HOSTS[:1])
    assert data_source_class.call_args.kwargs["filter_dict"] == expected_filter


def test_strict_agent_status_rejects_nodeman_chunk_failure(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock(return_value=Mock()))
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)
    failed_future = Mock()
    failed_future.get.side_effect = RuntimeError("nodeman failed")
    pool = Mock()
    pool.apply_async.return_value = failed_future
    mocker.patch("monitor_web.cc.resources.cmdb.ThreadPool", return_value=pool)

    with pytest.raises(RuntimeError, match="node manager returned incomplete"):
        resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:1], fail_on_incomplete=True)


def test_default_agent_status_keeps_nodeman_chunk_failure_degradation(mocker):
    mocker.patch("monitor_web.cc.resources.cmdb.load_data_source", return_value=Mock(return_value=Mock()))
    query = Mock(is_partial=False)
    query.query_data.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.UnifyQuery", return_value=query)
    failed_future = Mock()
    failed_future.get.side_effect = RuntimeError("nodeman failed")
    pool = Mock()
    pool.apply_async.return_value = failed_future
    mocker.patch("monitor_web.cc.resources.cmdb.ThreadPool", return_value=pool)

    result = resource.cc.get_agent_status(bk_biz_id=2, hosts=HOSTS[:1])

    assert result == {HOSTS[0].bk_host_id: 2}


def test_business_alarm_query_uses_paginated_composite_aggregation_and_cmdb_whitelist(mocker):
    ipv4_host = HOSTS[0]
    ipv6_host = HOSTS[2]

    def aggregation_response(buckets, after_key=None):
        aggregation = SimpleNamespace(buckets=buckets)
        if after_key is not None:
            aggregation.after_key = after_key
        return SimpleNamespace(aggregations=SimpleNamespace(host_alarm_identity=aggregation))

    responses = [
        aggregation_response(
            [
                SimpleNamespace(key={"bk_host_id": str(ipv4_host.bk_host_id), "severity": 1}, doc_count=3),
                SimpleNamespace(key={"bk_host_id": "999999", "severity": 1}, doc_count=99),
            ],
            after_key={"bk_host_id": str(ipv4_host.bk_host_id), "severity": 1},
        ),
        aggregation_response(
            [SimpleNamespace(key={"bk_host_id": str(ipv6_host.bk_host_id), "severity": 2}, doc_count=4)]
        ),
        aggregation_response(
            [
                SimpleNamespace(
                    key={"bk_cloud_id": str(ipv4_host.bk_cloud_id), "ip": ipv4_host.bk_host_innerip, "severity": 1},
                    doc_count=2,
                ),
                SimpleNamespace(key={"bk_cloud_id": "0", "ip": "203.0.113.1", "severity": 1}, doc_count=88),
            ]
        ),
        aggregation_response(
            [
                SimpleNamespace(
                    key={
                        "bk_cloud_id": str(ipv6_host.bk_cloud_id),
                        "ipv6": ipv6_host.bk_host_innerip_v6,
                        "severity": 3,
                    },
                    doc_count=5,
                )
            ]
        ),
    ]
    searches = []
    for response in responses:
        search = Mock()
        search.filter.return_value = search
        search.exclude.return_value = search
        search.extra.return_value = search
        search.execute.return_value = response
        search.scan.side_effect = AssertionError("business snapshot must not scan alert documents")
        searches.append(search)
    search_api = mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search", side_effect=searches)

    result = resource.cc.get_host_alarm_count(
        bk_biz_id=2,
        hosts=[ipv4_host, ipv6_host],
        start_time=100,
        end_time=200,
        filter_by_host_ip=False,
    )

    assert result[ipv4_host.bk_host_id] == {1: 5, 2: 0, 3: 0}
    assert result[ipv6_host.bk_host_id] == {1: 0, 2: 4, 3: 5}
    assert search_api.call_count == 4
    first_composite = searches[0].aggs.bucket.call_args.kwargs
    second_composite = searches[1].aggs.bucket.call_args.kwargs
    assert first_composite["size"] == 1000
    assert "after" not in first_composite
    assert second_composite["after"] == {"bk_host_id": str(ipv4_host.bk_host_id), "severity": 1}

    def identity_queries(search, method):
        return [
            call.args[0].to_dict()
            for call in getattr(search, method).call_args_list
            if call.args and hasattr(call.args[0], "to_dict")
        ]

    non_empty_host_id = {
        "bool": {
            "filter": [{"exists": {"field": "event.bk_host_id"}}],
            "must_not": [{"term": {"event.bk_host_id": ""}}],
        }
    }
    non_empty_ipv4 = {
        "bool": {
            "filter": [{"exists": {"field": "event.ip"}}],
            "must_not": [{"term": {"event.ip": ""}}],
        }
    }
    non_empty_ipv6 = {
        "bool": {
            "filter": [{"exists": {"field": "event.ipv6"}}],
            "must_not": [{"term": {"event.ipv6": ""}}],
        }
    }
    assert non_empty_host_id in identity_queries(searches[0], "filter")
    assert non_empty_host_id in identity_queries(searches[2], "exclude")
    assert non_empty_ipv4 in identity_queries(searches[2], "filter")
    assert non_empty_host_id in identity_queries(searches[3], "exclude")
    assert non_empty_ipv4 in identity_queries(searches[3], "exclude")
    assert non_empty_ipv6 in identity_queries(searches[3], "filter")


def test_business_alarm_identity_priority_treats_empty_values_as_missing():
    cmdb = import_module("monitor_web.cc.resources.cmdb")
    host_id = cmdb._non_empty_host_alarm_identity("event.bk_host_id")
    ipv4 = cmdb._non_empty_host_alarm_identity("event.ip")
    ipv6 = cmdb._non_empty_host_alarm_identity("event.ipv6")

    ipv4_query = cmdb.AlertDocument.search().exclude(host_id).filter(ipv4).to_dict()["query"]
    ipv6_query = cmdb.AlertDocument.search().exclude(host_id).exclude(ipv4).filter(ipv6).to_dict()["query"]

    assert {
        "bool": {
            "should": [
                {"bool": {"must_not": [{"exists": {"field": "event.bk_host_id"}}]}},
                {"term": {"event.bk_host_id": ""}},
            ]
        }
    } in ipv4_query["bool"]["filter"]
    assert {
        "bool": {"filter": [{"exists": {"field": "event.ip"}}], "must_not": [{"term": {"event.ip": ""}}]}
    } in ipv4_query["bool"]["filter"]
    assert {
        "bool": {"should": [{"bool": {"must_not": [{"exists": {"field": "event.ip"}}]}}, {"term": {"event.ip": ""}}]}
    } in ipv6_query["bool"]["filter"]
    assert {
        "bool": {"filter": [{"exists": {"field": "event.ipv6"}}], "must_not": [{"term": {"event.ipv6": ""}}]}
    } in ipv6_query["bool"]["filter"]


def test_scoped_alarm_query_filters_event_host_id_ipv4_and_ipv6(mocker):
    known_host = HOSTS[3]
    search = Mock()
    search.filter.return_value = search
    search.source.return_value = search
    search.scan.return_value = []
    mocker.patch("monitor_web.cc.resources.cmdb.AlertDocument.search", return_value=search)

    resource.cc.get_host_alarm_count(
        bk_biz_id=2,
        hosts=[known_host],
        start_time=100,
        end_time=200,
    )

    identity_filter = next(
        call.args[0] for call in search.filter.call_args_list if call.args and not isinstance(call.args[0], str)
    )
    query = identity_filter.to_dict()["bool"]
    assert query["minimum_should_match"] == 1
    assert {next(iter(clause["terms"])) for clause in query["should"]} == {
        "event.bk_host_id",
        "event.ip",
        "event.ipv6",
    }
    assert {"terms": {"event.bk_host_id": [str(known_host.bk_host_id)]}} in query["should"]


def test_alarm_host_mapping_supports_event_and_dimension_host_id_and_ipv6():
    known_host = HOSTS[2]
    known_host_ids = {known_host.bk_host_id}
    ip_to_host_id = {(known_host.bk_host_innerip_v6, int(known_host.bk_cloud_id or 0)): known_host.bk_host_id}

    event_host = SimpleNamespace(
        event=SimpleNamespace(bk_host_id=str(known_host.bk_host_id), ip="", ipv6="", bk_cloud_id=0), dimensions=[]
    )
    event_ipv6 = SimpleNamespace(
        event=SimpleNamespace(
            bk_host_id=None,
            ip="",
            ipv6=known_host.bk_host_innerip_v6,
            bk_cloud_id=known_host.bk_cloud_id,
        ),
        dimensions=[],
    )
    dimension_host = SimpleNamespace(
        event=SimpleNamespace(bk_host_id=None, ip="", ipv6="", bk_cloud_id=0),
        dimensions=[SimpleNamespace(key="bk_host_id", value=str(known_host.bk_host_id))],
    )
    dimension_ipv6 = SimpleNamespace(
        event=SimpleNamespace(bk_host_id=None, ip="", ipv6="", bk_cloud_id=0),
        dimensions=[
            SimpleNamespace(key="ipv6", value=known_host.bk_host_innerip_v6),
            SimpleNamespace(key="bk_cloud_id", value=str(known_host.bk_cloud_id)),
        ],
    )
    unknown = SimpleNamespace(
        event=SimpleNamespace(bk_host_id=999999, ip="203.0.113.1", ipv6="", bk_cloud_id=0), dimensions=[]
    )

    resolver = import_module("monitor_web.cc.resources.cmdb")._resolve_host_id_from_alert
    assert resolver(event_host, known_host_ids, ip_to_host_id) == known_host.bk_host_id
    assert resolver(event_ipv6, known_host_ids, ip_to_host_id) == known_host.bk_host_id
    assert resolver(dimension_host, known_host_ids, ip_to_host_id) == known_host.bk_host_id
    assert resolver(dimension_ipv6, known_host_ids, ip_to_host_id) == known_host.bk_host_id
    assert resolver(unknown, known_host_ids, ip_to_host_id) is None
