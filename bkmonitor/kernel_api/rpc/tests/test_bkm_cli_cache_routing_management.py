"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli import cache_routing


def _node(node_id: int, alias: str, *, is_default: bool = False, is_enable: bool = True):
    return SimpleNamespace(
        id=node_id,
        node_alias=alias,
        cluster_name="default",
        cache_type="RedisCache",
        is_default=is_default,
        is_enable=is_enable,
        host="must-not-leak",
        port=6379,
        password="must-not-leak",
        connection_kwargs={"must": "not-leak"},
    )


def _router(score: int, node):
    return SimpleNamespace(strategy_score=score, node_id=node.id, node=node)


def _snapshot(*, target: bool = False, revision: int = 0):
    stock = _node(1, "alarm-stock", is_default=True)
    increment = _node(2, "alarm-increment")
    routes = [
        _router(-1, stock),
        _router(200 if target else 100, stock),
        _router(1000, increment),
    ]
    return cache_routing._build_snapshot(
        "default",
        [stock, increment],
        routes,
        max_strategy_id=950,
        revision=revision,
    )


def _impact_snapshot(*, first_score: int = 3, include_third_node: bool = False):
    stock = _node(1, "alarm-stock", is_default=True)
    increment = _node(2, "alarm-increment")
    nodes = [stock, increment]
    routes = [_router(first_score, stock)]
    if include_third_node:
        archive = _node(3, "alarm-archive")
        nodes.append(archive)
        routes.extend([_router(6, increment), _router(11, archive)])
    else:
        routes.append(_router(11, increment))
    return cache_routing._build_snapshot("default", nodes, routes, max_strategy_id=10)


def _drain_snapshot(*, target_enabled: bool = True, reserved_target: bool = False):
    stock = _node(1, "alarm-stock", is_default=True)
    draining = _node(2, "alarm-draining", is_enable=target_enabled)
    increment = _node(3, "alarm-increment")
    routes = [
        _router(2, stock),
        _router(4, draining),
        _router(6, increment),
        _router(8, draining),
        _router(11, increment),
    ]
    if reserved_target:
        routes.append(_router(-1, draining))
    return cache_routing._build_snapshot("default", [stock, draining, increment], routes, max_strategy_id=10)


def _drain_desired():
    return [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 4, "node_id": 3},
        {"strategy_score": 6, "node_id": 3},
        {"strategy_score": 8, "node_id": 1},
        {"strategy_score": 11, "node_id": 3},
    ]


def _strategy_rows(count: int = 10, *, disabled_ids: set[int] | None = None):
    disabled_ids = disabled_ids or set()
    return [{"id": strategy_id, "is_enabled": strategy_id not in disabled_ids} for strategy_id in range(1, count + 1)]


def _preview_with_strategies(mocker, snapshot, desired_routes, strategy_rows):
    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=snapshot)
    mocker.patch.object(
        cache_routing,
        "_load_cluster_strategy_rows",
        return_value=strategy_rows,
        create=True,
    )
    mocker.patch.object(cache_routing.db_router, "db_for_read", return_value="monitor_api")
    return cache_routing.list_cache_routing(
        {
            "operation": "preview",
            "expected_snapshot_id": snapshot["snapshot_id"],
            "desired_routes": desired_routes,
        }
    )


def test_snapshot_is_stable_safe_and_rounds_max_id_to_next_hundred():
    first = _snapshot()
    second = _snapshot()

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["suggested_cutoff_100"] == 1000
    assert first["max_strategy_id_scope"] == "all_strategy_rows"
    assert first["suggested_cutoff_usage"] == "intermediate_boundary_only"
    assert first["terminal_score"] == 1000
    assert first["topology_validation"] == {"valid": True, "errors": []}
    assert first["reserved_routes"] == [{"strategy_score": -1, "node_id": 1}]
    for node in first["nodes"]:
        assert set(node) == {"id", "node_alias", "cluster_name", "cache_type", "is_default", "is_enable"}


@pytest.mark.parametrize(
    "desired_routes",
    [
        [{"strategy_score": True, "node_id": 1}],
        [{"strategy_score": 0, "node_id": 1}],
        [{"strategy_score": 100, "node_id": 1, "extra": "rejected"}],
        [{"strategy_score": 100, "node_id": 1}, {"strategy_score": 100, "node_id": 2}],
        [{"strategy_score": 2147483648, "node_id": 1}],
        [{"strategy_score": 100, "node_id": 2147483648}],
    ],
)
def test_desired_routes_reject_ambiguous_or_unsafe_shapes(desired_routes):
    with pytest.raises(CustomException):
        cache_routing._normalize_desired_routes(desired_routes)


def test_preview_is_bound_to_snapshot_plan_and_expected_after_state():
    before = _snapshot()
    desired = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]

    preview = cache_routing._build_preview(before, desired, before["snapshot_id"], strategy_rows=[])

    assert preview["changed"] is True
    assert preview["diff"] == {
        "create": [{"strategy_score": 200, "node_id": 1}],
        "update": [],
        "delete": [{"strategy_score": 100, "node_id": 1}],
    }
    assert preview["expected_after_snapshot_id"] == _snapshot(target=True, revision=1)["snapshot_id"]
    assert preview["plan_id"].startswith("sha256:")
    assert preview["states"] == {
        "configuration": "previewed",
        "worker_activation": "not_evaluated",
        "traffic_landing": "not_evaluated",
        "capacity": "not_evaluated",
    }


