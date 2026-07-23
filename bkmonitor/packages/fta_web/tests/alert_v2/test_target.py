import logging
from types import SimpleNamespace
from typing import Any

import pytest
from elasticsearch_dsl import AttrDict

from constants.data_source import DataSourceLabel
from fta_web.alert_v2 import target as target_module
from fta_web.alert_v2.target import BaseTarget, DefaultTarget, HostTarget, K8SPodTarget, merge_log_targets


def test_default_target_merges_addition_for_non_clustering_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    query_config = {
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
        "index_set_id": 100,
        "query_string": 'message: "failed"',
        "agg_condition": [],
    }
    alert = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2),
        origin_alarm={
            "data": {
                "dimensions": {"service": "api"},
                "dimension_fields": ["service"],
            }
        },
    )

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: query_config)
    monkeypatch.setattr(target_module, "get_log_clustering_info", lambda _: ("", ""))
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 100, "index_set_name": "application"}],
    )

    result = DefaultTarget(alert).list_related_log_targets()

    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "application",
            "addition": [],
            "keyword": '(message: "failed") AND (service: "api")',
        }
    ]


def test_default_target_clustering_keeps_addition_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    query_config = {
        "query_string": 'message: "failed"',
        "agg_condition": [],
    }
    alert = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2),
        origin_alarm={
            "data": {
                "dimensions": {"service": "api"},
                "dimension_fields": ["service"],
            }
        },
    )

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: query_config)
    monkeypatch.setattr(target_module, "get_log_clustering_info", lambda _: ("count", "100"))
    monkeypatch.setattr(target_module, "get_log_clustering_time_range", lambda *_: None)
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 100, "index_set_name": "clustering"}],
    )

    result = DefaultTarget(alert).list_related_log_targets()

    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "clustering",
            "addition": [{"field": "service", "operator": "=", "value": ["api"]}],
            "keyword": "",
        }
    ]


def test_log_host_target_prefers_origin_log_strategy_without_event_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_config: dict[str, object] = {
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
        "index_set_id": 100,
        "query_string": 'message: "failed"',
        "agg_condition": [],
    }
    alert = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, ip=""),
        origin_alarm={
            "data": {
                "dimensions": {"ip": "127.0.0.1"},
                "dimension_fields": ["ip"],
            }
        },
    )

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: query_config)
    monkeypatch.setattr(target_module, "get_log_clustering_info", lambda _: ("", ""))
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 100, "index_set_name": "origin"}],
    )

    result: list[dict[str, object]] = HostTarget(alert).list_related_log_targets()

    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "origin",
            "addition": [],
            "keyword": '(message: "failed") AND (ip: "127.0.0.1")',
        }
    ]


def test_list_related_log_targets_uses_data_id_rt_map(monkeypatch: pytest.MonkeyPatch) -> None:
    data_id_queries: list[list[int]] = []
    relation = SimpleNamespace(
        nodes=[
            SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "1001"})),
            SimpleNamespace(source_info=SimpleNamespace(to_source_info=lambda: {"bk_data_id": "invalid"})),
        ]
    )

    def get_data_id_rt_map(data_ids: list[int]) -> dict[int, set[str]]:
        data_id_queries.append(data_ids)
        return {1001: {"2_bklog.demo"}}

    monkeypatch.setattr(target_module.RelationQ, "query", lambda *_args, **_kwargs: [relation])
    monkeypatch.setattr(target_module.ServiceLogHandler, "get_data_id_rt_map", get_data_id_rt_map)
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_kwargs: [
            {
                "index_set_id": 100,
                "indices": [{"result_table_id": "2_bklog.demo"}],
            }
        ],
    )

    result: list[dict[str, Any]] = BaseTarget._list_related_log_targets(2, [{}])

    assert data_id_queries == [[1001]]
    assert result == [
        {
            "index_set_id": 100,
            "indices": [{"result_table_id": "2_bklog.demo"}],
            "addition": [],
        }
    ]


