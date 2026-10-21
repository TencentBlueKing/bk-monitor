from importlib import import_module
from pathlib import Path

import pytest
import yaml
from django.apps import apps
from django.db import connections
from django.db import models as django_models
from django.db.migrations.state import ModelState, ProjectState
from django.test.utils import CaptureQueriesContext
from django.urls import include, path, resolve
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from bkmonitor.as_code import recording_rule
from core.drf_resource.exceptions import CustomException
from core.drf_resource.routers import ResourceRouter
from kernel_api.resource import recording_rule as api
from kernel_api.rpc.functions.admin import record_rule_v4 as admin
from metadata import config, models
from metadata.models.record_rule.v4.models import RecordRuleV4
from metadata.task.record_rule_v4 import refresh_record_rule_v4
from metadata.tests.record_rule.test_v4_operator import (
    SOURCE_VM_TABLE_ID,
    TENANT_ID,
    build_check_result,
    external_api as _external_api,
    v4_base_data as _v4_base_data,
)

external_api = _external_api
v4_base_data = _v4_base_data

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def public_context(v4_base_data, external_api, mocker):
    mocker.patch.object(recording_rule, "get_request_tenant_id", return_value=TENANT_ID)
    mocker.patch.object(recording_rule, "get_request_username", return_value="alice")
    return external_api


def group(name="cpu"):
    return {
        "name": name,
        "interval": "1min",
        "labels": {"env": "test"},
        "bkmonitor": {"auto_refresh": False},
        "rules": [{"record": "cpu_avg", "expr": "avg(system_cpu_usage)", "labels": {"env": "prod"}}],
    }


def call(resource, **params):
    return resource().request(bk_biz_id=2, **params)


@pytest.mark.parametrize("as_yaml", [False, True])
def test_preview_is_read_only(public_context, as_yaml):
    value = group()
    if as_yaml:
        value = yaml.safe_dump(value)
    with CaptureQueriesContext(connections[config.DATABASE_CONNECTION_NAME]) as queries:
        result = call(api.PreviewConfigResource, config=value)
    assert result["records"][0]["metricql"] == "promql_metricql"
    assert result["records"][0]["src_vm_table_ids"] == [SOURCE_VM_TABLE_ID]
    assert result["records"][0]["labels"] == [{"env": "prod"}]
    assert all(not q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries)
    assert not RecordRuleV4.objects.exists()
    public_context.check_promql.assert_called_once()
    public_context.apply_data_link.assert_not_called()
    public_context.space_redis._push_space_table_ids.assert_not_called()


def test_preview_structured_query(public_context):
    value = group()
    value["rules"] = [
        {
            "record": "cpu_avg",
            "query": {
                "data_source": "bk_monitor",
                "data_type": "time_series",
                "query_configs": [{"metric": "system.cpu.usage", "method": "avg", "interval": 60, "alias": "a"}],
            },
        }
    ]
    result = call(api.PreviewConfigResource, config=value)
    assert result["records"][0]["src_result_table_configs"][0]["vm_result_table_id"] == SOURCE_VM_TABLE_ID
    public_context.check_query_ts.assert_called_once()
    public_context.apply_data_link.assert_not_called()
    assert not RecordRuleV4.objects.exists()


def test_preview_failure_and_edit_self_reference(public_context):
    created = call(api.CreateConfigResource, config=group(), apply=True)
    rule_id = created["rule"]["id"]
    public_context.check_promql.return_value = build_check_result(
        result_table_id=[SOURCE_VM_TABLE_ID, created["rule"]["dst_vm_table_id"]]
    )
    result = call(api.PreviewConfigResource, config=group(), id=rule_id)
    assert result["records"][0]["src_vm_table_ids"] == [SOURCE_VM_TABLE_ID]
    public_context.check_promql.side_effect = RuntimeError("query unavailable")
    with pytest.raises(ValidationError, match=r"config.rules\[0\].*query unavailable"):
        call(api.PreviewConfigResource, config=group(), id=rule_id)
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.specs.count() == rule.resolved.count() == 1