def test_preview_reports_real_strategy_assignment_impact_and_allows_small_change(mocker):
    before = _impact_snapshot()
    desired = [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 11, "node_id": 2},
    ]

    preview = _preview_with_strategies(mocker, before, desired, _strategy_rows())

    assert preview["impact_summary"] == {
        "scope": "current_alarm_cluster_strategy_rows",
        "hard_limit_ratio": 0.5,
        "total_strategy_count": 10,
        "affected_strategy_count": 1,
        "affected_ratio": 0.1,
        "enabled_strategy_count": 10,
        "affected_enabled_strategy_count": 1,
        "affected_enabled_ratio": 0.1,
        "effective_affected_ratio": 0.1,
        "node_movements": [
            {
                "before_node_id": 1,
                "after_node_id": 2,
                "strategy_count": 1,
                "enabled_strategy_count": 1,
            }
        ],
        "drained_node_ids": [],
        "collapsed_to_single_node": False,
        "apply_allowed": True,
        "block_reasons": [],
    }
    assert preview["impact_digest"].startswith("sha256:")


def test_preview_blocks_half_or_more_strategies_and_single_node_collapse(mocker):
    before = _impact_snapshot(first_score=6)
    desired = [{"strategy_score": 11, "node_id": 2}]

    preview = _preview_with_strategies(mocker, before, desired, _strategy_rows())

    impact = preview["impact_summary"]
    assert impact["affected_strategy_count"] == 5
    assert impact["affected_ratio"] == 0.5
    assert impact["effective_affected_ratio"] == 0.5
    assert impact["drained_node_ids"] == [1]
    assert impact["collapsed_to_single_node"] is True
    assert impact["apply_allowed"] is False
    assert any("hard limit" in reason for reason in impact["block_reasons"])
    assert any("drain" in reason for reason in impact["block_reasons"])
    assert any("collapse" in reason for reason in impact["block_reasons"])
    assert preview["next_actions"][0].startswith("Do not call manage-cache-routing")


def test_preview_uses_enabled_strategy_ratio_to_avoid_disabled_rows_diluting_risk(mocker):
    before = _impact_snapshot()
    desired = [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 11, "node_id": 2},
    ]
    disabled_ids = set(range(1, 11)) - {2}

    preview = _preview_with_strategies(
        mocker,
        before,
        desired,
        _strategy_rows(disabled_ids=disabled_ids),
    )

    impact = preview["impact_summary"]
    assert impact["affected_ratio"] == 0.1
    assert impact["affected_enabled_ratio"] == 1.0
    assert impact["effective_affected_ratio"] == 1.0
    assert impact["drained_node_ids"] == []
    assert impact["apply_allowed"] is False
    assert any("hard limit" in reason for reason in impact["block_reasons"])


def test_preview_blocks_draining_a_node_even_when_total_impact_is_below_half(mocker):
    before = _impact_snapshot(first_score=2, include_third_node=True)
    desired = [
        {"strategy_score": 6, "node_id": 2},
        {"strategy_score": 11, "node_id": 3},
    ]

    preview = _preview_with_strategies(mocker, before, desired, _strategy_rows())

    impact = preview["impact_summary"]
    assert impact["affected_strategy_count"] == 1
    assert impact["affected_ratio"] == 0.1
    assert impact["drained_node_ids"] == [1]
    assert impact["collapsed_to_single_node"] is False
    assert impact["apply_allowed"] is False
    assert impact["block_reasons"] == ["route change would drain strategy ownership from node IDs: [1]"]


def test_drain_preview_allows_exact_non_default_three_to_two_with_non_contiguous_routes():
    before = _drain_snapshot()
    desired = _drain_desired()

    preview = cache_routing._build_drain_preview(
        before,
        desired,
        before["snapshot_id"],
        drain_node_id=2,
        strategy_rows=_strategy_rows(),
    )
    ordinary = cache_routing._build_preview(
        before,
        desired,
        before["snapshot_id"],
        strategy_rows=_strategy_rows(),
    )

    assert preview["operation"] == "drain_preview"
    assert preview["plan_schema"] == "drain-positive-routes/v1"
    assert preview["impact_summary"]["affected_ratio"] == 0.4
    assert preview["impact_summary"]["drained_node_ids"] == [2]
    assert preview["impact_summary"]["collapsed_to_single_node"] is False
    assert preview["impact_summary"]["apply_allowed"] is True
    assert ordinary["impact_summary"]["apply_allowed"] is False
    assert preview["diff"] == {
        "create": [],
        "update": [
            {"strategy_score": 4, "before_node_id": 2, "after_node_id": 3},
            {"strategy_score": 8, "before_node_id": 2, "after_node_id": 1},
        ],
        "delete": [],
    }
    assert preview["drain_summary"] == {
        "drain_node": {
            "id": 2,
            "node_alias": "alarm-draining",
            "cluster_name": "default",
            "cache_type": "RedisCache",
            "is_default": False,
            "is_enable": True,
        },
        "changed_strategy_scores": [4, 8],
        "positive_route_references_before": 2,
        "remaining_positive_route_references": 0,
        "reserved_route_references": 0,
        "cache_node_mutated": False,
        "safe_to_disable_or_delete": False,
        "block_reasons": [],
    }


