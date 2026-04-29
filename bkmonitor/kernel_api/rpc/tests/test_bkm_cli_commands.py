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


# ── 其他白名单命令（尚未实现）────────────────────────────────────────────────


@pytest.mark.parametrize("command_id", ["strategy_check", "context_preview", "check_bcs_cluster_status"])
def test_run_readonly_command_not_yet_implemented(command_id):
    """已在白名单但尚未实现的命令应返回明确错误，不能静默成功。"""
    with pytest.raises(CustomException, match="not yet implemented"):
        run_readonly_command({"command_id": command_id, "params": {}})
