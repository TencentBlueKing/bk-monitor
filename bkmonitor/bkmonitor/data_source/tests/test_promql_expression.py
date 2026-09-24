from unittest import mock

import pytest

from bkmonitor.data_source.promql_expression import compile_promql_expression
from bkmonitor.data_source.data_source import PrometheusTimeSeriesDataSource
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.strategy.new_strategy import Item


def query(alias, promql, interval=60):
    return {
        "data_source_label": "prometheus",
        "data_type_label": "time_series",
        "alias": alias,
        "promql": promql,
        "agg_interval": interval,
    }


def test_compile_promql_expression_preserves_precedence_and_vector_matching():
    configs = [query("a", 'sum(rate(requests_total{status="ok"}[1m]))'), query("ab", "sum(rate(requests_total[1m]))")]

    assert compile_promql_expression(configs, "100 * a / ab") == (
        '100 * (sum(rate(requests_total{status="ok"}[1m]))) / (sum(rate(requests_total[1m])))'
    )
    assert compile_promql_expression(configs, "a / on(ab) ab") == (
        '(sum(rate(requests_total{status="ok"}[1m]))) / on(ab) (sum(rate(requests_total[1m])))'
    )
    assert compile_promql_expression(configs, "clamp_min(a, 0) / on(ab) group_left ab") == (
        'clamp_min((sum(rate(requests_total{status="ok"}[1m]))), 0) / on(ab) group_left (sum(rate(requests_total[1m])))'
    )
    assert compile_promql_expression(configs, 'label_replace(a, "dst", "$1", "src", "(.*)") / ab') == (
        'label_replace((sum(rate(requests_total{status="ok"}[1m]))), "dst", "$1", "src", "(.*)") / '
        "(sum(rate(requests_total[1m])))"
    )
    assert compile_promql_expression(configs, "label_replace(a, 'dst', 'ab', 'src', '(.*)') / ab") == (
        "label_replace((sum(rate(requests_total{status=\"ok\"}[1m]))), 'dst', 'ab', 'src', '(.*)') / "
        "(sum(rate(requests_total[1m])))"
    )
    assert compile_promql_expression(configs, "label_replace(a, `dst`, `ab`, `src`, `(.*)`) / ab") == (
        'label_replace((sum(rate(requests_total{status="ok"}[1m]))), `dst`, `ab`, `src`, `(.*)`) / '
        "(sum(rate(requests_total[1m])))"
    )
    assert compile_promql_expression(configs, "sum by(job) (a / ab)") == (
        'sum by(job) ((sum(rate(requests_total{status="ok"}[1m]))) / (sum(rate(requests_total[1m]))))'
    )


def test_compile_promql_expression_preserves_alias_case():
    configs = [query("A", "up"), query("B", "down")]

    assert compile_promql_expression(configs, "A / B * 100") == "(up) / (down) * 100"
    with pytest.raises(ValueError, match="unknown PromQL query alias: a"):
        compile_promql_expression(configs, "a / B * 100")


@pytest.mark.parametrize(
    ("configs", "expression", "error"),
    [
        ([query("a", "up"), query("a", "down")], "a", "duplicate"),
        ([query("offset", "up"), query("b", "down")], "offset / b", "invalid PromQL query alias"),
        ([query("a", "up"), query("b", "down", 30)], "a / b", "same interval"),
        ([query("a", "up"), query("b", "down")], "a / typo", "unknown"),
        ([query("a", "up"), query("b", "down")], "a", "unused"),
        ([query("a", "up"), query("b", "down")], "", "required"),
        ([query("a", "up"), query("b", "down")], "$a / b", "unsupported"),
        ([query("a", "up"), query("b", "down")], "a && b", "unsupported"),
        ([query("a", "up"), query("b", "down")], "a offset 5m / b", "individual PromQL query"),
        ([query("a", "up"), query("b", "down")], "a[5m] / b", "individual PromQL query"),
        ([query("sum", "up"), query("a", "down")], "sum(a)", "conflicts with a function"),
    ],
)
def test_compile_promql_expression_rejects_invalid_config(configs, expression, error):
    with pytest.raises(ValueError, match=error):
        compile_promql_expression(configs, expression)


def test_unify_query_uses_one_final_promql_for_multiple_queries():
    sources = [
        PrometheusTimeSeriesDataSource(bk_biz_id=2, promql="requests_ok", interval=60, alias="a"),
        PrometheusTimeSeriesDataSource(bk_biz_id=2, promql="requests_total", interval=60, alias="b"),
    ]

    query = UnifyQuery(
        bk_biz_id=2,
        bk_tenant_id="test",
        data_sources=sources,
        expression="100 * a / b",
        promql_multi_expression=True,
    )

    assert len(query.data_sources) == 1
    assert query.data_sources[0].promql == "100 * (requests_ok) / (requests_total)"
    assert query.data_sources[0].interval == 60

    response = {
        "series": [
            {
                "name": "ratio",
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": [],
                "group_values": [],
                "values": [[60, 50.0]],
            }
        ]
    }
    with mock.patch.object(PrometheusTimeSeriesDataSource, "_execute_promql", return_value=(response, 180_000)) as run:
        records = query.query_data(start_time=60_000, end_time=180_000)

    run.assert_called_once()
    assert records == [{"_time_": 60_000, "_result_": 50.0}]


def test_unify_query_keeps_single_promql_unchanged():
    source = PrometheusTimeSeriesDataSource(bk_biz_id=2, promql="requests_ok", interval=60, alias="a")

    query = UnifyQuery(bk_biz_id=2, bk_tenant_id="test", data_sources=[source], expression="a")

    assert query.data_sources == [source]


def test_unify_query_keeps_existing_multi_promql_behavior_without_opt_in():
    sources = [
        PrometheusTimeSeriesDataSource(bk_biz_id=2, promql="requests_ok", interval=60, alias="a"),
        PrometheusTimeSeriesDataSource(bk_biz_id=2, promql="requests_total", interval=60, alias="b"),
    ]

    query = UnifyQuery(bk_biz_id=2, bk_tenant_id="test", data_sources=sources, expression="a or b")

    assert query.data_sources == sources


def test_legacy_multi_promql_item_can_still_be_read_and_saved():
    configs = [query("a", "up"), query("b", "down")]
    item = Item(strategy_id=1, name="legacy", no_data_config={}, query_configs=configs, algorithms=[], expression="")
    payload = {
        "name": item.name,
        "no_data_config": item.no_data_config,
        "query_configs": item.to_dict()["query_configs"],
        "algorithms": [],
        "target": [],
        "expression": "",
    }

    assert Item.Serializer(data=payload).is_valid(raise_exception=True)


def test_new_multi_promql_item_requires_valid_expression_on_save():
    configs = [{**query("a", "up"), "expression_mode": "promql"}, {**query("b", "down"), "expression_mode": "promql"}]
    payload = {
        "name": "new",
        "no_data_config": {},
        "query_configs": configs,
        "algorithms": [],
        "target": [],
        "expression": "a / typo",
    }

    assert not Item.Serializer(data=payload).is_valid()
    payload["expression"] = "a / b"
    assert Item.Serializer(data=payload).is_valid(raise_exception=True)