def test_drain_preview_blocks_exactly_half_and_two_to_one():
    stock = _node(1, "alarm-stock", is_default=True)
    draining = _node(2, "alarm-draining")
    archive = _node(3, "alarm-archive")
    half = cache_routing._build_snapshot(
        "default",
        [stock, draining, archive],
        [_router(2, stock), _router(7, draining), _router(11, archive)],
        max_strategy_id=10,
    )
    two_to_one = cache_routing._build_snapshot(
        "default",
        [stock, draining],
        [_router(2, stock), _router(4, draining), _router(11, stock)],
        max_strategy_id=10,
    )

    half_preview = cache_routing._build_drain_preview(
        half,
        [
            {"strategy_score": 2, "node_id": 1},
            {"strategy_score": 7, "node_id": 3},
            {"strategy_score": 11, "node_id": 3},
        ],
        half["snapshot_id"],
        drain_node_id=2,
        strategy_rows=_strategy_rows(),
    )
    collapse_preview = cache_routing._build_drain_preview(
        two_to_one,
        [
            {"strategy_score": 2, "node_id": 1},
            {"strategy_score": 4, "node_id": 1},
            {"strategy_score": 11, "node_id": 1},
        ],
        two_to_one["snapshot_id"],
        drain_node_id=2,
        strategy_rows=_strategy_rows(),
    )

    assert half_preview["impact_summary"]["affected_ratio"] == 0.5
    assert any("hard limit" in reason for reason in half_preview["impact_summary"]["block_reasons"])
    assert half_preview["impact_summary"]["apply_allowed"] is False
    assert collapse_preview["impact_summary"]["affected_ratio"] == 0.2
    assert collapse_preview["impact_summary"]["collapsed_to_single_node"] is True
    assert any("collapse" in reason for reason in collapse_preview["impact_summary"]["block_reasons"])
    assert collapse_preview["impact_summary"]["apply_allowed"] is False


@pytest.mark.parametrize(
    ("snapshot", "desired", "drain_node_id", "reason"),
    [
        (_drain_snapshot(), _drain_desired(), 1, "default node"),
        (_drain_snapshot(target_enabled=False), _drain_desired(), 2, "must be enabled"),
        (
            _drain_snapshot(reserved_target=True),
            _drain_desired(),
            2,
            "reserved CacheRouter rows",
        ),
        (
            _drain_snapshot(),
            [
                {"strategy_score": 2, "node_id": 3},
                {"strategy_score": 4, "node_id": 3},
                {"strategy_score": 6, "node_id": 3},
                {"strategy_score": 8, "node_id": 1},
                {"strategy_score": 11, "node_id": 3},
            ],
            2,
            "non-target route score=2",
        ),
        (
            _drain_snapshot(),
            [
                {"strategy_score": 2, "node_id": 1},
                {"strategy_score": 4, "node_id": 3},
                {"strategy_score": 6, "node_id": 3},
                {"strategy_score": 8, "node_id": 2},
                {"strategy_score": 11, "node_id": 3},
            ],
            2,
            "still references drain_node_id",
        ),
        (
            _drain_snapshot(),
            [
                {"strategy_score": 2, "node_id": 1},
                {"strategy_score": 4, "node_id": 3},
                {"strategy_score": 6, "node_id": 3},
                {"strategy_score": 8, "node_id": 1},
                {"strategy_score": 9, "node_id": 1},
                {"strategy_score": 11, "node_id": 3},
            ],
            2,
            "preserve the exact positive strategy_score set",
        ),
    ],
)
def test_drain_preview_blocks_unsafe_structural_variants(snapshot, desired, drain_node_id, reason):
    preview = cache_routing._build_drain_preview(
        snapshot,
        desired,
        snapshot["snapshot_id"],
        drain_node_id=drain_node_id,
        strategy_rows=_strategy_rows(),
    )

    assert preview["impact_summary"]["apply_allowed"] is False
    assert any(reason in block_reason for block_reason in preview["impact_summary"]["block_reasons"])


