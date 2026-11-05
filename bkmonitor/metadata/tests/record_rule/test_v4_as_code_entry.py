import json
import tarfile
from pathlib import Path

import pytest
import yaml
from celery import current_app
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase

from bkmonitor.as_code import parse, recording_rule
from config.celery.app import SchedulerCelery
from metadata import config as metadata_config
from metadata.models.record_rule.v4.models import RecordRuleV4
from metadata.task.tasks import sync_as_code_recording_rules
from metadata.tests.record_rule.test_v4_operator import external_api as _external_api, v4_base_data as _v4_base_data
from metadata.tests.record_rule.test_v4_public_api import group, public_context as _public_context
from monitor_web.as_code import resources

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture(autouse=True)
def queued_task(mocker):
    task_app = mocker.patch.object(recording_rule, "SchedulerCelery").return_value.__enter__.return_value
    return task_app.send_task


def assert_queued_rules(queued_task, rule_ids, *, once=True):
    if once:
        assert queued_task.call_count == 1
    queued_task.assert_called_with(
        sync_as_code_recording_rules.name,
        kwargs={"rule_ids": rule_ids, "operator": "alice"},
        queue="celery_metadata_task_worker",
        serializer="pickle",
        ignore_result=True,
    )


def import_groups(*names, app="test-app", path="cpu.yaml", incremental=False, overwrite=False):
    config = {"groups": [group(name) for name in names]}
    with TestCase.captureOnCommitCallbacks(using=metadata_config.DATABASE_CONNECTION_NAME, execute=True):
        return parse.import_code_config(
            bk_biz_id=2,
            app=app,
            configs={
                f"recording_rule/{path}": json.dumps(config) if path.endswith(".json") else yaml.safe_dump(config)
            },
            incremental=incremental,
            overwrite=overwrite,
        )


def test_multigroup_import_queues_once_and_moving_file_keeps_ids(public_context, queued_task):
    assert not import_groups("cpu", "disk")
    rules = {rule.name: rule for rule in RecordRuleV4.objects.all()}
    assert len(rules) == 2
    public_context.check_promql.assert_not_called()
    public_context.check_query_ts.assert_not_called()
    public_context.apply_data_link.assert_not_called()
    public_context.space_redis._push_space_table_ids.assert_not_called()
    assert all(rule.applied_resolved_id is None for rule in rules.values())
    assert_queued_rules(queued_task, [rules["cpu"].pk, rules["disk"].pk])
    assert all(rule.app == "test-app" and rule.path == "cpu.yaml" for rule in rules.values())
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    assert public_context.apply_data_link.call_count == 2
    assert all(rule.applied_resolved_id for rule in RecordRuleV4.objects.all())
    queued_task.reset_mock()
    assert not import_groups("cpu", "disk")
    assert not import_groups("cpu", "disk", path="nested/moved.yaml")
    for name, old_rule in rules.items():
        rule = RecordRuleV4.objects.get(name=name)
        assert rule.pk == old_rule.pk and rule.generation == 1
        assert rule.path == "nested/moved.yaml"
    queued_task.assert_not_called()
    assert public_context.apply_data_link.call_count == 2


def test_full_import_soft_deletes_only_current_scope_and_app(public_context, queued_task):
    assert not import_groups("cpu", "removed")
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    removed = RecordRuleV4.objects.get(name="removed")
    assert not import_groups("other", app="other-app")
    other = RecordRuleV4.objects.get(name="other")
    assert not import_groups("cpu", incremental=True)
    removed.refresh_from_db()
    assert not removed.is_deleted
    assert not import_groups("cpu")
    removed.refresh_from_db()
    other.refresh_from_db()
    assert removed.is_deleted and removed.desired_status == "deleted" and removed.deleted_at is None
    public_context.delete_data_link.assert_not_called()
    assert_queued_rules(queued_task, [removed.pk], once=False)
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    removed.refresh_from_db()
    assert removed.deleted_at is not None
    assert removed.specs.exists() and removed.resolved.exists()
    assert not other.is_deleted
    public_context.delete_data_link.assert_called_once()
    assert not import_groups("removed", incremental=True)
    replacement = RecordRuleV4.objects.get(name="removed", is_deleted=False)
    assert replacement.pk != removed.pk


