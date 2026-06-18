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


def test_list_db_models_surfaces_model_note():
    result = BkmCliOpCallResource().perform_request({"op_id": "list-db-models", "params": {}})

    items = {item["model"]: item for item in result["result"]["items"]}
    assert items["metadata.models.data_source.DataSource"]["note"]
    assert "token" not in items["metadata.models.data_source.DataSource"]["allowed_fields"]


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
