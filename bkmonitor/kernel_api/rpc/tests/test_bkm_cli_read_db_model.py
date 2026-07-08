"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filter_kwargs = None
        self.order_by_args = None
        self.slice_value = None
        self.select_related_args = None

    def select_related(self, *args):
        self.select_related_args = args
        return self

    def filter(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def order_by(self, *args):
        self.order_by_args = args
        return self

    def __getitem__(self, value):
        self.slice_value = value
        return self.rows[value]


class FakeManager:
    def __init__(self, queryset):
        self.queryset = queryset

    def all(self):
        return self.queryset


class FakeModel:
    objects = None


def test_read_db_model_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("read-db-model")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.read_db_model")

    assert op.func_name == "bkm_cli.read_db_model"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_list_db_models_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("list-db-models")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.list_db_models")

    assert op.func_name == "bkm_cli.list_db_models"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_list_db_models_returns_read_db_model_allowlist(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    monkeypatch.setattr(db, "ALLOWED_MODEL_SPECS", {})
    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.Model",
        db.ModelSpec(
            model_path="demo.Model",
            fields={"id", "name", "token"},
            sensitive_fields={"token"},
            examples=[
                {
                    "filter": {"id": 1},
                    "fields": ["id", "name"],
                    "limit": 20,
                }
            ],
        ),
    )

    result = BkmCliOpCallResource().perform_request({"op_id": "list-db-models", "params": {}})

    assert result["op_id"] == "list-db-models"
    assert result["func_name"] == "bkm_cli.list_db_models"
    assert result["protocol"] == "bkm_cli_op_call"
    assert result["result"] == {
        "count": 1,
        "items": [
            {
                "model": "demo.Model",
                "allowed_fields": ["id", "name"],
                "allowed_filter_fields": ["id", "name"],
                "allowed_order_by": ["id", "name"],
                "allowed_lookups": ["contains", "endswith", "exact", "gte", "in", "isnull", "lte", "startswith"],
                "default_fields": ["id", "name"],
                "max_limit": 500,
                "examples": [{"filter": {"id": 1}, "fields": ["id", "name"], "limit": 20}],
            }
        ],
    }


def test_read_db_model_rejects_model_outside_allowlist():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "django.contrib.auth.models.User",
                    "filter": {"id": 1},
                },
            }
        )

    assert "不在 bkm-cli read-db-model 白名单" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_unsafe_lookup(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS, "demo.Model", db.ModelSpec(model_path="demo.Model", fields={"id", "name"})
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "demo.Model",
                    "filter": {"name__regex": "^admin"},
                },
            }
        )

    assert "不支持的 lookup" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_invalid_limit_with_discovery_next_actions():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "metadata.models.space.space.Space",
                    "limit": 501,
                },
            }
        )

    assert "limit 超过硬上限" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_rejects_invalid_filter_shape_with_discovery_next_actions():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "read-db-model",
                "params": {
                    "model": "metadata.models.space.space.Space",
                    "filter": "space_id=2",
                },
            }
        )

    assert "filter 必须是对象" in str(exc.value)
    assert exc.value.data == {
        "next_actions": ["调用 list-db-models 获取当前环境可读模型、字段、filter、排序和 limit 上限。"]
    }


def test_read_db_model_filters_limits_and_returns_allowed_fields(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet(
        [
            SimpleNamespace(id=1, name="demo", token="secret-token", payload="x" * 10),
            SimpleNamespace(id=2, name="next", token="secret-token-2", payload="y" * 10),
        ]
    )
    FakeModel.objects = FakeManager(queryset)

    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.Model",
        db.ModelSpec(model_path="demo.Model", fields={"id", "name", "payload"}, sensitive_fields={"token"}),
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "read-db-model",
            "params": {
                "model": "demo.Model",
                "filter": {"id__in": [1, 2]},
                "fields": ["id", "name", "token"],
                "order_by": ["-id"],
                "limit": 1,
            },
        }
    )

    assert result["result"]["model"] == "demo.Model"
    assert result["result"]["count"] == 1
    assert result["result"]["items"] == [{"id": 1, "name": "demo"}]
    assert queryset.filter_kwargs == {"id__in": [1, 2]}
    assert queryset.order_by_args == ("-id",)
    assert queryset.slice_value == slice(None, 1, None)


