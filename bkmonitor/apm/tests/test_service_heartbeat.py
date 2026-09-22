import json
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db import OperationalError, connections, router
from django.db.models.query import QuerySet

from apm.core.discover.exceptions import IncompleteDiscoveryError
from apm.core.discover.log.service import ServiceDiscover as LogServiceDiscover
from apm.core.discover.metric.service import ServiceDiscover as MetricServiceDiscover
from apm.core.discover.profile.service import ServiceDiscover as ProfileServiceDiscover
from apm.models import ProfileService, TopoNode
from apm.resources import QueryTopoNodeResource


pytestmark = pytest.mark.django_db(databases="__all__")


def make_node(name: str = "demo", **kwargs: Any) -> TopoNode:
    return TopoNode.objects.create(
        bk_biz_id=kwargs.pop("bk_biz_id", 2),
        app_name=kwargs.pop("app_name", "app"),
        topo_key=name,
        extra_data=kwargs.pop("extra_data", {"category": "other", "kind": "service"}),
        **kwargs,
    )


def datasource() -> SimpleNamespace:
    return SimpleNamespace(bk_biz_id=2, app_name="app", result_table_id="2_apm.app", retention=7)


def test_heartbeat_monotonic_and_preserves_unrequested_fields() -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 100, "checked_at": 110}})
    updated_at = node.updated_at
    for data_type, data_time, checked_at in (("trace", 150, 160), ("trace", 120, 130), ("trace", None, 200)):
        TopoNode.touch_heartbeat(2, "app", data_type, {"demo": data_time}, checked_at)
    node.refresh_from_db()
    assert node.heartbeat == {
        "metric": {"last_data_at": 100, "checked_at": 110},
        "trace": {"last_data_at": 150, "checked_at": 200},
    }
    assert node.updated_at == updated_at
    assert node.source == []


def test_heartbeat_scope_duplicates_empty_and_missing_nodes() -> None:
    nodes = [make_node(), make_node()]
    other_app = make_node(app_name="other")
    other_biz = make_node(bk_biz_id=3)
    TopoNode.touch_heartbeat(2, "app", "log", {"demo": None, "missing": 200}, 300)
    for node in nodes:
        node.refresh_from_db()
        assert node.heartbeat == {"log": {"last_data_at": None, "checked_at": 300}}
    for node in (other_app, other_biz):
        node.refresh_from_db()
        assert node.heartbeat == {}
    assert TopoNode.objects.count() == 4
    TopoNode.touch_heartbeat(2, "app", "log", {}, 400)
    nodes[0].refresh_from_db()
    assert nodes[0].heartbeat["log"]["checked_at"] == 300


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_heartbeat_locks_and_rolls_back_on_routed_database() -> None:
    node = make_node()
    database = router.db_for_write(TopoNode)
    assert not connections[database].in_atomic_block
    select_for_update = QuerySet.select_for_update
    bulk_update = QuerySet.bulk_update

    def lock(queryset: QuerySet, *args: Any, **kwargs: Any) -> QuerySet:
        assert queryset.db == database
        assert connections[database].in_atomic_block
        return select_for_update(queryset, *args, **kwargs)

    def fail_after_update(queryset: QuerySet, *args: Any, **kwargs: Any) -> None:
        bulk_update(queryset, *args, **kwargs)
        raise RuntimeError("write completed then failed")

    with (
        mock.patch.object(QuerySet, "select_for_update", lock),
        mock.patch.object(QuerySet, "bulk_update", fail_after_update),
    ):
        with pytest.raises(RuntimeError):
            TopoNode.touch_heartbeat(2, "app", "trace", {"demo": 100}, 110)
    node.refresh_from_db()
    assert node.heartbeat == {}


def log_response(name: str = "demo", timestamp: int = 150000) -> dict[str, Any]:
    return {
        "aggregations": {
            "service_names": {
                "buckets": [{"key": {"service_name": name}, "last_data_at": {"value": timestamp}}],
            }
        },
        "_shards": {"failed": 0},
        "timed_out": False,
    }


