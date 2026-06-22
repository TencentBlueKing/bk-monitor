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
    """多租户下 OS v2 承载系统事件 custom event 策略，校验聚合维度与恢复语义最终形态。"""
    import importlib

    from django.test import override_settings

    from monitor_web.strategies.default_settings.os import v2 as os_v2

    try:
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(os_v2)
            strategies = {s["metric_field"]: s for s in os_v2.DEFAULT_OS_STRATEGIES}

            # 4 个离散事件必然内置（PingUnreachable 受 Platform.te 控制，不强制断言其存在）
            assert {"AgentLost", "DiskReadonly", "CoreFile", "OOM"} <= set(strategies)

            # v2 仅承载 custom event 系统事件：走 custom 事件链路、按主机聚合、统一 close 恢复语义
            for strategy in os_v2.DEFAULT_OS_STRATEGIES:
                assert strategy["data_source_label"] == "custom"
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
    finally:
        # 还原为当前部署模式下的定义，避免污染其他用例
        importlib.reload(os_v2)


def test_os_v1_v3_multi_tenant_builtin_event_declaration():
    """真实多租户导入态下，主机重启/进程端口由 v3 声明，v1 不声明。

    关键回归：v1 把 os_restart/proc_port 圈在 `if not ENABLE_MULTI_TENANT_MODE` 块内，多租户
    reload 后 v1 不含这两条；必须由多租户专用 v3（bk_monitor 源伪事件）声明，否则指标缓存里
    有 bk_monitor.os_restart/proc_port，但策略定义侧没有对应项，loader 无东西可建。
    """
    import importlib

    from django.test import override_settings

    from monitor_web.strategies.default_settings.os import v1 as os_v1
    from monitor_web.strategies.default_settings.os import v3 as os_v3

    try:
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(os_v1)
            importlib.reload(os_v3)
            v1_fields = {s["metric_field"] for s in os_v1.DEFAULT_OS_STRATEGIES}
            v3_fields = {s["metric_field"] for s in os_v3.DEFAULT_OS_STRATEGIES}

            # v1 多租户不声明 os_restart/proc_port（与 gse 事件同处单租户块，被门控掉）
            assert "os_restart" not in v1_fields
            assert "proc_port" not in v1_fields

            # v3 多租户声明 os_restart/proc_port，且为 bk_monitor + event 伪事件（非 custom、非降级时序）
            assert {"os_restart", "proc_port"} == v3_fields
            for strategy in os_v3.DEFAULT_OS_STRATEGIES:
                assert strategy["data_source_label"] == "bk_monitor"
                assert strategy["data_type_label"] == "event"

            # 进程端口保留富维度，loader 重定向 system.proc_port 后由 ProcPort 算法判定（与单租户一致）
            proc_port = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "proc_port")
            assert {"nonlisten", "not_accurate_listen", "bind_ip"} <= set(proc_port["agg_dimension"])

            # 主机重启 MAX 聚合 + close 恢复语义，与单租户等价
            os_restart = next(s for s in os_v3.DEFAULT_OS_STRATEGIES if s["metric_field"] == "os_restart")
            assert os_restart["agg_method"] == "MAX"
            assert os_restart["recovery_status_setter"] == "close"
    finally:
        # 还原为当前部署模式下的定义，避免污染其他用例
        importlib.reload(os_v1)
        importlib.reload(os_v3)


def test_os_strategies_list_registers_v2_v3_only_in_multi_tenant():
    """端到端：多租户下 default_strategy_settings 注册 v1+v2+v3；单租户只注册 v1。

    保证 loader.get_default_strategy() 在真实多租户能拿到 v3（主机重启/进程端口的策略声明来源），
    否则即便指标缓存就绪、v3 模块声明了策略，版本未注册同样建不出来。
    """
    import importlib

    from django.test import override_settings

    from monitor_web.strategies import default_settings as ds

    try:
        with override_settings(ENABLE_MULTI_TENANT_MODE=True):
            importlib.reload(ds)
            versions = [item["version"] for item in ds.default_strategy_settings.DEFAULT_OS_STRATEGIES_LIST]
            assert versions == ["v1", "v2", "v3"]

        with override_settings(ENABLE_MULTI_TENANT_MODE=False):
            importlib.reload(ds)
            versions = [item["version"] for item in ds.default_strategy_settings.DEFAULT_OS_STRATEGIES_LIST]
            assert versions == ["v1"]
    finally:
        # 还原包级模块，避免 reload 污染其它用例
        importlib.reload(ds)
