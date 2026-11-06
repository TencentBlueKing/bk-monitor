from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import metric
from kernel_api.rpc.registry import KernelRPCRegistry

SCOPE = {"bk_tenant_id": "tenant-a", "bk_biz_id": 7}
METRIC = {
    "metric_id": "bk_monitor.system.cpu.usage",
    "promql_metric": "bkmonitor:system:cpu:usage",
    "dimensions": [{"id": "bk_target_ip", "name": "IP"}],
    "default_condition": [{"key": "x", "value": ["a"]}],
}


def test_search_reuses_selector_with_explicit_scope_and_pagination(monkeypatch):
    queryset = Mock()
    manager = Mock(return_value=queryset)
    monkeypatch.setattr(metric.MetricListCache.objects, "filter", manager)
    selector = metric.GetMetricListV2Resource
    conditions = Mock(return_value=queryset)
    serialize = Mock(return_value=[METRIC])
    for name, fn in [
        ("filter_by_conditions", conditions),
        ("data_type_filter", Mock(return_value=queryset)),
        ("data_source_filter", Mock(return_value=queryset)),
        ("page_filter", Mock(return_value=(queryset, 23))),
        ("get_metric_list", serialize),
    ]:
        monkeypatch.setattr(selector, name, fn)
    response = metric.search({**SCOPE, "query": "cpu", "page": 2, "page_size": 10})
    manager.assert_called_once_with(bk_tenant_id="tenant-a", bk_biz_id__in=[0, 7])
    query = conditions.call_args.args[1]
    assert query["conditions"] == [{"key": "query", "value": ["cpu"]}]
    assert query["data_type_label"] == "time_series"
    assert (query["page"], query["page_size"]) == (2, 10)
    serialize.assert_called_once_with(7, queryset)
    assert response["data"] == {"source": SCOPE, "items": [METRIC], "total": 23, "page": 2, "page_size": 10}
    assert response["meta"]["safety_level"] == "read"


def test_detail_preserves_native_query_information(monkeypatch):
    lookup = Mock(return_value=([METRIC], 1))
    monkeypatch.setattr(metric, "_metrics", lookup)
    result = metric.detail({**SCOPE, "metric_id": METRIC["metric_id"]})["data"]
    lookup.assert_called_once_with(
        {**SCOPE, "metric_id": METRIC["metric_id"]}, [{"key": "metric_id", "value": [METRIC["metric_id"]]}], 1, 1
    )
    assert result["metric"] == METRIC
    assert result["query_template"]["params"] == {
        **SCOPE,
        "promql": METRIC["promql_metric"],
        "step": 60,
        "parse_only": True,
    }
    assert result["query_template"]["required_params"] == ["start", "end"]
    assert result["dimension_values_template"]["params"]["match"] == [METRIC["promql_metric"]]


def test_missing_and_unsupported_metric_are_not_fabricated(monkeypatch):
    monkeypatch.setattr(metric, "_metrics", Mock(return_value=([], 0)))
    with pytest.raises(CustomException, match="未找到指标"):
        metric.detail({**SCOPE, "metric_id": "missing"})
    monkeypatch.setattr(metric, "_metrics", Mock(return_value=([{**METRIC, "promql_metric": ""}], 1)))
    result = metric.detail({**SCOPE, "metric_id": "log.index"})["data"]
    assert result["query_template"] is None
    assert result["dimension_values_template"] is None


def test_dimension_values_scope_paging_and_errors(monkeypatch):
    provider = Mock(return_value={"values": {"host": ["a", "b", "c"]}, "trace_id": "uq-trace"})
    monkeypatch.setattr(metric, "MetricLabelValuesResource", Mock(return_value=provider))
    params = {
        **SCOPE,
        "match": ['custom:app:requests{env="prod"}'],
        "label": "host",
        "start": 100,
        "end": 200,
        "page": 2,
        "page_size": 2,
    }
    result = metric.dimension_values(params)["data"]
    provider.assert_called_once_with(
        bk_tenant_id="tenant-a", bk_biz_ids=[7], match=params["match"], label="host", start="100", end="200"
    )
    assert result == {"source": SCOPE, "items": ["c"], "total": 3, "page": 2, "page_size": 2, "trace_id": "uq-trace"}
    provider.side_effect = RuntimeError("upstream unavailable")
    with pytest.raises(RuntimeError, match="upstream unavailable"):
        metric.dimension_values(params)


def test_uq_resource_preserves_explicit_tenant():
    params = metric.MetricLabelValuesResource().validate_request_data(
        {
            "bk_tenant_id": "tenant-a",
            "bk_biz_ids": [7],
            "match": ["up"],
            "label": "host",
            "start": "100",
            "end": "200",
        }
    )
    assert params["bk_tenant_id"] == "tenant-a"
    assert params["match[]"] == ["up"]


@pytest.mark.parametrize(
    "params", [{"bk_biz_id": 7}, {**SCOPE, "bk_tenant_id": "__all__"}, {**SCOPE, "page_size": 101}]
)
def test_invalid_search_inputs(params):
    with pytest.raises(ValidationError):
        metric.search(params)


def test_invalid_dimension_range():
    with pytest.raises(ValidationError):
        metric.dimension_values({**SCOPE, "match": ["up"], "label": "host", "start": 200, "end": 100})


@pytest.mark.parametrize("name", ["search", "detail", "dimension_values"])
def test_registered_discovery(name):
    detail = KernelRPCRegistry.get_function_detail(f"admin.metric.{name}")
    assert "bk_tenant_id" in detail["params_schema"]["required"]
    assert "bk_biz_id" in detail["params_schema"]["required"]
    assert detail["example_params"]["bk_biz_id"] == 2