def test_drain_preview_allows_zero_impact_referenced_node_and_rejects_unreferenced_node():
    before = _drain_snapshot()
    extra = _node(4, "alarm-unused")
    with_unused = cache_routing._build_snapshot(
        "default",
        [*before["nodes"], extra],
        before["raw_routes"],
        max_strategy_id=10,
    )

    preview = cache_routing._build_drain_preview(
        before,
        _drain_desired(),
        before["snapshot_id"],
        drain_node_id=2,
        strategy_rows=[],
    )
    unreferenced = cache_routing._build_drain_preview(
        with_unused,
        [route for route in with_unused["raw_routes"] if route["strategy_score"] > 0],
        with_unused["snapshot_id"],
        drain_node_id=4,
        strategy_rows=[],
    )

    assert preview["impact_summary"]["affected_strategy_count"] == 0
    assert preview["impact_summary"]["apply_allowed"] is True
    assert unreferenced["impact_summary"]["apply_allowed"] is False
    assert any(
        "no positive CacheRouter references" in reason for reason in unreferenced["impact_summary"]["block_reasons"]
    )


@pytest.mark.parametrize("drain_node_id", [True, 0, -1, 2_147_483_648, "2", 99])
def test_drain_preview_rejects_invalid_or_missing_target_node(drain_node_id):
    before = _drain_snapshot()

    with pytest.raises(CustomException, match="drain_node_id"):
        cache_routing._build_drain_preview(
            before,
            _drain_desired(),
            before["snapshot_id"],
            drain_node_id=drain_node_id,
            strategy_rows=_strategy_rows(),
        )


def test_drain_plan_id_binds_target_node():
    before = _drain_snapshot()

    valid = cache_routing._build_drain_preview(
        before,
        _drain_desired(),
        before["snapshot_id"],
        drain_node_id=2,
        strategy_rows=_strategy_rows(),
    )
    different_target = cache_routing._build_drain_preview(
        before,
        _drain_desired(),
        before["snapshot_id"],
        drain_node_id=3,
        strategy_rows=_strategy_rows(),
    )

    assert valid["plan_id"] != different_target["plan_id"]


def test_plan_id_binds_the_strategy_impact_seen_during_preview(mocker):
    before = _impact_snapshot()
    desired = [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 11, "node_id": 2},
    ]
    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=before)
    mocker.patch.object(
        cache_routing,
        "_load_cluster_strategy_rows",
        side_effect=[_strategy_rows(), _strategy_rows(9)],
        create=True,
    )
    mocker.patch.object(cache_routing.db_router, "db_for_read", return_value="monitor_api")
    params = {
        "operation": "preview",
        "expected_snapshot_id": before["snapshot_id"],
        "desired_routes": desired,
    }

    first = cache_routing.list_cache_routing(params)
    second = cache_routing.list_cache_routing(params)

    assert first["impact_digest"] != second["impact_digest"]
    assert first["plan_id"] != second["plan_id"]


def test_strategy_impact_population_is_limited_to_the_current_alarm_cluster(mocker):
    class FakeStrategyQuerySet:
        def using(self, alias):
            assert alias == "monitor_api"
            return self

        def filter(self, **kwargs):
            assert kwargs == {"id__lte": 10}
            return self

        def order_by(self, *args):
            assert args == ("id",)
            return self

        def values(self, *args):
            assert args == ("id", "bk_biz_id", "is_enabled")
            return self

        def iterator(self, *, chunk_size):
            assert chunk_size == 2000
            return iter(
                [
                    {"id": 1, "bk_biz_id": 100, "is_enabled": True},
                    {"id": 2, "bk_biz_id": 200, "is_enabled": False},
                ]
            )

    strategy_model = SimpleNamespace(objects=FakeStrategyQuerySet())
    cluster = SimpleNamespace(match=lambda target_type, biz_id: biz_id == 100)
    mocker.patch("bkmonitor.models.StrategyModel", strategy_model)
    mocker.patch("alarm_backends.core.cluster.get_cluster", return_value=cluster)

    assert hasattr(cache_routing, "_load_cluster_strategy_rows"), "cluster strategy impact loader is missing"
    rows = list(cache_routing._load_cluster_strategy_rows(using="monitor_api", max_strategy_id=10))

    assert rows == [{"id": 1, "is_enabled": True}]


def test_apply_recomputes_impact_and_blocks_before_writing(mocker):
    before = _impact_snapshot(first_score=6)
    desired = [{"strategy_score": 11, "node_id": 2}]
    after = cache_routing._after_snapshot(before, desired)
    load = mocker.patch.object(cache_routing, "_load_routing_snapshot", side_effect=[before, before, after])
    mocker.patch.object(
        cache_routing,
        "_load_cluster_strategy_rows",
        return_value=_strategy_rows(),
        create=True,
    )
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    mocker.patch.object(cache_routing.db_router, "db_for_read", return_value="monitor_api")
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})
    preview = cache_routing.list_cache_routing(
        {
            "operation": "preview",
            "expected_snapshot_id": before["snapshot_id"],
            "desired_routes": desired,
        }
    )

    with pytest.raises(CustomException, match="route change is blocked") as exc:
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
                "plan_id": preview["plan_id"],
                "desired_routes": desired,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )

    assert "5/10 strategies (50.00%)" in str(exc.value)
    assert "hard limit 50.00%" in str(exc.value)
    assert "drain strategy ownership" in str(exc.value)
    assert "collapse strategy ownership" in str(exc.value)
    assert load.call_count == 2
    write.assert_not_called()
    advance.assert_not_called()


