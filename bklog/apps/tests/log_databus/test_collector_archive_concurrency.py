from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import mock

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.log_databus.constants import ArchiveInstanceType
from apps.log_databus.handlers import archive as archive_module
from apps.log_databus.handlers.archive import ArchiveHandler
from apps.log_databus.models import ArchiveConfig, CollectorConfig


@skipUnlessDBFeature("has_select_for_update")
class CollectorArchiveConcurrencyTests(TransactionTestCase):
    def test_concurrent_first_upserts_create_one_archive(self):
        collector = CollectorConfig.objects.create(
            bk_biz_id=2,
            collector_config_name="concurrent_archive",
            collector_config_name_en="concurrent_archive",
            collector_scenario_id="row",
            category_id="os",
            table_id="2_concurrent_archive",
        )
        repository_name = "2_bklog_demo"
        first_created = Event()
        release_first = Event()
        second_reading_collector = Event()
        second_completed = Event()

        def create_snapshot(_params):
            if not first_created.is_set():
                first_created.set()
                if not release_first.wait(10):
                    raise TimeoutError("等待并发归档请求超时")

        def observe_collector_read(execute, sql, params, many, context):
            if "SELECT" in sql.upper() and CollectorConfig._meta.db_table in sql:
                second_reading_collector.set()
            return execute(sql, params, many, context)

        def upsert(second=False):
            close_old_connections()
            try:
                if second:
                    with connection.execute_wrapper(observe_collector_read):
                        return ArchiveHandler.upsert_collector_archive(collector.pk, repository_name, 30)
                return ArchiveHandler.upsert_collector_archive(collector.pk, repository_name, 30)
            finally:
                connections.close_all()
                if second:
                    second_completed.set()

        with (
            mock.patch.object(archive_module, "TransferApi") as transfer_api,
            mock.patch.object(archive_module, "StorageHandler") as storage_handler,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            transfer_api.get_result_table_storage.return_value = {
                collector.table_id: {"cluster_config": {"cluster_id": 1}}
            }
            transfer_api.create_result_table_snapshot.side_effect = create_snapshot
            storage_handler.return_value.repository.return_value = [{"repository_name": repository_name}]
            first = executor.submit(upsert)
            try:
                self.assertTrue(first_created.wait(5))
                second = executor.submit(upsert, second=True)
                self.assertTrue(second_reading_collector.wait(5))
                self.assertFalse(second_completed.wait(1), "首个事务提交前，第二个请求应等待采集项行锁")
            finally:
                release_first.set()
            first_result = first.result(timeout=10)
            second_result = second.result(timeout=10)

        self.assertEqual(first_result, second_result)
        self.assertEqual(
            ArchiveConfig.objects.filter(
                instance_type=ArchiveInstanceType.COLLECTOR_CONFIG.value, instance_id=collector.pk
            ).count(),
            1,
        )
        transfer_api.create_result_table_snapshot.assert_called_once_with(
            {
                "table_id": collector.table_id,
                "target_snapshot_repository_name": repository_name,
                "snapshot_days": 30,
            }
        )
        transfer_api.modify_result_table_snapshot.assert_not_called()
