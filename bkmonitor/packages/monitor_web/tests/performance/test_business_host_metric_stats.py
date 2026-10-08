from copy import deepcopy
from types import SimpleNamespace

import pytest

from monitor_web.performance import host_metric_stats as stats
from monitor_web.performance.resources import SearchHostMetricStatsResource


def business_query(mocker, host_ids=(1, 2), **flags):
    query = mocker.Mock(is_partial=False)
    query.query_data.return_value = [
        {"stat": key, "_result_": value}
        for key, value in {
            "value": len(host_ids),
            "id_count": len(host_ids),
            "ip_count": 0,
            "duplicates": 0,
            **flags,
        }.items()
    ] + [{"stat": "abnormal", "bk_host_id": str(host_id), "_result_": 1} for host_id in host_ids]
    mocker.patch.object(stats, "build_host_stats_query", return_value=query)
    return query


@pytest.mark.parametrize(
    "category,table,field",
    [("cpu", "system.cpu_summary", "usage"), ("mem", "system.mem", "pct_used"), ("disk", "system.disk", "in_use")],
)
def test_business_query_keeps_full_identity_flags_without_cmdb_whitelists(mocker, category, table, field):
    sources = []

    def source(**kwargs):
        sources.append(kwargs)
        return SimpleNamespace(**kwargs)

    mocker.patch.object(stats, "load_data_source", return_value=source)
    query = mocker.patch.object(stats, "UnifyQuery")
    stats.build_host_stats_query(2, category)
    assert len(sources) == 2
    assert all(source["filter_dict"] == {} for source in sources)
    assert all(source["table"] == table and source["metrics"][0]["field"] == field for source in sources)
    assert all(
        source["interval"] == 180 and source["group_by"] == ["bk_host_id", "bk_target_ip", "bk_target_cloud_id"]
        for source in sources
    )
    assert sources[0]["where"] == [{"key": "bk_host_id", "method": "neq", "value": [""]}]
    assert sources[1]["where"] == [{"key": "bk_host_id", "method": "eq", "value": [""]}]
    expression = query.call_args.kwargs["expression"]
    assert "group by (bk_host_id) (a >= 79.995)" in expression
    assert "count(a) or vector(0)" in expression
    assert "count(b) or vector(0)" in expression
    assert "count by (bk_host_id) (a) > 1" in expression
    assert '"raw_cloud"' in expression


def test_business_checks_only_abnormal_ids_against_current_cmdb(mocker):
    query = business_query(mocker, [1, 2, 3], id_count=29000)
    identities = mocker.patch.object(
        stats.api.cmdb, "get_host_identities", return_value=[{"bk_host_id": 1}, {"bk_host_id": 3}]
    )
    assert stats.query_business_host_metric_stats(2, "disk", 100, 400) == {
        "category": "disk",
        "value": 2,
        "complete": True,
    }
    identities.assert_called_once_with(bk_biz_id=2, bk_host_ids=[1, 2, 3])
    query.query_data.assert_called_once_with(start_time=220000, end_time=400000, instant=True)


@pytest.mark.parametrize(
    "host_ids,expected", [([], []), (["001", "1.0", "missing", " 1", "+1"], []), (["001", "1", "2"], [1, 2])]
)
def test_business_preserves_exact_cmdb_id_matching_and_skips_empty_candidates(mocker, host_ids, expected):
    business_query(mocker, host_ids)
    identities = mocker.patch.object(
        stats.api.cmdb, "get_host_identities", return_value=[{"bk_host_id": value} for value in expected]
    )
    assert stats.query_business_host_metric_stats(2, "cpu")["value"] == len(expected)
    if expected:
        identities.assert_called_once_with(bk_biz_id=2, bk_host_ids=expected)
    else:
        identities.assert_not_called()


@pytest.mark.parametrize("flags", [{"ip_count": 1}, {"duplicates": 1}, {"id_count": 0, "ip_count": 2}])
@pytest.mark.parametrize(
    "legacy", [{"value": 1, "complete": True}, {"value": None, "complete": False, "reason": "ambiguous_identity"}]
)
def test_business_ambiguity_uses_full_current_cmdb_scope_not_only_abnormal_hosts(mocker, flags, legacy):
    # 正常 ID + 异常 IP，或同 ID 一个正常一个异常，仍必须保留正常身份的歧义证据。
    business_query(mocker, [1], **flags)
    hosts = [{"bk_host_id": 1}, {"bk_host_id": 2}]
    identities = mocker.patch.object(stats.api.cmdb, "get_host_identities", return_value=hosts)
    fallback = mocker.patch.object(stats, "query_host_metric_stats", return_value=legacy)
    mocker.patch.object(stats.time, "time", return_value=400)
    assert stats.query_business_host_metric_stats(2, "cpu") == legacy
    identities.assert_called_once_with(bk_biz_id=2)
    fallback.assert_called_once_with(2, "cpu", hosts, 220, 400)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda query: setattr(query, "is_partial", True), "partial"),
        (lambda query: query.query_data.return_value.pop(), "invalid_result"),
        (lambda query: query.query_data.return_value.pop(0), "invalid_result"),
        (
            lambda query: query.query_data.return_value.append({"stat": "abnormal", "bk_host_id": "1", "_result_": 1}),
            "invalid_result",
        ),
        (lambda query: query.query_data.return_value.append({"stat": "unexpected", "_result_": 0}), "invalid_result"),
        (lambda query: query.query_data.return_value[0].update(_result_=float("nan")), "invalid_result"),
        (lambda query: query.query_data.return_value[0].update(_result_=float("inf")), "invalid_result"),
        (lambda query: query.query_data.return_value[0].update(_result_=-1), "invalid_result"),
        (lambda query: query.query_data.return_value[0].update(_result_=0.5), "invalid_result"),
        (lambda query: query.query_data.return_value[-1].update(_result_=80), "invalid_result"),
        (lambda query: query.query_data.return_value[-1].pop("bk_host_id"), "invalid_result"),
    ],
)
def test_business_incomplete_or_malformed_query_never_returns_a_count(mocker, mutation, reason):
    query = business_query(mocker)
    mutation(query)
    identities = mocker.patch.object(stats.api.cmdb, "get_host_identities")
    assert stats.query_business_host_metric_stats(2, "cpu") == {
        "category": "cpu",
        "value": None,
        "complete": False,
        "reason": reason,
    }
    identities.assert_not_called()


def test_business_query_error_propagates(mocker):
    query = business_query(mocker)
    query.query_data.side_effect = RuntimeError("query failed")
    identities = mocker.patch.object(stats.api.cmdb, "get_host_identities")
    with pytest.raises(RuntimeError, match="query failed"):
        stats.query_business_host_metric_stats(2, "cpu")
    identities.assert_not_called()


@pytest.mark.parametrize("scope", [{}, {"bk_obj_id": "biz", "bk_inst_id": 2}])
def test_only_business_root_resource_uses_candidate_path(mocker, scope):
    identities = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_identities")
    query = mocker.patch(
        "monitor_web.performance.resources.query_business_host_metric_stats", return_value={"value": 2}
    )
    result = SearchHostMetricStatsResource().perform_request(
        {"bk_biz_id": 2, "category": "cpu", "start_time": 100, "end_time": 400, **deepcopy(scope)}
    )
    assert result == {"value": 2}
    identities.assert_not_called()
    query.assert_called_once_with(2, "cpu", 100, 400)
