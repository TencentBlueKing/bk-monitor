"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_databus.constants import LogPluginInfo, TargetNodeTypeEnum
from apps.log_databus.handlers.collector_scenario import CollectorScenario
from apps.log_databus.nodeman_v3.constants import (
    SPEC_TYPE_SPECIFY_PLUGIN,
    SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
)
from apps.log_databus.nodeman_v3.identity import build_sub_config_name
from apps.log_databus.nodeman_v3.policy import SubscriptionStepsTranslator, build_policy_payload
from apps.tests.log_databus.nodeman_v3_test_utils import nodeman_v3_toggle
from apps.log_search.constants import AgentStatusEnum, CollectorScenarioEnum

PLUGIN_NAME = LogPluginInfo.NAME
BK_BIZ_ID = 2

# 六种物理机采集场景及各自的最小必需参数。
# 参数刻意走真实的 collector_scenario.get_subscription_steps，而不是手搓 steps：
# 本单要证明的正是「V2 的六种场景参数生成逻辑一行不改也能在 V3 下正确落地」，
# 手搓 steps 等于把要验证的那一段绕过去了。
SCENARIO_PARAMS = {
    CollectorScenarioEnum.ROW.value: {
        "paths": ["/var/log/row.log"],
        "encoding": "UTF-8",
        "conditions": {"type": "none"},
        # _deal_text_public_params 对这四个键是必需（直接下标取值，缺了就 KeyError），
        # 文本类场景（行/段）都要带
        "tail_files": True,
        "ignore_older": 86400,
        "max_bytes": 204800,
    },
    CollectorScenarioEnum.SECTION.value: {
        "paths": ["/var/log/section.log"],
        "encoding": "UTF-8",
        "conditions": {"type": "none"},
        "tail_files": True,
        "ignore_older": 86400,
        "max_bytes": 204800,
        "multiline_pattern": r"^\d{4}-\d{2}-\d{2}",
        "multiline_max_lines": 10,
        "multiline_timeout": 2,
    },
    CollectorScenarioEnum.WIN_EVENT.value: {
        "conditions": {"type": "none"},
        "winlog_name": ["Application", "Security"],
        "winlog_level": ["error"],
        "winlog_event_id": ["1-100"],
    },
    CollectorScenarioEnum.REDIS_SLOWLOG.value: {
        "conditions": {"type": "none"},
        "redis_hosts": [{"host": "127.0.0.1", "port": 6379, "password": "x"}],
    },
    CollectorScenarioEnum.SYSLOG.value: {
        "conditions": {"type": "none"},
        "syslog_protocol": "UDP",
        "syslog_port": 514,
        "syslog_monitor_host": "127.0.0.1",
    },
    CollectorScenarioEnum.KAFKA.value: {
        "conditions": {"type": "none"},
        "kafka_hosts": ["127.0.0.1:9092"],
        "kafka_topics": ["topic-a"],
        "kafka_group_id": "bklog-test",
        "kafka_initial_offset": "newest",
    },
}


def build_real_steps(scenario_id: str, data_id: int, collector_config_id: int) -> list[dict]:
    scenario = CollectorScenario.get_instance(collector_scenario_id=scenario_id)
    return scenario.get_subscription_steps(data_id, dict(SCENARIO_PARAMS[scenario_id]), collector_config_id, None)


