from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied

from kernel_api.resource import log_collection_discovery as discovery_module
from kernel_api.resource.log_collection_discovery import ListResultTablesResource, ListThirdPartyESClustersResource


def test_discovery_business_ids_allow_negative_business_ids():
    serializers = [ListThirdPartyESClustersResource.RequestSerializer(), ListResultTablesResource.RequestSerializer()]

    for serializer in serializers:
        assert serializer.fields["bk_biz_id"].run_validation(-2) == -2


def test_list_third_party_es_clusters_forwards_business(monkeypatch):
    list_log_cluster = Mock(return_value=[{"storage_cluster_id": 61, "storage_cluster_name": "external-es"}])
    monkeypatch.setattr(
        discovery_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(list_log_cluster=list_log_cluster)),
    )

    result = ListThirdPartyESClustersResource().perform_request({"bk_biz_id": 2})

    assert result == [{"storage_cluster_id": 61, "storage_cluster_name": "external-es"}]
    list_log_cluster.assert_called_once_with(bk_biz_id=2)


def test_list_result_tables_requires_storage_cluster_for_es():
    serializer = ListResultTablesResource.RequestSerializer(data={"bk_biz_id": 2, "scenario_id": "es"})

    assert not serializer.is_valid()
    assert "storage_cluster_id" in serializer.errors


def test_list_result_tables_allows_bkdata_without_storage_cluster():
    serializer = ListResultTablesResource.RequestSerializer(data={"bk_biz_id": 2, "scenario_id": "bkdata"})

    assert serializer.is_valid(), serializer.errors


def test_list_result_tables_forwards_validated_filters(monkeypatch):
    list_result_tables = Mock(return_value=[{"result_table_id": "logs-*"}])
    list_log_cluster = Mock(return_value=[{"storage_cluster_id": 61}])
    monkeypatch.setattr(
        discovery_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                list_log_cluster=list_log_cluster,
                list_result_tables=list_result_tables,
            )
        ),
    )
    serializer = ListResultTablesResource.RequestSerializer(
        data={"bk_biz_id": 2, "scenario_id": "es", "storage_cluster_id": 61, "result_table_id": "logs"}
    )
    assert serializer.is_valid(), serializer.errors

    result = ListResultTablesResource().perform_request(serializer.validated_data)

    assert result == [{"result_table_id": "logs-*"}]
    list_log_cluster.assert_called_once_with(bk_biz_id=2)
    list_result_tables.assert_called_once_with(
        bk_biz_id=2,
        scenario_id="es",
        storage_cluster_id=61,
        result_table_id="logs",
    )


def test_list_result_tables_rejects_invisible_storage_cluster(monkeypatch):
    list_result_tables = Mock()
    monkeypatch.setattr(
        discovery_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                list_log_cluster=Mock(return_value=[{"storage_cluster_id": 62}]),
                list_result_tables=list_result_tables,
            )
        ),
    )

    with pytest.raises(PermissionDenied):
        ListResultTablesResource().perform_request(
            {"bk_biz_id": 2, "scenario_id": "es", "storage_cluster_id": 61}
        )

    list_result_tables.assert_not_called()
