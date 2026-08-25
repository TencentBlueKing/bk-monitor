from types import SimpleNamespace

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from monitor_web.permissions import PlatformAdministratorPermission
from monitor_web.redis_management.resources import (
    GetRedisManagementOverviewResource,
    _load_latest_snapshots,
    _query_metric,
    build_cost_evidence,
    build_memory_view,
)
from monitor_web.redis_management.views import RedisManagementViewSet
from monitor_web.permissions import GlobalSettingPermission


def _routing_snapshot():
    return {
        "snapshot_id": "route-snapshot",
        "cluster_name": "alarm",
        "max_strategy_id": 1999,
        "terminal_score": 2**20 + 1,
        "topology_validation": {"valid": True, "errors": []},
        "nodes": [
            {
                "id": 1,
                "node_alias": "monitor-01",
                "cluster_name": "alarm",
                "cache_type": "RedisCache",
                "is_default": True,
                "is_enable": True,
            },
            {
                "id": 2,
                "node_alias": "monitor-02",
                "cluster_name": "alarm",
                "cache_type": "RedisCache",
                "is_default": False,
                "is_enable": True,
            },
        ],
        "routers": [
            {"strategy_score": 1000, "score_range": {"floor": 1, "ceil": 999}, "node": {"id": 1}},
            {
                "strategy_score": 2**20 + 1,
                "score_range": {"floor": 1000, "ceil": 2**20},
                "node": {"id": 2},
            },
        ],
    }


def _snapshot(node_id, finished_at, strategies, *, digest="sha256:old"):
    return {
        "snapshot_id": f"snapshot-{node_id}",
        "finished_at": finished_at,
        "node": {"id": node_id, "node_alias": f"monitor-0{node_id}"},
        "routing": {"digest": digest},
        "coverage": {"route_matched": len(strategies), "measured": len(strategies)},
        "strategies": strategies,
    }


def _measured(strategy_id, members, *, biz_id=2):
    return {
        "strategy_id": strategy_id,
        "bk_biz_id": biz_id,
        "status": "measured",
        "series_upper_bound": 10,
        "estimated_peak_members": members,
    }


def _unmeasured(strategy_id, *, status="failed", biz_id=2):
    return {
        "strategy_id": strategy_id,
        "bk_biz_id": biz_id,
        "status": status,
        "series_upper_bound": None,
        "estimated_peak_members": None,
    }


def test_platform_administrator_permission_checks_all_methods():
    permission = PlatformAdministratorPermission()

    for method in ("GET", "POST"):
        assert permission.has_permission(SimpleNamespace(method=method, user=SimpleNamespace(is_superuser=True)), None)
        assert not permission.has_permission(
            SimpleNamespace(method=method, user=SimpleNamespace(is_superuser=False)), None
        )


def test_build_memory_view_returns_trend_current_peak_and_usage():
    used_series = [
        {
            "dimensions": {
                "node": "node-1",
                "__name__": "redis_memory_used_bytes_value",
                "host": "127.0.0.1",
            },
            "datapoints": [[100.0, 1000], [None, 1060], [240.0, 1120], [200.0, 1180]],
        }
    ]
    capacity_series = [
        {
            "dimensions": {
                "node": "node-1",
                "__name__": "redis_memory_max_bytes_value",
                "host": "127.0.0.1",
            },
            "datapoints": [[400.0, 1000], [400.0, 1180]],
        }
    ]

    result = build_memory_view("node-1", used_series, capacity_series)

    assert result == {
        "trend": [[100.0, 1000], [None, 1060], [240.0, 1120], [200.0, 1180]],
        "usage_trend": [[0.25, 1000], [None, 1060], [0.6, 1120], [0.5, 1180]],
        "current_bytes": 200.0,
        "max_3h_bytes": 240.0,
        "max_3h_at": 1120,
        "capacity_bytes": 400.0,
        "current_usage_ratio": 0.5,
        "max_3h_usage_ratio": 0.6,
        "observed_at": 1180,
        "valid_points": 3,
        "total_points": 4,
        "sample_coverage_ratio": 0.75,
        "missing_points": 1,
    }


