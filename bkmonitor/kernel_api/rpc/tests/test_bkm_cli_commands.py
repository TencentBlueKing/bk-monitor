"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.bkm_cli.commands import run_readonly_command


# ── 分发器白名单 ──────────────────────────────────────────────────────────────


def test_run_readonly_command_rejects_unknown_command_id():
    with pytest.raises(CustomException, match="not in the readonly whitelist"):
        run_readonly_command({"command_id": "arbitrary_shell_exec", "params": {}})


def test_run_readonly_command_rejects_empty_command_id():
    with pytest.raises(CustomException, match="command_id is required"):
        run_readonly_command({"params": {}})


def test_run_readonly_command_rejects_non_dict_params():
    with pytest.raises(CustomException, match="params must be an object"):
        run_readonly_command({"command_id": "diagnose_ts_metric_sync", "params": "shell injection"})


# ── diagnose_ts_metric_sync 分发 ─────────────────────────────────────────────


def test_run_readonly_command_dispatches_diagnose_ts_metric_sync(mocker):
    """分发器正确路由到 diagnose_ts_metric_sync 并在结果中包含 command_id。"""
    fake_report = {
        "judge": "metadata",
        "context": {"data_id": 1579347},
        "summary": {},
        "metrics": [{"metric": "wea_agent_http_request", "diagnosis": {"stage": "metadata"}}],
    }
    # mock 在 utils 模块（_REGISTRY 存的函数从那里导入），而不是 commands 模块级名称
    mocker.patch(
        "bkmonitor.utils.ts_metric_diagnosis.diagnose_ts_metric_sync",
        return_value=fake_report,
    )
    result = run_readonly_command(
        {"command_id": "diagnose_ts_metric_sync", "params": {"data_id": 1579347, "metrics": ["wea_agent_http_request"]}}
    )
    assert result["command_id"] == "diagnose_ts_metric_sync"
    assert result["judge"] == "metadata"


def test_run_readonly_command_diagnose_rejects_missing_data_id():
    with pytest.raises(CustomException, match="data_id is required"):
        run_readonly_command({"command_id": "diagnose_ts_metric_sync", "params": {"metrics": ["m"]}})


def test_run_readonly_command_diagnose_rejects_missing_metrics():
    with pytest.raises(CustomException, match="metrics is required"):
        run_readonly_command({"command_id": "diagnose_ts_metric_sync", "params": {"data_id": 1}})


def test_run_readonly_command_diagnose_rejects_empty_metrics_list():
    with pytest.raises(CustomException, match="at least one non-empty metric"):
        run_readonly_command({"command_id": "diagnose_ts_metric_sync", "params": {"data_id": 1, "metrics": [" "]}})


# ── 白名单外的命令应被拒绝（含曾经预留但未实现的占位命令）────────────────────


@pytest.mark.parametrize("command_id", ["strategy_check", "context_preview", "check_bcs_cluster_status"])
def test_run_readonly_command_rejects_unregistered_placeholders(command_id):
    """未在白名单中注册的命令应被拒绝，返回 not in the readonly whitelist 错误。"""
    with pytest.raises(CustomException, match="not in the readonly whitelist"):
        run_readonly_command({"command_id": command_id, "params": {}})


# ── get_effective_setting 四源回显 ───────────────────────────────────────────


