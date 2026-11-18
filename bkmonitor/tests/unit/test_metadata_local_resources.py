"""Worker metadata clients reuse resources while preserving the API response and cache contract."""

import base64
import datetime
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pytest
from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from rest_framework.response import Response

from api.metadata import default as clients
from bkmonitor.utils import cache as cache_module
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.contrib import api as api_module
from core.drf_resource.contrib.nested_api import KernelAPIResource
from core.errors.api import BKAPIError
from kernel_api.adapters import ApiRenderer
from metadata.resources import resources


@pytest.fixture(autouse=True)
def local_worker(monkeypatch):
    monkeypatch.setattr(settings, "ROLE", "worker")
    monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    store = LocMemCache("metadata-local-tests", {})
    store.clear()
    monkeypatch.setattr(cache_module, "cache", store)
    monkeypatch.setattr(cache_module, "mem_cache", store)
    monkeypatch.setattr(api_module, "get_request_tenant_id", lambda **kwargs: "tenant-a")
    monkeypatch.setattr(KernelAPIResource, "perform_request", Mock(side_effect=AssertionError("unexpected HTTP path")))
    return store


def api_data(data):
    return json.loads(ApiRenderer().render(data, renderer_context={"response": Response(data), "request": None}))[
        "data"
    ]


@pytest.mark.parametrize("by_name", [False, True])
@pytest.mark.parametrize("with_rt_info", [None, False])
def test_data_source_lookup_and_defaults(monkeypatch, by_name, with_rt_info):
    source = Mock()
    source.to_json.return_value = {"bk_data_id": 42, "stamp": datetime.datetime(2026, 1, 1), "biz_id": 2}
    query = Mock(return_value=source)
    monkeypatch.setattr(resources.models.DataSource.objects, "get", query)
    params = {"data_name": "metrics"} if by_name else {"bk_data_id": 42}
    if with_rt_info is not None:
        params["with_rt_info"] = with_rt_info
    client = clients.GetDataIdResource()
    expected = api_data(resources.QueryDataSourceResource().request({**params, "bk_tenant_id": "tenant-a"}))
    query.reset_mock()
    source.to_json.reset_mock()
    render = Mock(wraps=client.render_response_data)
    monkeypatch.setattr(client, "render_response_data", render)
    result = client.request(params)
    assert result == expected
    assert result["bk_biz_id"] == 2
    assert isinstance(result["stamp"], str)
    assert client.request(params) == result
    assert client.get_cached(params) == result
    render.assert_called_once()
    query.assert_called_once_with(
        **({"data_name": "metrics", "bk_tenant_id": "tenant-a"} if by_name else {"bk_data_id": 42})
    )
    source.to_json.assert_called_once_with(with_rt_info=with_rt_info is not False)
    assert "bk_tenant_id" not in params


def test_list_resource_preserves_filters_pagination_and_empty_cache(monkeypatch):
    relations = MagicMock()
    relations.exclude.return_value.values.return_value.distinct.return_value = [{"table_id": "metric.cpu"}]
    relation_filter = Mock(return_value=relations)
    monkeypatch.setattr(resources.models.DataSourceResultTable.objects, "filter", relation_filter)
    tables = MagicMock()
    tables.filter.return_value = tables
    tables.order_by.return_value = tables
    tables.__getitem__.return_value = tables
    tables.count.return_value = 1
    tables.values_list.return_value = ["metric.cpu"]
    table_filter = Mock(return_value=tables)
    monkeypatch.setattr(resources.models.ResultTable.objects, "filter", table_filter)
    batch = Mock(return_value=[{"table_id": "metric.cpu", "field_list": [{"field_name": "cpu"}]}])
    monkeypatch.setattr(resources.models.ResultTable, "batch_to_json", batch)
    monkeypatch.setattr(resources, "get_bcs_dataids", Mock(return_value=([99], None)))
    recording = Mock(return_value=[])
    monkeypatch.setattr(resources, "get_record_rule_metrics_by_biz_id", recording)
    client = clients.ListResultTableResource()
    params = {
        "bk_tenant_id": "tenant-a",
        "bk_biz_id": 2,
        "is_public_include": True,
        "page_size": 1,
        "with_option": False,
    }
    assert client.request(params) == {"count": 1, "info": batch.return_value}
    assert client.request(params) == {"count": 1, "info": batch.return_value}
    relation_filter.assert_called_once_with(bk_tenant_id="tenant-a")
    relations.exclude.assert_called_once_with(bk_data_id__in=[99])
    table_filter.assert_called_once_with(bk_tenant_id="tenant-a", is_deleted=False, table_id__in={"metric.cpu"})
    assert call(bk_biz_id__in=[0, 2]) in tables.filter.call_args_list
    tables.order_by.assert_called_once_with("table_id")
    batch.assert_called_once_with(bk_tenant_id="tenant-a", result_table_id_list=["metric.cpu"], with_option=False)
    tables.values_list.return_value = []
    batch.return_value = []
    params = {"bk_tenant_id": "tenant-a"}
    assert client.request(params) == []
    assert client.request(params) == []
    assert relation_filter.call_count == 2


