"""VM Query 集群模型测试。"""

import pytest
from django.db import IntegrityError, transaction

from metadata import config
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.vm_query_cluster import VmQueryClusterConfig


@pytest.mark.django_db(databases="__all__")
def test_identity_unique_constraint():
    values = {"bk_tenant_id": "tenant-a", "namespace": "bkmonitor", "name": "query-a", "num_replicas": 1}
    VmQueryClusterConfig.objects.create(**values)
    with pytest.raises(IntegrityError), transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        VmQueryClusterConfig.objects.create(**values)


def test_vm_query_kind_mapping():
    assert DataLinkKind.get_choice_value(DataLinkKind.VMQUERYCLUSTER.value) == "vmqueryclusters"