def _patch_effective_setting_env(mocker, *, name, effective, db_conf, allowed_names=None):
    """统一 mock get_effective_setting 依赖的 settings / GlobalConfig / 白名单。

    _get_effective_setting 函数体内做 from django.conf import settings /
    from bkmonitor.define import global_config / from bkmonitor.models.config import GlobalConfig，
    都是延迟导入，故这里直接替换 django.conf.settings 对象 + 用 sys.modules 替换两个模块即可。
    """
    from types import SimpleNamespace

    import rest_framework.fields as drf_fields

    # settings：用 SimpleNamespace 整体替换 django.conf.settings；
    # effective_value 走 getattr(settings, name)；_wrapped 不是 DynamicSettings → settings_default 标 unavailable。
    fake_settings = SimpleNamespace(**{name: effective, "_wrapped": object()})
    mocker.patch("django.conf.settings", fake_settings)

    # 白名单 + serializer 注册表（global_config 模块）
    fake_gc = SimpleNamespace(
        GLOBAL_CONFIGS=allowed_names if allowed_names is not None else [name],
        # 让 _read_serializer_default 命中 ADVANCED_OPTIONS[name].default
        ADVANCED_OPTIONS={name: drf_fields.BooleanField(default=False)},
        STANDARD_CONFIGS={},
    )
    mocker.patch.dict("sys.modules", {"bkmonitor.define.global_config": fake_gc})

    # GlobalConfig.objects.filter(key=...).last()
    fake_qs = mocker.MagicMock()
    fake_qs.last.return_value = db_conf
    fake_model = mocker.MagicMock()
    fake_model.objects.filter.return_value = fake_qs
    fake_config_module = SimpleNamespace(GlobalConfig=fake_model)
    mocker.patch.dict("sys.modules", {"bkmonitor.models.config": fake_config_module})

    return fake_gc, fake_model


def test_get_effective_setting_returns_all_four_sources(mocker):
    """四源回显字段齐全，db_row_present/resolved_source 与 DB 行一致。"""
    from types import SimpleNamespace

    name = "COMPATIBLE_ALARM_FORMAT"
    db_conf = SimpleNamespace(value=True)
    _patch_effective_setting_env(mocker, name=name, effective=True, db_conf=db_conf)

    result = run_readonly_command({"command_id": "get_effective_setting", "params": {"name": name}})

    assert result["command_id"] == "get_effective_setting"
    assert result["name"] == name
    assert set(result) >= {
        "name",
        "effective_value",
        "db_row_present",
        "db_value",
        "settings_default",
        "serializer_default",
        "resolved_source",
    }
    assert result["db_row_present"] is True
    assert result["db_value"] is True
    assert result["resolved_source"] == "db_row"
    # serializer_default 来自 ADVANCED_OPTIONS[name].default=False
    assert result["serializer_default"] is False


def test_get_effective_setting_resolved_source_settings_default_when_no_db_row(mocker):
    """DB 无行 → resolved_source=settings_default、db_value=None。"""
    name = "COMPATIBLE_ALARM_FORMAT"
    _patch_effective_setting_env(mocker, name=name, effective=True, db_conf=None)

    result = run_readonly_command({"command_id": "get_effective_setting", "params": {"name": name}})

    assert result["db_row_present"] is False
    assert result["db_value"] is None
    assert result["resolved_source"] == "settings_default"


def test_get_effective_setting_rejects_name_outside_whitelist(mocker):
    """白名单外的 name 被拒。"""
    name = "COMPATIBLE_ALARM_FORMAT"
    _patch_effective_setting_env(mocker, name=name, effective=True, db_conf=None, allowed_names=[name])

    with pytest.raises(CustomException, match="not a known dynamic global config"):
        run_readonly_command({"command_id": "get_effective_setting", "params": {"name": "NOT_A_REAL_CONFIG"}})


def test_get_effective_setting_rejects_empty_name(mocker):
    with pytest.raises(CustomException, match="name is required"):
        run_readonly_command({"command_id": "get_effective_setting", "params": {}})


def test_get_effective_setting_masks_credential_name(mocker):
    """凭据类 name（含 token/secret 等）的所有值一律脱敏为 ***masked***。"""
    from types import SimpleNamespace

    name = "FRONTEND_REPORT_DATA_TOKEN"
    db_conf = SimpleNamespace(value="super-secret-token-value")
    _patch_effective_setting_env(mocker, name=name, effective="super-secret-token-value", db_conf=db_conf)

    result = run_readonly_command({"command_id": "get_effective_setting", "params": {"name": name}})

    assert result["masked"] is True
    assert result["effective_value"] == "***masked***"
    assert result["db_value"] == "***masked***"
    # 真实 token 值不得出现在任何回显字段里
    assert "super-secret-token-value" not in repr(result)


# ── GraphRelation dry-run 预览 ───────────────────────────────────────────────