@pytest.mark.parametrize("overwrite", [False, True])
def test_import_rejects_candidate_deleted_after_prepare(public_context, overwrite):
    assert not import_groups("cpu")
    rule = RecordRuleV4.objects.get()
    original_path = rule.path
    app = "new-app" if overwrite else "test-app"
    value = group()
    value["bkmonitor"]["auto_refresh"] = True
    space, records, errors = recording_rule.prepare_import(
        2, app, {"moved.yaml": {"groups": [value]}}, overwrite=overwrite
    )
    assert not errors and records[0]["rule"].pk == rule.pk
    assert recording_rule.soft_delete_rule(rule)["succeeded"]
    public_context.apply_data_link.reset_mock()

    errors = recording_rule.import_recording_rules(space, app, records, incremental=False)
    assert "RecordingRule 不存在" in errors["recording_rule/moved.yaml.groups[0]"]
    rule.refresh_from_db()
    assert rule.is_deleted and rule.desired_status == "deleted" and rule.deleted_at is not None
    assert rule.app == "test-app" and rule.path == original_path
    assert rule.specs.count() == 1
    public_context.apply_data_link.assert_not_called()


def test_missing_type_does_not_cleanup_recording_rules(public_context, queued_task):
    assert not import_groups("cpu")
    queued_task.reset_mock()
    assert not parse.import_code_config(2, "test-app", {}, incremental=False)
    assert not RecordRuleV4.objects.get(name="cpu").is_deleted
    public_context.delete_data_link.assert_not_called()
    queued_task.assert_not_called()


def test_overwrite_and_ambiguous_candidates(public_context, queued_task):
    assert not import_groups("cpu", app="one")
    original_id = RecordRuleV4.objects.get().pk
    queued_task.reset_mock()
    assert not import_groups("cpu", app="two", overwrite=True)
    adopted = RecordRuleV4.objects.get()
    assert adopted.pk == original_id and adopted.app == "two"
    queued_task.assert_not_called()
    assert not import_groups("cpu", app="three")
    assert RecordRuleV4.objects.count() == 2
    errors = import_groups("cpu", app="four", overwrite=True)
    assert "多个同名" in errors["recording_rule/cpu.yaml.groups[0]"]
    assert set(RecordRuleV4.objects.values_list("app", flat=True)) == {"two", "three"}


@pytest.mark.parametrize(
    "bad_config",
    [
        {"groups": [group("bad"), group("bad")]},
        {"groups": [{"name": "bad", "rules": []}]},
        {"groups": [dict(group("bad"), space_uid="bkcc__3")]},
    ],
)
def test_all_recording_configs_checked_before_saving(public_context, queued_task, bad_config):
    errors = parse.import_code_config(
        2,
        "test-app",
        {
            "recording_rule/good.yaml": yaml.safe_dump({"groups": [group("good")]}),
            "recording_rule/bad.yaml": yaml.safe_dump(bad_config),
        },
    )
    assert errors and any(key.startswith("recording_rule/bad.yaml") for key in errors)
    assert not RecordRuleV4.objects.exists()
    public_context.apply_data_link.assert_not_called()
    queued_task.assert_not_called()


def test_yaml_error_is_reported_by_file(public_context, queued_task):
    errors = parse.import_code_config(2, "test-app", {"recording_rule/bad.yaml": "groups: [:"})
    assert "recording_rule/bad.yaml" in errors
    assert not RecordRuleV4.objects.exists()
    queued_task.assert_not_called()