def test_apply_rolls_back_when_strategy_impact_changes_after_route_write(mocker):
    before = _impact_snapshot()
    desired = [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 11, "node_id": 2},
    ]
    after = cache_routing._after_snapshot(before, desired)
    initial_rows = _strategy_rows()
    changed_rows = _strategy_rows(disabled_ids={1, 3, 4, 5, 6, 7, 8, 9, 10})
    preview = cache_routing._build_preview(
        before,
        desired,
        before["snapshot_id"],
        strategy_rows=initial_rows,
    )
    mocker.patch.object(cache_routing, "_load_routing_snapshot", side_effect=[before, after])
    load_strategies = mocker.patch.object(
        cache_routing,
        "_load_cluster_strategy_rows",
        side_effect=[initial_rows, changed_rows],
    )
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})

    with pytest.raises(CustomException, match="strategy impact changed during apply"):
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
                "plan_id": preview["plan_id"],
                "desired_routes": desired,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )

    assert load_strategies.call_count == 2
    write.assert_called_once_with(before, desired, using="monitor_api")
    advance.assert_called_once_with(before, using="monitor_api")


def test_preview_rejects_stale_snapshot_and_terminal_shrink():
    before = _snapshot()
    desired = [{"strategy_score": 999, "node_id": 2}]

    with pytest.raises(CustomException, match="snapshot"):
        cache_routing._build_preview(before, desired, "sha256:stale", strategy_rows=[])
    with pytest.raises(CustomException, match="terminal"):
        cache_routing._build_preview(before, desired, before["snapshot_id"], strategy_rows=[])


def test_preview_can_repair_terminal_coverage_after_strategy_ids_grow():
    stock = _node(1, "alarm-stock", is_default=True)
    increment = _node(2, "alarm-increment")
    before = cache_routing._build_snapshot(
        "default",
        [stock, increment],
        [_router(100, stock), _router(1000, increment)],
        max_strategy_id=1000,
    )
    assert before["topology_validation"]["valid"] is False

    preview = cache_routing._build_preview(
        before,
        [
            {"strategy_score": 100, "node_id": 1},
            {"strategy_score": 1100, "node_id": 2},
        ],
        before["snapshot_id"],
        strategy_rows=[],
    )

    assert preview["after"]["topology_validation"] == {"valid": True, "errors": []}
    assert preview["expected_after_snapshot_id"] == preview["after"]["snapshot_id"]


def test_monotonic_revision_prevents_old_plan_reuse_after_aba_route_cycle():
    state_a_v0 = _snapshot(revision=0)
    routes_b = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    plan_a_to_b = cache_routing._build_preview(
        state_a_v0,
        routes_b,
        state_a_v0["snapshot_id"],
        strategy_rows=[],
    )
    state_b_v1 = plan_a_to_b["after"]

    routes_a = [
        {"strategy_score": 100, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    plan_b_to_a = cache_routing._build_preview(
        state_b_v1,
        routes_a,
        state_b_v1["snapshot_id"],
        strategy_rows=[],
    )
    state_a_v2 = plan_b_to_a["after"]

    assert state_a_v2["raw_routes"] == state_a_v0["raw_routes"]
    assert state_a_v2["revision"] == 2
    assert state_a_v2["snapshot_id"] != state_a_v0["snapshot_id"]
    with pytest.raises(CustomException):
        cache_routing._build_preview(state_a_v2, routes_b, state_a_v0["snapshot_id"], strategy_rows=[])


def test_apply_uses_locked_snapshot_writes_and_exact_readback(mocker):
    before = _snapshot()
    after = _snapshot(target=True, revision=1)
    desired = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    preview = cache_routing._build_preview(before, desired, before["snapshot_id"], strategy_rows=[])
    load = mocker.patch.object(cache_routing, "_load_routing_snapshot", side_effect=[before, after])
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    mocker.patch.object(cache_routing, "_cluster_name", return_value="default")
    mocker.patch.object(cache_routing, "_load_cluster_strategy_rows", return_value=[])
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(
        cache_routing,
        "_runtime_refresh_contract",
        return_value={"mode": "ttl_refresh", "runtime_validation_required": True},
    )

    result = cache_routing.manage_cache_routing(
        {
            "operation": "apply",
            "expected_snapshot_id": before["snapshot_id"],
            "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
            "plan_id": preview["plan_id"],
            "desired_routes": desired,
            "confirmed": True,
            "operator": "test-operator",
            "exclusive_change_window": True,
            "bk_tenant_id": "system-injected",
        }
    )

    assert load.call_args_list[0].kwargs == {"using": "monitor_api", "lock": True}
    assert load.call_args_list[1].kwargs == {"using": "monitor_api", "lock": False}
    write.assert_called_once_with(before, desired, using="monitor_api")
    advance.assert_called_once_with(before, using="monitor_api")
    assert result["changed"] is True
    assert result["snapshot_id"] == after["snapshot_id"]
    assert result["states"] == {
        "configuration": "readback_verified",
        "worker_activation": "pending",
        "traffic_landing": "not_evaluated",
        "capacity": "not_evaluated",
    }


def test_drain_apply_recomputes_locked_plan_and_only_writes_route_rows(mocker):
    before = _drain_snapshot()
    desired = _drain_desired()
    after = cache_routing._after_snapshot(before, desired)
    strategies = _strategy_rows()
    preview = cache_routing._build_drain_preview(
        before,
        desired,
        before["snapshot_id"],
        drain_node_id=2,
        strategy_rows=strategies,
    )
    load = mocker.patch.object(cache_routing, "_load_routing_snapshot", side_effect=[before, after])
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    load_strategies = mocker.patch.object(
        cache_routing,
        "_load_cluster_strategy_rows",
        side_effect=[strategies, strategies],
    )
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})

    result = cache_routing.manage_cache_routing(
        {
            "operation": "drain_apply",
            "drain_node_id": 2,
            "expected_snapshot_id": before["snapshot_id"],
            "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
            "plan_id": preview["plan_id"],
            "desired_routes": desired,
            "confirmed": True,
            "operator": "test-operator",
            "exclusive_change_window": True,
        }
    )

    assert load.call_count == 2
    assert load_strategies.call_count == 2
    write.assert_called_once_with(before, desired, using="monitor_api")
    advance.assert_called_once_with(before, using="monitor_api")
    assert result["operation"] == "drain_apply"
    assert result["drain_summary"]["remaining_positive_route_references"] == 0
    assert result["drain_summary"]["cache_node_mutated"] is False
    assert result["drain_summary"]["safe_to_disable_or_delete"] is False