@pytest.mark.parametrize("apply", [False, True])
def test_create_and_update_apply(public_context, apply):
    created = call(api.CreateConfigResource, config=group(), apply=apply)
    rule_id = created["rule"]["id"]
    assert created["saved"]
    assert created["execution"] == ({"succeeded": True, "error": ""} if apply else None)
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.current_spec.operator == "alice"
    assert rule.resolved.count() == int(apply)
    assert public_context.apply_data_link.call_count == int(apply)
    updated_config = group()
    updated_config["rules"][0]["expr"] = "sum(system_cpu_usage)"
    result = call(api.UpdateConfigResource, id=rule_id, config=updated_config, apply=apply)
    assert result["rule"]["generation"] == 2
    assert result["rule"]["id"] == rule_id
    assert result["config"]["rules"][0]["expr"] == "sum(system_cpu_usage)"
    assert public_context.apply_data_link.call_count == 2 * int(apply)


def test_apply_failure_keeps_saved_config(public_context):
    public_context.apply_data_link.side_effect = RuntimeError("bkbase unavailable")
    created = call(api.CreateConfigResource, config=group(), apply=True)
    assert created["saved"]
    assert not created["execution"]["succeeded"]
    assert "bkbase unavailable" in created["execution"]["error"]
    rule = RecordRuleV4.objects.get(pk=created["rule"]["id"])
    assert rule.current_spec is not None
    assert rule.applied_resolved is None
    public_context.apply_data_link.side_effect = None
    result = call(api.ApplyConfigResource, id=rule.pk)
    assert result["execution"]["succeeded"]
    assert result["rule"]["applied_resolved_id"] is not None


def test_output_preparation_failure_reports_cause(public_context, mocker):
    mocker.patch(
        "metadata.models.record_rule.v4.output.RecordRuleV4OutputResources.ensure_group_output",
        side_effect=RuntimeError("output unavailable"),
    )
    created = call(api.CreateConfigResource, config=group(), apply=True)
    assert created["saved"]
    assert not created["execution"]["succeeded"]
    assert created["execution"]["error"] == "output unavailable"


@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("delete_succeeded", [False, True])
def test_update_rechecks_soft_deletion_after_loading_rule(public_context, mocker, apply, delete_succeeded):
    value = group()
    value["bkmonitor"]["auto_refresh"] = True
    rule_id = call(api.CreateConfigResource, config=value, apply=True)["rule"]["id"]
    save_declaration = recording_rule.save_declaration
    if not delete_succeeded:
        public_context.delete_data_link.side_effect = RuntimeError("delete failed")

    def delete_before_save(space, declaration, *, rule, **kwargs):
        # 模拟更新已读取对象后，另一个删除请求完成声明或 Flow 删除。
        call(api.DeleteConfigResource, id=rule.pk)
        return save_declaration(space, declaration, rule=rule, **kwargs)

    public_context.apply_data_link.reset_mock()
    mocker.patch.object(recording_rule, "save_declaration", side_effect=delete_before_save)
    with pytest.raises(ValidationError, match="RecordingRule 不存在"):
        call(api.UpdateConfigResource, id=rule_id, config=value, apply=apply)

    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.is_deleted and rule.desired_status == "deleted"
    assert (rule.deleted_at is not None) == delete_succeeded
    assert rule.specs.count() == 1
    public_context.apply_data_link.assert_not_called()


def test_soft_delete_and_declaration_are_atomic(public_context, mocker):
    rule_id = call(api.CreateConfigResource, config=group())["rule"]["id"]
    mocker.patch.object(
        recording_rule.RecordRuleV4Operator, "delete_declaration", side_effect=RuntimeError("declaration failed")
    )
    with pytest.raises(RuntimeError, match="declaration failed"):
        call(api.DeleteConfigResource, id=rule_id)
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert not rule.is_deleted
    assert rule.desired_status == "running"
    public_context.delete_data_link.assert_not_called()