def test_host_target_falls_back_when_origin_log_strategy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        first_anomaly_time=1_000,
        end_time=1_100,
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=1, ip="127.0.0.1", bk_cloud_id=0),
    )
    target = HostTarget(alert)
    relation_queries: list[dict[str, Any]] = []

    def generate_q(**kwargs: Any) -> list[dict[str, Any]]:
        relation_queries.append(kwargs)
        return [kwargs]

    def list_relation_log_targets(_bk_biz_id: int, _relation_qs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"index_set_id": 100, "index_set_name": "relation", "addition": []}]

    def list_collector_log_targets(_host_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(target_module.RelationQ, "generate_q", generate_q)
    monkeypatch.setattr(target, "_list_related_log_targets", list_relation_log_targets)
    monkeypatch.setattr(target, "_list_related_host_collector_log_targets", list_collector_log_targets)

    result: list[dict[str, Any]] = target.list_related_log_targets()

    assert len(relation_queries) == 2
    assert result == [
        {
            "index_set_id": 100,
            "index_set_name": "relation",
            "addition": [{"field": "serverIp", "operator": "=", "value": ["127.0.0.1"]}],
        }
    ]


def test_host_target_adds_host_collector_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=1, ip="127.0.0.1", bk_cloud_id=0),
    )
    target = HostTarget(alert)
    cached_index_sets: list[dict[str, Any]] = [{"index_set_id": 200, "index_set_name": "collector"}]

    def query_indexes(_cls: type, validated_data: dict[str, Any]) -> list[dict[str, Any]]:
        assert validated_data == {"bk_biz_id": 2, "bk_host_id": 1}
        return [{"index_set_id": "200"}]

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(
        target,
        "_host_relation_log_targets",
        lambda: [{"index_set_id": 100, "index_set_name": "relation", "addition": []}],
    )
    monkeypatch.setattr(target_module.HostIndexQueryMixin, "query_indexes", classmethod(query_indexes))
    monkeypatch.setattr(target_module, "get_biz_index_sets_with_cache", lambda **_: cached_index_sets)

    result: list[dict[str, Any]] = target.list_related_log_targets()

    assert result == [
        {"index_set_id": 100, "index_set_name": "relation", "addition": []},
        {
            "index_set_id": 200,
            "index_set_name": "collector",
            "addition": [{"field": "serverIp", "operator": "=", "value": ["127.0.0.1"]}],
        },
    ]
    assert cached_index_sets == [{"index_set_id": 200, "index_set_name": "collector"}]


def test_host_target_deduplicates_relation_before_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=1, ip="127.0.0.1", bk_cloud_id=0),
    )
    target = HostTarget(alert)
    relation_target: dict[str, Any] = {"index_set_id": 100, "index_set_name": "relation"}
    collector_target: dict[str, Any] = {"index_set_id": "100", "index_set_name": "collector"}

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(target, "_host_relation_log_targets", lambda: [relation_target])
    monkeypatch.setattr(target, "_list_related_host_collector_log_targets", lambda _host_targets: [collector_target])

    result: list[dict[str, Any]] = target.list_related_log_targets()

    assert result == [relation_target]