def test_drain_apply_rejects_blocked_plan_before_route_write(mocker):
    stock = _node(1, "alarm-stock", is_default=True)
    draining = _node(2, "alarm-draining")
    before = cache_routing._build_snapshot(
        "default",
        [stock, draining],
        [_router(2, stock), _router(4, draining), _router(11, stock)],
        max_strategy_id=10,
    )
    desired = [
        {"strategy_score": 2, "node_id": 1},
        {"strategy_score": 4, "node_id": 1},
        {"strategy_score": 11, "node_id": 1},
    ]
    strategies = _strategy_rows()
    preview = cache_routing._build_drain_preview(
        before,
        desired,
        before["snapshot_id"],
        drain_node_id=2,
        strategy_rows=strategies,
    )
    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=before)
    mocker.patch.object(cache_routing, "_load_cluster_strategy_rows", return_value=strategies)
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})

    with pytest.raises(CustomException, match="collapse strategy ownership"):
        cache_routing.manage_cache_routing(
            {
                "operation": "drain_apply",
                "drain_node_id": 2,
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
                "plan_id": preview["plan_id"],
                "desired_routes": desired,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )

    write.assert_not_called()
    advance.assert_not_called()


def test_snapshot_loader_pins_every_query_to_requested_database_and_locks(mocker):
    stock = _node(1, "alarm-stock", is_default=True)
    increment = _node(2, "alarm-increment")

    class FakeQuerySet:
        def __init__(self, rows):
            self.rows = rows
            self.using_alias = None
            self.locked = False

        def using(self, alias):
            self.using_alias = alias
            return self

        def filter(self, **kwargs):
            assert kwargs == {"cluster_name": "default"}
            return self

        def order_by(self, *args):
            return self

        def select_for_update(self):
            self.locked = True
            return self

        def values(self, *args):
            assert args == ("strategy_score", "node_id")
            return self.rows

        def __iter__(self):
            return iter(self.rows)

    class FakeStrategyQuerySet:
        using_alias = None
        locked = False

        def using(self, alias):
            self.using_alias = alias
            return self

        def select_for_update(self):
            self.locked = True
            return self

        def order_by(self, *args):
            assert args == ("-id",)
            return self

        def values_list(self, *args, **kwargs):
            assert args == ("id",) and kwargs == {"flat": True}
            return self

        def first(self):
            return 950

    node_qs = FakeQuerySet([stock, increment])
    route_qs = FakeQuerySet(
        [
            {"strategy_score": 100, "node_id": stock.id},
            {"strategy_score": 1000, "node_id": increment.id},
        ]
    )
    strategy_qs = FakeStrategyQuerySet()
    mocker.patch("bkmonitor.models.CacheNode", SimpleNamespace(objects=node_qs))
    mocker.patch("bkmonitor.models.CacheRouter", SimpleNamespace(objects=route_qs))
    mocker.patch("bkmonitor.models.StrategyModel", SimpleNamespace(objects=strategy_qs))
    mocker.patch.object(cache_routing, "_cluster_name", return_value="default")
    revision = mocker.patch.object(cache_routing, "_load_routing_revision", return_value=7)

    snapshot = cache_routing._load_routing_snapshot(using="monitor_api", lock=True)

    assert node_qs.using_alias == "monitor_api" and node_qs.locked is True
    assert route_qs.using_alias == "monitor_api" and route_qs.locked is True
    assert strategy_qs.using_alias == "monitor_api" and strategy_qs.locked is True
    revision.assert_called_once_with(cluster_name="default", using="monitor_api", lock=True)
    assert snapshot["revision"] == 7
    assert snapshot["snapshot_id"].startswith("sha256:")


def test_routing_revision_is_created_locked_and_advanced_with_compare_and_swap(mocker):
    revision_config = SimpleNamespace(pk=31, value=0)

    class FakeRevisionQuerySet:
        def __init__(self):
            self.using_alias = None
            self.created = None
            self.locked = False
            self.filters = []
            self.updated_to = None

        def using(self, alias):
            self.using_alias = alias
            return self

        def get_or_create(self, **kwargs):
            self.created = kwargs
            return revision_config, True

        def select_for_update(self):
            self.locked = True
            return self

        def get(self, **kwargs):
            assert kwargs == {"pk": revision_config.pk}
            return revision_config

        def filter(self, **kwargs):
            self.filters.append(kwargs)
            return self

        def update(self, **kwargs):
            self.updated_to = kwargs
            return 1

    manager = FakeRevisionQuerySet()
    mocker.patch("bkmonitor.models.GlobalConfig", SimpleNamespace(objects=manager))

    revision = cache_routing._load_routing_revision(cluster_name="default", using="monitor_api", lock=True)
    cache_routing._advance_routing_revision(_snapshot(revision=revision), using="monitor_api")

    assert revision == 0
    assert manager.using_alias == "monitor_api"
    assert manager.created == {
        "key": "BKM_CLI_CACHE_ROUTING_REVISION:default",
        "defaults": {
            "value": 0,
            "description": "bkm-cli CacheRouter monotonic revision",
            "data_type": "Integer",
            "is_internal": True,
        },
    }
    assert manager.locked is True
    assert manager.filters[-1] == {
        "key": "BKM_CLI_CACHE_ROUTING_REVISION:default",
        "value": 0,
    }
    assert manager.updated_to == {"value": 1}


def test_routing_revision_compare_and_swap_failure_aborts_apply(mocker):
    manager = mocker.Mock()
    manager.using.return_value.filter.return_value.update.return_value = 0
    mocker.patch("bkmonitor.models.GlobalConfig", SimpleNamespace(objects=manager))

    with pytest.raises(CustomException, match="revision changed unexpectedly"):
        cache_routing._advance_routing_revision(_snapshot(), using="monitor_api")


def test_writer_only_mutates_positive_diff_and_keeps_reserved_rows_opaque(mocker):
    before = _snapshot()

    class FakeWriteQuerySet:
        def __init__(self):
            self.using_alias = None
            self.filters = []
            self.deleted = []
            self.updated = []
            self.created = []
            self.current_filter = None

        def using(self, alias):
            self.using_alias = alias
            return self

        def filter(self, **kwargs):
            self.current_filter = kwargs
            self.filters.append(kwargs)
            return self

        def delete(self):
            self.deleted.append(self.current_filter)
            return 1, {}

        def update(self, **kwargs):
            self.updated.append((self.current_filter, kwargs))
            return 1

        def bulk_create(self, objects):
            self.created.extend(objects)
            return objects

    manager = FakeWriteQuerySet()

    class FakeCacheRouter:
        objects = manager

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    mocker.patch("bkmonitor.models.CacheRouter", FakeCacheRouter)
    desired = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 1},
    ]

    cache_routing._write_positive_routes(before, desired, using="monitor_api")

    assert manager.using_alias == "monitor_api"
    assert manager.deleted == [
        {
            "cluster_name": "default",
            "strategy_score__gt": 0,
            "strategy_score__in": [100],
        }
    ]
    assert manager.updated == [
        (
            {"cluster_name": "default", "strategy_score": 1000},
            {"node_id": 1},
        )
    ]
    assert [(row.strategy_score, row.node_id) for row in manager.created] == [(200, 1)]


