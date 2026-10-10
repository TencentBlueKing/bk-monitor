from types import SimpleNamespace
from unittest import mock

import pytest

from apm.core.discover.profile.service import ServiceDiscover as ProfileDiscover
from apm.models import ProfileService, TopoNode
from apm.core.discover.metric.service import ServiceDiscover as MetricDiscover
from apm_web.handlers.service_handler import ServiceHandler
from apm.tests.test_service_heartbeat import (
    datasource,
    make_node,
    profile_builder,
)
from kernel_api.resource.operation.handlers import apm_service_count
from kernel_api.rpc.functions.admin.apm import _load_service_count_map
from monitor_web.search.handlers.apm import ApmSearchHandler
from monitor_web.search.handlers.base import SearchScope
from monitor_web.statistics.v2.apm import APMCollector


pytestmark = pytest.mark.django_db(databases="__all__")


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


def test_profile_limit_result_only_updates_observed_services() -> None:
    unknown = make_node("unknown", heartbeat={"profiling": {"last_data_at": 50, "checked_at": 60}})
    discover = ProfileDiscover(datasource())
    discover.MAX_DIMENSION_COMBINATION_LIMIT = 1
    builder = profile_builder(
        [
            [{"service_name": "demo", "type": "cpu", "sample_type": "cpu", "count": 1}],
            [{"period": 10_000_000, "period_type": "cpu/nanoseconds", "type": "cpu", "value": 100}],
            [],
        ]
    )
    with (
        mock.patch.object(discover, "get_builder", return_value=builder),
        mock.patch("apm.core.discover.profile.service.EventReportHelper.report"),
        mock.patch.object(discover, "clear_expired"),
    ):
        discover.discover(100000, 200000)
    assert TopoNode.objects.get(topo_key="demo").heartbeat["profiling"]["last_data_at"] == int(
        ProfileService.objects.get(name="demo").last_check_time.timestamp()
    )
    unknown.refresh_from_db()
    assert unknown.heartbeat == {"profiling": {"last_data_at": 50, "checked_at": 60}}


def test_profile_node_is_reused_by_metric_and_service_list(settings) -> None:
    settings.USE_TZ = False
    template = {"kind": "service", "category": "other", "predicate_value": "", "service_language": ""}
    TopoNode.upsert_telemetry_nodes(2, "app", "profiling", {"demo"}, template)
    TopoNode.touch_heartbeat(2, "app", "profiling", {"demo": 100}, 110)
    discover = MetricDiscover(datasource())
    with mock.patch.object(discover, "query_dimensions", side_effect=[[{"service_name": "demo"}], []]):
        discover.discover_services(100, 300)
    node = TopoNode.objects.get(topo_key="demo")
    assert node.source == ["profiling", "metric"]
    assert node.extra_data == template
    assert node.heartbeat == {"profiling": {"last_data_at": 100, "checked_at": 110}}
    result = ServiceHandler._combine_profile_trace_service(
        [{"topo_key": node.topo_key, "extra_data": node.extra_data}], [{"name": "demo"}]
    )
    assert result == [{"topo_key": "demo", "extra_data": template}]
