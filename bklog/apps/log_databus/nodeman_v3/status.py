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

from dataclasses import dataclass

from django.utils import timezone
from django.utils.translation import gettext as _

from apps.log_databus.constants import CollectStatus, LogPluginInfo, RunStatus
from apps.log_databus.nodeman_v3.client import get_client
from apps.log_databus.nodeman_v3.constants import (
    NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING,
    NodeManV3OperationStatus,
    NodeManV3TargetState,
    PROCESS_STATUS_RUNNING,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
)
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_resource_key
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3SubConfigTarget,
    NodeManV3Workflow,
)
from apps.utils.log import logger

# NodeMan 一次 list 的分页上限，按主机展开的接口都要翻页
PAGE_LIMIT = 500

# 父流程落终态后，child workflow/父子关联仍可能短暂不可见。NodeMan 自身对 operation
# 缺失使用一分钟宽限；日志侧沿用同一量级，避免把首次空查询误判成合法 no-op。
CHILD_VISIBILITY_GRACE_SECONDS = 60


def iter_paged(fetch, items_key: str):
    """
    按 {offset, limit} 逐页取数。

    ⚠️ NodeMan 的分页参数分两套，不能混用：

    - `plugin/workflow/list`、`plugin/workflow/operation/list`、`process/list` 用 `{offset, limit}`，
      且 `limit` 必填、必须落在 `(0, 500]`
    - 最新 `deploy_policy/list` application proto 同样使用 `{offset, limit}`；其 apigw 文档里的
      `{count, start, limit}` 已滞后，找回策略的实现独立放在 reconciler 并按 proto 处理

    传错不会报错 —— gin 没开 `EnableDecoderDisallowUnknownFields`，未知字段被静默忽略，
    于是 `offset` 恒为 0，翻页永远停在第一页。

    终止条件用「本页条数不足 limit」而不是 `total`：这两个接口的 `total` 由**顶层** `only_count`
    控制，`only_count` 为假时 `total` 可能回 0，拿它当边界会在第一页就退出。
    """
    offset = 0
    seen_item_ids = set()
    while True:
        items = (fetch(offset) or {}).get(items_key) or []
        if not items:
            return
        item_ids = {
            item.get("workflow_id") or item.get("operation_id") or repr(item)
            for item in items
            if isinstance(item, dict)
        }
        if len(item_ids) != len(items) or seen_item_ids & item_ids:
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("节点管理分页结果重复，无法确认任务数据完整性"))
            )
        yield items
        if len(items) < PAGE_LIMIT:
            return
        seen_item_ids.update(item_ids)
        offset += PAGE_LIMIT


# 同一主机多条 operation 时的取舍优先级，数值越大越「坏」。
# 未知 state 排在成功之上：拿不准的时候不能报成功，否则一个新增的生命周期状态会被静默当成已生效
_OPERATION_SEVERITY = {
    NodeManV3OperationStatus.SUCCESS: 0,
    NodeManV3OperationStatus.PENDING: 2,
    NodeManV3OperationStatus.RUNNING: 2,
    NodeManV3OperationStatus.FAILED: 3,
}
_UNKNOWN_OPERATION_SEVERITY = 1


def _operation_severity(state: str) -> int:
    normalized = NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(state)
    if normalized is None:
        return _UNKNOWN_OPERATION_SEVERITY
    return _OPERATION_SEVERITY.get(normalized, _UNKNOWN_OPERATION_SEVERITY)


def _aggregate_workflow_status(
    parent_status: str,
    child_workflow_ids: list[str],
    child_statuses: dict[str, str],
    *,
    has_parent: bool,
    children_resolved: bool,
) -> str:
    """
    汇总 deploy-policy 父流程与 plugin 子流程状态。

    父流程成功只表示 dispatch 完成，不能覆盖仍在运行或失败的子流程。反过来，父流程失败说明
    dispatch 没有完整完成，即使已启动的部分子流程成功，整轮也不能报成功。
    """
    parent_failed = False
    if has_parent:
        if not parent_status:
            return NodeManV3OperationStatus.RUNNING
        if parent_status not in (
            NodeManV3OperationStatus.SUCCESS,
            NodeManV3OperationStatus.FAILED,
            NodeManV3OperationStatus.PARTIAL_FAILED,
        ):
            return NodeManV3OperationStatus.RUNNING
        parent_failed = parent_status in (
            NodeManV3OperationStatus.FAILED,
            NodeManV3OperationStatus.PARTIAL_FAILED,
        )
        if not children_resolved:
            return NodeManV3OperationStatus.RUNNING
        if not child_workflow_ids:
            return parent_status

    if not child_workflow_ids:
        return NodeManV3OperationStatus.RUNNING
    if any(workflow_id not in child_statuses for workflow_id in child_workflow_ids):
        return NodeManV3OperationStatus.RUNNING

    statuses = [child_statuses[workflow_id] for workflow_id in child_workflow_ids]
    if any(
        status
        not in (
            NodeManV3OperationStatus.SUCCESS,
            NodeManV3OperationStatus.FAILED,
            NodeManV3OperationStatus.PARTIAL_FAILED,
        )
        for status in statuses
    ):
        return NodeManV3OperationStatus.RUNNING
    if any(status == NodeManV3OperationStatus.PARTIAL_FAILED for status in statuses):
        return NodeManV3OperationStatus.PARTIAL_FAILED
    failed_count = sum(status == NodeManV3OperationStatus.FAILED for status in statuses)
    if parent_failed:
        if parent_status == NodeManV3OperationStatus.PARTIAL_FAILED or failed_count != len(statuses):
            return NodeManV3OperationStatus.PARTIAL_FAILED
        return NodeManV3OperationStatus.FAILED
    if failed_count:
        return (
            NodeManV3OperationStatus.FAILED
            if failed_count == len(statuses)
            else NodeManV3OperationStatus.PARTIAL_FAILED
        )
    if any(status != NodeManV3OperationStatus.SUCCESS for status in statuses):
        return NodeManV3OperationStatus.RUNNING
    return NodeManV3OperationStatus.SUCCESS


