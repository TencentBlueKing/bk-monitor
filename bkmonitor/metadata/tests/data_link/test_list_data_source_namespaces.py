import pytest

from metadata import models
from metadata.resources import ListDataSourceNamespacesResource


@pytest.mark.django_db(databases="__all__")
def test_list_data_source_namespaces(mocker):
    mocker.patch("bkmonitor.utils.serializers.get_request_tenant_id", return_value="tenant-a")
    for tenant, data_id, namespace, name, status in [
        ("tenant-a", 101, "shared", "source", ""),
        ("tenant-a", 101, "bkmonitor", "second", "Pending"),
        ("tenant-a", 101, "bkmonitor", "first", "Ok"),
        ("tenant-a", 101, "bklog", "logs", "Ok"),
        ("tenant-b", 101, "other-tenant", "source", "Ok"),
        ("tenant-a", 102, "other-data-id", "source", "Ok"),
    ]:
        models.DataIdConfig.objects.create(
            bk_tenant_id=tenant, bk_data_id=data_id, bk_biz_id=2, namespace=namespace, name=name, status=status
        )

    resource = ListDataSourceNamespacesResource()
    assert resource.request(bk_data_id=101, bk_tenant_id="tenant-b") == [
        {"namespace": "shared", "name": "source", "status": ""},
    ]
    assert resource.request(bk_data_id=101, include_builtin="true") == [
        {"namespace": "bklog", "name": "logs", "status": "Ok"},
        {"namespace": "bkmonitor", "name": "first", "status": "Ok"},
        {"namespace": "bkmonitor", "name": "second", "status": "Pending"},
        {"namespace": "shared", "name": "source", "status": ""},
    ]
    assert resource.request(bk_data_id=103) == []