def test_log_discover_creates_nodes_and_merges_fields() -> None:
    existing = make_node("existing", source=["trace"], heartbeat={"trace": {"last_data_at": 80, "checked_at": 90}})
    with (
        mock.patch(
            "apm.core.discover.log.service.api.log_search.es_query_dsl",
            side_effect=[log_response(timestamp=150000), log_response(timestamp=190000)],
        ) as query,
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service", "category": "other"}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    created = TopoNode.objects.get(topo_key="demo")
    assert created.source == ["log"]
    assert created.heartbeat["log"]["last_data_at"] == 190
    assert query.call_count == 2
    for call in query.call_args_list:
        assert call.kwargs["indices"] == "2_apm_app*"
        aggregation = call.kwargs["body"]["aggs"]["service_names"]
        assert aggregation["composite"]["size"] == 1000
        assert aggregation["aggs"]["last_data_at"] == {"max": {"field": "time"}}
    existing.refresh_from_db()
    assert existing.heartbeat["log"]["last_data_at"] is None
    assert existing.heartbeat["trace"] == {"last_data_at": 80, "checked_at": 90}


@pytest.mark.parametrize("failure", ["exception", "shard", "timeout"])
def test_log_failure_does_not_write_or_renew(failure: str) -> None:
    previous = {"log": {"last_data_at": 90, "checked_at": 100}}
    node = make_node(heartbeat=previous)
    response = log_response()
    if failure == "shard":
        response["_shards"]["failed"] = 1
    elif failure == "timeout":
        response["timed_out"] = True
    with mock.patch(
        "apm.core.discover.log.service.api.log_search.es_query_dsl",
        side_effect=[log_response("new"), RuntimeError("failed") if failure == "exception" else response],
    ):
        with pytest.raises((RuntimeError, IncompleteDiscoveryError)):
            LogServiceDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == previous
    assert TopoNode.objects.count() == 1


def metric_series(keys: list[str], values: list[str], points: list[list[Any]]) -> dict[str, Any]:
    return {"group_keys": keys, "group_values": values, "columns": ["_time", "_value"], "values": points}


def test_metric_heartbeat_keys_and_non_null_zero() -> None:
    for name in ("demo", "demo-redis", "demo-kafka", "http:remote", "empty"):
        make_node(name)
    responses = [
        {"series": [metric_series(["service_name"], ["demo"], [[150, 0], [190, None], [210, 1]])]},
        {"series": [metric_series(["service_name", "db_system"], ["demo", "redis"], [[160, 1]])]},
        {"series": [metric_series(["service_name", "messaging_system"], ["demo", "kafka"], [[170, 1]])]},
        {"series": [metric_series(["peer_service"], ["remote"], [[180, 1]])]},
    ]
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql", side_effect=responses
    ) as query:
        MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    assert {node.topo_key: node.heartbeat["metric"]["last_data_at"] for node in TopoNode.objects.all()} == {
        "demo": 150,
        "demo-redis": 160,
        "demo-kafka": 170,
        "http:remote": 180,
        "empty": None,
    }
    assert all(call.args[0]["step"] == "60s" for call in query.call_args_list)
    assert all('__name__="custom:2_apm:app:bk_apm_count"' in call.args[0]["promql"] for call in query.call_args_list)


@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("failed"),
        {"series": [], "is_partial": True},
        {"series": [], "status": {"series_limit_reached": True}},
    ],
)
def test_metric_partial_failure_keeps_old_heartbeat(response: Any) -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 90, "checked_at": 100}})
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=[
            {"series": [metric_series(["service_name"], ["demo"], [[150, 1]])]},
            response,
        ],
    ):
        with pytest.raises((RuntimeError, IncompleteDiscoveryError)):
            MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == {"metric": {"last_data_at": 90, "checked_at": 100}}