# V3 生效态 -> V2 状态页口径。
# STALE 映射成 SUCCESS 是有意的：旧版配置仍在出数，把它显示成失败会让用户去重试一个
# 正在正常采集的采集项。真正需要用户介入的只有 FAILED。
TARGET_STATE_TO_COLLECT_STATUS = {
    NodeManV3TargetState.LATEST: CollectStatus.SUCCESS,
    NodeManV3TargetState.STALE: CollectStatus.SUCCESS,
    NodeManV3TargetState.DISPATCHING: CollectStatus.RUNNING,
    NodeManV3TargetState.FAILED: CollectStatus.FAILED,
    NodeManV3TargetState.ABSENT: CollectStatus.PENDING,
    NodeManV3TargetState.PENDING_REMOVAL: CollectStatus.TERMINATED,
}


def build_v2_compatible_instance_data(host_statuses: dict[int, "HostStatus"], host_info: dict[int, dict]) -> list:
    """
    把 V3 的 per-host 状态拼成 V2 订阅任务状态的实例结构。

    这样做而不是改 format_task_instance_status / format_subscription_instance_status：
    那两个函数后面还接着 _get_status_content 的拓扑分组，以及前端按 host_id/ip/cloud_id/steps
    取值的渲染逻辑。在这里做一次形状适配，比在下游改三处、再赌前端不受影响要安全得多。

    与 V2 的两处不可消除差异（BKL-5 联调要确认前端能接受）：

    - `task_id` 是字符串 workflow_id，不是自增整数。keep_latest_task_status_per_instance 会
      把非数字 task_id 的 task_index 算成 -1，所以 V3 路径不能走那条按任务 ID 取最新的聚合，
      调用方要自己保证一台主机只出现一次。
    - `steps` 为空：V3 的 operation 实例是 action 粒度，与 V2 的订阅 step 不是同一套概念。
    """
    instance_data = []
    for bk_host_id, status in host_statuses.items():
        host = host_info.get(bk_host_id) or {}
        inner_ip = host.get("bk_host_innerip", "")
        instance_data.append(
            {
                "instance_id": f"host|instance|host|{bk_host_id}",
                "status": TARGET_STATE_TO_COLLECT_STATUS.get(status.state, CollectStatus.UNKNOWN),
                "task_id": status.task_id or status.operation_id,
                "create_time": host.get("create_time", ""),
                "steps": [],
                "instance_info": {
                    "host": {
                        "bk_host_id": bk_host_id,
                        "bk_host_innerip": inner_ip,
                        "bk_host_innerip_v6": host.get("bk_host_innerip_v6", ""),
                        "bk_host_name": host.get("bk_host_name", ""),
                        "bk_cloud_id": host.get("bk_cloud_id", 0),
                        "bk_supplier_account": host.get("bk_supplier_account", ""),
                    }
                },
                # 供上层展示失败原因；V2 的日志来自 steps，V3 要单独查 operation instance log
                "log": status.message,
            }
        )
    return instance_data


def summary_to_status(summary: dict, collector_config) -> dict:
    """
    把 V3 汇总翻译成 V2 状态页的 status/status_name/total/success/failed/pending 口径。

    刻意沿用 V2 的判定顺序（pending > 部分失败 > 全失败 > 成功），前端与告警都按这套口径写的，
    换判定顺序会让同一批主机在切 V3 前后显示成不同状态，而这类差异在联调里很难归因。
    """
    total = summary["total"]
    success = summary["success"]
    failed = summary["failed"]
    pending = summary["pending"]

    if not total:
        # 与 V2 的「订阅未创建」分支对齐：配了目标但还没下发算准备中，没配目标算成功
        status = CollectStatus.PREPARE if collector_config.target_nodes else CollectStatus.SUCCESS
        status_name = RunStatus.PREPARE if collector_config.target_nodes else RunStatus.SUCCESS
    elif pending:
        status, status_name = CollectStatus.RUNNING, RunStatus.RUNNING
    elif failed and success:
        status, status_name = CollectStatus.FAILED, RunStatus.PARTFAILED
    elif failed:
        status, status_name = CollectStatus.FAILED, RunStatus.FAILED
    else:
        status, status_name = CollectStatus.SUCCESS, RunStatus.SUCCESS

    return {
        "status": status,
        "status_name": status_name,
        "total": total,
        "success": success,
        "failed": failed,
        "pending": pending,
    }


