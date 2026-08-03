from contextlib import nullcontext
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from apm.constants import GLOBAL_CONFIG_BK_BIZ_ID
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.core.handlers.trace_index_set import TraceScopeIndexSetHandler
from apm.task import tasks
from constants.common import DEFAULT_TENANT_ID
from core.errors.alarm_backends import LockError

BK_BIZ_ID = 2
BK_TENANT_ID = "tenant-a"


class FakeQuerySet(list[dict[str, Any]]):
    def values(self, *fields: str) -> "FakeQuerySet":
        return FakeQuerySet([{field: item[field] for field in fields} for item in self])

    def order_by(self, *fields: str) -> "FakeQuerySet":
        return self


def mock_snapshot_rows(
    mocker: MockerFixture,
    applications: list[dict[str, Any]],
    trace_datasources: list[dict[str, Any]],
    storages: list[dict[str, Any]],
) -> None:
    mocker.patch(
        "apm.core.handlers.trace_index_set.ApmApplication.objects.filter",
        return_value=FakeQuerySet(applications),
    )
    mocker.patch(
        "apm.core.handlers.trace_index_set.TraceDataSource.objects.filter",
        return_value=FakeQuerySet(trace_datasources),
    )
    mocker.patch(
        "apm.core.handlers.trace_index_set.ESStorage.objects.filter",
        return_value=FakeQuerySet(storages),
    )


@pytest.fixture
def index_set_api_mocks(mocker: MockerFixture) -> dict[str, MagicMock]:
    return {
        "search": mocker.patch(
            "apm.core.handlers.trace_index_set.api.log_search.search_index_set.request.cacheless",
            return_value=[],
        ),
        "create": mocker.patch("apm.core.handlers.trace_index_set.api.log_search.create_index_set"),
        "update": mocker.patch("apm.core.handlers.trace_index_set.api.log_search.update_index_set"),
        "delete": mocker.patch("apm.core.handlers.trace_index_set.api.log_search.delete_index_set"),
    }