def test_build_memory_view_merges_node_series_split_by_runtime_labels():
    used_series = [
        {
            "dimensions": {"node": "node-1", "role": "master", "host": "old"},
            "datapoints": [[100.0, 1000], [180.0, 1060]],
        },
        {
            "dimensions": {"node": "node-1", "role": "master", "host": "new"},
            "datapoints": [[200.0, 1120], [220.0, 1180]],
        },
    ]
    capacity_series = [
        {
            "dimensions": {"node": "node-1", "role": "master", "host": "old"},
            "datapoints": [[400.0, 1000], [400.0, 1060]],
        },
        {
            "dimensions": {"node": "node-1", "role": "master", "host": "new"},
            "datapoints": [[500.0, 1120], [500.0, 1180]],
        },
    ]

    result = build_memory_view("node-1", used_series, capacity_series)

    assert result["trend"] == [[100.0, 1000], [180.0, 1060], [200.0, 1120], [220.0, 1180]]
    assert result["current_bytes"] == 220.0
    assert result["max_3h_bytes"] == 220.0
    assert result["capacity_bytes"] == 500.0
    assert result["current_usage_ratio"] == 0.44
    assert result["max_3h_at"] == 1180
    assert result["max_3h_usage_ratio"] == 0.44
    assert result["observed_at"] == 1180


def test_build_memory_view_does_not_pair_capacity_from_another_runtime_identity():
    result = build_memory_view(
        "node-1",
        [
            {
                "dimensions": {
                    "node": "node-1",
                    "__name__": "redis_memory_used_bytes_value",
                    "host": "used-host",
                },
                "datapoints": [[200.0, 1180]],
            }
        ],
        [
            {
                "dimensions": {
                    "node": "node-1",
                    "__name__": "redis_memory_max_bytes_value",
                    "host": "another-host",
                },
                "datapoints": [[400.0, 1180]],
            }
        ],
    )

    assert result["capacity_bytes"] is None
    assert result["current_usage_ratio"] is None
    assert result["max_3h_usage_ratio"] is None


def test_build_memory_view_usage_trend_follows_the_same_runtime_as_maximum_used_bytes():
    result = build_memory_view(
        "node-1",
        [
            {"dimensions": {"node": "node-1", "host": "larger"}, "datapoints": [[200.0, 1180]]},
            {"dimensions": {"node": "node-1", "host": "higher-ratio"}, "datapoints": [[150.0, 1180]]},
        ],
        [
            {"dimensions": {"node": "node-1", "host": "larger"}, "datapoints": [[400.0, 1180]]},
            {"dimensions": {"node": "node-1", "host": "higher-ratio"}, "datapoints": [[200.0, 1180]]},
        ],
    )

    assert result["trend"] == [[200.0, 1180]]
    assert result["usage_trend"] == [[0.5, 1180]]
    assert result["max_3h_usage_ratio"] == 0.5


def test_build_memory_view_marks_stale_current_value_unknown():
    result = build_memory_view(
        "node-1",
        [{"dimensions": {"node": "node-1"}, "datapoints": [[200.0, 1_700_000_000_000]]}],
        [{"dimensions": {"node": "node-1"}, "datapoints": [[400.0, 1_700_000_000_000]]}],
        reference_time=1_700_000_401,
    )

    assert result["current_bytes"] is None
    assert result["current_usage_ratio"] is None
    assert result["max_3h_bytes"] == 200.0
    assert result["observed_at"] == 1_700_000_000


def test_build_cost_evidence_uses_current_owner_and_deduplicates_stale_rows():
    routing = _routing_snapshot()
    snapshots = {
        1: _snapshot(1, "2026-08-24T10:00:00+00:00", [_measured(100, 1000), _measured(1200, 9999)]),
        2: _snapshot(2, "2026-08-24T10:02:00+00:00", [_measured(100, 8888), _measured(1200, 2000)]),
    }

    result = build_cost_evidence(routing, snapshots)

    assert result["status"] == "partial"
    assert result["valid_strategy_count"] == 2
    assert result["stale_strategy_count"] == 2
    assert result["cost_prefix"] == [
        {
            "strategy_id": 100,
            "lower_bytes": 100_000,
            "upper_bytes": 150_000,
            "peak_members": 1000,
            "measured_count": 1,
            "unmeasured_count": 0,
        },
        {
            "strategy_id": 1200,
            "lower_bytes": 300_000,
            "upper_bytes": 450_000,
            "peak_members": 3000,
            "measured_count": 2,
            "unmeasured_count": 0,
        },
    ]
    assert [item["strategy_id"] for item in result["hot_strategies"]] == [1200, 100]
    assert result["nodes"][0]["snapshot_time"] == "2026-08-24T10:00:00+00:00"
    assert result["nodes"][0]["routing_matches_current"] is False