class SixScenarioSpecTest(TestCase):
    """六种物理机采集场景在 V3 下的期望态"""

    def test_every_scenario_produces_sub_config_spec(self):
        for index, scenario_id in enumerate(SCENARIO_PARAMS, start=1):
            with self.subTest(scenario=scenario_id):
                steps = build_real_steps(scenario_id, 1000 + index, 8000 + index)
                specs = SubscriptionStepsTranslator().build_specs(steps)
                self.assertEqual([spec["type"] for spec in specs], [SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE])

    def test_every_scenario_carries_its_own_dataid(self):
        # 「各场景 dataid 正确，无重复无漏报」：dataid 错了数据会静默落到别的链路上
        seen = {}
        for index, scenario_id in enumerate(SCENARIO_PARAMS, start=1):
            data_id = 1000 + index
            steps = build_real_steps(scenario_id, data_id, 8000 + index)
            specs = SubscriptionStepsTranslator().build_specs(steps)
            context = specs[0]["param"]["custom_config_context"]
            with self.subTest(scenario=scenario_id):
                self.assertEqual(context["dataid"], data_id)
            seen[scenario_id] = context["dataid"]
        self.assertEqual(len(set(seen.values())), len(SCENARIO_PARAMS))

    def test_no_scenario_leaks_specify_plugin_into_collector_policy(self):
        # 采集项策略一旦带 specify_plugin，同机后建的采集项会被静默剔除并删掉已生效子配置，
        # 成因链见 docs/节点管理V3适配/deploypolicy冲突消解_同机多采集项互斥_取证.md
        for index, scenario_id in enumerate(SCENARIO_PARAMS, start=1):
            with self.subTest(scenario=scenario_id):
                payload = build_policy_payload(
                    collector_config_id=8000 + index,
                    bk_biz_id=BK_BIZ_ID,
                    target_node_type=TargetNodeTypeEnum.INSTANCE.value,
                    target_nodes=[{"bk_host_id": 11}],
                    steps=build_real_steps(scenario_id, 1000 + index, 8000 + index),
                )
                self.assertNotIn(SPEC_TYPE_SPECIFY_PLUGIN, [spec["type"] for spec in payload["specs"]])

    def test_no_scenario_puts_main_config_into_sub_config_spec(self):
        # 主配置由业务级安装策略承载。混进子配置 spec 会让节点管理重写主配置，
        # 进而影响同机其它采集项
        for index, scenario_id in enumerate(SCENARIO_PARAMS, start=1):
            with self.subTest(scenario=scenario_id):
                steps = build_real_steps(scenario_id, 1000 + index, 8000 + index)
                specs = SubscriptionStepsTranslator().build_specs(steps)
                details = specs[0]["param"]["config_files_detail"]
                self.assertTrue(details)
                self.assertTrue(all(detail["is_main_config"] is False for detail in details))

    def test_every_scenario_fingerprint_is_distinct(self):
        # 指纹相同会让第二个场景的期望态被当成「无变化」而跳过下发
        from apps.log_databus.nodeman_v3.policy import calculate_fingerprint

        fingerprints = set()
        for index, scenario_id in enumerate(SCENARIO_PARAMS, start=1):
            payload = build_policy_payload(
                collector_config_id=8000 + index,
                bk_biz_id=BK_BIZ_ID,
                target_node_type=TargetNodeTypeEnum.INSTANCE.value,
                target_nodes=[{"bk_host_id": 11}],
                steps=build_real_steps(scenario_id, 1000 + index, 8000 + index),
            )
            fingerprints.add(calculate_fingerprint(payload))
        self.assertEqual(len(fingerprints), len(SCENARIO_PARAMS))


class SameHostIsolationTest(TestCase):
    """同机多场景采集项的隔离"""

    def test_three_scenarios_on_same_host_land_in_distinct_files(self):
        # 验收项「同机不少于三份不同场景采集项，删一份其余出数不变」的静态部分：
        # 落地文件名必须两两不同，否则后下发的会覆盖前一个
        scenario_ids = [
            CollectorScenarioEnum.ROW.value,
            CollectorScenarioEnum.SECTION.value,
            CollectorScenarioEnum.REDIS_SLOWLOG.value,
        ]
        names = set()
        for policy_id, scenario_id in enumerate(scenario_ids, start=1001):
            steps = build_real_steps(scenario_id, 1000 + policy_id, policy_id)
            for template_name in SubscriptionStepsTranslator().sub_config_template_names(steps):
                names.add(build_sub_config_name(template_name, policy_id))
        self.assertEqual(len(names), len(scenario_ids))