def test_async_apply_failure_keeps_declaration_and_does_not_block_cleanup(public_context, queued_task):
    assert not import_groups("old")
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    public_context.apply_data_link.side_effect = RuntimeError("apply failed")
    assert not import_groups("new")
    new_rule = RecordRuleV4.objects.get(name="new")
    old_rule = RecordRuleV4.objects.get(name="old")
    assert old_rule.is_deleted and old_rule.deleted_at is None
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    new_rule.refresh_from_db()
    old_rule.refresh_from_db()
    assert new_rule.applied_resolved_id is None
    assert new_rule.status == "failed"
    assert new_rule.events.filter(message__contains="apply failed", source="as_code", operator="alice").exists()
    assert old_rule.deleted_at is not None
    public_context.delete_data_link.assert_called_once()
    queued_task.reset_mock()
    assert not import_groups("new")
    queued_task.assert_not_called()


def test_import_export_enforce_tenant_and_space(public_context):
    assert not import_groups("cpu")
    rule = RecordRuleV4.objects.get()
    RecordRuleV4.objects.filter(pk=rule.pk).update(bk_tenant_id="other-tenant")
    assert not import_groups("cpu", overwrite=True)
    assert RecordRuleV4.objects.count() == 2
    rule.refresh_from_db()
    assert not rule.is_deleted
    exported = list(recording_rule.export_recording_rules(2, recording_rule_ids=[rule.pk]))
    assert exported == []
    own = RecordRuleV4.objects.exclude(pk=rule.pk).get()
    RecordRuleV4.objects.filter(pk=own.pk).update(space_id="3")
    assert list(recording_rule.export_recording_rules(2)) == []
    assert not import_groups("cpu", overwrite=True)
    own.refresh_from_db()
    assert not own.is_deleted


def test_export_preserves_groups_and_roundtrip(public_context):
    assert not import_groups("cpu", "disk", path="nested/cpu.json")
    # 导出必须由 .json 转成 YAML，并把同一文件中的多个 group 一并返回。
    exported = list(recording_rule.export_recording_rules(2, app="test-app"))
    assert len(exported) == 1 and exported[0][:2] == ("nested", "cpu.yaml")
    assert len(yaml.safe_load(exported[0][2])["groups"]) == 2
    ids = set(RecordRuleV4.objects.values_list("id", flat=True))
    assert not parse.import_code_config(2, "test-app", {"recording_rule/nested/cpu.yaml": exported[0][2]})
    assert set(RecordRuleV4.objects.values_list("id", flat=True)) == ids
    selected = list(recording_rule.export_recording_rules(2, recording_rule_ids=[min(ids)], lock_filename=True))
    assert len(selected) == 1
    assert selected[0][1].startswith(RecordRuleV4.objects.get(pk=min(ids)).table_id.split(".")[0])
    assert list(recording_rule.export_recording_rules(2, recording_rule_ids=[])) == []
    RecordRuleV4.objects.filter(id=min(ids)).update(is_deleted=True)
    exported = list(recording_rule.export_recording_rules(2))
    assert len(yaml.safe_load(exported[0][2])["groups"]) == 1


def test_json_yaml_filename_collision_keeps_both_groups(public_context):
    assert not import_groups("cpu", path="metrics.json", incremental=True)
    assert not import_groups("disk", path="metrics.yaml", incremental=True)
    exported = list(recording_rule.export_recording_rules(2))
    assert len(exported) == 1
    assert {entry["name"] for entry in yaml.safe_load(exported[0][2])["groups"]} == {"cpu", "disk"}


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_import_resource_reports_enqueue_failure(public_context, queued_task, mocker):
    mocker.patch.object(resources, "send_frontend_report_event")
    queued_task.side_effect = RuntimeError("broker unavailable")
    result = resources.ImportConfigResource().request(
        bk_biz_id=2,
        incremental=True,
        configs={"recording_rule/cpu.json": json.dumps({"groups": [group()]})},
    )
    assert not result["result"]
    assert "broker unavailable" in result["errors"]["recording_rule"]
    assert "已保存" in result["errors"]["recording_rule"]
    assert RecordRuleV4.objects.get().applied_resolved_id is None
    public_context.apply_data_link.assert_not_called()