def test_build_cost_evidence_keeps_unmeasured_strategy_in_coverage_prefix():
    routing = _routing_snapshot()
    snapshots = {
        1: _snapshot(1, "2026-08-24T10:00:00+00:00", [_measured(100, 1000), _unmeasured(500)]),
        2: _snapshot(2, "2026-08-24T10:02:00+00:00", [_measured(1200, 2000)]),
    }

    result = build_cost_evidence(routing, snapshots)

    assert result["unmeasured_strategy_count"] == 1
    assert result["cost_prefix"][1] == {
        "strategy_id": 500,
        "lower_bytes": 100_000,
        "upper_bytes": 150_000,
        "peak_members": 1000,
        "measured_count": 1,
        "unmeasured_count": 1,
    }


def test_redis_management_view_requires_both_administrator_permissions():
    assert RedisManagementViewSet.permission_classes == (GlobalSettingPermission, PlatformAdministratorPermission)


@pytest.mark.parametrize(
    ("is_superuser", "global_allowed", "expected_status"),
    [(True, True, 200), (True, False, 403), (False, True, 403), (False, False, 403)],
)
def test_redis_management_endpoint_permission_matrix(mocker, is_superuser, global_allowed, expected_status):
    mocker.patch.object(GlobalSettingPermission, "has_permission", return_value=global_allowed)
    mocker.patch.object(GetRedisManagementOverviewResource, "perform_request", return_value={})
    request = APIRequestFactory().get("/rest/v2/redis_management/overview/")
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True, is_superuser=is_superuser))
    endpoint = resolve("/rest/v2/redis_management/overview/").func

    response = endpoint(request)

    assert response.status_code == expected_status


def test_overview_resource_aggregates_routing_metrics_and_existing_snapshots(mocker):
    class FakeNode:
        def __init__(self, node_id, label):
            self.id = node_id
            self.label = label

        def __str__(self):
            return self.label

    routing = _routing_snapshot()
    node_models = [FakeNode(1, "node-1"), FakeNode(2, "node-2")]
    snapshots = {
        1: _snapshot(1, "2026-08-24T10:00:00+00:00", [_measured(100, 1000)]),
        2: _snapshot(2, "2026-08-24T10:02:00+00:00", [_measured(1200, 2000)]),
    }
    mocker.patch("monitor_web.redis_management.resources.load_routing_observation", return_value=(routing, node_models))

    snapshot_loader = mocker.patch(
        "monitor_web.redis_management.resources._load_latest_snapshots", return_value=snapshots
    )

    def query_metric(**kwargs):
        if "used" in kwargs["promql"]:
            return {
                "series": [
                    {"dimensions": {"node": "node-1"}, "datapoints": [[100.0, 1000], [120.0, 1180]]},
                    {"dimensions": {"node": "node-2"}, "datapoints": [[200.0, 1000], [220.0, 1180]]},
                ]
            }
        return {
            "series": [
                {"dimensions": {"node": "node-1"}, "datapoints": [[400.0, 1180]]},
                {"dimensions": {"node": "node-2"}, "datapoints": [[500.0, 1180]]},
            ]
        }

    query = mocker.patch("monitor_web.redis_management.resources.resource.grafana.graph_promql_query")
    query.side_effect = query_metric
    mocker.patch("monitor_web.redis_management.resources.time", return_value=1200)

    result = GetRedisManagementOverviewResource().perform_request({})

    assert result["generated_at"] == 1200
    assert result["routing"]["snapshot_id"] == "route-snapshot"
    assert result["routing"]["routers"] == routing["routers"]
    assert result["nodes"][0]["node_alias"] == "monitor-01"
    assert result["nodes"][0]["memory"]["current_bytes"] == 120.0
    assert result["nodes"][0]["memory"]["valid_points"] == 2
    assert result["nodes"][0]["memory"]["total_points"] == 180
    assert result["nodes"][0]["memory"]["sample_coverage_ratio"] == 2 / 180
    assert result["nodes"][1]["memory"]["max_3h_usage_ratio"] == 0.44
    assert result["cost_evidence"]["valid_strategy_count"] == 2
    assert result["data_health"] == {
        "memory_used": "ok",
        "memory_capacity": "ok",
        "cost_snapshot": "ok",
    }
    assert all("host" not in node and "password" not in node for node in result["nodes"])
    assert all(call.kwargs["start_time"] == 1200 - 3 * 60 * 60 for call in query.call_args_list)
    snapshot_loader.assert_called_once_with()


