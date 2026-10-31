"""Database-backed contracts for business-scoped, exact result-table lookup."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import PermissionDenied

from bkmonitor.iam import ActionEnum
from bkmonitor.models.strategy import QueryConfigModel, StrategyModel
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli import strategy, strategy_management as management
from kernel_api.rpc.functions.bkm_cli.platform_catalog import _authorization
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import ParamsGuardRejected

pytestmark = pytest.mark.django_db

TABLE_ID = "synthetic.metrics"
SUMMARY_FIELDS = {"id", "name", "bk_biz_id", "scenario", "is_enabled", "is_invalid"}


@pytest.fixture(autouse=True)
def authorize(monkeypatch):
    check = Mock()
    monkeypatch.setattr(strategy, "authorize_strategy_business", check)
    return check


def create_strategy(object_id, *, business=2, enabled=True, invalid=False):
    return StrategyModel.objects.create(
        id=object_id,
        bk_biz_id=business,
        name=f"synthetic-{object_id}",
        source="synthetic",
        scenario="os",
        type="monitor",
        is_enabled=enabled,
        is_invalid=invalid,
        update_user="private-user",
    )


def create_query(strategy_id, *, table=TABLE_ID, item_id=1, **config):
    return QueryConfigModel.objects.create(
        strategy_id=strategy_id,
        item_id=item_id,
        alias="a",
        data_source_label="bk_monitor",
        data_type_label="time_series",
        metric_id="synthetic_metric",
        config={"result_table_id": table, **config},
    )


def lookup(**overrides):
    return strategy.inspect_strategy_config(
        {"operation": "by_result_table", "bk_biz_id": 2, "result_table_id": TABLE_ID, **overrides}
    )


@pytest.fixture
def matching_strategies():
    for object_id, enabled, invalid in [(30, True, True), (10, True, False), (20, False, False)]:
        create_strategy(object_id, enabled=enabled, invalid=invalid)
        create_query(object_id)
    # 多个监控项和查询均命中同一策略，策略摘要只能出现一次。
    create_query(10, item_id=2)
    create_query(10, item_id=2)
    create_strategy(40, business=3)
    create_query(40)
    for object_id, table in [(50, f"{TABLE_ID}_extra"), (60, f"prefix_{TABLE_ID}")]:
        create_strategy(object_id)
        create_query(object_id, table=table)
    create_strategy(70)
    create_query(70, table="other.metrics", promql=TABLE_ID, metadata={"result_table_id": TABLE_ID})


def test_exact_lookup_uses_business_scope_and_includes_disabled_invalid(matching_strategies, authorize):
    params = {
        "operation": "by_result_table",
        "bk_biz_id": 2,
        "result_table_id": f" {TABLE_ID} ",
        "bk_tenant_id": "synthetic-tenant",
    }
    with CaptureQueriesContext(connection) as queries:
        result = strategy.inspect_strategy_config(params)

    authorize.assert_called_once_with(params, ActionEnum.VIEW_RULE)
    assert result["match_scope"] == "query_config.result_table_id"
    assert result["result_table_id"] == TABLE_ID
    assert result["count"] == 3
    assert result["truncated"] is False
    assert [row["id"] for row in result["strategies"]] == [10, 20, 30]
    assert [row["is_enabled"] for row in result["strategies"]] == [True, False, True]
    assert [row["is_invalid"] for row in result["strategies"]] == [False, False, True]
    assert all(set(row) == SUMMARY_FIELDS for row in result["strategies"])
    assert result["page"] == {
        "number": 1,
        "size": 50,
        "returned": 3,
        "total_pages": 1,
        "has_more": False,
        "max_result_window": 10000,
    }
    # 总数和当前页各一次 SQL；多监控项不引入逐策略读取。
    assert len(queries) == 2
    assert all("SELECT" in query["sql"].upper() for query in queries)


@pytest.mark.parametrize(
    ("page", "expected_ids", "has_more"),
    [(1, [10, 20], True), (2, [30], False), (3, [], False)],
)
def test_stable_pages_keep_total_separate_from_returned(matching_strategies, page, expected_ids, has_more):
    result = lookup(page=page, page_size=2)
    assert result["count"] == 3
    assert result["truncated"] is True
    assert result["page"]["total_pages"] == 2
    assert result["page"]["has_more"] is has_more
    assert result["page"]["returned"] == len(expected_ids)
    assert [row["id"] for row in result["strategies"]] == expected_ids


def test_zero_match_is_a_complete_exact_scope_result(matching_strategies):
    result = lookup(result_table_id="absent.metrics")
    assert result["count"] == 0
    assert result["strategies"] == []
    assert result["truncated"] is False
    assert result["page"]["returned"] == 0
    assert result["page"]["total_pages"] == 0
    assert result["page"]["has_more"] is False


def test_negative_space_scope_is_supported():
    create_strategy(1, business=-2)
    create_query(1)
    assert [row["id"] for row in lookup(bk_biz_id=-2)["strategies"]] == [1]


def test_table_id_length_boundary_is_accepted():
    assert lookup(result_table_id="x" * 128)["count"] == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"bk_biz_id": None},
        {"bk_biz_id": 0},
        {"bk_biz_id": True},
        {"bk_biz_id": "2"},
        {"bk_biz_id": 2.0},
        {"result_table_id": None},
        {"result_table_id": ""},
        {"result_table_id": " "},
        {"result_table_id": "x" * 129},
        {"result_table_id": " " + "x" * 128},
        {"page": 0},
        {"page": True},
        {"page": "1"},
        {"page": 1.5},
        {"page_size": 0},
        {"page_size": 201},
        {"page_size": None},
        {"page_size": False},
        {"page_size": "50"},
        {"page_size": 1.5},
        {"page": 51, "page_size": 200},
        {"include_disabled": False},
        {"include_invalid": False},
        {"name": "synthetic"},
        {"strategy_id": 1},
        {"unknown": True},
    ],
)
def test_invalid_parameters_are_rejected_before_authorization_or_database(overrides, authorize):
    with CaptureQueriesContext(connection) as queries, pytest.raises(CustomException):
        lookup(**overrides)
    authorize.assert_not_called()
    assert not queries


@pytest.mark.parametrize("whitespace", [" ", "\t", "\n", "\u0085", "\u001c", "\u001d", "\u001e", "\u001f"])
@pytest.mark.parametrize("position", ["prefix", "suffix"])
def test_noncanonical_operation_is_rejected_before_authorization_or_database(whitespace, position, authorize):
    operation = f"{whitespace}by_result_table" if position == "prefix" else f"by_result_table{whitespace}"
    with CaptureQueriesContext(connection) as queries, pytest.raises(CustomException, match="operation 必须精确匹配"):
        lookup(operation=operation)
    authorize.assert_not_called()
    assert not queries


def test_permission_denied_propagates_before_strategy_reads(authorize):
    authorize.side_effect = PermissionDenied("synthetic permission refusal")
    with CaptureQueriesContext(connection) as queries, pytest.raises(PermissionDenied):
        lookup()
    authorize.assert_called_once()
    assert not queries


@pytest.fixture
def principal(monkeypatch):
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, username="synthetic-user", tenant_id="system"),
        META={},
        jwt=SimpleNamespace(app=SimpleNamespace(app_code="synthetic-app")),
    )
    monkeypatch.setattr(management, "get_request", lambda **_kwargs: request)
    monkeypatch.setattr(_authorization, "get_request", lambda **_kwargs: request)
    monkeypatch.setattr(_authorization, "bk_biz_id_to_bk_tenant_id", lambda _value: "system")
    monkeypatch.setattr(_authorization, "is_match_api_token", lambda *_args: True)
    permission = Mock(skip_check=True)
    permission.is_allowed.return_value = True
    factory = Mock(return_value=permission)
    monkeypatch.setattr(management, "Permission", factory)
    monkeypatch.setattr(strategy, "authorize_strategy_business", management.authorize_strategy_business)
    return request, factory, permission


def test_real_authorization_uses_view_permission_and_request_principal(principal):
    _request, factory, permission = principal
    assert lookup(bk_tenant_id="system")["count"] == 0
    factory.assert_called_once_with(username="synthetic-user", bk_tenant_id="system")
    assert permission.skip_check is False
    action, resources = permission.is_allowed.call_args.args
    assert action == ActionEnum.VIEW_RULE
    assert resources[0].id == "2"


@pytest.mark.parametrize("kind", ["iam", "tenant", "application", "token", "expired", "missing"])
def test_real_authorization_refuses_before_reading_strategy_sql(monkeypatch, principal, kind):
    request, _factory, permission = principal
    params = {}
    if kind == "iam":
        permission.is_allowed.return_value = False
    elif kind == "tenant":
        params["bk_tenant_id"] = "another"
    elif kind == "application":
        monkeypatch.setattr(_authorization, "is_match_api_token", lambda *_args: False)
    elif kind in ("token", "expired"):
        request.META["HTTP_AUTHORIZATION"] = "Bearer synthetic-token"
        record = SimpleNamespace(is_expired=lambda: kind == "expired", is_allowed_namespace=lambda _value: False)
        monkeypatch.setattr(
            _authorization.ApiAuthToken.objects, "filter", lambda **_kwargs: SimpleNamespace(first=lambda: record)
        )
    else:
        request.user.is_authenticated = False
    with CaptureQueriesContext(connection) as queries, pytest.raises((PermissionDenied, ParamsGuardRejected)):
        lookup(**params)
    assert not queries
    if kind != "iam":
        permission.is_allowed.assert_not_called()


def test_last_allowed_window_discloses_more_matches_without_misreporting_completion():
    StrategyModel.objects.bulk_create(
        [
            StrategyModel(id=i, bk_biz_id=2, name=f"synthetic-{i}", source="synthetic", scenario="os", type="monitor")
            for i in range(1, 10002)
        ]
    )
    QueryConfigModel.objects.bulk_create(
        [
            QueryConfigModel(
                strategy_id=i,
                item_id=i,
                alias="a",
                data_source_label="bk_monitor",
                data_type_label="time_series",
                metric_id="synthetic_metric",
                config={"result_table_id": TABLE_ID},
            )
            for i in range(1, 10002)
        ]
    )
    result = lookup(page=50, page_size=200)
    assert result["count"] == 10001
    assert result["truncated"] is True
    assert result["page"]["returned"] == 200
    assert result["page"]["total_pages"] == 51
    assert result["page"]["has_more"] is True
    assert result["page"]["max_result_window"] == 10000
    assert result["strategies"][0]["id"] == 9801
    assert result["strategies"][-1]["id"] == 10000