def test_run_readonly_command_dispatches_graph_relation_sync_dry_run(mocker):
    """GraphRelation 写入激活预览必须通过只读 command_id 分发，且强制 dry_run=true。"""
    fake_preview = {
        "namespace": "bkcc__100",
        "action": "manual",
        "dry_run": True,
        "matched": 1,
        "would_apply": 1,
        "previews": [
            {
                "data_link_name": "graph_relation_builtin",
                "bk_biz_id": 100,
                "current_write_mode": "vm",
                "target_write_mode": "vm_and_surrealdb",
                "would_apply": True,
                "reason": "graph_definitions_changed",
                "vm_target": {"result_table_name": "vm_100_bkcc_built_in_time_series"},
                "surrealdb_target": {"binding_name": "bkm_100_bkcc_built_in_time_series_graph"},
                "graph_databus_target": {"databus_name": "bkm_100_bkcc_built_in_time_series_graph"},
                "vertices_count": 2,
                "relations_count": 1,
            }
        ],
    }
    preview = mocker.patch(
        "metadata.task.sync_cmdb_relation.preview_graph_definition_sync_to_bkbase",
        return_value=fake_preview,
        create=True,
    )

    result = run_readonly_command(
        {
            "command_id": "graph_relation_sync_dry_run",
            "params": {"bk_biz_id": 100, "dry_run": True},
        }
    )

    assert result["command_id"] == "graph_relation_sync_dry_run"
    assert result["dry_run"] is True
    assert result["would_apply"] == 1
    assert result["previews"][0]["target_write_mode"] == "vm_and_surrealdb"
    preview.assert_called_once_with(namespace="", bk_biz_id=100, action="manual")


def test_graph_relation_sync_dry_run_rejects_non_dry_run():
    with pytest.raises(CustomException, match="dry_run=true is required"):
        run_readonly_command(
            {
                "command_id": "graph_relation_sync_dry_run",
                "params": {"bk_biz_id": 100, "dry_run": False},
            }
        )


# ── get_report_token 上报凭证回显（prometheus aes256 算 + json DataSource.token 读）──


def _mock_ds_token(mocker, token="UUID_TOK", found=True):
    """mock metadata DataSource：filter(bk_data_id=...).first() → 带 .token 的对象或 None。"""
    from types import SimpleNamespace

    fake_ds_cls = mocker.MagicMock()
    fake_ds_cls.objects.filter.return_value.first.return_value = SimpleNamespace(token=token) if found else None
    mocker.patch("metadata.models.data_source.DataSource", fake_ds_cls)
    return fake_ds_cls


def test_get_report_token_format_all_returns_both(mocker):
    """默认 format=all：prometheus(aes256 算) + json(DataSource.token 读) 两个 token 都回显。"""
    transform = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    _mock_ds_token(mocker, token="UUID_TOK")
    result = run_readonly_command(
        {"command_id": "get_report_token", "params": {"metric_data_id": 575975, "bk_biz_id": 555}}
    )
    assert result["command_id"] == "get_report_token"
    assert result["format"] == "all"
    assert result["tokens"] == {"prometheus": "AES_TOK", "json": "UUID_TOK"}
    transform.assert_called_once_with(
        metric_data_id=575975, trace_data_id=-1, log_data_id=-1, bk_biz_id=555, app_name=""
    )


def test_get_report_token_format_prometheus_only(mocker):
    """format=prometheus：只出 aes256 token、不读 DataSource；非默认 dataid/app_name 透传。"""
    transform = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    result = run_readonly_command(
        {
            "command_id": "get_report_token",
            "params": {
                "format": "prometheus",
                "metric_data_id": 575975,
                "trace_data_id": 111,
                "log_data_id": 222,
                "bk_biz_id": 555,
                "app_name": "app",
            },
        }
    )
    assert result["format"] == "prometheus"
    assert result["tokens"] == {"prometheus": "AES_TOK"}
    transform.assert_called_once_with(
        metric_data_id=575975, trace_data_id=111, log_data_id=222, bk_biz_id=555, app_name="app"
    )