def test_import_resource_success_does_not_wait_for_execution(public_context, queued_task, mocker):
    mocker.patch.object(resources, "send_frontend_report_event")
    public_context.apply_data_link.side_effect = RuntimeError("gateway down")
    with TestCase.captureOnCommitCallbacks(using=metadata_config.DATABASE_CONNECTION_NAME, execute=True):
        result = resources.ImportConfigResource().request(
            bk_biz_id=2,
            incremental=True,
            configs={"recording_rule/cpu.json": json.dumps({"groups": [group()]})},
        )
    assert result["result"] and not result["errors"]
    public_context.apply_data_link.assert_not_called()
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    assert RecordRuleV4.objects.get().status == "failed"
    assert result["result"]


@pytest.mark.parametrize(
    "change",
    [
        {"interval": "5min"},
        {"labels": {"env": "prod"}},
        {"bkmonitor": {"description": "changed"}},
        {"bkmonitor": {"data_label": "cpu_summary"}},
        {"bkmonitor": {"desired_status": "stopped"}},
        {"bkmonitor": {"auto_refresh": True}},
        {"rules": [{"record": "cpu_avg", "expr": "sum(system_cpu_usage)"}]},
        {
            "rules": [
                {
                    "record": "cpu_avg",
                    "query": {
                        "data_source": "bk_monitor",
                        "data_type": "time_series",
                        "query_configs": [{"metric": "system.cpu.usage", "method": "avg", "interval": 60}],
                    },
                }
            ]
        },
    ],
)
def test_changed_declaration_is_queued(public_context, queued_task, change):
    assert not import_groups("cpu")
    rule = RecordRuleV4.objects.get()
    queued_task.reset_mock()
    value = group()
    for field, content in change.items():
        if isinstance(content, dict):
            value[field].update(content)
        else:
            value[field] = content
    with TestCase.captureOnCommitCallbacks(using=metadata_config.DATABASE_CONNECTION_NAME, execute=True):
        assert not parse.import_code_config(
            2, "test-app", {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [value]})}
        )
    assert_queued_rules(queued_task, [rule.pk])
    public_context.check_promql.assert_not_called()
    public_context.check_query_ts.assert_not_called()
    public_context.apply_data_link.assert_not_called()


def test_partial_save_failure_queues_saved_changes_and_skips_cleanup(public_context, queued_task, mocker):
    assert not import_groups("old")
    old_rule = RecordRuleV4.objects.get()
    queued_task.reset_mock()
    save = recording_rule.save_declaration

    def save_or_fail(space, declaration, **kwargs):
        if declaration["name"] == "bad":
            raise RuntimeError("save failed")
        return save(space, declaration, **kwargs)

    mocker.patch.object(recording_rule, "save_declaration", side_effect=save_or_fail)
    errors = import_groups("good", "bad")
    assert "save failed" in errors["recording_rule/cpu.yaml.groups[1]"]
    good_rule = RecordRuleV4.objects.get(name="good")
    assert_queued_rules(queued_task, [good_rule.pk])
    old_rule.refresh_from_db()
    assert not old_rule.is_deleted


def test_task_is_deferred_until_metadata_commit(public_context, queued_task):
    with TestCase.captureOnCommitCallbacks(using=metadata_config.DATABASE_CONNECTION_NAME, execute=True) as callbacks:
        with transaction.atomic(using=metadata_config.DATABASE_CONNECTION_NAME):
            assert not parse.import_code_config(
                2, "test-app", {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [group()]})}
            )
            queued_task.assert_not_called()
        queued_task.assert_not_called()
    assert len(callbacks) == 1
    assert_queued_rules(queued_task, [RecordRuleV4.objects.get().pk])


