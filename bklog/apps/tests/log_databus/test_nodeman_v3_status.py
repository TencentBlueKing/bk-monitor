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

from django.test import TestCase, override_settings

from apps.log_databus.constants import CollectStatus, LogPluginInfo, RunStatus, TargetNodeTypeEnum
from apps.log_databus.nodeman_v3.constants import (
    NodeManV3OperationType,
    NodeManV3TargetState,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_resource_key, build_sub_config_name
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3Operation,
    NodeManV3SubConfigTarget,
    NodeManV3Workflow,
)
from apps.log_databus.nodeman_v3.status import (
    CollectorStatusReader,
    PAGE_LIMIT,
    build_v2_compatible_instance_data,
    summary_to_status,
)

PLUGIN_NAME = LogPluginInfo.NAME
TEMPLATE_NAME = f"{PLUGIN_NAME}.conf"
BK_BIZ_ID = 2
COLLECTOR_CONFIG_ID = 8001
POLICY_ID = 1001
TRIGGER_ID = "trigger-1001-1"
WORKFLOW_ID = "workflow-abc"


class FakeStatusClient:
    """按 NodeMan v3 proto 的真实返回结构造桩"""

    def __init__(self):
        self.tenant_id = "system"
        self.calls = []
        self.workflow_items = [{"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "deploy_policy_ids": [POLICY_ID]}]
        # bk_host_id -> life_cycle.state
        self.host_states = {}
        # bk_host_id -> 该主机上**额外**几条 operation 的 state（同机多 spec 会各出一条）
        self.host_extra_states = {}
        # bk_host_id -> process_info.status
        self.process_states = {}
        self.retry_payloads = []
        self.instance_logs = {"install": {"message": {"logs": []}}}

    @staticmethod
    def _paged(items, payload):
        """
        按真实接口语义切页。

        这三个接口（workflow/list、workflow/operation/list、process/list）只认
        `page.offset` 与 `page.limit`，**刻意不认 `page.start`**：把 deploy_policy/list 的
        `{count, start, limit}` 传过来时 gin 会静默忽略未知字段、offset 退化成 0，翻页永远停在
        第一页。桩必须能把这个退化暴露成用例失败，否则这类 bug 只能等联调才发现。
        """
        page = payload.get("page") or {}
        assert "start" not in page, "workflow/process 系列接口的分页字段是 offset，不是 start"
        limit = page.get("limit") or 0
        assert 0 < limit <= 500, "page.limit 必填且必须落在 (0, 500]"
        offset = page.get("offset") or 0
        return items[offset : offset + limit]

    def list_workflows(self, payload):
        self.calls.append(("list_workflows", payload))
        return {"items": self._paged(self.workflow_items, payload), "total": len(self.workflow_items)}

    def list_workflow_operations(self, payload):
        self.calls.append(("list_workflow_operations", payload))
        # 一台主机可以有多条 operation：策略至少带两个 spec（装插件 + 下子配置），各自一条。
        # 桩要能造出这种形状，否则「多条里取最坏」这条规则没法被用例约束住
        operations = []
        for bk_host_id, primary_state in self.host_states.items():
            states = [primary_state, *self.host_extra_states.get(bk_host_id, [])]
            for index, oper_state in enumerate(states):
                suffix = "" if index == 0 else f"-{index}"
                operations.append(
                    {
                        "operation_id": f"op-{bk_host_id}{suffix}",
                        "instance_ids": [f"inst-{bk_host_id}{suffix}"],
                        "plugin_deployment_info": {"bk_host_id": bk_host_id, "plugin_name": PLUGIN_NAME},
                        "latest_oper_inst_brief_data": {"life_cycle": {"state": oper_state}},
                    }
                )
        # total 刻意按「全量条数」返回：真实接口的 total 由顶层 only_count 控制，
        # only_count 为假时可能回 0，所以实现不能拿 total 当翻页边界
        return {"operations": self._paged(operations, payload), "total": len(operations)}

    def list_processes(self, payload):
        self.calls.append(("list_processes", payload))
        items = [
            {"bk_host_id": bk_host_id, "plugin_name": PLUGIN_NAME, "process_info": {"status": status}}
            for bk_host_id, status in self.process_states.items()
        ]
        return {"items": self._paged(items, payload)}

    def list_workflow_operation_instances(self, payload):
        self.calls.append(("list_workflow_operation_instances", payload))
        return {
            "oper_inst_data": [
                {"operation_id": payload["operation_id"][0], "oper_inst_id": "oi-1", "oper_inst_status": "success"}
            ]
        }

    def get_workflow_operation_instance_log(self, payload):
        self.calls.append(("get_workflow_operation_instance_log", payload))
        return {"oper_inst_logs": self.instance_logs}

    def retry_workflow_operation(self, payload):
        self.calls.append(("retry_workflow_operation", payload))
        self.retry_payloads.append(payload)
        return {}

    def call_names(self):
        return [name for name, _payload in self.calls]


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class StatusReaderTest(TestCase):
    def setUp(self):
        self.collector_config = SimpleNamespace(
            collector_config_id=COLLECTOR_CONFIG_ID,
            bk_biz_id=BK_BIZ_ID,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 11}],
            description="unit test",
        )
        self.binding = NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(COLLECTOR_CONFIG_ID),
            bk_biz_id=BK_BIZ_ID,
            bk_tenant_id="system",
            collector_config_id=COLLECTOR_CONFIG_ID,
            deploy_policy_id=POLICY_ID,
            policy_name=f"bklog-collector-{COLLECTOR_CONFIG_ID}",
            sub_config_template_names=[TEMPLATE_NAME],
            generation=2,
        )
        self.operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=2,
        )
        NodeManV3Workflow.objects.create(operation=self.operation, trigger_id=TRIGGER_ID)

        self.client = FakeStatusClient()
        patcher = patch("apps.log_databus.nodeman_v3.status.get_client", side_effect=lambda *a, **kw: self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _add_target(self, bk_host_id, generation=0, is_desired=True):
        return NodeManV3SubConfigTarget.objects.create(
            binding=self.binding,
            bk_host_id=bk_host_id,
            config_file_name=build_sub_config_name(TEMPLATE_NAME, POLICY_ID),
            generation=generation,
            is_desired=is_desired,
        )

    def _reader(self):
        return CollectorStatusReader(self.collector_config)

    # ------------------------------------------------------------------
    # workflow 反查
    # ------------------------------------------------------------------
    def test_workflow_id_resolved_from_trigger_id(self):
        # execute 只返回 trigger_id，而 per-host 详情与重试都要 workflow_id；
        # workflow/list 的精确条件里没有 trigger_id，只能按 deploy_policy_id 过滤后自己匹配
        self.assertEqual(self._reader().resolve_workflow_id(), WORKFLOW_ID)

    def test_workflow_id_is_cached_after_first_resolve(self):
        self._reader().resolve_workflow_id()
        self._reader().resolve_workflow_id()
        self.assertEqual(self.client.call_names().count("list_workflows"), 1)
        self.assertEqual(NodeManV3Workflow.objects.get(operation=self.operation).workflow_id, WORKFLOW_ID)

    def test_workflow_id_resolved_beyond_first_page(self):
        # workflow/list 既不支持按 trigger_id 过滤也没有排序参数，只能按策略拉全量自己匹配，
        # 目标 workflow 完全可能不在第一页。分页写错时这里只会拿到空字符串
        self.client.workflow_items = [
            {"workflow_id": f"noise-{index}", "trigger_id": f"trigger-noise-{index}"}
            for index in range(PAGE_LIMIT + 100)
        ] + self.client.workflow_items

        self.assertEqual(self._reader().resolve_workflow_id(), WORKFLOW_ID)
        self.assertGreater(self.client.call_names().count("list_workflows"), 1)

    def test_host_operations_span_multiple_pages(self):
        # 超过单页上限的业务，分页写错会静默只回前 500 台，状态页的总数从此不可信
        host_count = PAGE_LIMIT + 100
        self.client.host_states = {bk_host_id: "success" for bk_host_id in range(1, host_count + 1)}

        operations = self._reader().fetch_host_operations(WORKFLOW_ID)

        self.assertEqual(len(operations), host_count)
        self.assertIn(host_count, operations)

    def test_unmatched_trigger_id_resolves_to_empty(self):
        # execute 之后 workflow 可能还没落库，这不是错误，下次开页面再试
        self.client.workflow_items = [{"workflow_id": "other", "trigger_id": "trigger-x"}]
        self.assertEqual(self._reader().resolve_workflow_id(), "")

    def test_host_operations_are_keyed_by_host_id(self):
        self.client.host_states = {11: "success", 12: "failed"}
        operations = self._reader().fetch_host_operations(WORKFLOW_ID)
        self.assertEqual(set(operations.keys()), {11, 12})
        self.assertEqual(operations[11]["operation_id"], "op-11")

    # ------------------------------------------------------------------
    # 生效态判定
    # ------------------------------------------------------------------
    def test_success_advances_applied_generation_to_latest(self):
        self._add_target(11, generation=0)
        self.client.host_states = {11: "success"}
        self.client.process_states = {11: "running"}

        states = self._reader().refresh()

        self.assertEqual(states[11].state, NodeManV3TargetState.LATEST)
        self.assertEqual(NodeManV3SubConfigTarget.objects.get(bk_host_id=11).generation, 2)

    def test_old_generation_is_stale_not_failed(self):
        # 生效的是旧版配置，仍在出数。翻红会让用户去重试一个正在正常采集的采集项
        self._add_target(11, generation=1)
        self.client.host_states = {}
        self.client.process_states = {11: "running"}

        states = self._reader().refresh()

        self.assertEqual(states[11].state, NodeManV3TargetState.STALE)

    def test_running_operation_is_dispatching(self):
        self._add_target(11, generation=1)
        self.client.host_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.DISPATCHING)

    def test_failed_operation_is_failed_when_process_running(self):
        self._add_target(11, generation=0)
        self.client.host_states = {11: "failed"}
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.FAILED)

    def test_failed_operation_is_not_failed_when_process_down(self):
        # 采集器进程不 running 时节点管理本来就不下发子配置，还会删掉已有记录
        # （analyze_specific_plugin_sub_config_template.go:113-117、:228-236）。
        # 这是采集器重启期间的常态，判成失败会让每次升级窗口整页翻红
        self._add_target(11, generation=0)
        self.client.host_states = {11: "failed"}
        self.client.process_states = {11: "stopped"}

        status = self._reader().refresh()[11]
        self.assertEqual(status.state, NodeManV3TargetState.ABSENT)
        self.assertIn("采集器进程未运行", str(status.message))

    def test_never_applied_host_is_absent(self):
        self._add_target(11, generation=0)
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.ABSENT)

    def test_removed_host_is_pending_removal_not_absent(self):
        # 删除是异步的，说「不存在」会让人以为已经摘干净了
        self._add_target(12, generation=1, is_desired=False)

        self.assertEqual(self._reader().refresh()[12].state, NodeManV3TargetState.PENDING_REMOVAL)

    def test_process_running_alone_does_not_mean_applied(self):
        # 同机多采集项共用一个 bkunifylogbeat 进程，进程活着只说明别的采集项在跑。
        # 这是 BKL-4 明确要消除的口径错误
        self._add_target(11, generation=0)
        self.client.host_states = {}
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.ABSENT)

    def test_stale_generation_is_not_rolled_back_by_older_workflow(self):
        # 回读到的是一轮更早的 workflow 时，不能把已生效代数往回退
        self._add_target(11, generation=5)
        self.client.host_states = {11: "success"}

        self._reader().refresh()

        self.assertEqual(NodeManV3SubConfigTarget.objects.get(bk_host_id=11).generation, 5)

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------
    def test_worst_operation_wins_when_host_has_several(self):
        # 策略至少两个 spec，同机会有多条 operation。按返回顺序取一条等于随机挑，
        # 会把失败那条盖掉而显示成功
        self._add_target(11, generation=2)
        self.client.host_states = {11: "success"}
        self.client.host_extra_states = {11: ["failed"]}
        self.client.process_states = {11: "running"}
        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.FAILED)

    def test_unknown_operation_state_does_not_advance_generation(self):
        # 节点管理新增一个生命周期状态时，未知值不能被当成成功而推进代次 ——
        # 那等于凭一个读不懂的状态宣布配置已生效
        row = self._add_target(11, generation=0)
        self.client.host_states = {11: "success"}
        self.client.host_extra_states = {11: ["some_future_state"]}
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.ABSENT)

        row.refresh_from_db()
        self.assertEqual(row.generation, 0)

    def test_host_keeping_one_desired_row_is_not_pending_removal(self):
        # 改采集场景会换模板名：同一台仍在范围内的主机上会同时存在「新文件名 desired」与
        # 「旧文件名 已移出」两行。挑中后者会把一台正在正常采集的主机显示成待删除
        self._add_target(11, generation=2)
        NodeManV3SubConfigTarget.objects.create(
            binding=self.binding,
            bk_host_id=11,
            config_file_name=build_sub_config_name(f"{PLUGIN_NAME}_old.conf", POLICY_ID),
            generation=1,
            is_desired=False,
        )
        self.client.host_states = {11: "success"}
        self.client.process_states = {11: "running"}
        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.LATEST)

    def test_removed_row_generation_is_not_advanced(self):
        # 已移出的行 generation 表示「移出时生效的是哪一代」，推进它会让待删除主机显示成已生效最新
        row = self._add_target(11, generation=1, is_desired=False)
        self.client.host_states = {11: "success"}
        self.client.process_states = {11: "running"}

        self._reader().refresh()

        row.refresh_from_db()
        self.assertEqual(row.generation, 1)

    def test_summary_counts_states(self):
        self._add_target(11, generation=2)
        self._add_target(12, generation=1)
        self._add_target(13, generation=0)
        self.client.host_states = {13: "failed"}
        self.client.process_states = {11: "running", 12: "running", 13: "running"}

        summary = self._reader().summary()

        self.assertEqual(summary["total"], 3)
        # 已生效最新 + 已生效旧版都算成功：旧版确实在出数
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["counts"][NodeManV3TargetState.STALE], 1)

    def test_summary_to_status_marks_part_failed(self):
        summary = {"total": 2, "success": 1, "failed": 1, "pending": 0}
        result = summary_to_status(summary, self.collector_config)
        self.assertEqual(result["status"], CollectStatus.FAILED)
        self.assertEqual(result["status_name"], RunStatus.PARTFAILED)

    def test_summary_to_status_prepare_when_no_host_yet(self):
        summary = {"total": 0, "success": 0, "failed": 0, "pending": 0}
        result = summary_to_status(summary, self.collector_config)
        self.assertEqual(result["status"], CollectStatus.PREPARE)

    def test_summary_to_status_success_when_no_target_configured(self):
        collector_config = SimpleNamespace(collector_config_id=1, bk_biz_id=BK_BIZ_ID, target_nodes=[])
        summary = {"total": 0, "success": 0, "failed": 0, "pending": 0}
        self.assertEqual(summary_to_status(summary, collector_config)["status"], CollectStatus.SUCCESS)

    # ------------------------------------------------------------------
    # per-host 详情与重试
    # ------------------------------------------------------------------
    def test_instance_detail_fetches_logs(self):
        self.client.host_states = {11: "failed"}
        detail = self._reader().instance_detail(11)
        self.assertEqual(len(detail["instances"]), 1)
        self.assertIn("oi-1", detail["logs"])

    def test_retry_sends_operation_ids_of_requested_hosts(self):
        self.client.host_states = {11: "failed", 12: "success"}
        self._reader().retry_hosts([11])
        self.assertEqual(self.client.retry_payloads[0]["operation_ids"], ["op-11"])
        self.assertEqual(self.client.retry_payloads[0]["workflow_id"], WORKFLOW_ID)

    def test_retry_fails_closed_without_workflow(self):
        # 静默成功会让用户以为已经重试过了
        self.client.workflow_items = []
        with self.assertRaises(NodeManV3CapabilityBlocked):
            self._reader().retry_hosts([11])

    def test_retry_fails_closed_for_host_without_operation(self):
        self.client.host_states = {12: "success"}
        with self.assertRaises(NodeManV3CapabilityBlocked):
            self._reader().retry_hosts([11])

    def test_reader_without_binding_returns_empty(self):
        other = SimpleNamespace(
            collector_config_id=9999,
            bk_biz_id=BK_BIZ_ID,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[],
            description="",
        )
        self.assertEqual(CollectorStatusReader(other).refresh(), {})