class TestTraceScopeIndexSetHandler:
    @pytest.mark.parametrize(
        ("bk_biz_id", "expected"),
        [
            (2, "bkapm_cross_trace_2"),
            (-3, "bkapm_cross_trace_space_3"),
        ],
    )
    def test_build_index_set_name(self, bk_biz_id: int, expected: str) -> None:
        assert TraceScopeIndexSetHandler.build_index_set_name(bk_biz_id) == expected

    def test_get_index_set_uses_cacheless_exact_match(self, index_set_api_mocks: dict[str, MagicMock]) -> None:
        index_set_api_mocks["search"].return_value = [
            {"index_set_id": 1, "index_set_name": "other", "ignored": True},
            {"index_set_id": 2, "index_set_name": "bkapm_cross_trace_2", "ignored": True},
        ]

        index_set = TraceScopeIndexSetHandler.get_index_set(BK_TENANT_ID, BK_BIZ_ID)

        assert index_set == {"index_set_id": 2, "index_set_name": "bkapm_cross_trace_2"}
        index_set_api_mocks["search"].assert_called_once_with(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=BK_BIZ_ID,
        )

    def test_get_index_set_returns_none_when_not_found(self, index_set_api_mocks: dict[str, MagicMock]) -> None:
        assert TraceScopeIndexSetHandler.get_index_set(BK_TENANT_ID, BK_BIZ_ID) is None

    def test_get_index_set_rejects_multiple_exact_matches(self, index_set_api_mocks: dict[str, MagicMock]) -> None:
        index_set_api_mocks["search"].return_value = [
            {"index_set_id": 1, "index_set_name": "bkapm_cross_trace_2"},
            {"index_set_id": 2, "index_set_name": "bkapm_cross_trace_2"},
        ]

        with pytest.raises(ValueError, match="multiple"):
            TraceScopeIndexSetHandler.get_index_set(BK_TENANT_ID, BK_BIZ_ID)

    def test_sync_creates_deduplicated_multi_cluster_snapshot(
        self,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        mock_snapshot_rows(
            mocker,
            applications=[
                {"id": 1, "app_name": "exclusive", "bk_tenant_id": BK_TENANT_ID},
                {"id": 2, "app_name": "shared-a", "bk_tenant_id": BK_TENANT_ID},
                {"id": 3, "app_name": "shared-b", "bk_tenant_id": BK_TENANT_ID},
            ],
            trace_datasources=[
                {
                    "app_name": "exclusive",
                    "result_table_id": "2_bkapm.trace_exclusive",
                    "shared_datasource_id": None,
                },
                {
                    "app_name": "shared-a",
                    "result_table_id": "bkapm_shared.trace_0001",
                    "shared_datasource_id": 1,
                },
                {
                    "app_name": "shared-b",
                    "result_table_id": "bkapm_shared.trace_0001",
                    "shared_datasource_id": 1,
                },
            ],
            storages=[
                {
                    "bk_tenant_id": BK_TENANT_ID,
                    "table_id": "2_bkapm.trace_exclusive",
                    "storage_cluster_id": 11,
                },
                {
                    "bk_tenant_id": DEFAULT_TENANT_ID,
                    "table_id": "bkapm_shared.trace_0001",
                    "storage_cluster_id": 22,
                },
            ],
        )

        TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["create"].assert_called_once_with(
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=BK_BIZ_ID,
            index_set_name="bkapm_cross_trace_2",
            category_id="application_check",
            scenario_id="es",
            view_roles=[],
            storage_cluster_id=11,
            time_field="end_time",
            time_field_type="date",
            time_field_unit="microsecond",
            indexes=[
                {
                    "bk_biz_id": BK_BIZ_ID,
                    "result_table_id": "2_bkapm_trace_exclusive_*",
                    "storage_cluster_id": 11,
                },
                {
                    "bk_biz_id": GLOBAL_CONFIG_BK_BIZ_ID,
                    "result_table_id": "bkapm_shared_trace_0001_*",
                    "storage_cluster_id": 22,
                },
            ],
        )
        index_set_api_mocks["update"].assert_not_called()
        index_set_api_mocks["delete"].assert_not_called()

    def test_sync_updates_existing_index_set(
        self,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        indexes = [
            {
                "bk_biz_id": BK_BIZ_ID,
                "result_table_id": "2_bkapm_trace_demo_*",
                "storage_cluster_id": 11,
            }
        ]
        mocker.patch.object(TraceScopeIndexSetHandler, "build_indexes", return_value=indexes)
        index_set_api_mocks["search"].return_value = [{"index_set_id": 42, "index_set_name": "bkapm_cross_trace_2"}]

        TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["update"].assert_called_once()
        assert index_set_api_mocks["update"].call_args.kwargs["index_set_id"] == 42
        assert index_set_api_mocks["update"].call_args.kwargs["indexes"] == indexes
        index_set_api_mocks["create"].assert_not_called()
        index_set_api_mocks["delete"].assert_not_called()

    def test_sync_deletes_existing_index_set_when_scope_is_empty(
        self,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(TraceScopeIndexSetHandler, "build_indexes", return_value=[])
        index_set_api_mocks["search"].return_value = [{"index_set_id": 42, "index_set_name": "bkapm_cross_trace_2"}]

        TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["delete"].assert_called_once_with(
            bk_tenant_id=BK_TENANT_ID,
            index_set_id=42,
        )
        index_set_api_mocks["create"].assert_not_called()
        index_set_api_mocks["update"].assert_not_called()

    def test_sync_does_not_write_when_scope_and_index_set_are_empty(
        self,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.object(TraceScopeIndexSetHandler, "build_indexes", return_value=[])

        TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["create"].assert_not_called()
        index_set_api_mocks["update"].assert_not_called()
        index_set_api_mocks["delete"].assert_not_called()

    @pytest.mark.parametrize("missing", ["result_table", "storage"])
    def test_sync_does_not_write_incomplete_snapshot(
        self,
        missing: str,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        result_table_id = "" if missing == "result_table" else "2_bkapm.trace_demo"
        mock_snapshot_rows(
            mocker,
            applications=[{"id": 1, "app_name": "demo", "bk_tenant_id": BK_TENANT_ID}],
            trace_datasources=[
                {
                    "app_name": "demo",
                    "result_table_id": result_table_id,
                    "shared_datasource_id": None,
                }
            ],
            storages=[],
        )

        with pytest.raises(ValueError, match="result table|storage"):
            TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["search"].assert_not_called()
        index_set_api_mocks["create"].assert_not_called()
        index_set_api_mocks["update"].assert_not_called()
        index_set_api_mocks["delete"].assert_not_called()

    def test_sync_rejects_conflicting_result_table_members(
        self,
        index_set_api_mocks: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        mock_snapshot_rows(
            mocker,
            applications=[
                {"id": 1, "app_name": "exclusive", "bk_tenant_id": BK_TENANT_ID},
                {"id": 2, "app_name": "shared", "bk_tenant_id": BK_TENANT_ID},
            ],
            trace_datasources=[
                {"app_name": "exclusive", "result_table_id": "same.trace", "shared_datasource_id": None},
                {"app_name": "shared", "result_table_id": "same.trace", "shared_datasource_id": 1},
            ],
            storages=[
                {"bk_tenant_id": BK_TENANT_ID, "table_id": "same.trace", "storage_cluster_id": 11},
                {"bk_tenant_id": DEFAULT_TENANT_ID, "table_id": "same.trace", "storage_cluster_id": 22},
            ],
        )

        with pytest.raises(ValueError, match="conflicting"):
            TraceScopeIndexSetHandler.sync(BK_TENANT_ID, BK_BIZ_ID)

        index_set_api_mocks["search"].assert_not_called()
        index_set_api_mocks["create"].assert_not_called()
        index_set_api_mocks["update"].assert_not_called()
        index_set_api_mocks["delete"].assert_not_called()


class TestSyncTraceScopeIndexSet:
    def test_single_scope_task_sets_tenant_and_holds_scope_lock(self, settings, mocker: MockerFixture) -> None:
        settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST = [BK_BIZ_ID]
        resolve_tenant = mocker.patch(
            "apm.task.tasks.bk_biz_id_to_bk_tenant_id",
            return_value=BK_TENANT_ID,
        )
        set_tenant = mocker.patch("apm.task.tasks.set_local_tenant_id")
        cache_handler = mocker.patch("apm.task.tasks.ApmCacheHandler").return_value
        cache_handler.distributed_lock.return_value = nullcontext()
        sync = mocker.patch("apm.task.tasks.TraceScopeIndexSetHandler.sync")

        tasks.sync_trace_scope_index_set.run(BK_BIZ_ID)

        resolve_tenant.assert_called_once_with(BK_BIZ_ID)
        set_tenant.assert_called_once_with(BK_TENANT_ID)
        cache_handler.distributed_lock.assert_called_once_with(
            "trace_scope_index_set",
            bk_tenant_id=BK_TENANT_ID,
            bk_biz_id=BK_BIZ_ID,
        )
        sync.assert_called_once_with(BK_TENANT_ID, BK_BIZ_ID)

    def test_single_scope_task_stops_after_scope_leaves_whitelist(self, settings, mocker: MockerFixture) -> None:
        settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST = []
        resolve_tenant = mocker.patch("apm.task.tasks.bk_biz_id_to_bk_tenant_id")
        sync = mocker.patch("apm.task.tasks.TraceScopeIndexSetHandler.sync")

        tasks.sync_trace_scope_index_set.run(BK_BIZ_ID)

        resolve_tenant.assert_not_called()
        sync.assert_not_called()

    def test_batch_task_dispatches_each_whitelisted_scope(self, settings, mocker: MockerFixture) -> None:
        settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST = [2, -3]
        delay = mocker.patch("apm.task.tasks.sync_trace_scope_index_set.delay")

        tasks.sync_trace_scope_index_sets.run()

        assert delay.call_args_list == [call(2), call(-3)]

    def test_create_application_dispatches_scope_sync_after_datasource_success(
        self,
        settings,
        mocker: MockerFixture,
    ) -> None:
        settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST = [BK_BIZ_ID]
        application = MagicMock(
            id=1,
            bk_biz_id=BK_BIZ_ID,
            app_name="demo",
            create_user="admin",
        )
        mocker.patch("apm.task.tasks.ApmApplication.objects.get", return_value=application)
        mocker.patch("apm.task.tasks.EventReportHelper.report")
        mocker.patch("apm.task.tasks.ApplicationConfig.refresh_k8s")
        mocker.patch("apm.task.tasks.bmw_task_cron.apply_async")
        delay = mocker.patch("apm.task.tasks.sync_trace_scope_index_set.delay")
        storage_config: dict[str, Any] = {"es_storage_cluster": 11}
        options: dict[str, Any] = {"is_enabled_trace": True}

        tasks.create_application_async.run(application.id, storage_config, options)

        application.apply_datasource.assert_called_once_with(storage_config, storage_config, options)
        delay.assert_called_once_with(BK_BIZ_ID)

    def test_delete_application_dispatches_scope_sync_after_delete(
        self,
        settings,
        mocker: MockerFixture,
    ) -> None:
        settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST = [BK_BIZ_ID]
        application = MagicMock(bk_biz_id=BK_BIZ_ID, app_name="demo")
        mocker.patch("apm.task.tasks.ApmApplication.objects.filter").return_value.first.return_value = application
        mocker.patch("apm.task.tasks.QpsConfig.get_application_qps", return_value=-1)
        mocker.patch("apm.task.tasks.refresh_apm_application_config")
        mocker.patch("apm.task.tasks.EventReportHelper.report")
        delay = mocker.patch("apm.task.tasks.sync_trace_scope_index_set.delay")

        tasks.delete_application_async.run(BK_BIZ_ID, "demo")

        application.delete.assert_called_once_with()
        delay.assert_called_once_with(BK_BIZ_ID)


def test_distributed_lock_passes_configured_wait_time(mocker: MockerFixture) -> None:
    handler = object.__new__(ApmCacheHandler)
    handler.redis_client = MagicMock()
    lock = mocker.patch("apm.core.handlers.apm_cache_handler.ApmLock").return_value
    lock.acquire.return_value = False

    with pytest.raises(LockError):
        with handler.distributed_lock("trace_scope_index_set", ttl=60, wait_time=2.5, bk_biz_id=BK_BIZ_ID):
            pass

    lock.acquire.assert_called_once_with(2.5)
    lock.release.assert_called_once_with()