def test_bcs_cluster_info_allowlist_has_diagnostic_fields():
    from kernel_api.rpc.functions.bkm_cli.db import ALLOWED_MODEL_SPECS

    spec = ALLOWED_MODEL_SPECS["metadata.models.bcs.cluster.BCSClusterInfo"]

    required = {"bk_env", "K8sMetricDataID", "K8sEventDataID", "operator_ns", "create_time", "last_modify_time"}
    assert required <= spec.fields, f"Missing fields: {required - spec.fields}"

    stale = {"created_at", "updated_at"}
    assert not (stale & spec.fields), f"Stale field names still present: {stale & spec.fields}"


def test_allowlist_excludes_deprecated_and_low_value_models():
    from kernel_api.rpc.functions.bkm_cli.db import ALLOWED_MODEL_SPECS

    removed = {
        "bkmonitor.models.base.ReportItems",
        "bkmonitor.models.base.ReportContents",
        "bkmonitor.models.base.ReportStatus",
        "bkmonitor.models.fta.action.ActionInstance",
        "bkmonitor.models.fta.action.ActionInstanceLog",
    }
    present = removed & set(ALLOWED_MODEL_SPECS.keys())
    assert not present, f"Deprecated/low-value models still in allowlist: {present}"


def test_datasource_and_resulttable_in_allowlist_with_token_excluded():
    from kernel_api.rpc.functions.bkm_cli import db

    ds = db.ALLOWED_MODEL_SPECS["metadata.models.data_source.DataSource"]
    assert {"bk_data_id", "data_name", "bk_tenant_id", "etl_config", "is_enable"} <= ds.fields
    # token 是上报校验密钥，不可读、不可过滤
    assert "token" not in ds.fields
    assert "token" not in db._safe_fields(ds)
    assert ds.note

    rt = db.ALLOWED_MODEL_SPECS["metadata.models.result_table.ResultTable"]
    assert {"table_id", "bk_biz_id", "default_storage", "data_label", "is_builtin"} <= rt.fields


def test_graph_relation_binding_config_registered_in_allowlist():
    from kernel_api.rpc.functions.bkm_cli import db

    spec = db.ALLOWED_MODEL_SPECS["metadata.models.data_link.data_link_configs.GraphRelationBindingConfig"]

    required = {
        "bk_tenant_id",
        "namespace",
        "name",
        "data_link_name",
        "bk_biz_id",
        "status",
        "write_mode",
        "table_id",
        "bkbase_result_table_name",
        "graph_result_table_name",
        "vm_storage_binding_name",
        "vm_databus_name",
        "surrealdb_binding_name",
        "graph_databus_name",
        "vm_cluster_name",
        "surrealdb_cluster_name",
        "surrealdb_auto_restore",
        "create_time",
        "last_modify_time",
    }
    assert required <= spec.fields
    assert {"bk_biz_id", "data_link_name", "name", "write_mode", "status"} <= db._safe_fields(spec)
    assert {"bk_tenant_id", "namespace", "name", "data_link_name", "bk_biz_id", "status", "write_mode"} <= (
        spec.default_fields
    )
    assert "vertices" not in spec.fields
    assert "relations" not in spec.fields
    assert spec.note


def test_list_db_models_surfaces_model_note():
    result = BkmCliOpCallResource().perform_request({"op_id": "list-db-models", "params": {}})

    items = {item["model"]: item for item in result["result"]["items"]}
    assert items["metadata.models.data_source.DataSource"]["note"]
    assert "token" not in items["metadata.models.data_source.DataSource"]["allowed_fields"]
    graph_binding = items["metadata.models.data_link.data_link_configs.GraphRelationBindingConfig"]
    assert graph_binding["note"]
    assert "write_mode" in graph_binding["allowed_fields"]
    assert "vertices" not in graph_binding["allowed_fields"]


