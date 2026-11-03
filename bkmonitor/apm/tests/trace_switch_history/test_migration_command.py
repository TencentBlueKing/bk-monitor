from dataclasses import replace
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import CommandError

from apm.management.commands.migrate_apm_trace_datasource import Command, TraceDataSourceMigrationContext
from apm.models import TraceDataSource, SharedTraceDataSource
from apm.tests.trace_switch_history import EXCLUSIVE_RT, SHARED_RT

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def second_pool():
    return SharedTraceDataSource.objects.create(
        bk_data_id=202,
        result_table_id="apm_global.shared_trace_0002",
        is_enabled=True,
        usage_count=0,
        quota=2,
        index_set_id=22,
        index_set_name="second-index",
    )


def test_shared_pool_switch_preserves_exclusive_backup_and_history(
    exclusive, shared_pool, second_pool, datasource_apis, migration_command, migration_context
):
    for pool in (shared_pool, second_pool, shared_pool):
        migration_command.migrate_to_shared(migration_context, pool.pk)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    second_pool.refresh_from_db()
    assert exclusive.shared_datasource_id == shared_pool.pk
    assert exclusive.backup_link_info["result_table_id"] == EXCLUSIVE_RT
    assert [link["table_id"] for link in exclusive.history_link_info] == [
        EXCLUSIVE_RT,
        SHARED_RT,
        second_pool.result_table_id,
    ]
    assert (shared_pool.usage_count, second_pool.usage_count) == (1, 0)
    migration_command.migrate_to_shared(migration_context, shared_pool.pk)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert len(exclusive.history_link_info) == 3
    assert shared_pool.usage_count == 1
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    exclusive.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.index_set_id == 11


@pytest.mark.parametrize("unavailable", ["disabled", "full", "missing", "race", "save_failure"])
def test_explicit_pool_failure_does_not_fallback_or_release_source(
    exclusive, shared_pool, second_pool, datasource_apis, mocker, unavailable, migration_command, migration_context
):
    migration_command.migrate_to_shared(migration_context, shared_pool.pk)
    exclusive.refresh_from_db()
    history = exclusive.history_link_info
    target_id = second_pool.pk
    if unavailable == "disabled":
        second_pool.is_enabled = False
        second_pool.save()
    elif unavailable == "full":
        second_pool.usage_count = second_pool.quota
        second_pool.save()
    elif unavailable == "missing":
        target_id += 100
    elif unavailable == "race":
        mocker.patch.object(SharedTraceDataSource, "acquire", return_value=False)
    else:
        mocker.patch.object(TraceDataSource, "save", side_effect=RuntimeError("save failed"))
    with pytest.raises((CommandError, RuntimeError)):
        migration_command.migrate_to_shared(migration_context, target_id)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    second_pool.refresh_from_db()
    assert exclusive.shared_datasource_id == shared_pool.pk
    assert exclusive.history_link_info == history
    assert shared_pool.usage_count == 1
    assert second_pool.usage_count == (second_pool.quota if unavailable == "full" else 0)
    assert SharedTraceDataSource.objects.count() == 2
    datasource_apis["create_rt"].assert_not_called()


@pytest.fixture
def migration_command():
    return Command(stdout=StringIO())


@pytest.fixture
def migration_context(exclusive):
    return TraceDataSourceMigrationContext(2, "demo", SimpleNamespace(id=1, is_enabled_trace=True), exclusive)


def test_batch_plan_balances_only_requested_pools(migration_command, migration_context, shared_pool, second_pool):
    shared_pool.quota = 1
    shared_pool.save()
    contexts = [replace(migration_context, app_name=f"app-{i}") for i in range(3)]
    assert migration_command.plan_shared_targets(contexts, [second_pool.pk, shared_pool.pk]) == [
        shared_pool.pk,
        second_pool.pk,
        second_pool.pk,
    ]
    # 预览不占用池配额。
    shared_pool.refresh_from_db()
    second_pool.refresh_from_db()
    assert (shared_pool.usage_count, second_pool.usage_count) == (0, 0)


def test_batch_keeps_apps_already_in_target_pool(migration_command, migration_context, shared_pool):
    migration_context.trace_datasource.shared_datasource_id = shared_pool.pk
    shared_pool.usage_count = shared_pool.quota
    shared_pool.save()
    assert migration_command.plan_shared_targets([migration_context], [shared_pool.pk]) == [shared_pool.pk]


