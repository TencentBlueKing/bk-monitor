from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from django.db import OperationalError, connections, router
from django.db.models.query import QuerySet
from django.utils import timezone

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
    return SimpleNamespace(bk_biz_id=2, app_name="app", result_table_id="2_apm.app", retention=7, index_set_id=123)


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
        assert node.heartbeat == {"log": {"checked_at": 300}}
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


def log_response(name: str = "demo", timestamp: int = 150000) -> list[dict[str, Any]]:
    return [{"resource": {"service": {"name": name}, "server": name}, "time": timestamp}]


def test_log_discover_creates_nodes_and_merges_fields() -> None:
    existing = make_node("existing", source=["trace"], heartbeat={"trace": {"last_data_at": 80, "checked_at": 90}})
    with (
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            side_effect=[log_response(timestamp=150000), log_response(timestamp=190000)],
        ) as query,
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service", "category": "other"}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    created = TopoNode.objects.get(topo_key="demo")
    assert created.source == ["log"]
    assert created.heartbeat["log"]["last_data_at"] == 190
    assert query.call_count == 2
    existing.refresh_from_db()
    assert "log" not in existing.heartbeat
    assert existing.heartbeat["trace"] == {"last_data_at": 80, "checked_at": 90}


def test_log_failure_does_not_write_or_renew() -> None:
    previous = {"log": {"last_data_at": 90, "checked_at": 100}}
    node = make_node(heartbeat=previous)
    with (
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            side_effect=[log_response("new"), RuntimeError("failed")],
        ),
        pytest.raises(RuntimeError),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == previous
    assert TopoNode.objects.count() == 1


def metric_series(keys: list[str], values: list[str], points: list[list[Any]]) -> dict[str, Any]:
    return {"group_keys": keys, "group_values": values, "columns": ["_time", "_value"], "values": points}


def test_metric_heartbeat_uses_sample_times_for_all_service_keys() -> None:
    for name in ("demo", "demo-redis", "demo-kafka", "http:remote", "empty"):
        make_node(name)
    responses = [
        {
            "series": [
                metric_series(
                    ["service_name"],
                    ["demo"],
                    [[150000, 140.9], [190000, 140.9], [195000, None], [200000, 0], [200000, 140]],
                )
            ]
        },
        {"series": [metric_series(["service_name", "db_system"], ["demo", "redis"], [[190000, 160]])]},
        {"series": [metric_series(["service_name", "messaging_system"], ["demo", "kafka"], [[190000, 170]])]},
        {"series": [metric_series(["peer_service"], ["remote"], [[190000, 180]])]},
    ]
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        return_value={"series": [series for response in responses for series in response["series"]]},
    ) as query:
        MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    assert {
        node.topo_key: node.heartbeat["metric"]["last_data_at"] for node in TopoNode.objects.exclude(topo_key="empty")
    } == {
        "demo": 170,
        "demo-redis": 160,
        "demo-kafka": 170,
        "http:remote": 180,
    }
    assert TopoNode.objects.get(topo_key="empty").heartbeat == {}
    assert "trace" not in TopoNode.objects.get(topo_key="demo").heartbeat
    for name, timestamp in (("demo-redis", 160), ("demo-kafka", 170), ("http:remote", 180)):
        assert TopoNode.objects.get(topo_key=name).heartbeat["trace"]["last_data_at"] == timestamp
    assert query.call_count == 1
    assert all(call.args[0]["step"] == "100s" for call in query.call_args_list)
    assert all('__name__="custom:2_apm:app:bk_apm_count"' in call.args[0]["promql"] for call in query.call_args_list)


@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("failed"),
        {"series": [], "is_partial": True},
        {"series": [], "status": {"code": "QUERY_TS_PARTIAL"}},
        {"series": [], "status": {"code": "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS"}},
        {"series": [], "status": {"code": "EXCEEDS_MAXIMUM_LIMIT"}},
        {"series": [], "status": {"code": "EXCEEDS_MAXIMUM_SLIMIT"}},
    ],
)
def test_metric_query_error_or_empty_result_keeps_heartbeat(response: Any) -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 90, "checked_at": 100}})
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=response if isinstance(response, Exception) else None,
        return_value=response,
    ):
        MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == {"metric": {"last_data_at": 90, "checked_at": 100}}


def test_topology_includes_all_discovery_sources() -> None:
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
        make_node(
            name, source=sources, heartbeat={"trace": {"last_data_at": 10, "checked_at": 20}} if name == "trace" else {}
        )
    with mock.patch(
        "apm.resources.DiscoverHandler.get_retention_filter_params", return_value={"bk_biz_id": 2, "app_name": "app"}
    ):
        nodes = QueryTopoNodeResource().perform_request({"bk_biz_id": 2, "app_name": "app"})
    assert {node["topo_key"] for node in nodes} == {
        "legacy",
        "trace",
        "metric",
        "mixed",
        "log",
        "profile",
        "both",
        "reverse",
    }
    stored = {node.topo_key: node for node in TopoNode.objects.all()}
    for node in nodes:
        assert node["heartbeat"] == stored[node["topo_key"]].heartbeat
        assert node["source"] == stored[node["topo_key"]].source