def test_get_report_token_format_json_reads_datasource(mocker):
    """format=json：token=DataSource.token（uuid），按 metric_data_id 读取，不算 aes256。"""
    ds = _mock_ds_token(mocker, token="UUID_TOK")
    transform = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token")
    result = run_readonly_command(
        {"command_id": "get_report_token", "params": {"format": "json", "metric_data_id": 575975}}
    )
    assert result["tokens"] == {"json": "UUID_TOK"}
    ds.objects.filter.assert_called_once_with(bk_data_id=575975)
    transform.assert_not_called()


def test_get_report_token_format_alias(mocker):
    """format 别名：otlp→prometheus、proxy→json。"""
    mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    r1 = run_readonly_command({"command_id": "get_report_token", "params": {"format": "otlp", "metric_data_id": 1}})
    assert r1["format"] == "prometheus"
    assert "prometheus" in r1["tokens"]
    _mock_ds_token(mocker, token="UUID_TOK")
    r2 = run_readonly_command({"command_id": "get_report_token", "params": {"format": "proxy", "metric_data_id": 1}})
    assert r2["format"] == "json"
    assert r2["tokens"] == {"json": "UUID_TOK"}


def test_get_report_token_json_requires_metric_data_id():
    with pytest.raises(CustomException, match="metric_data_id is required for json"):
        run_readonly_command({"command_id": "get_report_token", "params": {"format": "json", "trace_data_id": 1}})


def test_get_report_token_json_datasource_not_found(mocker):
    _mock_ds_token(mocker, found=False)
    with pytest.raises(CustomException, match="json/proxy token unavailable"):
        run_readonly_command({"command_id": "get_report_token", "params": {"format": "json", "metric_data_id": 999}})


def test_get_report_token_json_empty_token_strict(mocker):
    """format=json + DataSource.token 为空串（系统/内建源）→ 严格失败，不回显空 token。"""
    _mock_ds_token(mocker, token="", found=True)
    with pytest.raises(CustomException, match="empty token"):
        run_readonly_command({"command_id": "get_report_token", "params": {"format": "json", "metric_data_id": 1001}})


def test_get_report_token_all_best_effort_when_no_datasource(mocker):
    """format=all 且 DataSource 查不到：prometheus 照常给出，json 置 null + notes，不丢弃 prometheus。"""
    mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    _mock_ds_token(mocker, found=False)
    result = run_readonly_command(
        {"command_id": "get_report_token", "params": {"metric_data_id": 999, "bk_biz_id": 555}}
    )
    assert result["tokens"]["prometheus"] == "AES_TOK"
    assert result["tokens"]["json"] is None
    assert any("json token unavailable" in n for n in result.get("notes", []))


def test_get_report_token_all_best_effort_when_empty_token(mocker):
    """format=all 且 DataSource.token 为空串：json 置 null + notes，prometheus 照常。"""
    mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    _mock_ds_token(mocker, token="", found=True)
    result = run_readonly_command(
        {"command_id": "get_report_token", "params": {"metric_data_id": 1001, "bk_biz_id": 555}}
    )
    assert result["tokens"]["prometheus"] == "AES_TOK"
    assert result["tokens"]["json"] is None
    assert any("empty token" in n for n in result.get("notes", []))


def test_get_report_token_all_requires_metric_data_id(mocker):
    """format=all（默认）即便 prometheus 有 trace dataid 可算，json 仍需 metric_data_id。"""
    mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="AES_TOK")
    with pytest.raises(CustomException, match="metric_data_id is required for json"):
        run_readonly_command({"command_id": "get_report_token", "params": {"trace_data_id": 111}})


def test_get_report_token_all_v1_both_tokens(mocker):
    """format=all + token_version=v1：prometheus 走 v1_token，json 读 DataSource，两者都出。"""
    mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_v1_token", return_value="AES_V1")
    _mock_ds_token(mocker, token="UUID_TOK")
    result = run_readonly_command(
        {
            "command_id": "get_report_token",
            "params": {"metric_data_id": 575975, "profile_data_id": 7, "token_version": "v1"},
        }
    )
    assert result["tokens"] == {"prometheus": "AES_V1", "json": "UUID_TOK"}
    assert result["profile_data_id"] == 7