def test_replaying_old_apply_is_stale_even_when_target_already_matches(mocker):
    old = _snapshot()
    current = _snapshot(target=True, revision=1)
    desired = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    old_preview = cache_routing._build_preview(old, desired, old["snapshot_id"], strategy_rows=[])
    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=current)
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    mocker.patch.object(cache_routing, "_cluster_name", return_value="default")
    mocker.patch.object(cache_routing, "_load_cluster_strategy_rows", return_value=[])
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})

    with pytest.raises(CustomException, match="snapshot"):
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "expected_snapshot_id": old["snapshot_id"],
                "expected_after_snapshot_id": old_preview["expected_after_snapshot_id"],
                "plan_id": old_preview["plan_id"],
                "desired_routes": desired,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )
    write.assert_not_called()


def test_old_apply_cannot_be_reused_after_routes_cycle_back_to_same_shape(mocker):
    state_a_v0 = _snapshot(revision=0)
    routes_b = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    old_plan = cache_routing._build_preview(
        state_a_v0,
        routes_b,
        state_a_v0["snapshot_id"],
        strategy_rows=[],
    )
    state_b_v1 = old_plan["after"]
    routes_a = [
        {"strategy_score": 100, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    state_a_v2 = cache_routing._build_preview(
        state_b_v1,
        routes_a,
        state_b_v1["snapshot_id"],
        strategy_rows=[],
    )["after"]

    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=state_a_v2)
    write = mocker.patch.object(cache_routing, "_write_positive_routes")
    advance = mocker.patch.object(cache_routing, "_advance_routing_revision")
    mocker.patch.object(cache_routing, "_load_cluster_strategy_rows", return_value=[])
    mocker.patch.object(cache_routing.db_router, "db_for_write", return_value="monitor_api")
    mocker.patch.object(cache_routing.transaction, "atomic", return_value=nullcontext())
    mocker.patch.object(cache_routing, "_runtime_refresh_contract", return_value={"mode": "ttl_refresh"})

    with pytest.raises(CustomException):
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "expected_snapshot_id": state_a_v0["snapshot_id"],
                "expected_after_snapshot_id": old_plan["expected_after_snapshot_id"],
                "plan_id": old_plan["plan_id"],
                "desired_routes": routes_b,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )
    write.assert_not_called()
    advance.assert_not_called()