def test_enqueue_uses_backend_client_without_switching_current_app(public_context, settings, mocker):
    settings.APP_CODE = "saas"
    settings.BACKEND_APP_CODE = "backend"
    previous_app = current_app._get_current_object()
    mocker.patch.object(recording_rule, "SchedulerCelery", SchedulerCelery)
    constructor = mocker.spy(recording_rule, "SchedulerCelery")
    send_task = mocker.patch.object(SchedulerCelery, "send_task")
    rabbitmq = mocker.patch.object(
        recording_rule, "get_rabbitmq_settings", return_value=("localhost", 5672, "backend", "worker", "p@ss", "")
    )
    assert not import_groups("cpu")
    rabbitmq.assert_called_once_with("backend", backend=True)
    assert constructor.spy_return.conf.broker_url == "amqp://worker:p%40ss@localhost:5672/backend"
    assert_queued_rules(send_task, [RecordRuleV4.objects.get().pk])
    assert current_app._get_current_object() is previous_app


def test_rollback_does_not_enqueue_task(public_context, queued_task):
    with TestCase.captureOnCommitCallbacks(using=metadata_config.DATABASE_CONNECTION_NAME, execute=True) as callbacks:
        with pytest.raises(RuntimeError, match="rollback"):
            with transaction.atomic(using=metadata_config.DATABASE_CONNECTION_NAME):
                assert not parse.import_code_config(
                    2, "test-app", {"recording_rule/cpu.yaml": yaml.safe_dump({"groups": [group()]})}
                )
                raise RuntimeError("rollback")
    assert not callbacks
    assert not RecordRuleV4.objects.exists()
    queued_task.assert_not_called()


def test_async_parse_failure_continues_with_other_rules(public_context, queued_task):
    assert not import_groups("bad", "good")
    public_context.check_promql.side_effect = [RuntimeError("parse failed"), public_context.check_promql.return_value]
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    failed = RecordRuleV4.objects.get(name="bad")
    succeeded = RecordRuleV4.objects.get(name="good")
    assert failed.status == "failed" and failed.applied_resolved_id is None
    assert failed.events.filter(message__contains="parse failed", source="as_code", operator="alice").exists()
    assert succeeded.applied_resolved_id is not None
    public_context.apply_data_link.assert_called_once()


def test_async_apply_failure_continues_with_other_rules(public_context, queued_task):
    assert not import_groups("bad", "good")
    public_context.apply_data_link.side_effect = [RuntimeError("apply failed"), {}]
    sync_as_code_recording_rules(**queued_task.call_args.kwargs["kwargs"])
    assert RecordRuleV4.objects.get(name="bad").status == "failed"
    assert RecordRuleV4.objects.get(name="good").applied_resolved_id is not None
    assert public_context.apply_data_link.call_count == 2


def test_task_executes_latest_declaration_with_submitting_user(public_context, queued_task):
    assert not import_groups("cpu")
    pending = queued_task.call_args.kwargs["kwargs"]
    value = group()
    value["rules"][0]["expr"] = "sum(system_cpu_usage)"
    recording_rule.save_declaration(
        recording_rule.get_space(2), recording_rule.parse_group_config(value), rule=RecordRuleV4.objects.get()
    )
    sync_as_code_recording_rules(**pending)
    assert public_context.check_promql.call_args.kwargs["promql"] == "sum(system_cpu_usage)"
    rule = RecordRuleV4.objects.get()
    assert rule.applied_resolved.spec_id == rule.current_spec_id
    assert rule.events.filter(event_type="apply.succeeded", source="as_code", operator="alice").exists()