def test_default_save_and_optional_observation(public_context):
    created = call(api.CreateConfigResource, config=group())
    assert created["execution"] is None
    rule_id = created["rule"]["id"]
    result = call(api.GetConfigResource, id=rule_id)
    assert result["observation"] is None
    public_context.get_data_link.assert_not_called()
    result = call(api.GetConfigResource, id=rule_id, with_status=True)
    assert result["observation"]["error"] == "尚未下发 Flow"
    call(api.ApplyConfigResource, id=rule_id)
    result = call(api.GetConfigResource, id=rule_id, with_status=True)
    assert result["observation"] == {"succeeded": True, "flow_status": "ok", "error": ""}
    public_context.get_data_link.side_effect = RuntimeError("status unavailable")
    result = call(api.GetConfigResource, id=rule_id, with_status=True)
    assert result["config"]["name"] == "cpu"
    assert not result["observation"]["succeeded"]
    assert "status unavailable" in result["observation"]["error"]


def test_soft_delete_hidden_and_scheduler_retries_without_admin_filter(public_context):
    created = call(api.CreateConfigResource, config=group(), apply=True)
    rule_id = created["rule"]["id"]
    public_context.delete_data_link.side_effect = RuntimeError("delete unavailable")
    result = call(api.DeleteConfigResource, id=rule_id)
    assert result["is_deleted"]
    assert not result["execution"]["succeeded"]
    rule = RecordRuleV4.objects.get(pk=rule_id)
    assert rule.is_deleted and rule.desired_status == "deleted" and rule.deleted_at is None
    assert rule.specs.exists() and rule.resolved.exists() and rule.flows.exists() and rule.events.exists()
    for resource, params in [
        (api.GetConfigResource, {}),
        (api.UpdateConfigResource, {"config": group()}),
        (api.PreviewConfigResource, {"config": group()}),
        (api.ApplyConfigResource, {}),
        (api.DeleteConfigResource, {}),
    ]:
        with pytest.raises(ValidationError, match="不存在"):
            call(resource, id=rule_id, **params)
    assert call(api.ListConfigsResource)["total"] == 0
    assert admin.get_record_rule_v4_config({"bk_tenant_id": TENANT_ID, "id": rule_id})["data"]["rule"]["id"] == rule_id
    assert admin.list_record_rule_v4({"bk_tenant_id": TENANT_ID})["data"]["total"] == 1
    public_context.delete_data_link.side_effect = None
    refresh_record_rule_v4()
    rule.refresh_from_db()
    assert rule.is_deleted and rule.deleted_at is not None
    assert rule.status == "deleted"
    assert admin.list_record_rule_v4({"bk_tenant_id": TENANT_ID, "include_deleted": True})["data"]["total"] == 1


def test_tenant_space_isolation_and_filters(public_context, mocker):
    first = call(api.CreateConfigResource, config=group("first"))["rule"]["id"]
    second = call(api.CreateConfigResource, config=group("second"))["rule"]["id"]
    RecordRuleV4.objects.filter(pk=first).update(app="test-app")
    assert call(api.ListConfigsResource, app="test-app")["items"][0]["id"] == first
    assert call(api.ListConfigsResource, name="second", page_size=1)["items"][0]["id"] == second
    assert call(api.ListConfigsResource, status="does-not-exist")["total"] == 0
    assert call(api.ListConfigsResource, page=2, page_size=1)["total"] == 2
    public_context.get_data_link.assert_not_called()
    models.Space.objects.create(bk_tenant_id=TENANT_ID, space_type_id="bkcc", space_id="3")
    with pytest.raises(ValidationError, match="不存在"):
        api.GetConfigResource().request(bk_biz_id=3, id=first)
    mocker.patch.object(recording_rule, "get_request_tenant_id", return_value="another-tenant")
    with pytest.raises(ValidationError, match="租户"):
        call(api.GetConfigResource, id=first)


def test_configuration_boundary_validation(public_context):
    value = group()
    value["space_uid"] = "bkcc__3"
    with pytest.raises(CustomException, match="not allowed"):
        call(api.CreateConfigResource, config=value)
    with pytest.raises(ValidationError, match="不匹配"):
        call(api.CreateConfigResource, config=group(), space_uid="bkcc__3")
    created = call(api.CreateConfigResource, config=group())
    with pytest.raises(ValidationError, match="名称不可修改"):
        call(api.UpdateConfigResource, id=created["rule"]["id"], config=group("renamed"))