@dataclass
class HostStatus:
    """单台主机上本采集项的状态"""

    bk_host_id: int
    state: str
    # 该主机当前生效的是第几代期望态；0 表示从未成功下发过
    applied_generation: int = 0
    # 采集器进程状态。不是采集项状态——同机多采集项共用一个进程，进程活着只说明「别的采集项可能在跑」
    process_status: str = ""
    task_id: str = ""
    operation_id: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "bk_host_id": self.bk_host_id,
            "state": self.state,
            "state_name": str(NodeManV3TargetState(self.state).label),
            "applied_generation": self.applied_generation,
            "process_status": self.process_status,
            "task_id": self.task_id,
            "operation_id": self.operation_id,
            "message": self.message,
        }


@dataclass
class WorkflowResolution:
    """最近一次本地任务对应的 deploy-policy 父流程和 plugin 子流程。"""

    workflow: NodeManV3Workflow | None = None
    parent_workflow_id: str = ""
    plugin_workflow_ids: list[str] | None = None
    parent_status: str = ""
    child_statuses: dict[str, str] | None = None
    normalized_status: str = NodeManV3OperationStatus.UNKNOWN
    children_resolved: bool = False

    def __post_init__(self):
        self.plugin_workflow_ids = list(self.plugin_workflow_ids or [])
        self.child_statuses = dict(self.child_statuses or {})

    @property
    def task_id(self) -> str:
        if self.parent_workflow_id:
            return self.parent_workflow_id
        if self.plugin_workflow_ids:
            return self.plugin_workflow_ids[0]
        return self.workflow.task_id if self.workflow else ""

    @property
    def missing_operation_is_noop(self) -> bool:
        """
        父 dispatch 成功且所有已知子流程都已结束时，operation 列表里没有某台主机，
        表示该主机配置无需变更。父失败时不能这样推断，因为 dispatch 可能没走到该主机。
        """
        if not self.parent_workflow_id or self.parent_status != NodeManV3OperationStatus.SUCCESS:
            return False
        if not self.children_resolved:
            return False
        return all(
            self.child_statuses.get(workflow_id)
            in (
                NodeManV3OperationStatus.SUCCESS,
                NodeManV3OperationStatus.FAILED,
                NodeManV3OperationStatus.PARTIAL_FAILED,
            )
            for workflow_id in self.plugin_workflow_ids
        )