class InstanceDataCompatTest(TestCase):
    """V3 状态 -> V2 实例结构的形状适配"""

    def _status(self, state, **kwargs):
        from apps.log_databus.nodeman_v3.status import HostStatus

        return HostStatus(bk_host_id=11, state=state, **kwargs)

    def test_shape_matches_v2_instance_contract(self):
        data = build_v2_compatible_instance_data(
            {11: self._status(NodeManV3TargetState.LATEST, operation_id="op-11")},
            {11: {"bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0, "bk_host_name": "h1"}},
        )
        host = data[0]["instance_info"]["host"]
        self.assertEqual(data[0]["status"], CollectStatus.SUCCESS)
        self.assertEqual(host["bk_host_id"], 11)
        self.assertEqual(host["bk_host_innerip"], "127.0.0.1")
        self.assertEqual(host["bk_host_name"], "h1")

    def test_stale_is_reported_as_success(self):
        data = build_v2_compatible_instance_data({11: self._status(NodeManV3TargetState.STALE)}, {})
        self.assertEqual(data[0]["status"], CollectStatus.SUCCESS)

    def test_failed_is_reported_as_failed(self):
        data = build_v2_compatible_instance_data({11: self._status(NodeManV3TargetState.FAILED)}, {})
        self.assertEqual(data[0]["status"], CollectStatus.FAILED)

    def test_pending_removal_is_reported_as_terminated(self):
        data = build_v2_compatible_instance_data({11: self._status(NodeManV3TargetState.PENDING_REMOVAL)}, {})
        self.assertEqual(data[0]["status"], CollectStatus.TERMINATED)

    def test_missing_cmdb_host_does_not_break(self):
        # CMDB 里查不到主机（刚下架）时不能抛异常，否则整页 500
        data = build_v2_compatible_instance_data({11: self._status(NodeManV3TargetState.LATEST)}, {})
        self.assertEqual(data[0]["instance_info"]["host"]["bk_host_innerip"], "")


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class HostHandlerWiringTest(TestCase):
    """
    物理机 handler 的 V3 接线。

    单测 status.py 本身证明不了「页面上点重试会走到 V3」：handler 里那几个入口
    （get_subscription_task_detail / retry_instances / retry_target_nodes）原来是直接
    调 V2 订阅接口的，漏接一个就会在 V3-only 环境里打到不存在的订阅 ID 上。
    """

    def setUp(self):
        from apps.log_databus.handlers.collector import HostCollectorHandler

        self.collector_config = CollectorConfig.objects.create(
            collector_config_id=COLLECTOR_CONFIG_ID,
            collector_config_name="nmv3-wiring",
            collector_config_name_en="nmv3_wiring",
            collector_scenario_id="row",
            bk_biz_id=BK_BIZ_ID,
            category_id="host_process",
            target_object_type="HOST",
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 11}],
            bk_data_id=1500998,
            table_id="2_bklog.nmv3_wiring",
        )
        self.binding = NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(COLLECTOR_CONFIG_ID),
            bk_biz_id=BK_BIZ_ID,
            bk_tenant_id="system",
            collector_config_id=COLLECTOR_CONFIG_ID,
            deploy_policy_id=POLICY_ID,
            policy_name=f"bklog-collector-{COLLECTOR_CONFIG_ID}",
            sub_config_template_names=[TEMPLATE_NAME],
            generation=1,
        )
        operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
        )
        NodeManV3Workflow.objects.create(operation=operation, trigger_id=TRIGGER_ID)

        self.client = FakeStatusClient()
        self.client.host_states = {11: "failed"}
        patcher = patch("apps.log_databus.nodeman_v3.status.get_client", side_effect=lambda *a, **kw: self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

        # retry_instances / retry_target_nodes 会投递操作审计任务，本地没有 broker
        record_patcher = patch("apps.log_databus.handlers.collector.host.user_operation_record")
        record_patcher.start()
        self.addCleanup(record_patcher.stop)

        self.handler = HostCollectorHandler(data=self.collector_config)

    def test_instance_id_keeps_v2_shape_so_frontend_needs_no_change(self):
        self.assertEqual(self.handler._parse_bk_host_id("host|instance|host|11"), 11)

    def test_service_instance_id_is_not_mistaken_for_host_id(self):
        # 服务实例 ID 末段也是纯数字，只取末段会把它当主机 ID，重试打到别的机器上
        self.assertEqual(self.handler._parse_bk_host_id("service|instance|service|11"), 0)

    def test_unparsable_instance_id_does_not_crash_detail(self):
        # 前端历史缓存里可能还留着 V2 的服务实例 ID，解析不出主机 ID 时要给空详情而不是抛
        self.assertEqual(
            self.handler.get_subscription_task_detail("service|instance|service|99"),
            {"log_detail": "", "log_result": {}},
        )

    def test_detail_flattens_action_logs(self):
        self.client.instance_logs = {
            "install": {
                "message": {
                    "logs": [
                        {"level": "ERROR", "text_zh": "渲染子配置失败", "text_en": "render failed"},
                        {"level": "INFO", "text_en": "only english"},
                        {"level": "INFO"},
                    ]
                }
            }
        }
        detail = self.handler.get_subscription_task_detail("host|instance|host|11")
        self.assertIn("渲染子配置失败", detail["log_detail"])
        # 中文缺失时退英文
        self.assertIn("only english", detail["log_detail"])
        # 两个都没有的条目不能输出空行
        self.assertNotIn("[INFO] \n", detail["log_detail"])
        self.assertEqual(detail["log_result"]["bk_host_id"], 11)

    def test_retry_goes_to_v3_workflow_not_v2_subscription(self):
        from apps.api import NodeApi

        with patch.object(NodeApi, "retry_subscription") as v2_retry:
            task_id_list = self.handler.retry_instances(["host|instance|host|11"])

        v2_retry.assert_not_called()
        self.assertEqual(self.client.retry_payloads[0]["workflow_id"], WORKFLOW_ID)
        self.assertEqual(task_id_list, [WORKFLOW_ID])

    def test_retry_task_id_is_persisted_as_string(self):
        # V3 的 task_id 是 workflow_id 字符串，写进 IntegerField 会炸；这里确认落的是 task_id_list
        self.handler.retry_target_nodes(["host|instance|host|11"])
        self.collector_config.refresh_from_db()
        self.assertEqual(self.collector_config.task_id_list, [WORKFLOW_ID])

    def test_retry_without_resolvable_host_fails_closed(self):
        # 解析不出主机就重试，会退化成「全量重试」，把好的机器也拖下来重跑一遍
        with self.assertRaises(NodeManV3CapabilityBlocked):
            self.handler.retry_instances(["service|instance|service|99"])
        self.assertEqual(self.client.retry_payloads, [])
