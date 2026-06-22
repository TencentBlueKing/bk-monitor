"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.strategies.default_settings import default_strategy_settings
from monitor_web.strategies.default_settings.k8s.v1 import DEFAULT_K8S_STRATEGIES as DEFAULT_K8S_STRATEGIES_V1
from monitor_web.strategies.default_settings.k8s.v2 import DEFAULT_K8S_STRATEGIES as DEFAULT_K8S_STRATEGIES_V2


def test_get_k8s_strategies():
    strategies_list = default_strategy_settings.DEFAULT_K8S_STRATEGIES_LIST
    assert strategies_list[0]["version"] == "v1"
    module = strategies_list[0]["module"]
    assert module.DEFAULT_K8S_STRATEGIES == DEFAULT_K8S_STRATEGIES_V1

    assert strategies_list[1]["version"] == "v2"
    module = strategies_list[1]["module"]
    assert module.DEFAULT_K8S_STRATEGIES == DEFAULT_K8S_STRATEGIES_V2


def test_os_v2_multi_tenant_system_event_strategies():
    """多租户下 OS v2 内置策略：5 类 custom event 系统事件 + 主机重启/进程端口时序事件，校验最终形态。"""
    import importlib

    from django.test import override_settings

    from monitor_web.strategies.default_settings.os import v2 as os_v2

    try:
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(os_v2)
            strategies = {s["metric_field"]: s for s in os_v2.DEFAULT_OS_STRATEGIES}

            # 4 个离散事件必然内置（PingUnreachable 受 Platform.te 控制，不强制断言其存在）
            assert {"AgentLost", "DiskReadonly", "CoreFile", "OOM"} <= set(strategies)

            # custom event 系统事件：走 custom 事件链路、按主机聚合、统一 close 恢复语义
            event_strategies = [s for s in os_v2.DEFAULT_OS_STRATEGIES if s["data_source_label"] == "custom"]
            assert event_strategies, "多租户下应至少内置一类 custom event 系统事件"
            for strategy in event_strategies:
                assert strategy["data_type_label"] == "event"
                # 必须按主机聚合，避免全业务聚合丢失主机归属
                assert strategy["agg_dimension"][:2] == ["bk_target_ip", "bk_target_cloud_id"]
                # 离散系统事件统一 close 恢复语义
                assert strategy["recovery_status_setter"] == "close"

            # 磁盘只读 / Corefile 叠加实例维度，区分同主机不同盘 / 不同 corefile 信号
            assert strategies["DiskReadonly"]["agg_dimension"] == [
                "bk_target_ip",
                "bk_target_cloud_id",
                "position",
                "type",
                "fs",
            ]
            assert strategies["CoreFile"]["agg_dimension"] == [
                "bk_target_ip",
                "bk_target_cloud_id",
                "executable_path",
                "executable",
                "signal",
            ]

            # 主机重启：时序 system.env.uptime + OsRestart 检测算法（event_detect 标记），与单租户等价
            os_restart = strategies["uptime"]
            assert os_restart["data_source_label"] == "bk_monitor"
            assert os_restart["data_type_label"] == "time_series"
            assert os_restart["result_table_id"] == "system.env"
            assert os_restart["event_detect"] == "os_restart"
            assert os_restart["agg_dimension"] == ["bk_target_ip", "bk_target_cloud_id"]
            assert os_restart["recovery_status_setter"] == "close"

            # 进程端口：降级版时序 process.port.alive 存活阈值（无 event_detect，走普通 Threshold）
            proc_port = strategies["alive"]
            assert proc_port["data_source_label"] == "bk_monitor"
            assert proc_port["data_type_label"] == "time_series"
            assert proc_port["result_table_id"] == "process.port"
            assert "event_detect" not in proc_port
            assert proc_port["threshold"] == 1
            assert proc_port["method"] == "lt"
    finally:
        # 还原为当前部署模式下的定义，避免污染其他用例
        importlib.reload(os_v2)