def test_host_target_without_origin_log_skips_host_queries_without_event_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=None, ip="", bk_cloud_id=0),
    )
    target = HostTarget(alert)

    def fail_query(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("主机日志查询不应执行")

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(target, "_host_relation_log_targets", fail_query)
    monkeypatch.setattr(target, "_list_related_host_collector_log_targets", fail_query)

    assert target.list_related_log_targets() == []


def test_host_collector_falls_back_to_ip_and_cloud_id_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(event=SimpleNamespace(bk_biz_id=2))
    target = HostTarget(alert)
    query_params: list[dict[str, Any]] = []

    def query_indexes(_cls: type, validated_data: dict[str, Any]) -> list[dict[str, Any]]:
        query_params.append(validated_data)
        return [{"index_set_id": 200}]

    monkeypatch.setattr(target_module.HostIndexQueryMixin, "query_indexes", classmethod(query_indexes))
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 200, "index_set_name": "collector"}],
    )

    result: list[dict[str, Any]] = target._query_host_collector_log_targets(
        {"bk_host_id": None, "bk_target_ip": "127.0.0.1", "bk_cloud_id": 0}
    )

    assert query_params == [{"bk_biz_id": 2, "bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0}]
    assert result == [
        {
            "index_set_id": 200,
            "index_set_name": "collector",
            "addition": [{"field": "serverIp", "operator": "=", "value": ["127.0.0.1"]}],
        }
    ]


def test_k8s_target_merges_k8s_apm_and_collector_logs_in_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(
        event=SimpleNamespace(
            bk_biz_id=2,
            tags=[
                AttrDict({"key": "bk_target_ip", "value": "127.0.0.1"}),
                AttrDict({"key": "bk_host_id", "value": 1}),
                AttrDict({"key": "bk_cloud_id", "value": 0}),
            ],
        ),
        dimensions=[],
    )
    target = K8SPodTarget(alert)
    k8s_target: dict[str, Any] = {"index_set_id": 100, "source": "k8s"}
    apm_target: dict[str, Any] = {"index_set_id": "100", "source": "apm"}
    apm_only_target: dict[str, Any] = {"index_set_id": 200, "source": "apm"}
    collector_duplicate_target: dict[str, Any] = {"index_set_id": "200", "source": "collector"}
    collector_only_target: dict[str, Any] = {"index_set_id": 300, "source": "collector"}

    def list_collector_log_targets(host_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assert host_targets == [
            {
                "bk_target_ip": "127.0.0.1",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
                "display_name": "127.0.0.1",
                "bk_host_name": "",
            }
        ]
        return [collector_duplicate_target, collector_only_target]

    monkeypatch.setattr(target, "_k8s_related_log_targets", lambda: [k8s_target])
    monkeypatch.setattr(target, "_apm_related_log_targets", lambda: [apm_target, apm_only_target])
    monkeypatch.setattr(target, "_list_related_host_collector_log_targets", list_collector_log_targets)

    result: list[dict[str, Any]] = target.list_related_log_targets()

    assert result == [k8s_target, apm_only_target, collector_only_target]


def test_host_collector_query_failure_does_not_break_log_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=1, ip="127.0.0.1", bk_cloud_id=0),
    )
    target = HostTarget(alert)
    queried_host_ids: list[int] = []

    def query_indexes(_cls: type, validated_data: dict[str, Any]) -> list[dict[str, Any]]:
        bk_host_id: int = validated_data["bk_host_id"]
        queried_host_ids.append(bk_host_id)
        if bk_host_id == 1:
            raise RuntimeError("collector query failed")
        return [{"index_set_id": 200}]

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(target, "_host_relation_log_targets", lambda: [{"index_set_id": 100, "source": "relation"}])
    monkeypatch.setattr(
        target,
        "list_related_host_targets",
        lambda: [
            {"bk_host_id": 1, "bk_target_ip": "127.0.0.1", "bk_cloud_id": 0},
            {"bk_host_id": 2, "bk_target_ip": "127.0.0.2", "bk_cloud_id": 0},
        ],
    )
    monkeypatch.setattr(target_module.HostIndexQueryMixin, "query_indexes", classmethod(query_indexes))
    monkeypatch.setattr(
        target_module,
        "get_biz_index_sets_with_cache",
        lambda **_: [{"index_set_id": 200, "index_set_name": "collector"}],
    )

    result: list[dict[str, Any]] = target.list_related_log_targets()

    assert sorted(queried_host_ids) == [1, 2]
    assert result == [
        {"index_set_id": 100, "source": "relation"},
        {
            "index_set_id": 200,
            "index_set_name": "collector",
            "addition": [{"field": "serverIp", "operator": "=", "value": ["127.0.0.2"]}],
        },
    ]


def test_host_collector_index_set_query_failure_does_not_break_log_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alert: Any = SimpleNamespace(
        strategy={},
        event=SimpleNamespace(bk_biz_id=2, bk_host_id=1, ip="127.0.0.1", bk_cloud_id=0),
    )
    target = HostTarget(alert)

    def query_indexes(_cls: type, _validated_data: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"index_set_id": 200}]

    def query_index_sets(**_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("index set query failed")

    monkeypatch.setattr(target_module, "get_alert_query_config_or_none", lambda _: None)
    monkeypatch.setattr(target, "_host_relation_log_targets", lambda: [{"index_set_id": 100, "source": "relation"}])
    monkeypatch.setattr(target_module.HostIndexQueryMixin, "query_indexes", classmethod(query_indexes))
    monkeypatch.setattr(target_module, "get_biz_index_sets_with_cache", query_index_sets)

    assert target.list_related_log_targets() == [{"index_set_id": 100, "source": "relation"}]


def test_merge_log_targets_keeps_highest_priority_group(caplog: pytest.LogCaptureFixture) -> None:
    highest_priority_target: dict[str, Any] = {"index_set_id": 100, "source": "relation"}

    with caplog.at_level(logging.INFO, logger=target_module.__name__):
        result: list[dict[str, Any]] = merge_log_targets(
            [highest_priority_target],
            [{"index_set_id": "100", "source": "collector"}, {"index_set_id": 200, "source": "collector"}],
        )

    assert result == [highest_priority_target, {"index_set_id": 200, "source": "collector"}]
    assert "index_set_id=100" in caplog.text