def test_get_report_token_prometheus_defaults_absent_ids(mocker):
    """format=prometheus 只传 metric_data_id：其余 dataid 落 -1、app_name 落 ""。"""
    transform = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="T")
    run_readonly_command(
        {"command_id": "get_report_token", "params": {"format": "prometheus", "metric_data_id": 575975}}
    )
    transform.assert_called_once_with(
        metric_data_id=575975, trace_data_id=-1, log_data_id=-1, bk_biz_id=-1, app_name=""
    )


def test_get_report_token_prometheus_rejects_no_data_id():
    with pytest.raises(CustomException, match="required for prometheus format"):
        run_readonly_command({"command_id": "get_report_token", "params": {"format": "prometheus", "bk_biz_id": 555}})


def test_get_report_token_prometheus_accepts_trace_only(mocker):
    """prometheus trace-only（metric 缺省）也可算，不被 metric 必填误伤。"""
    transform = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_token", return_value="T")
    result = run_readonly_command(
        {"command_id": "get_report_token", "params": {"format": "prometheus", "trace_data_id": 888}}
    )
    assert result["tokens"]["prometheus"] == "T"
    transform.assert_called_once_with(
        metric_data_id=-1, trace_data_id=888, log_data_id=-1, bk_biz_id=-1, app_name=""
    )


def test_get_report_token_rejects_non_int_metric_data_id():
    with pytest.raises(CustomException, match="metric_data_id must be an integer"):
        run_readonly_command(
            {"command_id": "get_report_token", "params": {"format": "prometheus", "metric_data_id": "abc"}}
        )


def test_get_report_token_v1_dispatches_v1_token(mocker):
    """format=prometheus + token_version=v1 走 transform_data_id_to_v1_token，回显 profile_data_id。"""
    transform_v1 = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_v1_token", return_value="AES_V1")
    result = run_readonly_command(
        {
            "command_id": "get_report_token",
            "params": {
                "format": "prometheus",
                "metric_data_id": 575975,
                "bk_biz_id": 555,
                "profile_data_id": 123,
                "token_version": "v1",
            },
        }
    )
    assert result["tokens"]["prometheus"] == "AES_V1"
    assert result["token_version"] == "v1"
    assert result["profile_data_id"] == 123
    transform_v1.assert_called_once_with(
        metric_data_id=575975, trace_data_id=-1, log_data_id=-1, profile_data_id=123, bk_biz_id=555, app_name=""
    )


def test_get_report_token_normalizes_token_version(mocker):
    """token_version 大小写/空白归一：'  V1 ' → v1。"""
    transform_v1 = mocker.patch("bkmonitor.utils.cipher.transform_data_id_to_v1_token", return_value="T")
    result = run_readonly_command(
        {
            "command_id": "get_report_token",
            "params": {"format": "prometheus", "metric_data_id": 1, "token_version": "  V1 "},
        }
    )
    assert result["token_version"] == "v1"
    transform_v1.assert_called_once()


def test_get_report_token_rejects_profile_data_id_without_v1():
    """非（prometheus+v1）却传 profile_data_id → 显式拒绝，不静默丢弃。"""
    with pytest.raises(CustomException, match="profile_data_id is only valid"):
        run_readonly_command(
            {"command_id": "get_report_token", "params": {"format": "prometheus", "metric_data_id": 1, "profile_data_id": 2}}
        )


def test_get_report_token_rejects_bad_token_version():
    with pytest.raises(CustomException, match="token_version must be 'v0' or 'v1'"):
        run_readonly_command(
            {"command_id": "get_report_token", "params": {"format": "prometheus", "metric_data_id": 1, "token_version": "v2"}}
        )


def test_get_report_token_rejects_bad_format():
    with pytest.raises(CustomException, match="format must be"):
        run_readonly_command({"command_id": "get_report_token", "params": {"metric_data_id": 1, "format": "xml"}})