def test_apply_is_disabled_when_api_process_code_does_not_expose_ttl_refresh(mocker):
    before = _snapshot()
    desired = [
        {"strategy_score": 200, "node_id": 1},
        {"strategy_score": 1000, "node_id": 2},
    ]
    preview = cache_routing._build_preview(before, desired, before["snapshot_id"], strategy_rows=[])
    load = mocker.patch.object(cache_routing, "_load_routing_snapshot")
    mocker.patch.object(
        cache_routing,
        "_runtime_refresh_contract",
        return_value={"mode": "process_lifetime_cache"},
    )

    with pytest.raises(
        CustomException,
        match="current API process code does not expose ttl_refresh; this check does not verify alarm worker deployment",
    ):
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": preview["expected_after_snapshot_id"],
                "plan_id": preview["plan_id"],
                "desired_routes": desired,
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )
    load.assert_not_called()


def test_runtime_refresh_contract_does_not_claim_worker_deployment_verification():
    contract = cache_routing._runtime_refresh_contract()

    assert contract["capability_source"] == "api_process_code"
    assert contract["worker_deployment_verified"] is False
    assert contract["runtime_validation_required"] is True


def test_drain_operations_require_target_and_generic_operations_reject_it(mocker):
    before = _drain_snapshot()
    mocker.patch.object(cache_routing, "_load_routing_snapshot", return_value=before)
    mocker.patch.object(cache_routing, "_load_cluster_strategy_rows", return_value=_strategy_rows())
    mocker.patch.object(cache_routing.db_router, "db_for_read", return_value="monitor_api")

    with pytest.raises(CustomException, match="drain_node_id"):
        cache_routing.list_cache_routing(
            {
                "operation": "preview",
                "drain_node_id": 2,
                "expected_snapshot_id": before["snapshot_id"],
                "desired_routes": _drain_desired(),
            }
        )
    with pytest.raises(CustomException, match="drain_node_id"):
        cache_routing.list_cache_routing(
            {
                "operation": "drain_preview",
                "expected_snapshot_id": before["snapshot_id"],
                "desired_routes": _drain_desired(),
            }
        )
    with pytest.raises(CustomException, match="drain_node_id"):
        cache_routing.manage_cache_routing(
            {
                "operation": "apply",
                "drain_node_id": 2,
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": before["snapshot_id"],
                "plan_id": before["snapshot_id"],
                "desired_routes": _drain_desired(),
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )
    with pytest.raises(CustomException, match="drain_node_id"):
        cache_routing.manage_cache_routing(
            {
                "operation": "drain_apply",
                "expected_snapshot_id": before["snapshot_id"],
                "expected_after_snapshot_id": before["snapshot_id"],
                "plan_id": before["snapshot_id"],
                "desired_routes": _drain_desired(),
                "confirmed": True,
                "operator": "test-operator",
                "exclusive_change_window": True,
            }
        )


@pytest.mark.parametrize(
    "override",
    [
        {"confirmed": False},
        {"exclusive_change_window": False},
        {"operator": ""},
        {"route_key": "forbidden"},
        {"source_env": "forbidden"},
        {"cluster_name": "forbidden"},
        {"force": True},
        {"unknown": "forbidden"},
    ],
)
def test_apply_rejects_missing_gates_and_client_routing_fields(override):
    params = {
        "operation": "apply",
        "expected_snapshot_id": "sha256:before",
        "expected_after_snapshot_id": "sha256:after",
        "plan_id": "sha256:plan",
        "desired_routes": [{"strategy_score": 1000, "node_id": 1}],
        "confirmed": True,
        "operator": "test-operator",
        "exclusive_change_window": True,
    }
    params.update(override)

    with pytest.raises(CustomException):
        cache_routing.manage_cache_routing(params)


def test_manage_operation_is_registered_as_confirmed_admin_mutation():
    from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

    op = BkmCliOpRegistry.resolve("manage-cache-routing")
    assert op.func_name == "bkm_cli.manage_cache_routing"
    assert op.capability_level == "admin"
    assert op.risk_level == "mutation"
    assert op.requires_confirmation is True