def test_json_and_archive_export_import(public_context, mocker, tmp_path, settings):
    mocker.patch.object(resources, "send_frontend_report_event")
    storage = FileSystemStorage(location=str(tmp_path), base_url="/media/")
    mocker.patch.object(resources, "default_storage", storage)
    # AsCodeImportTask.file 的存储也使用测试目录。
    mocker.patch.object(resources.AsCodeImportTask._meta.get_field("file"), "storage", storage)
    settings.BK_MONITOR_HOST = "http://localhost"
    assert not import_groups("cpu", "disk")
    selected = RecordRuleV4.objects.get(name="cpu")
    result = resources.ExportConfigResource().request(
        bk_biz_id=2,
        recording_rule_ids=[selected.pk],
        rule_ids=[],
        notice_group_ids=[],
        action_ids=[],
        assign_group_ids=[],
        dashboard_uids=[],
    )
    assert len(yaml.safe_load(result["recording_rule"]["cpu.yaml"])["groups"]) == 1

    resources.ExportConfigFileResource().request(bk_biz_id=2, recording_rule_ids=[selected.pk], app="test-app")
    archive_path = next(Path(tmp_path).glob("as_code/export/*.tar.gz"))
    with tarfile.open(archive_path) as archive:
        files = [entry for entry in archive.getmembers() if entry.isfile()]
        assert [entry.name for entry in files] == ["configs/recording_rule/cpu.yaml"]
    result = resources.ImportConfigFileResource().request(
        bk_biz_id=2,
        app="test-app",
        incremental=True,
        file=SimpleUploadedFile("configs.tar.gz", archive_path.read_bytes()),
    )
    assert result["result"]
    assert RecordRuleV4.objects.filter(is_deleted=False).count() == 2


@pytest.mark.parametrize("source_path", ["a/b/cpu.yaml", "a/b/cpu.json"])
def test_archive_merges_normalized_folders_and_restores_all_groups(
    public_context, mocker, tmp_path, settings, source_path
):
    mocker.patch.object(resources, "send_frontend_report_event")
    storage = FileSystemStorage(location=str(tmp_path), base_url="/media/")
    mocker.patch.object(resources, "default_storage", storage)
    mocker.patch.object(resources.AsCodeImportTask._meta.get_field("file"), "storage", storage)
    settings.BK_MONITOR_HOST = "http://localhost"
    assert not import_groups("cpu", path=source_path)
    assert not import_groups("disk", path="a-b/cpu.yaml", incremental=True)
    ids = list(RecordRuleV4.objects.values_list("id", flat=True))

    exported = resources.ExportConfigResource().request(
        bk_biz_id=2,
        recording_rule_ids=ids,
        rule_ids=[],
        notice_group_ids=[],
        action_ids=[],
        assign_group_ids=[],
        dashboard_uids=[],
    )["recording_rule"]
    assert set(exported) == {"a/b|cpu.yaml", "a-b|cpu.yaml"}
    expected = {group["name"]: group for content in exported.values() for group in yaml.safe_load(content)["groups"]}
    resources.ExportConfigFileResource().request(bk_biz_id=2, recording_rule_ids=ids, app="test-app")
    archive_path = next(Path(tmp_path).glob("as_code/export/*.tar.gz"))
    with tarfile.open(archive_path) as archive:
        files = [entry for entry in archive.getmembers() if entry.isfile()]
        assert [entry.name for entry in files] == ["configs/recording_rule/a-b/cpu.yaml"]
        groups = yaml.safe_load(archive.extractfile(files[0]).read())["groups"]
    assert {group["name"]: group for group in groups} == expected

    result = resources.ImportConfigFileResource().request(
        bk_biz_id=2,
        app="restored-app",
        incremental=True,
        file=SimpleUploadedFile("configs.tar.gz", archive_path.read_bytes()),
    )
    assert result["result"]
    restored = RecordRuleV4.objects.filter(app="restored-app", is_deleted=False)
    assert set(restored.values_list("name", flat=True)) == {"cpu", "disk"}
    assert {rule.name: recording_rule.dump_rule(rule) for rule in restored} == expected
