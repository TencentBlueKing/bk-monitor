import json
import tarfile
from pathlib import Path

import pytest
import yaml
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile

from bkmonitor.as_code import parse, recording_rule
from metadata.models.record_rule.v4.models import RecordRuleV4
from metadata.tests.record_rule.test_v4_operator import external_api as _external_api, v4_base_data as _v4_base_data
from metadata.tests.record_rule.test_v4_public_api import group, public_context as _public_context
from monitor_web.as_code import resources

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context

pytestmark = pytest.mark.django_db(databases="__all__")


def import_groups(*names, app="test-app", path="cpu.yaml", incremental=False, overwrite=False):
    config = {"groups": [group(name) for name in names]}
    return parse.import_code_config(
        bk_biz_id=2,
        app=app,
        configs={f"recording_rule/{path}": json.dumps(config) if path.endswith(".json") else yaml.safe_dump(config)},
        incremental=incremental,
        overwrite=overwrite,
    )


def test_multigroup_import_applies_and_moving_file_keeps_ids(public_context):
    assert not import_groups("cpu", "disk")
    rules = {rule.name: rule for rule in RecordRuleV4.objects.all()}
    assert len(rules) == 2
    assert public_context.apply_data_link.call_count == 2
    assert all(rule.applied_resolved_id for rule in rules.values())
    assert all(rule.app == "test-app" and rule.path == "cpu.yaml" for rule in rules.values())
    assert not import_groups("cpu", "disk", path="nested/moved.yaml")
    for name, old_rule in rules.items():
        rule = RecordRuleV4.objects.get(name=name)
        assert rule.pk == old_rule.pk and rule.generation == 1
        assert rule.path == "nested/moved.yaml"
    assert public_context.apply_data_link.call_count == 4


def test_full_import_soft_deletes_only_current_scope_and_app(public_context):
    assert not import_groups("cpu", "removed")
    removed = RecordRuleV4.objects.get(name="removed")
    assert not import_groups("other", app="other-app")
    other = RecordRuleV4.objects.get(name="other")
    assert not import_groups("cpu", incremental=True)
    removed.refresh_from_db()
    assert not removed.is_deleted
    assert not import_groups("cpu")
    removed.refresh_from_db()
    other.refresh_from_db()
    assert removed.is_deleted and removed.deleted_at is not None
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


def test_missing_type_does_not_cleanup_recording_rules(public_context):
    assert not import_groups("cpu")
    assert not parse.import_code_config(2, "test-app", {}, incremental=False)
    assert not RecordRuleV4.objects.get(name="cpu").is_deleted
    public_context.delete_data_link.assert_not_called()


def test_overwrite_and_ambiguous_candidates(public_context):
    assert not import_groups("cpu", app="one")
    original_id = RecordRuleV4.objects.get().pk
    assert not import_groups("cpu", app="two", overwrite=True)
    adopted = RecordRuleV4.objects.get()
    assert adopted.pk == original_id and adopted.app == "two"
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
def test_all_recording_configs_checked_before_saving(public_context, bad_config):
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


def test_yaml_error_is_reported_by_file(public_context):
    errors = parse.import_code_config(2, "test-app", {"recording_rule/bad.yaml": "groups: [:"})
    assert "recording_rule/bad.yaml" in errors
    assert not RecordRuleV4.objects.exists()


def test_apply_failure_keeps_declaration_and_skips_cleanup(public_context):
    assert not import_groups("old")
    public_context.apply_data_link.side_effect = RuntimeError("apply failed")
    errors = import_groups("new")
    new_rule = RecordRuleV4.objects.get(name="new")
    assert str(new_rule.pk) in errors["recording_rule/cpu.yaml.groups[0]"]
    assert "apply failed" in errors["recording_rule/cpu.yaml.groups[0]"]
    assert new_rule.applied_resolved_id is None
    assert not RecordRuleV4.objects.get(name="old").is_deleted
    public_context.delete_data_link.assert_not_called()


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


def test_import_resource_reports_execution_failure(public_context, mocker):
    mocker.patch.object(resources, "send_frontend_report_event")
    public_context.apply_data_link.side_effect = RuntimeError("gateway down")
    result = resources.ImportConfigResource().request(
        bk_biz_id=2,
        incremental=True,
        configs={"recording_rule/cpu.json": json.dumps({"groups": [group()]})},
    )
    assert not result["result"]
    assert "gateway down" in result["errors"]["recording_rule/cpu.json.groups[0]"]


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