@nodeman_v3_toggle("on")
class V2OutboundZeroGateTest(TestCase):
    """
    物理机采集路径的 V2 出站清零门禁。

    做法是把 V2 的 NodeApi / BKNodeApi 整体替换成「一调用就失败」的桩，然后跑完采集项的
    创建、启用、停用、删除、重新下发。任何一次 V2 出站都会让用例直接失败，并且报出是哪个接口。

    只 patch 不断言调用次数的写法在这里不够用：V2 出站往往藏在异常分支里，正常路径跑不到，
    而一旦生产上走进那个分支就是静默双写。让桩本身抛异常才能把这类路径逼出来。
    """

    V2_API_ATTRS = [
        "get_subscription_info",
        "get_subscription_task_status",
        "subscription_statistic",
        "query_host_subscriptions",
        "ipchooser_host_details",
        "create_subscription",
        "update_subscription_info",
        "switch_subscription",
        "run_subscription_task",
        "delete_subscription",
        "plugin_search",
    ]

    def setUp(self):
        from apps.log_databus.nodeman_v3.reconciler import CollectorPolicyReconciler  # noqa: F401
        from apps.tests.log_databus.test_nodeman_v3_contract import FakeNodeManV3Client

        self.collector_config = SimpleNamespace(
            collector_config_id=8101,
            bk_biz_id=BK_BIZ_ID,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 11}],
            description="v2 zero gate",
            collector_scenario_id=CollectorScenarioEnum.ROW.value,
            bk_data_id=1001,
            data_link_id=None,
            data_encoding="UTF-8",
            collector_config_overlay=None,
            params=dict(SCENARIO_PARAMS[CollectorScenarioEnum.ROW.value]),
        )

        self.v3_client = FakeNodeManV3Client()
        patcher = patch(
            "apps.log_databus.nodeman_v3.reconciler.get_client", side_effect=lambda *a, **kw: self.v3_client
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.v2_calls = []
        self._install_v2_tripwires()

    def _install_v2_tripwires(self):
        from apps.api import NodeApi
        from apps.api.modules.bk_node import BKNodeApi

        def make_tripwire(name):
            def _tripwire(*args, **kwargs):
                self.v2_calls.append(name)
                raise AssertionError(f"V3 模式下不应调用 V2 节点管理接口: {name}")

            return _tripwire

        for module in (NodeApi, BKNodeApi):
            for attr in self.V2_API_ATTRS:
                if not hasattr(module, attr):
                    continue
                patcher = patch.object(module, attr, side_effect=make_tripwire(attr))
                patcher.start()
                self.addCleanup(patcher.stop)

    def _installer(self):
        from apps.log_databus.nodeman_v3.installer import NodeManV3CollectorInstaller

        return NodeManV3CollectorInstaller(self.collector_config)

    def test_full_lifecycle_makes_no_v2_outbound_call(self):
        installer = self._installer()
        installer.apply(self.collector_config.params)
        installer.start()
        installer.rerun()
        installer.stop()
        installer.destroy()
        self.assertEqual(self.v2_calls, [])

    def test_lifecycle_only_touches_v3_deploy_policy_apis(self):
        installer = self._installer()
        installer.apply(self.collector_config.params)
        installer.stop()

        # 物理机采集路径只允许碰部署策略这四个接口。多出任何一个（尤其是 apply_subconfig /
        # remove_subconfig）都说明有人绕过了「期望态收敛」这条唯一通路，那条路没有指纹与
        # generation 记账，会直接破坏状态回读
        allowed = {"list", "create", "update", "execute"}
        actual = {name for name, _payload in self.v3_client.calls}
        self.assertTrue(actual, "本轮生命周期没有产生任何 V3 出站，用例本身失效了")
        self.assertEqual(actual - allowed, set())
        # 采集项策略与安装策略都必须被收敛到
        self.assertEqual(
            {self.v3_client.policy_kind_of(name, payload) for name, payload in self.v3_client.calls},
            {"collector", "plugin"},
        )

    def test_stop_removes_sub_configs_without_disabling_policy(self):
        # 停用必须表达为空范围而不是 disable：被 disable 的策略不再参与收敛，
        # 已下发的子配置会永久残留在主机上继续采集
        installer = self._installer()
        installer.apply(self.collector_config.params)
        installer.stop()

        collector_updates = self.v3_client.payloads_of("update", "collector")
        self.assertTrue(collector_updates)
        last = collector_updates[-1]["deploy_policies"][0]
        self.assertEqual(last["scopes"], [])
        self.assertTrue(last["enabled"])


class AuditPrefixTest(TestCase):
    """审计前缀是门禁的运行期取证依据，不能随意改名"""

    def test_outbound_audit_prefix_is_stable(self):
        from apps.log_databus.nodeman_v3.audit import NODEMAN_OUTBOUND_AUDIT_PREFIX

        self.assertEqual(NODEMAN_OUTBOUND_AUDIT_PREFIX, "[nodeman_outbound_audit]")

    def test_audit_records_metadata_only(self):
        # 子配置内容里可能带业务日志路径与 Redis 口令，审计日志不能记请求体
        from apps.log_databus.nodeman_v3.audit import record_outbound_audit

        with patch("apps.log_databus.nodeman_v3.audit.logger") as mock_logger:
            record_outbound_audit(
                api_version="v3",
                action="deploy_policy/create",
                method="POST",
                outcome="success",
                bk_biz_id=BK_BIZ_ID,
                operation_id="op-1",
            )
        message = mock_logger.info.call_args[0][0]
        self.assertIn("[nodeman_outbound_audit]", message)
        self.assertIn("deploy_policy/create", message)
        for leaked in ("paths", "password", "specs", "scopes", "custom_config_context"):
            self.assertNotIn(leaked, message)


class FakeHostListClient:
    def __init__(self, items):
        self.items = items
        self.payloads = []

    def list_hosts(self, payload):
        self.payloads.append(payload)
        wanted = set(payload["exact_include_conditions"]["bk_host_id"])
        # 真实接口按 bk_host_id 过滤，查不到的主机直接不出现在返回里 —— 不会回一条 offline 占位
        return {"items": [item for item in self.items if item["bk_host_id"] in wanted]}


@nodeman_v3_toggle("on")
class AgentStatusV3Test(TestCase):
    """V3 下 Agent 状态改走 topo/host/list，node_status 的映射口径不能有默认在线的口子"""

    def _status(self, items, bk_host_ids):
        from apps.log_search.handlers.biz import BizHandler

        client = FakeHostListClient(items)
        with patch("apps.log_databus.nodeman_v3.client.get_client", return_value=client):
            return BizHandler(BK_BIZ_ID)._get_agent_status_v3(bk_host_ids), client

    def test_running_is_online_and_others_are_not(self):
        items = [
            {"bk_host_id": 1, "state": {"node_status": "running"}},
            {"bk_host_id": 2, "state": {"node_status": "starting"}},
            {"bk_host_id": 3, "state": {"node_status": "damaged"}},
        ]
        result, _ = self._status(items, [1, 2, 3])
        self.assertEqual(result[1], AgentStatusEnum.ON.value)
        # starting / upgrade 不能算在线：Agent 还没起来却显示正常，用户会以为是配置下发失败而反复重试
        self.assertEqual(result[2], AgentStatusEnum.NOT_EXIST.value)
        self.assertEqual(result[3], AgentStatusEnum.NOT_EXIST.value)

    def test_host_absent_from_response_is_not_online(self):
        # AgentStatusEnum.ON == 0，用 defaultdict(int) 兜底会把没在节点管理注册过的主机
        # 报成在线，调用方的 agent_error_count 直接少算
        result, _ = self._status([{"bk_host_id": 1, "state": {"node_status": "running"}}], [1, 999])
        self.assertEqual(result[999], AgentStatusEnum.NOT_EXIST.value)
        self.assertEqual(len([s for s in result.values() if s != AgentStatusEnum.ON.value]), 1)

    def test_missing_state_is_not_online(self):
        result, _ = self._status([{"bk_host_id": 1}], [1])
        self.assertEqual(result[1], AgentStatusEnum.NOT_EXIST.value)

    def test_pagination_uses_offset_not_start(self):
        # topo/host/list 的分页字段是 offset；传 start 会被忽略而静默回第一页
        _, client = self._status([], [1])
        self.assertIn("offset", client.payloads[0]["page"])
        self.assertNotIn("start", client.payloads[0]["page"])

    def test_hosts_are_chunked_to_page_limit(self):
        bk_host_ids = list(range(1, 1201))
        _, client = self._status([], bk_host_ids)
        # 每片必须 <= limit，否则超出的主机会被接口截掉而落到「不在线」，看起来像整批 Agent 掉线
        for payload in client.payloads:
            self.assertLessEqual(len(payload["exact_include_conditions"]["bk_host_id"]), payload["page"]["limit"])
        queried = [h for payload in client.payloads for h in payload["exact_include_conditions"]["bk_host_id"]]
        self.assertEqual(sorted(queried), bk_host_ids)

    def test_empty_input_makes_no_request(self):
        result, client = self._status([], [])
        self.assertEqual(result, {})
        self.assertEqual(client.payloads, [])