@pytest.mark.parametrize("invalid", ["full", "disabled", "missing_index", "missing"])
def test_batch_preflight_rejects_unavailable_capacity(
    migration_command,
    migration_context,
    shared_pool,
    mocker,
    invalid,
):
    pool_id = shared_pool.pk
    if invalid == "full":
        shared_pool.usage_count = shared_pool.quota
    elif invalid == "disabled":
        shared_pool.is_enabled = False
    elif invalid == "missing_index":
        shared_pool.index_set_id = None
    else:
        pool_id += 100
    shared_pool.save()
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_batch")
    with pytest.raises(CommandError):
        migration_command.handle(target="shared", apps=["2:demo"], dry_run=False, shared_datasource_ids=[pool_id])
    migrate.assert_not_called()


def test_batch_dry_run_shows_target_without_mutation(migration_command, migration_context, shared_pool, mocker):
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_batch")
    migration_command.handle(target="shared", apps=["2:demo"], dry_run=True, shared_datasource_ids=[shared_pool.pk])
    assert f"target_shared_datasource_id：{shared_pool.pk}" in migration_command.stdout.getvalue()
    migrate.assert_not_called()


@pytest.fixture
def mixed_contexts(migration_context, shared_pool):
    shared = TraceDataSource.objects.create(bk_biz_id=2, app_name="shared")
    shared.set_from_shared({**shared_pool.to_shared_info(), "shared_datasource_id": shared_pool.pk})
    shared.save()
    shared_pool.usage_count = 1
    shared_pool.save()
    return [
        migration_context,
        replace(
            migration_context,
            app_name="shared",
            application=SimpleNamespace(id=2, is_enabled_trace=True),
            trace_datasource=shared,
        ),
    ]


def test_batch_migrates_mixed_apps_and_refreshes_once(
    migration_command, mixed_contexts, shared_pool, second_pool, datasource_apis, mocker
):
    module = "apm.management.commands.migrate_apm_trace_datasource"
    mocker.patch.object(migration_command, "get_migration_context", side_effect=mixed_contexts)
    request = mocker.patch(f"{module}.ApplyDatasourceResource.request")
    apply = mocker.patch.object(TraceDataSource, "apply_datasource")
    refresh = mocker.patch(f"{module}.ApplicationConfig")
    migration_command.handle(
        target="shared", apps=["2:demo", "2:shared"], dry_run=False, shared_datasource_ids=[second_pool.pk]
    )
    request.assert_not_called()
    apply.assert_not_called()
    refresh.assert_not_called()
    refresh.refresh_k8s.assert_called_once_with([c.application for c in mixed_contexts])
    exclusive, shared = [c.trace_datasource for c in mixed_contexts]
    for datasource in (exclusive, shared, shared_pool, second_pool):
        datasource.refresh_from_db()
    assert exclusive.result_table_id == shared.result_table_id == second_pool.result_table_id
    assert [link["table_id"] for link in exclusive.history_link_info] == [EXCLUSIVE_RT]
    assert exclusive.backup_link_info["result_table_id"] == EXCLUSIVE_RT
    assert [link["table_id"] for link in shared.history_link_info] == [shared_pool.result_table_id]
    assert shared.backup_link_info == {}
    assert (shared_pool.usage_count, second_pool.usage_count) == (0, 2)
    for api_name in ("modify", "delete_index", "create_rt"):
        datasource_apis[api_name].assert_not_called()


def test_batch_continues_after_failure_and_refreshes_successes(
    migration_command, mixed_contexts, shared_pool, second_pool, datasource_apis, mocker
):
    original_save = TraceDataSource.save

    def save(instance, *args, **kwargs):
        if instance.app_name == "demo":
            raise RuntimeError("save failed")
        return original_save(instance, *args, **kwargs)

    mocker.patch.object(TraceDataSource, "save", autospec=True, side_effect=save)
    refresh = mocker.patch("apm.management.commands.migrate_apm_trace_datasource.ApplicationConfig.refresh_k8s")
    with pytest.raises(CommandError, match="部分应用迁移失败"):
        migration_command.migrate_batch(mixed_contexts, [second_pool.pk, second_pool.pk])
    refresh.assert_called_once_with([mixed_contexts[1].application])
    exclusive, shared = [c.trace_datasource for c in mixed_contexts]
    for datasource in (exclusive, shared, shared_pool, second_pool):
        datasource.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.history_link_info == []
    assert exclusive.backup_link_info == {}
    assert shared.shared_datasource_id == second_pool.pk
    assert (shared_pool.usage_count, second_pool.usage_count) == (0, 1)


