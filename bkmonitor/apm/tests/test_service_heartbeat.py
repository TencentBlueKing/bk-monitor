import os

from collections.abc import Iterator
from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from django.db import OperationalError, connections
from django.db.models.query import QuerySet
from django.test import override_settings

from apm.core.discover.exceptions import IncompleteDiscoveryError
from apm.core.discover.log.service import ServiceDiscover as LogServiceDiscover
from apm.core.discover.metric.service import ServiceDiscover as MetricServiceDiscover
from apm.core.discover.profile.service import ServiceDiscover as ProfileServiceDiscover
from apm.models import ProfileService, TopoNode
from apm.resources import QueryTopoNodeResource


@pytest.fixture
def heartbeat_db(django_db_blocker: Any) -> Iterator[str]:
    """默认使用内存 SQLite；显式指定测试 socket 时连接隔离的 MySQL 测试库。"""
    alias = "apm_heartbeat_test"
    config = deepcopy(connections.databases["default"])
    config.update(ENGINE="django.db.backends.sqlite3", NAME=":memory:", OPTIONS={}, ATOMIC_REQUESTS=False)
    mysql_socket: str | None = os.environ.get("APM_HEARTBEAT_TEST_MYSQL_SOCKET")
    if mysql_socket:
        config.update(
            ENGINE="django.db.backends.mysql",
            NAME="apm_heartbeat_test",
            USER="root",
            PASSWORD="",
            HOST="localhost",
            PORT="",
            OPTIONS={"unix_socket": mysql_socket, "charset": "utf8mb4"},
        )
    connections.databases[alias] = config
    with (
        django_db_blocker.unblock(),
        override_settings(USE_TZ=False),
        mock.patch("apm.models.topo.router.db_for_write", return_value=alias),
        mock.patch("apm.models.topo.router.db_for_read", return_value=alias),
    ):
        connection = connections[alias]
        with connection.schema_editor() as editor:
            editor.create_model(TopoNode)
            editor.create_model(ProfileService)
        try:
            yield alias
        finally:
            if mysql_socket:
                with connection.schema_editor() as editor:
                    editor.delete_model(ProfileService)
                    editor.delete_model(TopoNode)
            connection.close()
            del connections[alias]
            connections.databases.pop(alias)


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


def test_heartbeat_monotonic_and_preserves_unrequested_fields(heartbeat_db: str) -> None:
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


def test_heartbeat_scope_duplicates_empty_and_missing_nodes(heartbeat_db: str) -> None:
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


def test_heartbeat_locks_and_rolls_back_on_routed_database(heartbeat_db: str) -> None:
    node = make_node()
    select_for_update = QuerySet.select_for_update
    bulk_update = QuerySet.bulk_update

    def lock(queryset: QuerySet, *args: Any, **kwargs: Any) -> QuerySet:
        assert queryset.db == heartbeat_db
        assert connections[heartbeat_db].in_atomic_block
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


def test_log_discover_creates_nodes_and_merges_fields(heartbeat_db: str) -> None:
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
def test_log_failure_does_not_write_or_renew(heartbeat_db: str, failure: str) -> None:
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


def test_metric_heartbeat_keys_and_non_null_zero(heartbeat_db: str) -> None:
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
def test_metric_partial_failure_keeps_old_heartbeat(heartbeat_db: str, response: Any) -> None:
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


def test_legacy_topology_filters_only_new_source_nodes(heartbeat_db: str) -> None:
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


def test_upsert_preserves_metadata_and_legacy_empty_source(heartbeat_db: str) -> None:
    legacy = make_node()
    trace = make_node("trace", source=["trace"], extra_data={"kind": "service", "category": "rpc"})
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo", "trace", "new"}, {"kind": "profiling"})
    legacy.refresh_from_db()
    trace.refresh_from_db()
    assert legacy.source == []
    assert trace.source == ["trace", "profiling"]
    assert trace.extra_data == {"kind": "service", "category": "rpc"}
    assert TopoNode.objects.get(topo_key="new").source == ["profiling"]


def test_successful_empty_log_check_keeps_data_time(heartbeat_db: str) -> None:
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


def test_profile_discover_keeps_old_table_and_creates_topology(heartbeat_db: str) -> None:
    existing = make_node("trace", source=["trace"], heartbeat={"trace": {"last_data_at": 90, "checked_at": 100}})
    builder = profile_builder([])
    builder.execute.side_effect = [
        [
            {"service_name": "demo", "type": "cpu", "sample_type": "cpu"},
            {"service_name": "demo", "type": "alloc_objects", "sample_type": "alloc_objects"},
        ],
        [{"period": 10_000_000, "period_type": "cpu/nanoseconds", "type": "cpu", "value": 100}],
        [{"period": 10, "period_type": "space/bytes", "type": "alloc_objects", "value": 100}],
    ]
    discover = ProfileServiceDiscover(datasource())
    with (
        mock.patch.object(discover, "get_builder", return_value=builder),
        mock.patch.object(discover, "is_large_service", return_value=False),
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


def test_profile_failed_sample_query_does_not_touch_heartbeat(heartbeat_db: str) -> None:
    node = make_node(heartbeat={"profiling": {"last_data_at": 90, "checked_at": 100}})
    builder = profile_builder(
        [[{"service_name": "demo", "type": "cpu", "sample_type": "cpu"}], RuntimeError("sample failed")]
    )
    discover = ProfileServiceDiscover(datasource())
    with mock.patch.object(discover, "get_builder", return_value=builder), pytest.raises(RuntimeError):
        discover.discover(100000, 200000)
    node.refresh_from_db()
    assert node.heartbeat == {"profiling": {"last_data_at": 90, "checked_at": 100}}
    assert ProfileService.objects.count() == 0


def test_metric_promotes_profile_node_without_overwriting_other_nodes(heartbeat_db: str) -> None:
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
def test_metric_timestamp_units(heartbeat_db: str, timestamp: Any) -> None:
    node = make_node()
    series = metric_series(["service_name"], ["demo"], [[timestamp, 0]])
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=[{"series": [series]}, {"series": []}, {"series": []}, {"series": []}],
    ):
        MetricServiceDiscover(datasource()).discover_heartbeat(1789530000, 1789530600)
    node.refresh_from_db()
    assert node.heartbeat["metric"]["last_data_at"] == 1789530120


def test_metric_does_not_overwrite_concurrent_trace_classification(heartbeat_db: str) -> None:
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


def test_log_paginates_all_services_before_publishing(heartbeat_db: str) -> None:
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


def test_log_failed_later_page_does_not_publish_partial_coverage(heartbeat_db: str) -> None:
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


def test_complete_empty_check_and_partial_observation_have_different_coverage(heartbeat_db: str) -> None:
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
def test_database_lock_failure_rolls_back_but_other_errors_propagate(heartbeat_db: str, error_code: int) -> None:
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