def test_legacy_topology_filters_only_new_source_nodes() -> None:
    for name, sources in (
        ("legacy", []),
        ("trace", ["trace"]),
        ("metric", ["metric"]),
        ("log", ["log"]),
        ("profile", ["profiling"]),
        ("both", ["log", "profiling"]),
        ("reverse", ["profiling", "log"]),
        ("mixed", ["log", "trace"]),
    ):
        make_node(name, source=sources)
    with mock.patch(
        "apm.resources.DiscoverHandler.get_retention_filter_params", return_value={"bk_biz_id": 2, "app_name": "app"}
    ):
        nodes = QueryTopoNodeResource().perform_request({"bk_biz_id": 2, "app_name": "app"})
    assert {node["topo_key"] for node in nodes} == {"legacy", "trace", "metric", "mixed"}
    assert all("heartbeat" not in node and "source" not in node for node in nodes)


def test_upsert_preserves_metadata_and_legacy_empty_source() -> None:
    legacy = make_node()
    trace = make_node("trace", source=["trace"], extra_data={"kind": "service", "category": "rpc"})
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo", "trace", "new"}, {"kind": "profiling"})
    legacy.refresh_from_db()
    trace.refresh_from_db()
    assert legacy.source == []
    assert trace.source == ["trace", "profiling"]
    assert trace.extra_data == {"kind": "service", "category": "rpc"}
    assert TopoNode.objects.get(topo_key="new").source == ["profiling"]


def test_successful_empty_log_check_keeps_data_time() -> None:
    node = make_node(heartbeat={"log": {"last_data_at": 90, "checked_at": 100}})
    response = log_response()
    response["aggregations"]["service_names"]["buckets"] = []
    with (
        mock.patch("apm.core.discover.log.service.api.log_search.es_query_dsl", return_value=response),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat["log"]["last_data_at"] == 90
    assert node.heartbeat["log"]["checked_at"] > 100


def profile_builder(results: list[Any]) -> mock.MagicMock:
    builder = mock.MagicMock()
    for name in (
        "with_api_type",
        "with_time",
        "with_metric_fields",
        "with_dimension_fields",
        "with_offset_limit",
        "with_service_filter",
        "with_type",
        "with_general_filters",
    ):
        getattr(builder, name).return_value = builder
    builder.execute.side_effect = results
    return builder


def test_profile_discover_keeps_old_table_and_creates_topology() -> None:
    existing = make_node("trace", source=["trace"], heartbeat={"trace": {"last_data_at": 90, "checked_at": 100}})
    builder = profile_builder([])
    builder.execute.side_effect = [
        [
            {"service_name": "demo", "type": "cpu", "sample_type": "cpu", "count": 1},
            {"service_name": "demo", "type": "alloc_objects", "sample_type": "alloc_objects", "count": 1},
        ],
        [{"period": 10_000_000, "period_type": "cpu/nanoseconds", "type": "cpu", "value": 100}],
        [{"period": 10, "period_type": "space/bytes", "type": "alloc_objects", "value": 100}],
    ]
    discover = ProfileServiceDiscover(datasource())
    with (
        mock.patch.object(discover, "get_builder", return_value=builder),
    ):
        discover.discover(100000, 200000)
    node = TopoNode.objects.get(topo_key="demo")
    assert node.source == ["profiling"]
    assert node.extra_data["kind"] == "profiling"
    assert node.heartbeat["profiling"]["last_data_at"] == 200
    profiles = list(ProfileService.objects.filter(name="demo"))
    assert len(profiles) == 2
    assert profiles[0].last_check_time == profiles[1].last_check_time
    existing.refresh_from_db()
    assert existing.heartbeat["trace"] == {"last_data_at": 90, "checked_at": 100}
    assert existing.heartbeat["profiling"]["last_data_at"] is None


def test_profile_failed_sample_query_does_not_touch_heartbeat() -> None:
    node = make_node(heartbeat={"profiling": {"last_data_at": 90, "checked_at": 100}})
    builder = profile_builder(
        [[{"service_name": "demo", "type": "cpu", "sample_type": "cpu", "count": 1}], RuntimeError("sample failed")]
    )
    discover = ProfileServiceDiscover(datasource())
    with mock.patch.object(discover, "get_builder", return_value=builder), pytest.raises(RuntimeError):
        discover.discover(100000, 200000)
    node.refresh_from_db()
    assert node.heartbeat == {"profiling": {"last_data_at": 90, "checked_at": 100}}
    assert ProfileService.objects.count() == 0


def test_metric_promotes_profile_node_without_overwriting_other_nodes() -> None:
    profile = make_node(source=["profiling"], extra_data={"kind": "profiling", "category": "profiling"})
    trace = make_node("trace", source=["trace"], extra_data={"kind": "service", "category": "rpc"})
    discover = MetricServiceDiscover(datasource())
    with (
        mock.patch.object(
            discover, "query_dimensions", side_effect=[[{"service_name": "demo"}, {"service_name": "trace"}], []]
        ),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service", "category": "other"}),
    ):
        discover.discover_services(100, 200)
    profile.refresh_from_db()
    trace.refresh_from_db()
    assert profile.extra_data["kind"] == "service"
    assert profile.source == ["profiling", "metric"]
    assert trace.extra_data == {"kind": "service", "category": "rpc"}


def test_metric_splits_discovery_but_queries_heartbeat_once(settings: Any) -> None:
    settings.APM_APPLICATION_METRIC_DISCOVER_SPLIT_DELTA = 200
    discover = MetricServiceDiscover(datasource())
    with (
        mock.patch.object(discover, "discover_services") as services,
        mock.patch.object(discover, "discover_heartbeat") as heartbeat,
    ):
        discover.discover(100, 750)
    assert services.call_args_list == [
        mock.call(100, 300),
        mock.call(300, 500),
        mock.call(500, 700),
        mock.call(700, 750),
    ]
    heartbeat.assert_called_once_with(100, 750)


@pytest.mark.parametrize("timestamp", [1789530120, 1789530120000, "2026-09-16T03:42:00Z"])
def test_metric_timestamp_units(timestamp: Any) -> None:
    node = make_node()
    series = metric_series(["service_name"], ["demo"], [[timestamp, 0]])
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=[{"series": [series]}, {"series": []}, {"series": []}, {"series": []}],
    ):
        MetricServiceDiscover(datasource()).discover_heartbeat(1789530000, 1789530600)
    node.refresh_from_db()
    assert node.heartbeat["metric"]["last_data_at"] == 1789530120


