from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError
from core.drf_resource.exceptions import CustomException

from kernel_api.rpc.functions.admin.bcs_management import management_scope
from kernel_api.rpc.functions.admin import bcs_metadata as rpc
from metadata.task import bcs


@pytest.mark.parametrize("value", ["", "__all__"])
def test_explicit_tenant(value):
    with pytest.raises((ValidationError, CustomException)):
        rpc.context({"bk_tenant_id": value, "cluster_id": "BCS-K8S-1"})


def test_page_size_limit():
    with pytest.raises(ValidationError):
        rpc.context({"bk_tenant_id": "system", "cluster_id": "BCS-K8S-1", "page_size": 101})


@pytest.mark.parametrize("black,white,biz,expected", [([2], [2], 2, False), ([], [2], 2, True), ([], [], 2, False)])
def test_scope_uses_loaded_legacy_function(monkeypatch, black, white, biz, expected):
    monkeypatch.setattr(bcs.settings, "NEW_ENV_CLUSTER_BLACK_LIST", black)
    monkeypatch.setattr(bcs.settings, "NEW_ENV_CLUSTER_WHITE_LIST", white)
    monkeypatch.setattr(bcs.settings, "NEW_ENV_START_CLUSTER_ID", "BCS-K8S-100")
    assert management_scope("BCS-K8S-1", biz)["managed"] is expected


def test_scope_uses_new_ranges_function(monkeypatch):
    monkeypatch.setattr(bcs, "get_discover_cluster_id_ranges", lambda: [{"start": 10, "end": 20}], raising=False)
    helper = Mock(return_value=False)
    monkeypatch.setattr(bcs, "is_discover_managed_cluster", helper)
    result = management_scope("BCS-K8S-20", 2)
    helper.assert_called_once_with("BCS-K8S-20", [{"start": 10, "end": 20}], 2)
    assert result["rule_version"] == "ranges"
    assert result["managed"] is False


def test_upstream_reads_one_page_and_projects_safe_fields(monkeypatch):
    monkeypatch.setattr(rpc, "cluster_context", lambda _: (object(), None))
    page = Mock(
        return_value=[
            {
                "metadata": {"name": "pod-a", "annotations": {"secret": "credential"}},
                "spec": {"containers": [{"env": [{"value": "secret"}]}]},
            }
        ]
    )
    monkeypatch.setattr(rpc, "api", SimpleNamespace(bcs_storage=SimpleNamespace(fetch_page=page)))
    p = rpc.context({"bk_tenant_id": "system", "cluster_id": "BCS-K8S-1", "page": 3})
    result = rpc.upstream_inspect(p)
    assert page.call_count == 1
    assert page.call_args.args[0]["offset"] == 40
    assert result["complete"] is False
    assert "credential" not in str(result)
    assert "spec" not in str(result)


@pytest.mark.parametrize("rows,outcome", [([], "empty"), ([{"metadata": {"name": "pod"}}], "success")])
def test_empty_is_not_error(monkeypatch, rows, outcome):
    monkeypatch.setattr(rpc, "cluster_context", lambda _: (object(), None))
    monkeypatch.setattr(rpc, "api", SimpleNamespace(bcs_storage=SimpleNamespace(fetch_page=Mock(return_value=rows))))
    result = rpc.upstream_inspect(rpc.context({"bk_tenant_id": "system", "cluster_id": "c"}))
    assert result["outcome"] == outcome
    assert result["complete"]


def test_upstream_failure_is_not_empty(monkeypatch):
    monkeypatch.setattr(rpc, "cluster_context", lambda _: (object(), None))
    monkeypatch.setattr(
        rpc,
        "api",
        SimpleNamespace(bcs_storage=SimpleNamespace(fetch_page=Mock(side_effect=RuntimeError("upstream unavailable")))),
    )
    result = rpc.upstream_inspect(rpc.context({"bk_tenant_id": "system", "cluster_id": "c"}))
    assert result["outcome"] == "error"
    assert not result["complete"]
    assert "upstream unavailable" in result["error"]


def test_summary_never_reads_resource_tables_or_upstream(monkeypatch):
    monkeypatch.setattr(rpc, "cluster_context", lambda _: (None, None))
    resources = {key: Mock() for key in rpc.KINDS}
    monkeypatch.setattr(rpc, "KINDS", resources)
    api = Mock()
    monkeypatch.setattr(rpc, "api", api)
    rpc.summary({"bk_tenant_id": "system", "cluster_id": "c"})
    assert not api.mock_calls
    assert all(not model.mock_calls for model in resources.values())


def test_cluster_manager_business_error_is_not_empty():
    with pytest.raises(rpc.BKAPIError):
        rpc.ClusterLookup().render_response_data({}, {"code": 403, "message": "permission denied", "data": []})


def test_list_uses_limit_plus_one_without_count(monkeypatch):
    from unittest.mock import MagicMock

    query = MagicMock()
    query.model._meta.fields = [
        SimpleNamespace(name=n) for n in ["id", "name", "namespace", "status", "last_synced_at"]
    ]
    selected = query.order_by.return_value.values.return_value
    selected.__getitem__.return_value = [{"id": i} for i in range(21)]
    monkeypatch.setattr(rpc, "scoped_resources", lambda _: query)
    result = rpc.resource_list({"page": 3, "page_size": 20})
    selected.__getitem__.assert_called_once_with(slice(40, 61))
    query.count.assert_not_called()
    selected.count.assert_not_called()
    assert len(result["items"]) == 20
    assert result["has_more"] is True