def test_soft_delete_migration_backfill(public_context):
    ids = [call(api.CreateConfigResource, config=group(str(index)))["rule"]["id"] for index in range(3)]
    RecordRuleV4.objects.filter(pk=ids[1]).update(desired_status="deleted")
    RecordRuleV4.objects.filter(pk=ids[2]).update(deleted_at=timezone.now())
    migration = import_module("metadata.migrations.0280_recordrulev4_as_code")
    with connections[config.DATABASE_CONNECTION_NAME].schema_editor() as editor:
        migration.mark_deleted_rules(apps, editor)
    assert list(RecordRuleV4.objects.order_by("id").values_list("is_deleted", flat=True)) == [False, True, True]


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_migration_adds_fields_and_matches_model():
    """独立执行本次迁移，避免依赖仓库历史迁移的其他应用节点。"""
    connection = connections[config.DATABASE_CONNECTION_NAME]
    state = ProjectState()
    state.add_model(
        ModelState(
            "metadata",
            "RecordRuleV4",
            fields=[
                ("id", django_models.AutoField(primary_key=True)),
                ("desired_status", django_models.CharField(max_length=32, default="running")),
                ("deleted_at", django_models.DateTimeField(null=True)),
            ],
            options={"db_table": "test_recordrulev4_ascode_migration"},
        )
    )
    old_model = state.apps.get_model("metadata", "RecordRuleV4")
    with connection.schema_editor() as editor:
        editor.create_model(old_model)
    try:
        old_model.objects.using(connection.alias).bulk_create(
            [old_model(), old_model(desired_status="deleted"), old_model(deleted_at=timezone.now())]
        )
        migration = import_module("metadata.migrations.0280_recordrulev4_as_code").Migration(
            "0280_recordrulev4_as_code", "metadata"
        )
        with connection.schema_editor() as editor:
            state = migration.apply(state, editor)
        migrated_model = state.apps.get_model("metadata", "RecordRuleV4")
        rows = list(migrated_model.objects.using(connection.alias).order_by("id").values("is_deleted", "app", "path"))
        assert rows == [
            {"is_deleted": False, "app": "", "path": ""},
            {"is_deleted": True, "app": "", "path": ""},
            {"is_deleted": True, "app": "", "path": ""},
        ]
        for field in ("is_deleted", "app", "path"):
            assert (
                migrated_model._meta.get_field(field).deconstruct()[1:]
                == RecordRuleV4._meta.get_field(field).deconstruct()[1:]
            )
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(state.apps.get_model("metadata", "RecordRuleV4"))


def test_gateway_routes_and_http_create(public_context):
    from kernel_api.views.v4.recording_rule import RecordingRuleViewSet

    router = ResourceRouter()
    router.register_module(import_module("kernel_api.views.v4"))
    urlconf = (path("api/v4/", include(router.urls)),)
    root = Path(__file__).resolve().parents[3]
    definition = yaml.safe_load((root / "support-files/apigw/resources/external/app/recording_rule.yaml").read_text())
    for path_data in definition["paths"].values():
        method, operation = next(iter(path_data.items()))
        backend_path = operation["x-bk-apigateway-resource"]["backend"]["path"]
        match = resolve(backend_path, urlconf=urlconf)
        assert match.func.cls is RecordingRuleViewSet
        assert method in match.func.actions
        assert operation["x-bk-apigateway-resource"]["authConfig"]["resourcePermissionRequired"]
        assert (root / "support-files/apigw/docs/zh" / (operation["operationId"] + ".md")).is_file()
    match = resolve("/api/v4/recording_rule/create_config/", urlconf=urlconf)
    request = APIRequestFactory().post(match.route, {"bk_biz_id": 2, "config": group()}, format="json")
    response = match.func(request)
    assert response.status_code == 200
    assert response.data["saved"]
    assert response.data["execution"] is None