def test_metric_does_not_overwrite_concurrent_trace_classification() -> None:
    node = make_node(source=["profiling"], extra_data={"kind": "profiling", "category": "profiling"})
    discover = MetricServiceDiscover(datasource())
    old_mapping = discover.list_exists_mapping()
    TopoNode.objects.filter(id=node.id).update(
        source=["profiling", "trace"], extra_data={"kind": "service", "category": "rpc"}
    )
    with (
        mock.patch.object(discover, "query_dimensions", side_effect=[[{"service_name": "demo"}], []]),
        mock.patch.object(discover, "list_exists_mapping", return_value=old_mapping),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service", "category": "other"}),
    ):
        discover.discover_services(100, 200)
    node.refresh_from_db()
    assert node.extra_data == {"kind": "service", "category": "rpc"}


def test_log_paginates_all_services_before_publishing() -> None:
    page = log_response()
    page["aggregations"]["service_names"]["buckets"] = [
        {"key": {"service_name": f"svc-{number}"}, "last_data_at": {"value": 150000}} for number in range(1000)
    ]
    page["aggregations"]["service_names"]["after_key"] = {"service_name": "svc-999"}
    second_page = log_response("svc-1000", 180000)
    with (
        mock.patch(
            "apm.core.discover.log.service.api.log_search.es_query_dsl",
            side_effect=[
                page,
                second_page,
                log_response("svc-1000", 190000),
            ],
        ) as query,
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service"}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    assert TopoNode.objects.count() == 1001
    assert query.call_count == 3
    assert query.call_args_list[1].kwargs["body"]["aggs"]["service_names"]["composite"]["after"] == {
        "service_name": "svc-999"
    }
    assert "after" not in query.call_args_list[2].kwargs["body"]["aggs"]["service_names"]["composite"]
    assert TopoNode.objects.get(topo_key="svc-1000").heartbeat["log"]["last_data_at"] == 190


def test_log_failed_later_page_does_not_publish_partial_coverage() -> None:
    node = make_node(heartbeat={"log": {"last_data_at": 90, "checked_at": 100}})
    page = log_response("new")
    page["aggregations"]["service_names"]["after_key"] = {"service_name": "new"}
    with (
        mock.patch(
            "apm.core.discover.log.service.api.log_search.es_query_dsl",
            side_effect=[page, RuntimeError("next page failed")],
        ),
        pytest.raises(RuntimeError),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == {"log": {"last_data_at": 90, "checked_at": 100}}
    assert TopoNode.objects.count() == 1


def test_complete_empty_check_and_partial_observation_have_different_coverage() -> None:
    first = make_node("first")
    second = make_node("second")
    TopoNode.touch_heartbeat(2, "app", "log", {"first": 90}, 100)
    second.refresh_from_db()
    assert second.heartbeat == {}
    TopoNode.touch_heartbeat(2, "app", "log", {}, 200, check_all_services=True)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.heartbeat["log"] == {"last_data_at": 90, "checked_at": 200}
    assert second.heartbeat["log"] == {"last_data_at": None, "checked_at": 200}


@pytest.mark.parametrize("error_code", [1205, 1213, 2006])
def test_database_lock_failure_rolls_back_but_other_errors_propagate(error_code: int) -> None:
    node = make_node(heartbeat={"trace": {"last_data_at": 80, "checked_at": 90}})
    original = QuerySet.bulk_update

    def fail_after_write(queryset: QuerySet, *args: Any, **kwargs: Any) -> None:
        original(queryset, *args, **kwargs)
        raise OperationalError(error_code, "database failure")

    with mock.patch.object(QuerySet, "bulk_update", fail_after_write):
        if error_code == 2006:
            with pytest.raises(OperationalError):
                TopoNode.touch_heartbeat(2, "app", "trace", {"demo": 100}, 110)
        else:
            assert TopoNode.touch_heartbeat(2, "app", "trace", {"demo": 100}, 110) is False
    node.refresh_from_db()
    assert node.heartbeat == {"trace": {"last_data_at": 80, "checked_at": 90}}


@pytest.mark.parametrize("response", [{}, {"list": None}, {"list": {}}])
@pytest.mark.parametrize("stage", ["aggregate", "sample"])
def test_profile_invalid_response_does_not_refresh_or_create(response: dict[str, Any], stage: str) -> None:
    previous = {"profiling": {"last_data_at": 1789957493, "checked_at": 1789957512}}
    node = make_node(heartbeat=previous)
    responses = [response]
    if stage == "sample":
        responses.insert(0, {"list": [{"service_name": "demo", "type": "cpu", "sample_type": "cpu", "count": 1}]})
    with mock.patch("apm.core.handlers.profile.query.api.bkdata.query_profile_data", side_effect=responses):
        with pytest.raises(ValueError, match="list"):
            ProfileServiceDiscover(datasource()).discover(1789956912000, 1789957512000)
    node.refresh_from_db()
    assert node.heartbeat == previous
    assert ProfileService.objects.count() == 0


def test_profile_empty_query_is_successful_check() -> None:
    node = make_node(heartbeat={"profiling": {"last_data_at": 90, "checked_at": 100}})
    with mock.patch("apm.core.handlers.profile.query.api.bkdata.query_profile_data", return_value={"list": []}):
        ProfileServiceDiscover(datasource()).discover(1789956912000, 1789957512000)
    node.refresh_from_db()
    assert node.heartbeat["profiling"]["last_data_at"] == 90
    assert node.heartbeat["profiling"]["checked_at"] > 100
    assert ProfileService.objects.count() == 0


def test_profile_reuses_group_count_and_requires_a_sample() -> None:
    groups = [
        {"service_name": "boundary", "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 10000},
        {"service_name": "large", "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 10001},
        {"service_name": "no-sample", "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 10},
    ]
    sample = {"period": "10000000", "period_type": "cpu/nanoseconds", "type": "cpu", "value": "10000000"}

    def query(**kwargs: Any) -> dict[str, Any]:
        request = json.loads(kwargs["sql"])
        params = request["api_params"]
        assert request["result_table_id"] == "2_apm.app"
        assert (params["start"], params["end"]) == (1789956912000, 1789957512000)
        if request["api_type"] == "select_aggregate":
            return {"list": groups}
        assert request["api_type"] == "query_sample_by_json"
        assert params["general_filters"] == {"sample_type": "op_eq|cpu/nanoseconds"}
        return {"list": [] if params["service_name"] == "no-sample" else [sample]}

    with mock.patch("apm.core.handlers.profile.query.api.bkdata.query_profile_data", side_effect=query) as request:
        ProfileServiceDiscover(datasource()).discover(1789956912000, 1789957512000)
    assert request.call_count == 4  # 一次聚合加每个组合一次样本查询。
    assert json.loads(request.call_args_list[0].kwargs["sql"])["api_params"]["metric_fields"] == "count(*) AS count"
    profiles = {p.name: p for p in ProfileService.objects.all()}
    assert set(profiles) == {"boundary", "large"}
    assert profiles["boundary"].is_large is False
    assert profiles["large"].is_large is True
    assert profiles["boundary"].frequency == 100
    assert profiles["boundary"].last_check_time == profiles["large"].last_check_time
    assert not TopoNode.objects.filter(topo_key="no-sample").exists()
    assert TopoNode.objects.get(topo_key="large").heartbeat["profiling"]["last_data_at"] == 1789957512


@pytest.mark.parametrize("stage", ["dimensions", "heartbeat"])
def test_metric_soft_timeout_aborts_remaining_queries(stage: str) -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 90, "checked_at": 100}})
    discover = MetricServiceDiscover(datasource())
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql", side_effect=SoftTimeLimitExceeded
    ) as query:
        if stage == "heartbeat":
            with mock.patch.object(discover, "discover_services"), pytest.raises(SoftTimeLimitExceeded):
                discover.discover(100, 700)
        else:
            with pytest.raises(SoftTimeLimitExceeded):
                discover.discover(100, 700)
    assert query.call_count == 1
    node.refresh_from_db()
    assert node.heartbeat == {"metric": {"last_data_at": 90, "checked_at": 100}}


def test_profile_later_sample_failure_keeps_existing_profile_and_heartbeat() -> None:
    discover = ProfileServiceDiscover(datasource())
    groups = [{"service_name": "demo", "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 10001}]
    sample = {"period": "10000000", "period_type": "cpu/nanoseconds", "type": "cpu", "value": "1"}
    with mock.patch(
        "apm.core.handlers.profile.query.api.bkdata.query_profile_data",
        side_effect=[{"list": groups}, {"list": [sample]}],
    ):
        discover.discover(1789956912000, 1789957512000)
    profile = ProfileService.objects.get(name="demo")
    node = TopoNode.objects.get(topo_key="demo")
    old_heartbeat = node.heartbeat
    old_check_time = profile.last_check_time

    groups = [
        {"service_name": name, "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 1}
        for name in ["demo", "new-service"]
    ]
    with (
        mock.patch(
            "apm.core.handlers.profile.query.api.bkdata.query_profile_data",
            side_effect=[{"list": groups}, {"list": [sample]}, RuntimeError("later sample failed")],
        ),
        pytest.raises(RuntimeError),
    ):
        discover.discover(1789957512000, 1789958112000)
    profile.refresh_from_db()
    node.refresh_from_db()
    assert profile.is_large is True
    assert profile.last_check_time == old_check_time
    assert node.heartbeat == old_heartbeat
    assert ProfileService.objects.count() == TopoNode.objects.count() == 1

    with mock.patch(
        "apm.core.handlers.profile.query.api.bkdata.query_profile_data",
        side_effect=[{"list": groups[:1]}, {"list": [sample]}],
    ):
        discover.discover(1789957512000, 1789958112000)
    profile.refresh_from_db()
    node.refresh_from_db()
    assert ProfileService.objects.count() == 1
    assert profile.is_large is False
    assert profile.last_check_time >= old_check_time
    assert node.heartbeat["profiling"]["last_data_at"] == 1789958112