def test_upsert_preserves_metadata_and_legacy_empty_source() -> None:
    legacy = make_node()
    trace = make_node("trace", source=["trace"], extra_data={"kind": "service", "category": "rpc"})
    template = {"kind": "service", "category": "other"}
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo", "trace", "new"}, template)
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"trace"}, template)
    legacy.refresh_from_db()
    trace.refresh_from_db()
    assert legacy.source == []
    assert trace.source == ["trace", "profiling"]
    assert trace.extra_data == {"kind": "service", "category": "rpc"}
    created = TopoNode.objects.get(topo_key="new")
    assert created.source == ["profiling"]
    assert created.extra_data == template


def test_empty_log_result_keeps_heartbeat_unchanged() -> None:
    node = make_node(heartbeat={"log": {"last_data_at": 90, "checked_at": 100}})
    response = []
    with (
        mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=response),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat["log"]["last_data_at"] == 90
    assert node.heartbeat["log"]["checked_at"] == 100


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
        [{"service_name": "demo", "count": 10001}],
        [{"period": 10, "period_type": "space/bytes", "type": "alloc_objects", "value": 100}],
        [{"service_name": "demo", "count": 1}],
    ]
    check_time = timezone.now()
    completed_at = int(check_time.timestamp()) + 30
    discover = ProfileServiceDiscover(datasource())
    with (
        mock.patch.object(discover, "get_builder", return_value=builder),
        mock.patch.object(discover, "clear_expired"),
        mock.patch("apm.core.discover.profile.service.timezone.now", return_value=check_time),
        mock.patch("apm.core.discover.profile.service.time.time", return_value=completed_at),
    ):
        discover.discover(100000, 200000)
    node = TopoNode.objects.get(topo_key="demo")
    assert node.source == ["profiling"]
    assert node.extra_data == TopoNode.get_empty_extra_data()
    assert node.heartbeat["profiling"]["last_data_at"] == int(
        ProfileService.objects.first().last_check_time.timestamp()
    )
    profiles = list(ProfileService.objects.filter(name="demo"))
    assert len(profiles) == 2
    assert profiles[0].last_check_time == profiles[1].last_check_time == check_time
    assert profiles[0].is_large and not profiles[1].is_large
    assert profiles[0].frequency == 100
    assert node.heartbeat["profiling"]["checked_at"] == completed_at
    assert builder.with_metric_fields.call_args_list == [
        mock.call("count(1)"),
        mock.call("count(*) AS count"),
        mock.call("count(*) AS count"),
    ]
    existing.refresh_from_db()
    assert existing.heartbeat["trace"] == {"last_data_at": 90, "checked_at": 100}
    assert "profiling" not in existing.heartbeat


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


def test_log_limit_result_only_updates_observed_services() -> None:
    unknown = make_node("unknown", heartbeat={"log": {"last_data_at": 90, "checked_at": 100}})
    with (
        mock.patch.object(LogServiceDiscover, "QUERY_MAX_LIMIT", 1),
        mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=[log_response(), []]),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service"}),
    ):
        LogServiceDiscover(datasource()).discover(100, 200)
    unknown.refresh_from_db()
    assert unknown.heartbeat == {"log": {"last_data_at": 90, "checked_at": 100}}
    assert TopoNode.objects.get(topo_key="demo").heartbeat["log"]["last_data_at"] == 150


def test_log_without_index_set_does_not_query_or_renew() -> None:
    source = datasource()
    source.index_set_id = None
    node = make_node(heartbeat={"log": {"last_data_at": 90, "checked_at": 100}})
    with mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query") as query:
        LogServiceDiscover(source).discover(100, 200)
    query.assert_not_called()
    node.refresh_from_db()
    assert node.heartbeat == {"log": {"last_data_at": 90, "checked_at": 100}}


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


def test_empty_profile_result_keeps_heartbeat_unchanged() -> None:
    node = make_node(heartbeat={"profiling": {"last_data_at": 90, "checked_at": 100}})
    with (
        mock.patch("apm.core.handlers.profile.query.api.bkdata.query_profile_data", return_value={"list": []}),
        mock.patch.object(ProfileServiceDiscover, "clear_expired"),
    ):
        ProfileServiceDiscover(datasource()).discover(1789956912000, 1789957512000)
    node.refresh_from_db()
    assert node.heartbeat["profiling"]["last_data_at"] == 90
    assert node.heartbeat["profiling"]["checked_at"] == 100
    assert ProfileService.objects.count() == 0


