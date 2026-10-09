from types import SimpleNamespace
from unittest import mock

import pytest

from apm.constants import DiscoverRuleType
from apm.core.discover.node import NodeDiscover
from apm.core.discover.profile.service import ServiceDiscover as ProfileDiscover
from apm.core.discover.relation import RelationDiscover
from apm.models import TopoNode
from apm.tests.test_service_heartbeat import (
    datasource,
    make_node,
    profile_builder,
)
from constants.apm import SpanKind
from kernel_api.resource.operation.handlers import apm_service_count
from kernel_api.rpc.functions.admin.apm import _load_service_count_map
from monitor_web.search.handlers.apm import ApmSearchHandler
from monitor_web.search.handlers.base import SearchScope
from monitor_web.statistics.v2.apm import APMCollector


pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.mark.parametrize("sources,kind", [(["profiling"], "service"), (["log"], "service"), (["metric"], "service")])
def test_relation_discovery_does_not_consume_new_only_classification(sources: list[str], kind: str) -> None:
    extra_data = (
        {"kind": "profiling", "category": "profiling"}
        if sources != ["metric"]
        else {"kind": "service", "category": "rpc"}
    )
    make_node("consumer", source=sources, extra_data=extra_data)
    discover = object.__new__(RelationDiscover)
    discover.bk_biz_id = 2
    discover.app_name = "app"
    rule = SimpleNamespace(
        topo_kind="component",
        category_id="messaging",
        predicate_key=("attributes", "messaging.system"),
        instance_keys=[("attributes", "messaging.system")],
    )
    span = {
        "kind": SpanKind.SPAN_KIND_CONSUMER,
        "parent_span_id": "producer",
        "resource": {"service.name": "consumer"},
        "attributes": {"messaging.system": "kafka"},
    }
    with (
        mock.patch.object(discover, "get_rules", return_value=([rule], SimpleNamespace(topo_kind="service"))),
        mock.patch("apm.core.discover.relation.TopoRelation.objects.bulk_create") as create,
        mock.patch.object(discover, "handle_cache_refresh_after_create"),
    ):
        discover.discover([span], {})
    relation = create.call_args.args[0][0]
    assert relation.to_topo_key == "consumer"
    assert relation.to_topo_key_kind == kind
    assert relation.to_topo_key_category == ("rpc" if sources == ["metric"] else "http")


def test_service_counts_and_search_include_all_sources() -> None:
    make_node("old", source=["trace"])
    make_node("new-log", source=["log"])
    make_node("new-profile", source=["profiling"])
    assert _load_service_count_map([SimpleNamespace(bk_biz_id=2, app_name="app")]) == {(2, "app"): 3}
    assert apm_service_count(2) == 3
    collector = object.__new__(APMCollector)
    collector.__dict__["biz_info"] = {2: {}}
    assert {node.topo_key for node in collector.top_node_biz_map[2]} == {"old", "new-log", "new-profile"}
    search = object.__new__(ApmSearchHandler)
    search.scope = SearchScope.BIZ
    search.bk_biz_id = 2
    with mock.patch.object(search, "collect_results_by_biz", side_effect=lambda results, **kwargs: results):
        results = search.search_service("")
    assert {result.title for result in results} == {"old", "new-log", "new-profile"}
    # 诊断用途的原始节点读取保留全部数据。
    assert TopoNode.objects.count() == 3


def test_profile_truncated_result_only_checks_observed_services() -> None:
    unknown = make_node("unknown", heartbeat={"profiling": {"last_data_at": 50, "checked_at": 60}})
    discover = ProfileDiscover(datasource())
    discover.MAX_DIMENSION_COMBINATION_LIMIT = 1
    builder = profile_builder(
        [
            [{"service_name": "demo", "type": "cpu", "sample_type": "cpu", "count": 1}],
            [{"period": 10_000_000, "period_type": "cpu/nanoseconds", "type": "cpu", "value": 100}],
        ]
    )
    with (
        mock.patch.object(discover, "get_builder", return_value=builder),
        mock.patch("apm.core.discover.profile.service.EventReportHelper.report"),
        mock.patch.object(discover, "clear_expired"),
    ):
        discover.discover(100000, 200000)
    assert TopoNode.objects.get(topo_key="demo").heartbeat["profiling"]["last_data_at"] == 200
    unknown.refresh_from_db()
    assert unknown.heartbeat == {"profiling": {"last_data_at": 50, "checked_at": 60}}


@pytest.mark.parametrize("initial_sources", [[], ["metric"], ["profiling"]])
def test_trace_update_preserves_sources_added_after_discovery_snapshot(initial_sources: list[str]) -> None:
    previous_heartbeat = {"log": {"last_data_at": 80, "checked_at": 90}}
    node = make_node("demo", source=initial_sources, heartbeat=previous_heartbeat)
    discover = object.__new__(NodeDiscover)
    discover.bk_biz_id = 2
    discover.app_name = "app"
    old_mapping = discover.list_exists()
    TopoNode.upsert_telemetry_nodes(2, "app", "log", {"demo"}, {})
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo"}, {})
    node.refresh_from_db()
    expected_sources = [*node.source, "trace"]
    batch_result = (
        {"demo": {"extra_data": {"category": "other", "kind": "service"}, "platform": {}, "system": {}, "sdk": {}}},
        {},
    )
    with (
        mock.patch.object(
            discover, "get_rules", return_value=([SimpleNamespace(type=DiscoverRuleType.CATEGORY.value)], None)
        ),
        mock.patch("apm.core.discover.node.ThreadPool") as pool,
        mock.patch.object(discover, "list_exists", return_value=old_mapping),
        mock.patch.object(discover, "get_pod_workload_mapping", return_value={}),
        mock.patch.object(discover, "clear_expired"),
    ):
        pool.return_value.map_ignore_exception.return_value = [batch_result]
        discover.discover([])
    node.refresh_from_db()
    assert node.source == expected_sources
    assert node.heartbeat["log"] == previous_heartbeat["log"]
    assert "trace" not in node.heartbeat
    assert TopoNode.objects.filter(bk_biz_id=2, app_name="app").filter(pk=node.pk).exists()
