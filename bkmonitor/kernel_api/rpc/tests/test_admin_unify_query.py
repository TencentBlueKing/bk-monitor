"""Admin unify-query delegates scope and queries to the platform Resource."""

from unittest.mock import Mock

import pytest
from django.conf import settings
from rest_framework.exceptions import ValidationError

from kernel_api.rpc.functions.admin import unify_query
from kernel_api.rpc.registry import KernelRPCRegistry


def params(**overrides):
    return {"bk_tenant_id": "system", "promql": "up", "start": 1790100000, "end": 1790103600, "step": 60, **overrides}


def test_registered_with_machine_readable_schema():
    detail = KernelRPCRegistry.get_function_detail(unify_query.FUNC_QUERY)
    assert detail["params_schema"]["type"] == "object"
    assert detail["example_params"]["bk_biz_id"] == 2


def test_defaults_business_and_preserves_partial_results(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_BK_BIZ_ID", 7)
    raw = {"series": [], "is_partial": True, "trace_id": "uq-trace"}
    provider = Mock(return_value=raw)
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    response = unify_query.query(params())
    provider.assert_called_once_with(
        bk_tenant_id="system", bk_biz_ids=["7"], promql="up", start="1790100000", end="1790103600", step="60s"
    )
    assert response["data"] == {"source": {"bk_tenant_id": "system", "bk_biz_id": 7}, "result": raw}
    assert response["meta"]["safety_level"] == "read"


def test_explicit_query_business_and_tenant(monkeypatch):
    provider = Mock(return_value={"series": []})
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", provider)
    response = unify_query.query(params(bk_biz_id=12, bk_tenant_id="query-tenant"))
    assert provider.call_args.kwargs["bk_tenant_id"] == "query-tenant"
    assert provider.call_args.kwargs["bk_biz_ids"] == ["12"]
    assert response["data"]["source"]["bk_tenant_id"] == "query-tenant"


@pytest.mark.parametrize("overrides", [{"end": 99}, {"step": 0}, {"bk_tenant_id": "__all__"}])
def test_invalid_query_inputs(overrides):
    with pytest.raises(ValidationError):
        unify_query.query(params(**overrides))


def test_resource_accepts_explicit_tenant():
    from api.unify_query.default import QueryDataByPromqlResource

    validated = QueryDataByPromqlResource().validate_request_data(
        {"bk_tenant_id": "query-tenant", "promql": "up", "start": "100", "end": "200", "step": "60s"}
    )
    assert validated["bk_tenant_id"] == "query-tenant"


@pytest.mark.parametrize("entry", [unify_query.query, unify_query.preview])
def test_preview_never_calls_data_query(monkeypatch, entry):
    raw = {"data": [{"sql": "select value from metrics"}], "route_info": [{"table_id": "system.cpu"}]}
    check = Mock(return_value=raw)
    query = Mock()
    monkeypatch.setattr(unify_query.api.unify_query, "check_query_ts_by_promql", check)
    monkeypatch.setattr(unify_query.api.unify_query, "query_data_by_promql", query)
    assert entry(params(parse_only=True))["data"]["result"] == raw
    assert check.call_args.kwargs["promql"] == "up"
    query.assert_not_called()
    check.side_effect = RuntimeError("check unavailable")
    with pytest.raises(RuntimeError, match="check unavailable"):
        entry(params(parse_only=True))
    query.assert_not_called()
