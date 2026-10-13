"""联邦拓扑同步的事务和提交回调必须使用模型查询所在的数据库连接。"""

from django.db import connections, transaction
from django.test import override_settings
import pytest

from metadata import models
from metadata.service.federation_data_link import FederationReconcilePlan
from metadata.task.bcs import schedule_federation_reconcile, sync_federation_clusters


pytestmark = pytest.mark.django_db(databases="__all__", transaction=True)


class MetadataDatabaseRouter:
    def __init__(self, alias):
        self.alias = alias

    def db_for_read(self, model, **hints):
        if model._meta.app_label == "metadata":
            return self.alias
        return None

    db_for_write = db_for_read


@pytest.fixture(params=["default", "monitor_api"])
def backend_database(request, monkeypatch):
    alias = request.param
    monkeypatch.setattr("metadata.task.bcs.DATABASE_CONNECTION_NAME", alias)
    with override_settings(DATABASE_ROUTERS=[MetadataDatabaseRouter(alias)]):
        yield alias


def test_sync_federation_clusters_locks_in_backend_transaction(backend_database):
    connection = connections[backend_database]
    table_name = models.BcsFederalClusterInfo._meta.db_table
    locked_queries = []

    def check_transaction(execute, sql, params, many, context):
        if table_name in sql:
            assert context["connection"].in_atomic_block
            if backend_database != "default":
                assert not connections["default"].in_atomic_block
            locked_queries.append(sql)
        return execute(sql, params, many, context)

    assert not connection.in_atomic_block
    with connection.execute_wrapper(check_transaction):
        plan = sync_federation_clusters(fed_clusters={}, bk_tenant_id="transaction-test")

    assert locked_queries
    if connection.features.has_select_for_update:
        assert "FOR UPDATE" in locked_queries[0]
    assert plan == FederationReconcilePlan()


@pytest.mark.parametrize("rollback", [False, True])
def test_federation_reconcile_waits_for_backend_commit(backend_database, rollback, mocker):
    delay = mocker.patch("metadata.task.bcs.reconcile_federation_data_links_task.delay")
    plan = FederationReconcilePlan(active_proxy_cluster_ids=["BCS-K8S-10001"])

    with transaction.atomic(using=backend_database):
        schedule_federation_reconcile(bk_tenant_id="transaction-test", plan=plan)
        delay.assert_not_called()
        if rollback:
            transaction.set_rollback(True, using=backend_database)

    if rollback:
        delay.assert_not_called()
    else:
        delay.assert_called_once_with(
            bk_tenant_id="transaction-test",
            active_proxy_cluster_ids=["BCS-K8S-10001"],
            active_sub_cluster_ids=[],
            removed_proxy_cluster_ids=[],
            removed_sub_cluster_ids=[],
        )
