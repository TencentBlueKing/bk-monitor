"""联邦拓扑同步的事务和提交回调必须使用模型查询所在的数据库连接。"""

from contextlib import nullcontext

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
    monkeypatch.setattr("metadata.task.bcs.service_lock", lambda *args, **kwargs: nullcontext())
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


def test_empty_federation_plan_does_not_register_callback(backend_database, mocker):
    on_commit = mocker.patch("metadata.task.bcs.transaction.on_commit")
    delay = mocker.patch("metadata.task.bcs.reconcile_federation_data_links_task.delay")
    schedule_federation_reconcile("transaction-test", FederationReconcilePlan())
    on_commit.assert_not_called()
    delay.assert_not_called()


def test_mysql_sync_and_reconcile_share_tenant_lock(backend_database, monkeypatch):
    """使用 MySQL 独立连接验证：下发期间，同租户拓扑同步不能进入写事务。"""
    from contextlib import contextmanager
    from threading import Event, Lock, Thread

    from metadata.service.federation_data_link import reconcile_federation_data_links

    if connections[backend_database].vendor != "mysql":
        pytest.skip("requires MySQL")
    tenant = "federation-concurrency-test"
    models.BcsFederalClusterInfo.objects.create(
        bk_tenant_id=tenant,
        fed_cluster_id="proxy",
        sub_cluster_id="sub",
        host_cluster_id="host",
        fed_namespaces=["a"],
    )
    mutex = Lock()
    entered = Event()
    release = Event()
    errors = []
    lock_keys = []

    @contextmanager
    def shared_lock(key, **kwargs):
        lock_keys.append(key.get_key(**kwargs))
        if not mutex.acquire(blocking=False):
            raise RuntimeError("tenant locked")
        try:
            yield
        finally:
            mutex.release()

    def apply_proxy(**kwargs):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr("metadata.task.bcs.service_lock", shared_lock)
    monkeypatch.setattr("metadata.service.federation_data_link.service_lock", shared_lock)
    monkeypatch.setattr("metadata.service.federation_data_link.ensure_federal_proxy_data_link", apply_proxy)
    monkeypatch.setattr("metadata.service.federation_data_link.ensure_federal_subset_data_link", lambda **kwargs: None)

    def run():
        try:
            reconcile_federation_data_links(tenant, FederationReconcilePlan(active_sub_cluster_ids=["sub"]))
        except Exception as error:
            errors.append(error)
        finally:
            connections.close_all()

    worker = Thread(target=run)
    worker.start()
    try:
        assert entered.wait(5)
        with pytest.raises(RuntimeError, match="tenant locked"):
            sync_federation_clusters({}, tenant, allow_empty_topology=True)
        record = models.BcsFederalClusterInfo.objects.get(bk_tenant_id=tenant)
        assert not record.is_deleted
        assert record.reconcile_status == "pending"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert not errors
    assert len(set(lock_keys)) == 1
    record.refresh_from_db()
    assert record.reconcile_status == "success"
