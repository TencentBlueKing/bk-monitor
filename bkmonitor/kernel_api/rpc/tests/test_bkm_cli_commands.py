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
    # effective_value 走 getattr(settings, name)；_wrapped 不是 DynamicSettings → static_default 标 unavailable。
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
        "static_default",
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