class CollectorStatusReader:
    """
    V3 采集项状态回读。

    与 V2 状态页最根本的差别：**不能把 bkunifylogbeat 进程 running 当成采集项已生效**。
    同机多个采集项共用一个进程，进程活着只说明别的采集项在跑；本采集项有没有生效，
    取决于这台主机上有没有本策略的那份子配置（文件名带 deploy_policy_id）。

    状态来源分两层：

    - **权威层**：execute 返回 deploy-policy 父 workflow_id；deploy_policy/workflow/list 给出
      dispatch 状态和 plugin 子 workflow；再从 plugin workflow → operation（per-host）拿到
      每台主机的执行结果（PluginDeploymentInfo.bk_host_id）。
    - **本地层**：NodeManV3SubConfigTarget 记录每台主机当前生效的是第几代期望态，用于区分
      「已生效且最新」与「已生效但旧版」——这个区分节点管理给不出来，它只知道最近一轮任务的成败，
      不知道上一代配置是不是还留在机器上。

    进程状态只作为**否定证据**使用：进程不 running 时节点管理压根不会下发子配置，还会把已有记录删掉
    （analyze_specific_plugin_sub_config_template.go:113-117、:228-236）。这是采集器重启期间的
    常态，不是下发失败，所以这种情况不能翻红，否则每次采集器升级都会让整页告警。
    """

    def __init__(
        self,
        collector_config,
        plugin_name: str = LogPluginInfo.NAME,
        task_ids: list[str] | None = None,
    ):
        self.collector_config = collector_config
        self.plugin_name = plugin_name
        self.bk_biz_id = collector_config.bk_biz_id
        self.task_ids = {str(task_id) for task_id in (task_ids or []) if task_id}

    # ------------------------------------------------------------------
    # binding / workflow
    # ------------------------------------------------------------------
    @property
    def binding(self) -> NodeManV3Binding | None:
        if not hasattr(self, "_binding_cache"):
            self._binding_cache = NodeManV3Binding.objects.filter(
                resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
                resource_key=build_resource_key(self.collector_config.collector_config_id),
                bk_biz_id=self.bk_biz_id,
            ).first()
        return self._binding_cache

    def _latest_workflow(self) -> NodeManV3Workflow | None:
        binding = self.binding
        if not binding or not binding.deploy_policy_id:
            return None
        workflows = (
            NodeManV3Workflow.objects.filter(operation__binding=binding)
            .select_related("operation")
            .order_by("-operation__generation", "-created_at")
        )
        if not self.task_ids:
            return workflows.first()
        for workflow in workflows:
            identifiers = {
                workflow.parent_workflow_id,
                workflow.workflow_id,
                workflow.trigger_id,
                *(workflow.plugin_workflow_ids or []),
            }
            if self.task_ids & identifiers:
                return workflow
        return None

    def _resolve_plugin_workflows_by_trigger(
        self,
        workflow: NodeManV3Workflow,
        *,
        force_scan: bool = False,
        trigger_id: str = "",
    ) -> list[str]:
        """按父流程的 trigger_id 回查 plugin workflow，兼容旧记录并修复 children 关联丢失。"""
        existing_workflow_ids = list(workflow.plugin_workflow_ids or [])
        if existing_workflow_ids and not force_scan:
            return existing_workflow_ids
        if workflow.workflow_id:
            existing_workflow_ids = list(dict.fromkeys([*existing_workflow_ids, workflow.workflow_id]))

        binding = self.binding
        effective_trigger_id = trigger_id or workflow.trigger_id
        if not binding or not binding.deploy_policy_id or not effective_trigger_id:
            return existing_workflow_ids
        client = get_client(self.bk_biz_id)
        workflow_ids = list(existing_workflow_ids)
        for items in iter_paged(
            lambda offset: client.list_workflows(
                {
                    "page": {"offset": offset, "limit": PAGE_LIMIT},
                    "exact_include_conditions": {"deploy_policy_id": [binding.deploy_policy_id]},
                }
            ),
            "items",
        ):
            for item in items:
                if item.get("trigger_id") == effective_trigger_id and item.get("workflow_id"):
                    workflow_ids.append(item["workflow_id"])
        workflow_ids = list(dict.fromkeys(workflow_ids))
        if workflow_ids:
            workflow.workflow_id = workflow.workflow_id or workflow_ids[0]
            workflow.plugin_workflow_ids = workflow_ids
            workflow.save(update_fields=["workflow_id", "plugin_workflow_ids", "updated_at", "updated_by"])
            return workflow_ids

        logger.info(
            f"[nodeman_v3] plugin workflow not resolved by trigger, trigger_id={effective_trigger_id}, "
            f"deploy_policy_id={binding.deploy_policy_id}"
        )
        return []

    def _list_plugin_workflow_statuses(self, workflow_ids: list[str]) -> dict[str, str]:
        if not workflow_ids:
            return {}
        client = get_client(self.bk_biz_id)
        statuses = {}
        for chunk_start in range(0, len(workflow_ids), PAGE_LIMIT):
            chunk = workflow_ids[chunk_start : chunk_start + PAGE_LIMIT]
            for items in iter_paged(
                lambda offset: client.list_workflows(
                    {
                        "page": {"offset": offset, "limit": PAGE_LIMIT},
                        "exact_include_conditions": {"workflow_id": chunk},
                    }
                ),
                "items",
            ):
                for item in items:
                    workflow_id = item.get("workflow_id") or ""
                    if workflow_id in chunk:
                        statuses[workflow_id] = item.get("status") or ""
        return statuses

    @staticmethod
    def _sync_workflow(
        workflow: NodeManV3Workflow,
        *,
        trigger_id: str,
        plugin_workflow_ids: list[str],
        parent_status: str,
        child_statuses: dict[str, str],
        normalized_status: str,
        children_reconciled_by_trigger: bool,
        parent_terminal_observed_at: int,
    ) -> None:
        fields = []
        updates = {
            "trigger_id": trigger_id,
            "plugin_workflow_ids": plugin_workflow_ids,
            "normalized_status": normalized_status,
            "status_summary": {
                "parent_status": parent_status,
                "plugin_workflow_statuses": child_statuses,
                "children_reconciled_by_trigger": children_reconciled_by_trigger,
                "parent_terminal_observed_at": parent_terminal_observed_at,
            },
        }
        for field, value in updates.items():
            if getattr(workflow, field) != value:
                setattr(workflow, field, value)
                fields.append(field)
        if fields:
            workflow.save(update_fields=[*fields, "updated_at", "updated_by"])

        operation = workflow.operation
        if operation.status != normalized_status:
            operation.status = normalized_status
            operation.save(update_fields=["status", "updated_at", "updated_by"])

    def resolve_workflows(self) -> WorkflowResolution:
        """
        解析最近一次执行的父子 workflow。

        新契约按 execute 返回的父 workflow_id 精确查询，不再按策略扫描历史 plugin workflow。
        父记录暂不可见、子记录暂不可见都属于异步可见性窗口，保持 running 而不是误报 no-op。
        """
        workflow = self._latest_workflow()
        if not workflow:
            return WorkflowResolution()

        parent_workflow_id = workflow.parent_workflow_id
        parent_status = ""
        trigger_id = workflow.trigger_id
        plugin_workflow_ids = list(workflow.plugin_workflow_ids or [])
        cached_summary = workflow.status_summary or {}
        children_reconciled_by_trigger = bool(cached_summary.get("children_reconciled_by_trigger"))
        parent_terminal_observed_at = int(cached_summary.get("parent_terminal_observed_at") or 0)

        if parent_workflow_id:
            client = get_client(self.bk_biz_id)
            data = client.list_deploy_policy_workflows(
                {
                    "page": {"offset": 0, "limit": PAGE_LIMIT},
                    "exact_include_conditions": {"workflow_id": [parent_workflow_id]},
                }
            )
            parent = next(
                (item for item in (data.get("items") or []) if item.get("workflow_id") == parent_workflow_id),
                None,
            )
            if parent:
                parent_status = parent.get("status") or ""
                trigger_id = parent.get("trigger_id") or trigger_id
                observed_plugin_workflow_ids = list(
                    dict.fromkeys(
                        child.get("workflow_id")
                        for child in (parent.get("children") or [])
                        if child.get("type") == "plugin" and child.get("workflow_id")
                    )
                )
                plugin_workflow_ids = list(dict.fromkeys([*plugin_workflow_ids, *observed_plugin_workflow_ids]))
            else:
                # workflow 记录有保留期。已经观测过的终态不能因远端记录过期而倒退成 running。
                parent_status = cached_summary.get("parent_status") or ""
        else:
            plugin_workflow_ids = self._resolve_plugin_workflows_by_trigger(workflow)

        terminal_statuses = (
            NodeManV3OperationStatus.SUCCESS,
            NodeManV3OperationStatus.FAILED,
            NodeManV3OperationStatus.PARTIAL_FAILED,
        )
        if parent_workflow_id and parent_status in terminal_statuses:
            now_timestamp = int(timezone.now().timestamp())
            if not parent_terminal_observed_at:
                parent_terminal_observed_at = now_timestamp
            if trigger_id and not children_reconciled_by_trigger:
                # 宽限期内每次都按 trigger 全量扫描。看到一个 child 不代表关联完整：
                # NodeMan 对每个 child 独立落关联，允许部分成功、部分延迟或失败。
                workflow.plugin_workflow_ids = plugin_workflow_ids
                plugin_workflow_ids = self._resolve_plugin_workflows_by_trigger(
                    workflow,
                    force_scan=True,
                    trigger_id=trigger_id,
                )
                children_reconciled_by_trigger = (
                    now_timestamp - parent_terminal_observed_at >= CHILD_VISIBILITY_GRACE_SECONDS
                )
        elif parent_workflow_id:
            parent_terminal_observed_at = 0
            children_reconciled_by_trigger = False

        child_statuses = self._list_plugin_workflow_statuses(plugin_workflow_ids)
        cached_child_statuses = cached_summary.get("plugin_workflow_statuses") or {}
        for workflow_id in plugin_workflow_ids:
            if workflow_id not in child_statuses and cached_child_statuses.get(workflow_id):
                child_statuses[workflow_id] = cached_child_statuses[workflow_id]
        normalized_status = _aggregate_workflow_status(
            parent_status,
            plugin_workflow_ids,
            child_statuses,
            has_parent=bool(parent_workflow_id),
            children_resolved=children_reconciled_by_trigger,
        )
        self._sync_workflow(
            workflow,
            trigger_id=trigger_id,
            plugin_workflow_ids=plugin_workflow_ids,
            parent_status=parent_status,
            child_statuses=child_statuses,
            normalized_status=normalized_status,
            children_reconciled_by_trigger=children_reconciled_by_trigger,
            parent_terminal_observed_at=parent_terminal_observed_at,
        )
        return WorkflowResolution(
            workflow=workflow,
            parent_workflow_id=parent_workflow_id,
            plugin_workflow_ids=plugin_workflow_ids,
            parent_status=parent_status,
            child_statuses=child_statuses,
            normalized_status=normalized_status,
            children_resolved=children_reconciled_by_trigger,
        )

    # ------------------------------------------------------------------
    # 节点管理侧事实
    # ------------------------------------------------------------------
    def fetch_host_operations(self, workflow_ids: list[str]) -> dict[int, dict]:
        """
        按主机聚合最近一轮所有 plugin 子 workflow 的 operation。

        同一主机可能同时出现在多个子 workflow、每个 workflow 又可能有多个 spec operation。
        返回值保留完整 operations，顶层 operation_id/state 仅是用于列表展示的最差一条。
        """
        if not workflow_ids:
            return {}

        client = get_client(self.bk_biz_id)
        operations: dict[int, dict] = {}
        for workflow_id in workflow_ids:
            for items in iter_paged(
                lambda offset, current_workflow_id=workflow_id: client.list_workflow_operations(
                    {
                        "workflow_id": current_workflow_id,
                        "page": {"offset": offset, "limit": PAGE_LIMIT},
                        "exact_include_conditions": {"plugin_name": [self.plugin_name]},
                    }
                ),
                "operations",
            ):
                for item in items:
                    bk_host_id = ((item.get("plugin_deployment_info") or {}).get("bk_host_id")) or 0
                    if not bk_host_id:
                        continue
                    state = ((item.get("latest_oper_inst_brief_data") or {}).get("life_cycle") or {}).get("state") or ""
                    candidate = {
                        "workflow_id": workflow_id,
                        "operation_id": item.get("operation_id") or "",
                        "state": state,
                        "instance_ids": item.get("instance_ids") or [],
                    }
                    host = operations.setdefault(
                        int(bk_host_id),
                        {
                            "operation_id": "",
                            "state": "",
                            "instance_ids": [],
                            "operations": [],
                        },
                    )
                    host["operations"].append(candidate)
                    host["instance_ids"] = list(dict.fromkeys([*host["instance_ids"], *candidate["instance_ids"]]))
                    if not host["operation_id"] or _operation_severity(candidate["state"]) > _operation_severity(
                        host["state"]
                    ):
                        host.update(
                            {
                                "workflow_id": workflow_id,
                                "operation_id": candidate["operation_id"],
                                "state": candidate["state"],
                            }
                        )
        return operations

    def fetch_process_status(self, bk_host_ids: list[int]) -> dict[int, str]:
        """采集器进程状态，仅作为否定证据使用（见类文档）。"""
        if not bk_host_ids:
            return {}

        client = get_client(self.bk_biz_id)
        statuses: dict[int, str] = {}
        for chunk_start in range(0, len(bk_host_ids), PAGE_LIMIT):
            chunk = bk_host_ids[chunk_start : chunk_start + PAGE_LIMIT]
            data = client.list_processes(
                {
                    # 按 bk_host_id 分块查，每块不超过 PAGE_LIMIT 台，所以固定取第一页即可
                    "page": {"offset": 0, "limit": PAGE_LIMIT},
                    "exact_include_conditions": {
                        "bk_host_id": chunk,
                        "plugin_name": [self.plugin_name],
                        "bk_biz_id": [self.bk_biz_id],
                    },
                }
            )
            for item in (data or {}).get("items") or []:
                bk_host_id = item.get("bk_host_id")
                if not bk_host_id:
                    continue
                statuses[int(bk_host_id)] = (item.get("process_info") or {}).get("status") or ""
        return statuses

    # ------------------------------------------------------------------
    # 聚合
    # ------------------------------------------------------------------
    def refresh(self) -> dict[int, HostStatus]:
        """
        回读一轮状态并把「已生效的是第几代」落到本地快照。

        必须落库：节点管理只保留最近若干轮 workflow，一旦过期就再也回答不了「这台主机上生效的是
        哪一代配置」。而这正是区分 LATEST 与 STALE 的唯一依据。
        """
        binding = self.binding
        if not binding:
            return {}

        resolution = self.resolve_workflows()
        if self.task_ids and resolution.workflow is None:
            return {}
        host_operations = self.fetch_host_operations(resolution.plugin_workflow_ids)
        if self.task_ids:
            return self._historical_statuses(host_operations, resolution)

        # 本轮 workflow 对应的是哪一代期望态，取自本地 operation 记录而不是节点管理。
        dispatched_generation = resolution.workflow.operation.generation if resolution.workflow else 0

        rows = list(NodeManV3SubConfigTarget.objects.filter(binding=binding))
        process_status = self.fetch_process_status(sorted({row.bk_host_id for row in rows}))
        now = timezone.now()
        for row in rows:
            if not row.is_desired:
                # 已移出范围的行不该再认领新一代：它的 generation 是「移出时生效的是哪一代」，
                # 推进它会让待删除主机在页面上显示成已生效最新
                continue
            operation = host_operations.get(row.bk_host_id)
            proc = process_status.get(row.bk_host_id, "")
            process_allows_apply = not proc or proc == PROCESS_STATUS_RUNNING
            operation_succeeded = operation and (
                NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(operation["state"]) == NodeManV3OperationStatus.SUCCESS
            )
            # 父、子 workflow 均成功但该主机没有 operation，表示 NodeMan 判断资源无需变更。
            # 这是一轮合法 no-op，仍要把本地代次推进到最新。
            no_op_succeeded = not operation and resolution.missing_operation_is_noop
            if not process_allows_apply:
                continue
            if not operation_succeeded and not no_op_succeeded:
                continue
            if dispatched_generation <= row.generation:
                continue
            row.generation = dispatched_generation
            row.applied_at = now
            row.save(update_fields=["generation", "applied_at", "updated_at", "updated_by"])

        return self._assemble(
            binding,
            rows,
            host_operations,
            resolution.normalized_status,
            resolution.missing_operation_is_noop,
            resolution.task_id,
            process_status,
        )

    def _historical_statuses(
        self,
        host_operations: dict[int, dict],
        resolution: WorkflowResolution,
    ) -> dict[int, HostStatus]:
        """
        显式 task ID 查询是历史审计视图，只按该轮 operation 事实展示。

        当前 target 快照会随编辑、扩缩容变化，既不能拿来补历史 no-op，也不能在查看旧任务时
        被反向推进。没有 operation 的历史主机因 NodeMan 契约信息不足而不伪造。
        """
        generation = resolution.workflow.operation.generation if resolution.workflow else 0
        statuses = {}
        for bk_host_id, operation in host_operations.items():
            normalized = NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(operation.get("state"))
            if normalized == NodeManV3OperationStatus.SUCCESS:
                state = NodeManV3TargetState.LATEST
            elif normalized == NodeManV3OperationStatus.FAILED:
                state = NodeManV3TargetState.FAILED
            else:
                state = NodeManV3TargetState.DISPATCHING
            statuses[bk_host_id] = HostStatus(
                bk_host_id=bk_host_id,
                state=state,
                applied_generation=generation if normalized == NodeManV3OperationStatus.SUCCESS else 0,
                task_id=resolution.task_id,
                operation_id=operation.get("operation_id", ""),
            )
        return statuses

    def _assemble(
        self,
        binding: NodeManV3Binding,
        rows: list[NodeManV3SubConfigTarget],
        host_operations: dict[int, dict],
        workflow_status: str,
        missing_operation_is_noop: bool,
        task_id: str,
        process_status: dict[int, str] | None = None,
    ) -> dict[int, HostStatus]:
        if process_status is None:
            process_status = self.fetch_process_status(sorted({row.bk_host_id for row in rows}))

        # 一个采集项可能声明多个子配置模板（主配置 + 多个子配置），同一主机会有多行。
        # 必须取「最落后」的那一行：只要有一个模板没落地，这台主机就不算生效完整。
        # 按 DB 返回顺序取第一行会让 A 模板成功、B 模板失败的主机显示成绿色，掩盖真实缺口。
        #
        # is_desired 必须先分组再比 generation，不能放进同一个元组一起比：改采集场景会换模板名，
        # 于是同一台仍在范围内的主机上会同时存在「新文件名 is_desired=True」与
        # 「旧文件名 is_desired=False」两行。混在一起比会挑中后者（False < True），
        # 把一台正在正常采集的主机显示成「待删除」。只有一台主机的全部行都已移出，才算待删除。
        rows_by_host: dict[int, list[NodeManV3SubConfigTarget]] = {}
        for row in rows:
            rows_by_host.setdefault(row.bk_host_id, []).append(row)

        conservative: dict[int, NodeManV3SubConfigTarget] = {}
        for bk_host_id, host_rows in rows_by_host.items():
            desired_rows = [row for row in host_rows if row.is_desired]
            conservative[bk_host_id] = min(desired_rows or host_rows, key=lambda row: row.generation)

        return {
            bk_host_id: self._classify(
                binding,
                row,
                host_operations,
                process_status,
                workflow_status,
                missing_operation_is_noop,
                task_id,
            )
            for bk_host_id, row in conservative.items()
        }

    def _classify(
        self,
        binding: NodeManV3Binding,
        row: NodeManV3SubConfigTarget,
        host_operations: dict[int, dict],
        process_status: dict[int, str],
        workflow_status: str,
        missing_operation_is_noop: bool,
        task_id: str,
    ) -> HostStatus:
        operation = host_operations.get(row.bk_host_id) or {}
        normalized = NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(operation.get("state"))
        proc = process_status.get(row.bk_host_id, "")
        status = HostStatus(
            bk_host_id=row.bk_host_id,
            state=NodeManV3TargetState.ABSENT,
            applied_generation=row.generation,
            process_status=proc,
            task_id=task_id,
            operation_id=operation.get("operation_id", ""),
        )

        if not row.is_desired:
            # 已移出采集范围。删除是异步的，在确认主机上没有残留之前不能说它「不存在」
            status.state = NodeManV3TargetState.PENDING_REMOVAL
            status.message = _("已移出采集目标，等待节点管理删除子配置")
            return status

        if (
            not operation
            and not missing_operation_is_noop
            and workflow_status
            in (
                NodeManV3OperationStatus.PENDING,
                NodeManV3OperationStatus.RUNNING,
            )
        ):
            status.state = NodeManV3TargetState.DISPATCHING
            return status

        if (
            not operation
            and not missing_operation_is_noop
            and workflow_status
            in (
                NodeManV3OperationStatus.FAILED,
                NodeManV3OperationStatus.PARTIAL_FAILED,
            )
        ):
            if proc and proc != PROCESS_STATUS_RUNNING:
                status.message = _("采集器进程未运行，子配置暂不下发")
                return status
            status.state = NodeManV3TargetState.FAILED
            status.message = _("最近一次部署策略派发失败")
            return status

        if normalized in (NodeManV3OperationStatus.PENDING, NodeManV3OperationStatus.RUNNING):
            status.state = NodeManV3TargetState.DISPATCHING
            return status

        if proc and proc != PROCESS_STATUS_RUNNING:
            status.state = NodeManV3TargetState.ABSENT
            status.message = _("采集器进程未运行，子配置暂不下发")
            return status

        if normalized == NodeManV3OperationStatus.FAILED:
            status.state = NodeManV3TargetState.FAILED
            status.message = _("最近一次下发失败")
            return status

        if row.generation <= 0:
            status.state = NodeManV3TargetState.ABSENT
            if proc and proc != PROCESS_STATUS_RUNNING:
                status.message = _("采集器进程未运行，子配置暂不下发")
            return status

        if row.generation >= binding.generation:
            status.state = NodeManV3TargetState.LATEST
            return status

        # 仍在出数，只是配置是旧版。这一态刻意与 FAILED 分开：把它翻红会让用户去重试一个
        # 其实正在正常采集的采集项，而真正该做的是等下一轮收敛或手工重新下发
        status.state = NodeManV3TargetState.STALE
        status.message = _("生效的是第 {} 代配置，最新为第 {} 代").format(row.generation, binding.generation)
        return status

    def summary(self) -> dict:
        """采集项级汇总，替代 V2 的 subscription_statistic。"""
        states = self.refresh()
        counts = {state.value: 0 for state in NodeManV3TargetState}
        for status in states.values():
            counts[status.state] += 1
        return {
            "collector_config_id": self.collector_config.collector_config_id,
            "total": len(states),
            "counts": counts,
            # 兼容旧状态页的三态口径：STALE 归入成功（它确实在出数），PENDING_REMOVAL 不计入
            "success": counts[NodeManV3TargetState.LATEST] + counts[NodeManV3TargetState.STALE],
            "pending": counts[NodeManV3TargetState.DISPATCHING] + counts[NodeManV3TargetState.ABSENT],
            "failed": counts[NodeManV3TargetState.FAILED],
        }

    # ------------------------------------------------------------------
    # per-host 详情与重试
    # ------------------------------------------------------------------
    def instance_detail(self, bk_host_id: int) -> dict:
        """
        单台主机的执行实例与日志，附带一次子配置精确对账。

        对账只在这里做：`plugin/list_config_files` 是单主机接口，放进状态页会按主机数放大请求。
        点开单台详情正是它唯一负担得起的场景，而这时用户要回答的恰恰是
        「这台机器上到底有没有我这份配置」—— 状态页的 workflow 成败推断答不了。
        """
        resolution = self.resolve_workflows()
        operation = self.fetch_host_operations(resolution.plugin_workflow_ids).get(bk_host_id)
        if not operation:
            return {"bk_host_id": bk_host_id, "instances": [], "logs": {}, "config_files": self._verify(bk_host_id)}

        client = get_client(self.bk_biz_id)
        operation_ids_by_workflow: dict[str, list[str]] = {}
        for item in operation["operations"]:
            workflow_id = item.get("workflow_id") or ""
            operation_id = item.get("operation_id") or ""
            if workflow_id and operation_id:
                operation_ids_by_workflow.setdefault(workflow_id, []).append(operation_id)

        # instance/list 用首个 operation_id 定位所属 workflow 并做权限校验，不能把不同
        # plugin workflow 的 operation 混在同一次请求里。
        instances = []
        for operation_ids in operation_ids_by_workflow.values():
            data = client.list_workflow_operation_instances({"operation_id": list(dict.fromkeys(operation_ids))})
            instances.extend((data or {}).get("oper_inst_data") or [])

        logs = {}
        for instance in instances:
            oper_inst_id = instance.get("oper_inst_id")
            if not oper_inst_id:
                continue
            logs[oper_inst_id] = (client.get_workflow_operation_instance_log({"oper_inst_id": oper_inst_id}) or {}).get(
                "oper_inst_logs"
            ) or {}

        return {
            "bk_host_id": bk_host_id,
            "instances": instances,
            "logs": logs,
            "config_files": self._verify(bk_host_id),
        }

    def _verify(self, bk_host_id: int) -> dict:
        """
        子配置精确对账。失败不能影响详情页主体 —— 对账是附加信息，
        接口不可用（如联调环境的节点管理版本低于 v3.0.1-alpha.77）时详情页仍要能打开。
        """
        binding = self.binding
        if not binding:
            return {"checked": False}
        try:
            from apps.log_databus.nodeman_v3.config_files import verify_host_targets

            return verify_host_targets(binding, bk_host_id, self.plugin_name)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                f"[nodeman_v3] verify host config files failed, "
                f"collector_config_id={self.collector_config.collector_config_id}, bk_host_id={bk_host_id}"
            )
            return {"checked": False}

    def retry_hosts(self, bk_host_ids: list[int]) -> str:
        """
        按主机重试最近一轮下发。

        重试的是节点管理侧那一轮 workflow，不是重新推期望态：期望态没变时重推会被指纹短路，
        而这里要做的恰恰是「配置是对的、执行失败了，再跑一次」。
        """
        resolution = self.resolve_workflows()
        if not resolution.plugin_workflow_ids:
            # 失败关闭：拿不到 plugin 子 workflow 就没法定位要重试哪一批，静默成功会让用户
            # 以为已经重试过了
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("尚未解析到插件子 workflow，无法重试"))
            )

        host_operations = self.fetch_host_operations(resolution.plugin_workflow_ids)
        operations_by_workflow_and_mode: dict[tuple[str, str], list[dict]] = {}
        for bk_host_id in bk_host_ids:
            for item in (host_operations.get(bk_host_id) or {}).get("operations") or []:
                if NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(item.get("state")) != NodeManV3OperationStatus.FAILED:
                    continue
                workflow_id = item.get("workflow_id") or ""
                operation_id = item.get("operation_id") or ""
                if workflow_id and operation_id:
                    retry_mod = "ALL" if item.get("state") == "terminated" else "PARTIAL"
                    operations_by_workflow_and_mode.setdefault((workflow_id, retry_mod), []).append(item)

        if not operations_by_workflow_and_mode:
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("目标主机在最近一轮任务中没有失败的执行记录"))
            )

        binding = self.binding
        operation = binding.operations.order_by("-generation", "-created_at").first() if binding else None
        client = get_client(self.bk_biz_id, operation_id=str(operation.id) if operation else "")
        for (workflow_id, retry_mod), items in operations_by_workflow_and_mode.items():
            client.retry_workflow_operation(
                {
                    "workflow_id": workflow_id,
                    "retry_mod": retry_mod,
                    "operation_ids": list(dict.fromkeys(item["operation_id"] for item in items)),
                }
            )
        return resolution.task_id