def test_storage_resource_preserves_tenant_missing_tables_and_auth_encoding(monkeypatch):
    storage = resources.models.ResultTable.REAL_STORAGE_DICT["influxdb"]
    query = Mock(
        side_effect=[SimpleNamespace(consul_config={"auth_info": {"password": "example"}}), storage.DoesNotExist()]
    )
    monkeypatch.setattr(storage.objects, "get", query)
    params = {"bk_tenant_id": "tenant-a", "result_table_list": "metric.cpu,missing", "storage_type": "influxdb"}
    result = clients.GetResultTableStorageResource().request(params)
    assert isinstance(result["metric.cpu"]["auth_info"], str)
    assert json.loads(base64.b64decode(result["metric.cpu"]["auth_info"])) == {"password": "example"}
    assert list(result) == ["metric.cpu"]
    assert query.call_args_list == [
        call(table_id="metric.cpu", bk_tenant_id="tenant-a"),
        call(table_id="missing", bk_tenant_id="tenant-a"),
    ]


@pytest.mark.parametrize("role", ["web", "api"])
@pytest.mark.parametrize(
    "client_class,params",
    [
        (clients.ListResultTableResource, {}),
        (clients.GetDataIdResource, {"bk_data_id": 42}),
        (clients.GetResultTableStorageResource, {"result_table_list": "metric.cpu", "storage_type": "influxdb"}),
    ],
)
def test_other_roles_keep_kernel_api_path(monkeypatch, role, client_class, params):
    monkeypatch.setattr(settings, "ROLE", role)
    original = Mock(return_value="old path")
    monkeypatch.setattr(KernelAPIResource, "perform_request", original)
    assert client_class().perform_request(params) == "old path"
    original.assert_called_once_with(params)


@pytest.mark.parametrize(
    "params,context_tenant,space_tenant,expected",
    [
        ({"bk_tenant_id": "explicit", "bk_biz_id": 2}, "context", "space", "explicit"),
        ({"bk_biz_id": 2}, "context", "space", "space"),
        ({"space_uid": "bkcc__2"}, "context", "space", "space"),
        ({}, "context", None, "context"),
        ({}, None, None, DEFAULT_TENANT_ID),
    ],
)
def test_worker_tenant_priority(monkeypatch, params, context_tenant, space_tenant, expected):
    monkeypatch.setattr(api_module, "get_request_tenant_id", lambda **kwargs: context_tenant)
    space = Mock(return_value=SimpleNamespace(bk_tenant_id=space_tenant) if space_tenant else None)
    monkeypatch.setattr(api_module.SpaceApi, "get_space_detail", space)
    query = Mock(return_value=Mock(to_json=Mock(return_value={})))
    monkeypatch.setattr(resources.models.DataSource.objects, "get", query)
    client = clients.GetDataIdResource()
    client._request_local_resource(resources.QueryDataSourceResource, {**params, "data_name": "metrics"})
    query.assert_called_once_with(data_name="metrics", bk_tenant_id=expected)
    if "bk_tenant_id" in params or not params:
        space.assert_not_called()


@pytest.mark.parametrize("params", [{}, {"storage_type": "unknown", "result_table_list": "metric.cpu"}])
def test_resource_validation_and_query_errors_keep_bkapierror(params):
    with pytest.raises(BKAPIError):
        clients.GetResultTableStorageResource().perform_request(params)


def test_data_source_real_serialization_without_result_tables(monkeypatch):
    from metadata.models import data_source as source_module

    source = source_module.DataSource(bk_data_id=42, bk_tenant_id="tenant-a", data_name="metrics", etl_config="test")
    source._mq_config = SimpleNamespace(topic="topic", partition=1, batch_size=10, flush_interval=2, consume_rate=3)
    source._mq_cluster = SimpleNamespace(
        consul_config={"cluster_config": {"last_modify_time": "old", "domain_name": "mq"}}
    )
    monkeypatch.setattr(source_module.DataSource.objects, "get", Mock(return_value=source))
    monkeypatch.setattr(source_module.DataSourceOption, "get_option", Mock(return_value={"encoding": "json"}))
    monkeypatch.setattr(source_module, "get_space_uid_and_bk_biz_id_by_bk_data_id", Mock(return_value=(2, "bkcc__2")))
    table_query = Mock(side_effect=AssertionError("with_rt_info=False must not query result tables"))
    monkeypatch.setattr(source_module.DataSourceResultTable.objects, "filter", table_query)
    result = clients.GetDataIdResource().request({"bk_data_id": 42, "with_rt_info": False})
    assert result["mq_config"]["storage_config"] == {"topic": "topic", "partition": 1}
    assert result["mq_config"]["cluster_config"] == {"domain_name": "mq"}
    assert result["option"] == {"encoding": "json"}
    assert result["space_uid"] == "bkcc__2"
    assert "result_table_list" not in result
    table_query.assert_not_called()


def test_single_tenant_resource_uses_default_tenant(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", False)
    query = Mock(return_value=Mock(to_json=Mock(return_value={})))
    monkeypatch.setattr(resources.models.DataSource.objects, "get", query)
    clients.GetDataIdResource().request({"bk_tenant_id": "explicit", "data_name": "metrics"})
    query.assert_called_once_with(data_name="metrics", bk_tenant_id=DEFAULT_TENANT_ID)


def test_query_failure_is_bkapierror_and_not_cached(monkeypatch):
    query = Mock(side_effect=resources.models.DataSource.DoesNotExist("missing data source"))
    monkeypatch.setattr(resources.models.DataSource.objects, "get", query)
    client = clients.GetDataIdResource()
    for _ in range(2):
        with pytest.raises(BKAPIError, match="missing data source"):
            client.request({"bk_data_id": 42})
    assert query.call_count == 2