def test_profile_later_sample_failure_keeps_existing_profile_and_heartbeat() -> None:
    discover = ProfileServiceDiscover(datasource())
    groups = [{"service_name": "demo", "type": "cpu", "sample_type": "cpu/nanoseconds", "count": 10001}]
    sample = {"period": "10000000", "period_type": "cpu/nanoseconds", "type": "cpu", "value": "1"}
    with (
        mock.patch(
            "apm.core.handlers.profile.query.api.bkdata.query_profile_data",
            side_effect=[{"list": groups}, {"list": [sample]}, {"list": [{"service_name": "demo", "count": 10001}]}],
        ),
        mock.patch.object(discover, "clear_expired"),
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
            side_effect=[{"list": groups}, {"list": [sample]}, {"list": []}, RuntimeError("later sample failed")],
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

    with (
        mock.patch(
            "apm.core.handlers.profile.query.api.bkdata.query_profile_data",
            side_effect=[{"list": groups[:1]}, {"list": [sample]}, {"list": []}],
        ),
        mock.patch.object(discover, "clear_expired"),
    ):
        discover.discover(1789957512000, 1789958112000)
    profile.refresh_from_db()
    node.refresh_from_db()
    assert ProfileService.objects.count() == 1
    assert profile.is_large is False
    assert profile.last_check_time >= old_check_time
    assert node.heartbeat["profiling"]["last_data_at"] == int(profile.last_check_time.timestamp())


@pytest.mark.parametrize("sample_time", [90, 0, None])
def test_metric_old_or_missing_samples_do_not_advance_data_time(sample_time: Any) -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 90, "checked_at": 100}})
    series = metric_series(["service_name"], ["demo"], [[150000, sample_time], [200000, sample_time]])
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=[{"series": [series]}, {"series": []}, {"series": []}, {"series": []}],
    ):
        MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    node.refresh_from_db()
    assert node.heartbeat["metric"]["last_data_at"] == 90
    assert (node.heartbeat["metric"]["checked_at"] > 100) == (sample_time is not None)


@pytest.mark.parametrize("status", [None, {"code": "SPACE_TABLE_ID_FIELD_MISSING_FALLBACK"}])
def test_metric_non_failure_status_allows_heartbeat(status: Any) -> None:
    node = make_node(heartbeat={"metric": {"last_data_at": 90, "checked_at": 100}})
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        return_value={"series": [metric_series(["service_name"], ["demo"], [[180000, 150]])], "status": status},
    ):
        MetricServiceDiscover(datasource()).discover_heartbeat(100, 200)
    node.refresh_from_db()
    assert node.heartbeat["metric"]["last_data_at"] == 150


def test_sparse_heartbeat_only_updates_observed_nodes() -> None:
    previous = {"log": {"last_data_at": 80, "checked_at": 90}}
    for index in range(100):
        make_node(str(index), heartbeat=previous)
    TopoNode.touch_heartbeat(2, "app", "log", {str(index): 100 for index in range(10)}, 110)
    for node in TopoNode.objects.all():
        assert node.heartbeat == (
            {"log": {"last_data_at": 100, "checked_at": 110}} if int(node.topo_key) < 10 else previous
        )
    with mock.patch.object(TopoNode.objects, "using") as query:
        assert TopoNode.touch_heartbeat(2, "app", "log", {}, 200)
        query.assert_not_called()
    TopoNode.touch_heartbeat(2, "app", "log", {"0": None}, 200)
    assert TopoNode.objects.get(topo_key="0").heartbeat["log"] == {"last_data_at": 100, "checked_at": 200}
    assert TopoNode.objects.get(topo_key="1").heartbeat["log"]["checked_at"] == 110


def test_metric_dimensions_optional_sample_time_and_single_window() -> None:
    discover = MetricServiceDiscover(datasource())
    series = metric_series(["service_name"], ["demo"], [[150000, 90], [190000, None]])
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql", return_value={"series": [series]}
    ):
        assert discover.query_dimensions("query", 100, 300) == [{"service_name": "demo"}]
        assert discover.query_dimensions("query", 100, 300, True) == [{"service_name": "demo", "last_data_at": 90}]
    node = make_node()
    with mock.patch(
        "apm.core.discover.metric.service.api.unify_query.query_data_by_promql",
        side_effect=[{"series": []}, {"series": []}, {"series": [series]}],
    ) as query:
        discover.discover(100, 300)
    assert query.call_count == 3
    assert all(
        (c.args[0]["start"], c.args[0]["end"], c.args[0]["step"]) == (100, 300, "200s") for c in query.call_args_list
    )
    node.refresh_from_db()
    assert node.heartbeat["metric"]["last_data_at"] == 90