# ---------- GlobalConfig (row-level masking) ----------


def test_global_config_in_allowlist_with_row_masker():
    from kernel_api.rpc.functions.bkm_cli.db import ALLOWED_MODEL_SPECS

    spec = ALLOWED_MODEL_SPECS["bkmonitor.models.config.GlobalConfig"]

    assert {"key", "value", "data_type", "is_advanced", "is_internal", "update_at"} <= spec.fields
    assert spec.row_masker is not None


def test_list_db_models_marks_global_config_row_masking():
    result = BkmCliOpCallResource().perform_request({"op_id": "list-db-models", "params": {}})

    items = {item["model"]: item for item in result["result"]["items"]}
    global_config = items["bkmonitor.models.config.GlobalConfig"]

    assert "row_masking" in global_config
    assert "value" in global_config["allowed_fields"]


def test_mask_global_config_row_patterns():
    from kernel_api.rpc.functions.bkm_cli.db import MASKED_VALUE, _mask_global_config_row

    def mask(key, item):
        return _mask_global_config_row(item, SimpleNamespace(key=key))

    # 命名敏感的键脱敏
    assert mask("DEMO_TOKEN", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("demo_app_secret", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("WXWORK_BOT_WEBHOOK_URL", {"value": "v"})["value"] == MASKED_VALUE
    # MAJOR 回归：原正则漏掉的真实敏感键
    assert mask("SPECIFY_AES_KEY", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("MESSAGE_QUEUE_DSN", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("WECOM_APP_ACCOUNT", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("BK_DATA_KAFKA_BROKER_URL", {"value": "v"})["value"] == MASKED_VALUE
    assert mask("RSA_PRIVATE_KEY", {"value": "v"})["value"] == MASKED_VALUE
    # 非敏感键放行
    assert mask("DOUBLE_CHECK_SUM_STRATEGY_IDS", {"value": [1, 2]})["value"] == [1, 2]
    # 不误伤：含 KEY/URL 子串但实为公开配置
    assert mask("AIDEV_AGENT_AI_GENERATING_KEYWORD", {"value": "x"})["value"] == "x"
    assert mask("APM_ACCESS_URL", {"value": "http://a.b/c"})["value"] == "http://a.b/c"
    # value 形态兜底：denylist 漏键但 value 是凭据型 URL
    assert mask("SOME_PLAIN_NAME", {"value": "redis://user:pw@h:6379/0"})["value"] == MASKED_VALUE
    # value 字段未被选中时不报错、不新增字段
    assert mask("ANY_SECRET", {"key": "ANY_SECRET"}) == {"key": "ANY_SECRET"}


def test_read_db_model_global_config_masks_even_without_key_field(monkeypatch):
    """BLOCKER 回归：只选 value 不选 key 时，仍按 instance.key 判定脱敏，不可绕过。"""
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet([SimpleNamespace(key="DEMO_APP_SECRET_KEY", value="should-not-leak", data_type="Char")])
    FakeModel.objects = FakeManager(queryset)
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "read-db-model",
            "params": {
                "model": "bkmonitor.models.config.GlobalConfig",
                "filter": {"key": "DEMO_APP_SECRET_KEY"},
                "fields": ["value"],
            },
        }
    )

    assert result["result"]["items"] == [{"value": db.MASKED_VALUE}]


def test_read_db_model_global_config_masks_sensitive_rows(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet(
        [
            SimpleNamespace(key="DEMO_PLAIN_SWITCH", value=[101, 102], data_type="List"),
            SimpleNamespace(key="DEMO_APP_SECRET_KEY", value="should-not-leak", data_type="Char"),
        ]
    )
    FakeModel.objects = FakeManager(queryset)
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "read-db-model",
            "params": {
                "model": "bkmonitor.models.config.GlobalConfig",
                "filter": {"key__in": ["DEMO_PLAIN_SWITCH", "DEMO_APP_SECRET_KEY"]},
                "fields": ["key", "value", "data_type"],
            },
        }
    )

    items = {item["key"]: item for item in result["result"]["items"]}
    assert items["DEMO_PLAIN_SWITCH"]["value"] == [101, 102]
    assert items["DEMO_APP_SECRET_KEY"]["value"] == db.MASKED_VALUE
    assert items["DEMO_APP_SECRET_KEY"]["data_type"] == "Char"


# ---------- CollectConfigMeta / DeploymentConfigVersion 白名单 + params 凭据脱敏 ----------


def test_collecting_models_registered_in_allowlist():
    from kernel_api.rpc.functions.bkm_cli import db

    assert "monitor_web.models.collecting.CollectConfigMeta" in db.ALLOWED_MODEL_SPECS
    assert "monitor_web.models.collecting.DeploymentConfigVersion" in db.ALLOWED_MODEL_SPECS

    dep_spec = db.ALLOWED_MODEL_SPECS["monitor_web.models.collecting.DeploymentConfigVersion"]
    # params 字段暴露（取证需要 metrics_url），但挂 row_masker 脱敏内嵌凭据
    assert "params" in dep_spec.fields
    assert dep_spec.row_masker is db._mask_deployment_config_row
    serialized = db._serialize_model_spec("monitor_web.models.collecting.DeploymentConfigVersion", dep_spec)
    assert "params" in serialized["allowed_fields"]
    assert "password" in serialized["row_masking"]


def test_collect_config_meta_exposes_fk_id_not_fk_object():
    from kernel_api.rpc.functions.bkm_cli import db

    spec = db.ALLOWED_MODEL_SPECS["monitor_web.models.collecting.CollectConfigMeta"]
    # 暴露 FK 的 _id 列而非 FK 对象（FK 对象非 JSON 可序列化）
    assert "deployment_config_id" in spec.fields
    assert "deployment_config" not in spec.fields


def test_mask_deployment_config_row_masks_credentials_keeps_endpoint():
    from kernel_api.rpc.functions.bkm_cli import db

    item = {
        "id": 1,
        "params": {
            "collector": {
                "period": 60,
                "metrics_url": "http://127.0.0.1:25901/actuator/prometheus",
                "username": "svc",
                "password": "p@ss",
            },
            "plugin": {"token": "abc", "items": [{"secret_key": "k"}]},
        },
    }
    masked = db._mask_deployment_config_row(item, object())
    collector = masked["params"]["collector"]
    assert collector["metrics_url"] == "http://127.0.0.1:25901/actuator/prometheus"
    assert collector["period"] == 60
    assert collector["username"] == db.MASKED_VALUE
    assert collector["password"] == db.MASKED_VALUE
    assert masked["params"]["plugin"]["token"] == db.MASKED_VALUE
    assert masked["params"]["plugin"]["items"][0]["secret_key"] == db.MASKED_VALUE


def test_mask_deployment_config_row_masks_credential_url_value():
    from kernel_api.rpc.functions.bkm_cli import db

    item = {"params": {"endpoint": "http://user:secretpass@host:9090/metrics"}}
    masked = db._mask_deployment_config_row(item, object())
    assert masked["params"]["endpoint"] == db.MASKED_VALUE


def test_mask_deployment_config_row_noop_when_params_absent():
    from kernel_api.rpc.functions.bkm_cli import db

    item = {"id": 1, "subscription_id": 5}
    assert db._mask_deployment_config_row(dict(item), object()) == item


def test_mask_deployment_config_row_masks_author_named_credential_via_config_json():
    from kernel_api.rpc.functions.bkm_cli import db

    # 作者自定义的凭据参数名（my_endpoint_key 不命中名字正则），必须靠 config_json 的 type=password 脱敏
    config_json = [
        {"mode": "plugin", "name": "my_endpoint_key", "type": "password", "default": ""},
        {"mode": "collector", "name": "metric_url", "type": "text", "default": ""},
    ]
    instance = SimpleNamespace(plugin_version=SimpleNamespace(config=SimpleNamespace(config_json=config_json)))
    item = {
        "params": {
            "collector": {"metric_url": "http://127.0.0.1:9100/metrics"},
            "plugin": {"my_endpoint_key": "s3cr3t", "log_level": "info"},
        }
    }
    masked = db._mask_deployment_config_row(item, instance)["params"]
    # 类型驱动脱敏命中作者自定义名的凭据
    assert masked["plugin"]["my_endpoint_key"] == db.MASKED_VALUE
    # 非凭据 plugin 参数与端点 URL 保留（取证价值不损）
    assert masked["plugin"]["log_level"] == "info"
    assert masked["collector"]["metric_url"] == "http://127.0.0.1:9100/metrics"


def test_mask_deployment_config_row_config_json_unreachable_falls_back_to_heuristic():
    from kernel_api.rpc.functions.bkm_cli import db

    # config_json 取不到（instance 无 plugin_version）时不得报错，名字启发式仍兜住 collector 固定名凭据
    item = {"params": {"collector": {"password": "x", "period": 30}}}
    masked = db._mask_deployment_config_row(item, object())["params"]
    assert masked["collector"]["password"] == db.MASKED_VALUE
    assert masked["collector"]["period"] == 30


def test_deployment_config_spec_declares_select_related():
    from kernel_api.rpc.functions.bkm_cli import db

    # row_masker 按 config_json 脱敏要读 plugin_version.config，预取避免逐行 N+1
    spec = db.ALLOWED_MODEL_SPECS["monitor_web.models.collecting.DeploymentConfigVersion"]
    assert spec.select_related == ["plugin_version__config"]


def test_read_db_model_applies_select_related(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet([SimpleNamespace(id=1, name="demo")])
    FakeModel.objects = FakeManager(queryset)
    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.Model",
        db.ModelSpec(model_path="demo.Model", fields={"id", "name"}, select_related=["a__b"]),
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    BkmCliOpCallResource().perform_request(
        {"op_id": "read-db-model", "params": {"model": "demo.Model", "filter": {"id": 1}}}
    )
    assert queryset.select_related_args == ("a__b",)


def test_read_db_model_skips_select_related_when_unset(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    queryset = FakeQuerySet([SimpleNamespace(id=1, name="demo")])
    FakeModel.objects = FakeManager(queryset)
    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS, "demo.Model", db.ModelSpec(model_path="demo.Model", fields={"id", "name"})
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: FakeModel)

    BkmCliOpCallResource().perform_request(
        {"op_id": "read-db-model", "params": {"model": "demo.Model", "filter": {"id": 1}}}
    )
    # select_related 为空时不应调用（避免无谓 JOIN）
    assert queryset.select_related_args is None


def test_mask_deployment_config_row_masks_file_param_content_by_key():
    from kernel_api.rpc.functions.bkm_cli import db

    # file 型参数内容以 base64 编码的上传文件存储，键名 file_base64 非凭据名——名字层按 file_base64 键脱敏内容、
    # 保留 filename（config_json 取不到时也覆盖）
    item = {"params": {"plugin": {"env": {"filename": "env.sh", "file_base64": "Y29udGVudA=="}}}}
    masked = db._mask_deployment_config_row(item, object())["params"]
    assert masked["plugin"]["env"]["file_base64"] == db.MASKED_VALUE
    assert masked["plugin"]["env"]["filename"] == "env.sh"


def test_mask_deployment_config_row_masks_file_type_param_via_config_json():
    from kernel_api.rpc.functions.bkm_cli import db

    # config_json 声明 type=file 的参数：即便内容键不叫 file_base64（这里是 blob），类型驱动也整体脱敏其值
    config_json = [{"mode": "plugin", "name": "env", "type": "file", "default": ""}]
    instance = SimpleNamespace(plugin_version=SimpleNamespace(config=SimpleNamespace(config_json=config_json)))
    item = {"params": {"plugin": {"env": {"filename": "env.sh", "blob": "Y29udGVudA=="}}}}
    masked = db._mask_deployment_config_row(item, instance)["params"]
    assert masked["plugin"]["env"] == db.MASKED_VALUE


# ── P4: _serialize_instance 逐字段 json-safe 归一 ─────────────────────────────


def test_serialize_instance_datetime_field_becomes_json_safe_string():
    """含 datetime 字段的行：_serialize_instance 输出可被 json.dumps，datetime 变为字符串。"""
    import json as _json
    from datetime import datetime
    from decimal import Decimal

    from kernel_api.rpc.functions.bkm_cli.db import _serialize_instance

    instance = SimpleNamespace(
        id=7,
        name="alpha",
        create_at=datetime(2026, 6, 23, 10, 30, 0),
        ratio=Decimal("3.14"),
    )
    out = _serialize_instance(instance, {"id", "name", "create_at", "ratio"})

    # 整行可被 json.dumps（无 default=），证明所有字段已 JSON-safe
    _json.dumps(out)
    assert out["id"] == 7
    assert out["name"] == "alpha"
    assert isinstance(out["create_at"], str)
    assert out["create_at"].startswith("2026-06-23")
    # Decimal 经 json.dumps(default=str) 后是字符串
    assert isinstance(out["ratio"], str)
    assert out["ratio"] == "3.14"


def test_serialize_instance_bad_field_degrades_and_keeps_row():
    """单个不可序列化字段降级为 <unserializable: 类名>，绝不崩掉整行。"""
    import json as _json

    from kernel_api.rpc.functions.bkm_cli.db import _serialize_instance

    class _NotSerializable:
        # default=str 会回退到 repr/str，仍可序列化；这里用一个连 str() 都抛错的对象，
        # 强制走 except 分支，验证降级占位。
        def __repr__(self):
            raise RuntimeError("boom-repr")

        def __str__(self):
            raise RuntimeError("boom-str")

    instance = SimpleNamespace(ok="fine", bad=_NotSerializable())
    out = _serialize_instance(instance, {"ok", "bad"})

    # 整行仍可 json.dumps，坏字段被占位，好字段保留
    _json.dumps(out)
    assert out["ok"] == "fine"
    assert out["bad"] == "<unserializable: _NotSerializable>"


# ---------- ActionConfig / StrategyActionConfigRelation 白名单 + origin_objects 软删可见 + execute_config 脱敏 ----------


def test_action_config_and_relation_registered_in_allowlist():
    from kernel_api.rpc.functions.bkm_cli import db

    ac = db.ALLOWED_MODEL_SPECS["bkmonitor.models.fta.action.ActionConfig"]
    rel = db.ALLOWED_MODEL_SPECS["bkmonitor.models.fta.action.StrategyActionConfigRelation"]
    # 软删模型必须用 origin_objects 读，否则 .objects 过滤掉 is_deleted 行——那正是要看的证据
    assert ac.manager_name == "origin_objects"
    assert rel.manager_name == "origin_objects"
    assert {"is_deleted", "is_enabled", "create_time", "update_time"} <= ac.fields
    assert {"strategy_id", "config_id", "relate_type", "is_deleted"} <= rel.fields
    assert ac.note and rel.note


def test_action_config_execute_config_never_exposed():
    from kernel_api.rpc.functions.bkm_cli import db

    spec = db.ALLOWED_MODEL_SPECS["bkmonitor.models.fta.action.ActionConfig"]
    # execute_config（可内嵌 webhook/凭据）既不列入 fields，也登记 sensitive_fields 兜底显式请求
    assert "execute_config" not in spec.fields
    assert "execute_config" in spec.sensitive_fields
    assert "execute_config" not in db._safe_fields(spec)
    # list-db-models 自描述既不广告 execute_config，又回显 origin_objects manager
    serialized = db._serialize_model_spec("bkmonitor.models.fta.action.ActionConfig", spec)
    assert "execute_config" not in serialized["allowed_fields"]
    assert serialized["manager"] == "origin_objects"


def test_list_db_models_omits_manager_for_default_objects_models():
    """MAJOR 回归：默认 objects 的模型不回显 manager，保持既有自描述不变；origin_objects 模型才回显。"""
    from kernel_api.rpc.functions.bkm_cli import db

    ds = db.ALLOWED_MODEL_SPECS["metadata.models.data_source.DataSource"]
    assert "manager" not in db._serialize_model_spec("metadata.models.data_source.DataSource", ds)

    rel = db.ALLOWED_MODEL_SPECS["bkmonitor.models.fta.action.StrategyActionConfigRelation"]
    serialized = db._serialize_model_spec("bkmonitor.models.fta.action.StrategyActionConfigRelation", rel)
    assert serialized["manager"] == "origin_objects"


def test_read_db_model_uses_origin_objects_to_surface_soft_deleted_rows(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import db

    # objects（默认 manager，模拟 RecordModelManager）只回未删行；origin_objects 回含软删行的全集
    objects_qs = FakeQuerySet([SimpleNamespace(id=1, name="live", is_deleted=False)])
    origin_qs = FakeQuerySet(
        [
            SimpleNamespace(id=1, name="live", is_deleted=False),
            SimpleNamespace(id=2, name="soft-deleted", is_deleted=True),
        ]
    )

    class _SoftDeleteModel:
        objects = FakeManager(objects_qs)
        origin_objects = FakeManager(origin_qs)

    monkeypatch.setitem(
        db.ALLOWED_MODEL_SPECS,
        "demo.SoftDelete",
        db.ModelSpec(model_path="demo.SoftDelete", fields={"id", "name", "is_deleted"}, manager_name="origin_objects"),
    )
    monkeypatch.setattr(db, "import_string", lambda _model_path: _SoftDeleteModel)

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "read-db-model", "params": {"model": "demo.SoftDelete", "filter": {}}}
    )

    ids = {item["id"] for item in result["result"]["items"]}
    # 读到了软删行(id=2)——证明走 origin_objects 而非 objects(后者会过滤掉)
    assert ids == {1, 2}
    assert origin_qs.filter_kwargs == {}
    # 默认 objects manager 未被触碰
    assert objects_qs.filter_kwargs is None


def test_read_db_model_defaults_to_objects_manager(monkeypatch):
    """变异自检对偶：manager_name 缺省时走 objects，不得误用 origin_objects。"""
    from kernel_api.rpc.functions.bkm_cli import db

    objects_qs = FakeQuerySet([SimpleNamespace(id=1, name="x")])

    class _Model:
        objects = FakeManager(objects_qs)
        # origin_objects 存在且数据不同：若被错误使用，断言会暴露
        origin_objects = FakeManager(FakeQuerySet([SimpleNamespace(id=9, name="wrong")]))

    monkeypatch.setitem(db.ALLOWED_MODEL_SPECS, "demo.M", db.ModelSpec(model_path="demo.M", fields={"id", "name"}))
    monkeypatch.setattr(db, "import_string", lambda _model_path: _Model)

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "read-db-model", "params": {"model": "demo.M", "filter": {"id": 1}}}
    )
    assert [i["id"] for i in result["result"]["items"]] == [1]
    assert objects_qs.filter_kwargs == {"id": 1}


def test_read_db_model_action_config_drops_execute_config_even_when_explicitly_requested(monkeypatch):
    """兜底回归：显式 fields 含 execute_config 也拿不到（sensitive_fields 在 _normalize_selected_fields 拦截）。"""
    from kernel_api.rpc.functions.bkm_cli import db

    origin_qs = FakeQuerySet(
        [
            SimpleNamespace(
                id=1001,
                name="demo-notice",
                is_enabled=True,
                is_deleted=False,
                execute_config={"template_detail": {"webhook": "http://example/?token=should-not-leak"}},
            )
        ]
    )

    class _ActionConfig:
        objects = FakeManager(FakeQuerySet([]))
        origin_objects = FakeManager(origin_qs)

    monkeypatch.setattr(db, "import_string", lambda _model_path: _ActionConfig)

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "read-db-model",
            "params": {
                "model": "bkmonitor.models.fta.action.ActionConfig",
                "filter": {"id": 1001},
                "fields": ["id", "name", "is_enabled", "is_deleted", "execute_config"],
            },
        }
    )
    item = result["result"]["items"][0]
    assert "execute_config" not in item
    assert item == {"id": 1001, "name": "demo-notice", "is_enabled": True, "is_deleted": False}
