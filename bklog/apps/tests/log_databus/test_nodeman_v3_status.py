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

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

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
    CHILD_VISIBILITY_GRACE_SECONDS,
    CollectorStatusReader,
    PAGE_LIMIT,
    build_v2_compatible_instance_data,
    iter_paged,
    summary_to_status,
)

PLUGIN_NAME = LogPluginInfo.NAME
TEMPLATE_NAME = f"{PLUGIN_NAME}.conf"
BK_BIZ_ID = 2
COLLECTOR_CONFIG_ID = 8001
POLICY_ID = 1001
TRIGGER_ID = "trigger-1001-1"
PARENT_WORKFLOW_ID = "parent-workflow-abc"
WORKFLOW_ID = "plugin-workflow-abc"
SECOND_WORKFLOW_ID = "plugin-workflow-def"


class FakeStatusClient:
    """按 NodeMan v3 proto 的真实返回结构造桩"""

    def __init__(self):
        self.tenant_id = "system"
        self.calls = []
        self.parent_items = [
            {
                "workflow_id": PARENT_WORKFLOW_ID,
                "trigger_id": TRIGGER_ID,
                "deploy_policy_id": POLICY_ID,
                "status": "success",
                "children": [{"type": "plugin", "workflow_id": WORKFLOW_ID}],
            }
        ]
        self.workflow_items = [{"workflow_id": WORKFLOW_ID, "status": "success"}]
        # bk_host_id -> life_cycle.state
        self.host_states = {}
        # bk_host_id -> 该主机上**额外**几条 operation 的 state（同机多 spec 会各出一条）
        self.host_extra_states = {}
        # plugin workflow_id -> bk_host_id -> life_cycle.state；为空时沿用 host_states
        self.workflow_host_states = {}
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
        conditions = payload.get("exact_include_conditions") or {}
        workflow_ids = conditions.get("workflow_id") or []
        items = [item for item in self.workflow_items if not workflow_ids or item.get("workflow_id") in workflow_ids]
        return {"items": self._paged(items, payload), "total": len(items)}

    def list_deploy_policy_workflows(self, payload):
        self.calls.append(("list_deploy_policy_workflows", payload))
        conditions = payload.get("exact_include_conditions") or {}
        workflow_ids = conditions.get("workflow_id") or []
        items = [item for item in self.parent_items if not workflow_ids or item.get("workflow_id") in workflow_ids]
        return {"items": self._paged(items, payload), "total": len(items)}

    def list_workflow_operations(self, payload):
        self.calls.append(("list_workflow_operations", payload))
        # 一台主机可以有多条 operation：策略至少带两个 spec（装插件 + 下子配置），各自一条。
        # 桩要能造出这种形状，否则「多条里取最坏」这条规则没法被用例约束住
        operations = []
        states_by_host = self.workflow_host_states.get(payload["workflow_id"], self.host_states)
        for bk_host_id, primary_state in states_by_host.items():
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
                {
                    "operation_id": operation_id,
                    "oper_inst_id": f"oi-{index}",
                    "oper_inst_status": "success",
                }
                for index, operation_id in enumerate(payload["operation_id"], start=1)
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
        NodeManV3Workflow.objects.create(
            operation=self.operation,
            parent_workflow_id=PARENT_WORKFLOW_ID,
            status_summary={
                "parent_terminal_observed_at": int(
                    (timezone.now() - timedelta(seconds=CHILD_VISIBILITY_GRACE_SECONDS + 1)).timestamp()
                )
            },
        )

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

    def _expire_child_visibility_grace(self):
        workflow = NodeManV3Workflow.objects.get(operation=self.operation)
        workflow.status_summary = {
            **(workflow.status_summary or {}),
            "parent_terminal_observed_at": int(
                (timezone.now() - timedelta(seconds=CHILD_VISIBILITY_GRACE_SECONDS + 1)).timestamp()
            ),
            "children_reconciled_by_trigger": False,
        }
        workflow.save(update_fields=["status_summary"])

    def _reset_child_visibility_grace(self):
        workflow = NodeManV3Workflow.objects.get(operation=self.operation)
        workflow.status_summary = {}
        workflow.save(update_fields=["status_summary"])

    # ------------------------------------------------------------------
    # deploy-policy 父 workflow -> plugin 子 workflow
    # ------------------------------------------------------------------
    def test_repeated_full_page_fails_closed(self):
        with (
            patch("apps.log_databus.nodeman_v3.status.PAGE_LIMIT", 2),
            self.assertRaises(NodeManV3CapabilityBlocked),
        ):
            list(iter_paged(lambda _offset: {"items": [{"workflow_id": "a"}, {"workflow_id": "b"}]}, "items"))

    def test_parent_workflow_resolves_and_persists_plugin_children(self):
        resolution = self._reader().resolve_workflows()

        self.assertEqual(resolution.parent_workflow_id, PARENT_WORKFLOW_ID)
        self.assertEqual(resolution.plugin_workflow_ids, [WORKFLOW_ID])
        self.assertEqual(resolution.normalized_status, "success")
        workflow = NodeManV3Workflow.objects.get(operation=self.operation)
        self.assertEqual(workflow.trigger_id, TRIGGER_ID)
        self.assertEqual(workflow.plugin_workflow_ids, [WORKFLOW_ID])

    def test_parent_workflow_is_queried_by_exact_id(self):
        self._reader().resolve_workflows()
        call = next(payload for name, payload in self.client.calls if name == "list_deploy_policy_workflows")
        self.assertEqual(call["exact_include_conditions"]["workflow_id"], [PARENT_WORKFLOW_ID])

    def test_parent_workflow_visibility_window_stays_running(self):
        self.client.parent_items = []
        resolution = self._reader().resolve_workflows()
        self.assertEqual(resolution.plugin_workflow_ids, [])
        self.assertEqual(resolution.normalized_status, "running")

    def test_plugin_workflow_visibility_window_stays_running(self):
        self.client.workflow_items = []
        resolution = self._reader().resolve_workflows()
        self.assertEqual(resolution.plugin_workflow_ids, [WORKFLOW_ID])
        self.assertEqual(resolution.normalized_status, "running")

    def test_parent_success_does_not_hide_running_child(self):
        self.client.workflow_items[0]["status"] = "running"
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "running")

    def test_parent_failure_waits_for_running_child(self):
        # 父失败只表示 dispatch 没完整完成，已经启动的 child 不会被终止。
        self.client.parent_items[0]["status"] = "failed"
        self.client.workflow_items[0]["status"] = "running"
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "running")

    def test_multiple_children_aggregate_partial_failure(self):
        self.client.parent_items[0]["children"] = [
            {"type": "plugin", "workflow_id": WORKFLOW_ID},
            {"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID},
        ]
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "status": "success"},
            {"workflow_id": SECOND_WORKFLOW_ID, "status": "failed"},
        ]
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "partial_failed")

    def test_cached_terminal_state_survives_remote_retention(self):
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "success")
        self.client.parent_items = []
        self.client.workflow_items = []
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "success")

    def test_missing_parent_child_association_falls_back_to_trigger(self):
        # NodeMan 启动 child 后记录父子关联失败只记日志，父流程仍可能 success。
        # 不能把 children=[] 直接当 no-op。
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = [{"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"}]

        resolution = self._reader().resolve_workflows()

        self.assertEqual(resolution.plugin_workflow_ids, [WORKFLOW_ID])

    def test_trigger_fallback_keeps_all_plugin_children(self):
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"},
            {"workflow_id": SECOND_WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"},
        ]

        self.assertEqual(
            self._reader().resolve_workflows().plugin_workflow_ids,
            [WORKFLOW_ID, SECOND_WORKFLOW_ID],
        )

    def test_trigger_fallback_repairs_partially_missing_child_association(self):
        self.client.parent_items[0]["children"] = [{"type": "plugin", "workflow_id": WORKFLOW_ID}]
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"},
            {"workflow_id": SECOND_WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"},
        ]

        self.assertEqual(
            self._reader().resolve_workflows().plugin_workflow_ids,
            [WORKFLOW_ID, SECOND_WORKFLOW_ID],
        )

    def test_old_workflow_still_gets_grace_from_first_terminal_observation(self):
        self._reset_child_visibility_grace()
        NodeManV3Workflow.objects.filter(operation=self.operation).update(created_at=timezone.now() - timedelta(days=1))
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = []

        self.assertEqual(self._reader().resolve_workflows().normalized_status, "running")

    def test_delayed_second_child_is_discovered_during_visibility_grace(self):
        self._reset_child_visibility_grace()
        self.client.parent_items[0]["children"] = [{"type": "plugin", "workflow_id": WORKFLOW_ID}]
        self.client.workflow_items = [{"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"}]
        first = self._reader().resolve_workflows()
        self.assertEqual(first.plugin_workflow_ids, [WORKFLOW_ID])
        self.assertEqual(first.normalized_status, "running")

        self.client.workflow_items.append(
            {"workflow_id": SECOND_WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "failed"}
        )
        second = self._reader().resolve_workflows()
        self.assertEqual(second.plugin_workflow_ids, [WORKFLOW_ID, SECOND_WORKFLOW_ID])
        self.assertEqual(second.normalized_status, "running")

        self._expire_child_visibility_grace()
        self.assertEqual(self._reader().resolve_workflows().normalized_status, "partial_failed")

    def test_legacy_trigger_id_record_still_resolves_plugin_workflow(self):
        workflow = NodeManV3Workflow.objects.get(operation=self.operation)
        workflow.parent_workflow_id = ""
        workflow.trigger_id = TRIGGER_ID
        workflow.plugin_workflow_ids = []
        workflow.save(update_fields=["parent_workflow_id", "trigger_id", "plugin_workflow_ids"])
        self.client.workflow_items = [
            {
                "workflow_id": WORKFLOW_ID,
                "trigger_id": TRIGGER_ID,
                "deploy_policy_ids": [POLICY_ID],
                "status": "success",
            }
        ]

        resolution = self._reader().resolve_workflows()

        self.assertEqual(resolution.parent_workflow_id, "")
        self.assertEqual(resolution.plugin_workflow_ids, [WORKFLOW_ID])

    def test_legacy_trigger_id_resolves_beyond_first_page(self):
        workflow = NodeManV3Workflow.objects.get(operation=self.operation)
        workflow.parent_workflow_id = ""
        workflow.trigger_id = TRIGGER_ID
        workflow.plugin_workflow_ids = []
        workflow.save(update_fields=["parent_workflow_id", "trigger_id", "plugin_workflow_ids"])
        self.client.workflow_items = [
            {
                "workflow_id": f"noise-{index}",
                "trigger_id": f"trigger-noise-{index}",
                "status": "success",
            }
            for index in range(PAGE_LIMIT + 100)
        ] + [{"workflow_id": WORKFLOW_ID, "trigger_id": TRIGGER_ID, "status": "success"}]

        self.assertEqual(self._reader().resolve_workflows().plugin_workflow_ids, [WORKFLOW_ID])
        self.assertGreater(self.client.call_names().count("list_workflows"), 1)

    def test_host_operations_span_multiple_pages(self):
        # 超过单页上限的业务，分页写错会静默只回前 500 台，状态页的总数从此不可信
        host_count = PAGE_LIMIT + 100
        self.client.host_states = {bk_host_id: "success" for bk_host_id in range(1, host_count + 1)}

        operations = self._reader().fetch_host_operations([WORKFLOW_ID])

        self.assertEqual(len(operations), host_count)
        self.assertIn(host_count, operations)

    def test_host_operations_are_keyed_by_host_id(self):
        self.client.host_states = {11: "success", 12: "failed"}
        operations = self._reader().fetch_host_operations([WORKFLOW_ID])
        self.assertEqual(set(operations.keys()), {11, 12})
        self.assertEqual(operations[11]["operation_id"], "op-11")

    def test_host_operations_merge_multiple_plugin_children(self):
        self.client.parent_items[0]["children"] = [
            {"type": "plugin", "workflow_id": WORKFLOW_ID},
            {"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID},
        ]
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "status": "success"},
            {"workflow_id": SECOND_WORKFLOW_ID, "status": "success"},
        ]
        self.client.workflow_host_states = {
            WORKFLOW_ID: {11: "success"},
            SECOND_WORKFLOW_ID: {12: "failed"},
        }

        resolution = self._reader().resolve_workflows()
        operations = self._reader().fetch_host_operations(resolution.plugin_workflow_ids)

        self.assertEqual(set(operations), {11, 12})
        self.assertEqual(operations[12]["workflow_id"], SECOND_WORKFLOW_ID)

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
        NodeManV3Workflow.objects.all().delete()
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
        NodeManV3Workflow.objects.all().delete()
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
        NodeManV3Workflow.objects.all().delete()
        self.client.host_states = {}
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.ABSENT)

    def test_parent_success_without_children_is_valid_noop(self):
        row = self._add_target(11, generation=1)
        self._expire_child_visibility_grace()
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = []
        self.client.process_states = {11: "running"}

        status = self._reader().refresh()[11]

        self.assertEqual(status.state, NodeManV3TargetState.LATEST)
        row.refresh_from_db()
        self.assertEqual(row.generation, 2)

    def test_parent_running_without_children_is_dispatching(self):
        self._add_target(11, generation=0)
        self.client.parent_items[0]["status"] = "running"
        self.client.parent_items[0]["children"] = []

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.DISPATCHING)

    def test_parent_failure_without_host_operation_is_failed(self):
        self._add_target(11, generation=0)
        self._expire_child_visibility_grace()
        self.client.parent_items[0]["status"] = "failed"
        self.client.parent_items[0]["children"] = []
        self.client.process_states = {11: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.FAILED)

    def test_parent_success_empty_children_waits_during_visibility_grace(self):
        self._add_target(11, generation=0)
        self._reset_child_visibility_grace()
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = []

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.DISPATCHING)

    def test_noop_does_not_advance_generation_when_collector_process_is_down(self):
        row = self._add_target(11, generation=1)
        self._expire_child_visibility_grace()
        self.client.parent_items[0]["children"] = []
        self.client.workflow_items = []
        self.client.process_states = {11: "stopped"}

        status = self._reader().refresh()[11]

        self.assertEqual(status.state, NodeManV3TargetState.ABSENT)
        row.refresh_from_db()
        self.assertEqual(row.generation, 1)

    def test_terminal_failed_child_does_not_mark_unchanged_host_failed(self):
        # host 12 有变更且失败，host 11 配置无需变更所以没有 operation。父 dispatch 成功且
        # child 已终态时，host 11 应推进本地代次，不能被另一个主机的失败拖成红色。
        row = self._add_target(11, generation=1)
        self.client.workflow_items[0]["status"] = "failed"
        self.client.host_states = {12: "failed"}
        self.client.process_states = {11: "running", 12: "running"}

        self.assertEqual(self._reader().refresh()[11].state, NodeManV3TargetState.LATEST)
        row.refresh_from_db()
        self.assertEqual(row.generation, 2)

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
        # workflow 成功且 host 12 没有 operation 表示合法 no-op，仍应推进到最新代次
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["counts"][NodeManV3TargetState.LATEST], 2)

    def test_summary_to_status_marks_part_failed(self):
        summary = {"total": 2, "success": 1, "failed": 1, "pending": 0}
        result = summary_to_status(summary, self.collector_config)
        self.assertEqual(result["status"], CollectStatus.FAILED)
        self.assertEqual(result["status_name"], RunStatus.PARTFAILED)

    def test_absent_host_is_counted_as_pending(self):
        self._add_target(11, generation=0)
        NodeManV3Workflow.objects.all().delete()
        self.client.process_states = {11: "running"}

        summary = self._reader().summary()

        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary_to_status(summary, self.collector_config)["status"], CollectStatus.RUNNING)

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

    def test_instance_detail_groups_operations_by_plugin_workflow(self):
        self.client.parent_items[0]["children"] = [
            {"type": "plugin", "workflow_id": WORKFLOW_ID},
            {"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID},
        ]
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "status": "failed"},
            {"workflow_id": SECOND_WORKFLOW_ID, "status": "failed"},
        ]
        self.client.workflow_host_states = {
            WORKFLOW_ID: {11: "failed"},
            SECOND_WORKFLOW_ID: {11: "failed"},
        }

        self._reader().instance_detail(11)

        instance_calls = [payload for name, payload in self.client.calls if name == "list_workflow_operation_instances"]
        self.assertEqual(len(instance_calls), 2)
        self.assertTrue(all(len(payload["operation_id"]) == 1 for payload in instance_calls))

    def test_retry_sends_operation_ids_of_requested_hosts(self):
        self.client.host_states = {11: "failed", 12: "success"}
        self._reader().retry_hosts([11])
        self.assertEqual(self.client.retry_payloads[0]["operation_ids"], ["op-11"])
        self.assertEqual(self.client.retry_payloads[0]["workflow_id"], WORKFLOW_ID)
        self.assertEqual(self.client.retry_payloads[0]["retry_mod"], "PARTIAL")

    def test_retry_groups_failed_operations_by_plugin_workflow(self):
        self.client.parent_items[0]["children"] = [
            {"type": "plugin", "workflow_id": WORKFLOW_ID},
            {"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID},
        ]
        self.client.workflow_items = [
            {"workflow_id": WORKFLOW_ID, "status": "failed"},
            {"workflow_id": SECOND_WORKFLOW_ID, "status": "failed"},
        ]
        self.client.workflow_host_states = {
            WORKFLOW_ID: {11: "failed"},
            SECOND_WORKFLOW_ID: {11: "failed"},
        }

        task_id = self._reader().retry_hosts([11])

        self.assertEqual(task_id, PARENT_WORKFLOW_ID)
        self.assertEqual(
            {payload["workflow_id"] for payload in self.client.retry_payloads},
            {WORKFLOW_ID, SECOND_WORKFLOW_ID},
        )
        self.assertTrue(all(payload["retry_mod"] == "PARTIAL" for payload in self.client.retry_payloads))

    def test_retry_terminated_operation_uses_all_mode(self):
        # NodeMan 明确拒绝对 terminated 的最后一次实例做 PARTIAL retry。
        self.client.host_states = {11: "terminated"}

        self._reader().retry_hosts([11])

        self.assertEqual(self.client.retry_payloads[0]["retry_mod"], "ALL")

    def test_retry_mixed_terminated_and_failed_operations_keeps_modes_separate(self):
        self.client.host_states = {11: "terminated"}
        self.client.host_extra_states = {11: ["failed"]}

        self._reader().retry_hosts([11])

        payloads = {payload["retry_mod"]: payload["operation_ids"] for payload in self.client.retry_payloads}
        self.assertEqual(payloads["ALL"], ["op-11"])
        self.assertEqual(payloads["PARTIAL"], ["op-11-1"])

    def test_retry_fails_closed_without_workflow(self):
        # 静默成功会让用户以为已经重试过了
        self.client.parent_items = []
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

    def test_explicit_task_id_selects_historical_workflow(self):
        old_parent_id = "parent-workflow-old"
        old_operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
        )
        NodeManV3Workflow.objects.create(operation=old_operation, parent_workflow_id=old_parent_id)
        self.client.parent_items.append(
            {
                "workflow_id": old_parent_id,
                "trigger_id": "trigger-old",
                "deploy_policy_id": POLICY_ID,
                "status": "success",
                "children": [],
            }
        )

        resolution = CollectorStatusReader(self.collector_config, task_ids=[old_parent_id]).resolve_workflows()

        self.assertEqual(resolution.parent_workflow_id, old_parent_id)

    def test_historical_task_query_does_not_mutate_current_target_snapshot(self):
        old_parent_id = "parent-workflow-old"
        row = self._add_target(11, generation=0)
        old_operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
        )
        NodeManV3Workflow.objects.create(operation=old_operation, parent_workflow_id=old_parent_id)
        self.client.parent_items.append(
            {
                "workflow_id": old_parent_id,
                "trigger_id": "trigger-old",
                "deploy_policy_id": POLICY_ID,
                "status": "success",
                "children": [{"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID}],
            }
        )
        self.client.workflow_items.append({"workflow_id": SECOND_WORKFLOW_ID, "status": "success"})
        self.client.workflow_host_states[SECOND_WORKFLOW_ID] = {11: "success"}

        statuses = CollectorStatusReader(self.collector_config, task_ids=[old_parent_id]).refresh()

        self.assertEqual(statuses[11].state, NodeManV3TargetState.LATEST)
        row.refresh_from_db()
        self.assertEqual(row.generation, 0)


class InstanceDataCompatTest(TestCase):
    """V3 状态 -> V2 实例结构的形状适配"""

    def _status(self, state, **kwargs):
        from apps.log_databus.nodeman_v3.status import HostStatus

        return HostStatus(bk_host_id=11, state=state, **kwargs)

    def test_shape_matches_v2_instance_contract(self):
        data = build_v2_compatible_instance_data(
            {
                11: self._status(
                    NodeManV3TargetState.LATEST,
                    task_id=PARENT_WORKFLOW_ID,
                    operation_id="op-11",
                )
            },
            {11: {"bk_host_innerip": "127.0.0.1", "bk_cloud_id": 0, "bk_host_name": "h1"}},
        )
        host = data[0]["instance_info"]["host"]
        self.assertEqual(data[0]["status"], CollectStatus.SUCCESS)
        self.assertEqual(host["bk_host_id"], 11)
        self.assertEqual(host["bk_host_innerip"], "127.0.0.1")
        self.assertEqual(host["bk_host_name"], "h1")
        self.assertEqual(data[0]["task_id"], PARENT_WORKFLOW_ID)

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
        NodeManV3Workflow.objects.create(operation=operation, parent_workflow_id=PARENT_WORKFLOW_ID)

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

    def test_detail_honors_explicit_historical_task_id(self):
        old_parent_id = "parent-workflow-old"
        old_operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=0,
        )
        NodeManV3Workflow.objects.create(operation=old_operation, parent_workflow_id=old_parent_id)
        self.client.parent_items.append(
            {
                "workflow_id": old_parent_id,
                "trigger_id": "trigger-old",
                "deploy_policy_id": POLICY_ID,
                "status": "failed",
                "children": [{"type": "plugin", "workflow_id": SECOND_WORKFLOW_ID}],
            }
        )
        self.client.workflow_items.append({"workflow_id": SECOND_WORKFLOW_ID, "status": "failed"})
        self.client.workflow_host_states[SECOND_WORKFLOW_ID] = {11: "failed"}

        self.handler.get_subscription_task_detail("host|instance|host|11", task_id=old_parent_id)

        parent_calls = [payload for name, payload in self.client.calls if name == "list_deploy_policy_workflows"]
        self.assertEqual(parent_calls[-1]["exact_include_conditions"]["workflow_id"], [old_parent_id])

    def test_retry_goes_to_v3_workflow_not_v2_subscription(self):
        from apps.api import NodeApi

        with patch.object(NodeApi, "retry_subscription") as v2_retry:
            task_id_list = self.handler.retry_instances(["host|instance|host|11"])

        v2_retry.assert_not_called()
        self.assertEqual(self.client.retry_payloads[0]["workflow_id"], WORKFLOW_ID)
        self.assertEqual(task_id_list, [PARENT_WORKFLOW_ID])

    def test_retry_task_id_is_persisted_as_string(self):
        # V3 的 task_id 是 workflow_id 字符串，写进 IntegerField 会炸；这里确认落的是 task_id_list
        self.handler.retry_target_nodes(["host|instance|host|11"])
        self.collector_config.refresh_from_db()
        self.assertEqual(self.collector_config.task_id_list, [PARENT_WORKFLOW_ID])

    def test_repeated_retry_does_not_duplicate_same_parent_task_id(self):
        self.handler.retry_target_nodes(["host|instance|host|11"])
        self.handler.retry_target_nodes(["host|instance|host|11"])

        self.collector_config.refresh_from_db()
        self.assertEqual(self.collector_config.task_id_list, [PARENT_WORKFLOW_ID])

    def test_retry_without_resolvable_host_fails_closed(self):
        # 解析不出主机就重试，会退化成「全量重试」，把好的机器也拖下来重跑一遍
        with self.assertRaises(NodeManV3CapabilityBlocked):
            self.handler.retry_instances(["service|instance|service|99"])
        self.assertEqual(self.client.retry_payloads, [])