def test_overview_keeps_routing_and_memory_when_service_bridge_fails(mocker):
    class FakeNode:
        id = 1

        def __str__(self):
            return "node-1"

    routing = _routing_snapshot()
    routing["nodes"] = routing["nodes"][:1]
    routing["routers"] = routing["routers"][:1]
    mocker.patch(
        "monitor_web.redis_management.resources.load_routing_observation",
        return_value=(routing, [FakeNode()]),
    )
    mocker.patch(
        "monitor_web.redis_management.resources._load_latest_snapshots",
        side_effect=RuntimeError("monitor-api unavailable"),
    )
    mocker.patch(
        "monitor_web.redis_management.resources.resource.grafana.graph_promql_query",
        return_value={"series": []},
    )
    mocker.patch("monitor_web.redis_management.resources.time", return_value=1200)

    result = GetRedisManagementOverviewResource().perform_request({})

    assert result["routing"]["snapshot_id"] == "route-snapshot"
    assert [node["id"] for node in result["nodes"]] == [1]
    assert result["cost_evidence"]["status"] == "unavailable"
    assert result["data_health"] == {
        "memory_used": "empty",
        "memory_capacity": "empty",
        "cost_snapshot": "error",
    }


def test_overview_reports_metric_query_failure_without_hiding_other_data(mocker):
    class FakeNode:
        id = 1

        def __str__(self):
            return "node-1"

    routing = _routing_snapshot()
    routing["nodes"] = routing["nodes"][:1]
    routing["routers"] = routing["routers"][:1]
    mocker.patch(
        "monitor_web.redis_management.resources.load_routing_observation",
        return_value=(routing, [FakeNode()]),
    )
    mocker.patch("monitor_web.redis_management.resources._load_latest_snapshots", return_value={})
    query = mocker.patch(
        "monitor_web.redis_management.resources.resource.grafana.graph_promql_query",
        side_effect=[RuntimeError("used query failed"), {"series": []}],
    )
    mocker.patch("monitor_web.redis_management.resources.time", return_value=1200)

    result = GetRedisManagementOverviewResource().perform_request({})

    assert result["routing"]["snapshot_id"] == "route-snapshot"
    assert result["nodes"][0]["memory"]["current_bytes"] is None
    assert result["data_health"] == {
        "memory_used": "error",
        "memory_capacity": "empty",
        "cost_snapshot": "empty",
    }
    assert query.call_count == 2


def test_query_metric_uses_custom_report_namespace_and_cluster_job(mocker):
    query = mocker.patch(
        "monitor_web.redis_management.resources.resource.grafana.graph_promql_query",
        return_value={"series": []},
    )

    _query_metric("redis_memory_used_bytes", "alarm", 1000, 1180)

    assert query.call_args.kwargs["promql"] == 'custom:custom_report_aggate:redis_memory_used_bytes{job="alarm"}'


def test_load_latest_snapshots_uses_existing_monitor_api_service_bridge(mocker):
    bridge = mocker.patch(
        "monitor_web.redis_management.resources.api.monitor.bkm_cli_op_call",
        return_value={
            "result": {
                "nodes": [
                    {"node": {"id": 1}, "snapshots": [{"snapshot_id": "s1"}]},
                    {"node": {"id": 2}, "snapshots": []},
                ]
            }
        },
    )

    result = _load_latest_snapshots()

    assert result == {1: {"snapshot_id": "s1"}, 2: None}
    bridge.assert_called_once_with(
        op_id="read-redis-strategy-cost-snapshots",
        params={"operation": "latest"},
    )