def test_batch_retry_refreshes_without_repeating_migration(
    migration_command, migration_context, shared_pool, datasource_apis, mocker
):
    refresh = mocker.patch("apm.management.commands.migrate_apm_trace_datasource.ApplicationConfig.refresh_k8s")
    refresh.side_effect = RuntimeError("delivery failed")
    with pytest.raises(RuntimeError, match="delivery failed"):
        migration_command.migrate_batch([migration_context], [shared_pool.pk])
    refresh.side_effect = None
    migration_command.migrate_batch([migration_context], [shared_pool.pk])
    migration_context.trace_datasource.refresh_from_db()
    shared_pool.refresh_from_db()
    assert len(migration_context.trace_datasource.history_link_info) == 1
    assert shared_pool.usage_count == 1
    assert refresh.call_count == 2


@pytest.mark.parametrize("missing", ["datasource", "rt", "data_id"])
def test_batch_rejects_uncreated_source_before_migration(
    migration_command, migration_context, shared_pool, mocker, missing
):
    datasource = migration_context.trace_datasource
    if missing == "datasource":
        migration_context = replace(migration_context, trace_datasource=None)
    elif missing == "rt":
        datasource.result_table_id = ""
    else:
        datasource.bk_data_id = -1
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_batch")
    with pytest.raises(CommandError, match="仅支持已有"):
        migration_command.handle(
            target="shared", apps=["2:demo"], dry_run=False, shared_datasource_ids=[shared_pool.pk]
        )
    migrate.assert_not_called()


def test_shared_target_is_invalid_for_exclusive_mode(migration_command, migration_context, shared_pool, mocker):
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    with pytest.raises(CommandError, match="仅适用于"):
        migration_command.handle(
            target="exclusive", apps=["2:demo"], dry_run=False, shared_datasource_ids=[shared_pool.pk]
        )


def test_batch_rejects_disabled_trace_before_changing_counts(migration_command, migration_context, shared_pool, mocker):
    migration_context.application.is_enabled_trace = False
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_batch")
    with pytest.raises(CommandError, match="请先启用"):
        migration_command.handle(
            target="shared", apps=["2:demo"], dry_run=False, shared_datasource_ids=[shared_pool.pk]
        )
    migrate.assert_not_called()
    shared_pool.refresh_from_db()
    assert shared_pool.usage_count == 0


def test_batch_all_failed_does_not_refresh_config(migration_command, migration_context, shared_pool, mocker):
    mocker.patch.object(migration_command, "migrate_to_shared", side_effect=RuntimeError("failed"))
    refresh = mocker.patch("apm.management.commands.migrate_apm_trace_datasource.ApplicationConfig.refresh_k8s")
    with pytest.raises(CommandError, match="部分应用迁移失败"):
        migration_command.migrate_batch([migration_context], [shared_pool.pk])
    refresh.assert_not_called()


def test_automatic_migration_keeps_existing_resource_flow(migration_command, migration_context, mocker):
    module = "apm.management.commands.migrate_apm_trace_datasource"
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    mocker.patch(f"{module}.ApplicationHelper.get_default_storage_config", return_value={"es_storage_cluster": 1})
    request = mocker.patch(f"{module}.ApplyDatasourceResource.request")
    refresh = mocker.patch(f"{module}.ApplicationConfig")
    migration_command.handle(target="shared", apps=["2:demo"], dry_run=False)
    request.assert_called_once_with(
        {
            "application_id": 1,
            "trace_datasource_option": {"es_storage_cluster": 1},
            "shared_datasource_types": ["trace"],
        }
    )
    refresh.return_value.refresh.assert_called_once()
    refresh.refresh_k8s.assert_called_once_with([migration_context.application])


def test_command_parser_keeps_target_pools_and_deduplicates_apps(migration_command):
    parser = migration_command.create_parser("manage.py", "migrate_apm_trace_datasource")
    args = parser.parse_args(
        ["--target", "shared", "--apps", "2:a", "2:b", "2:a", "--shared-datasource-ids", "1", "2", "--dry-run"]
    )
    assert args.shared_datasource_ids == [1, 2]
    assert migration_command.parse_apps(args.apps) == [(2, "a"), (2, "b")]
    assert args.dry_run
