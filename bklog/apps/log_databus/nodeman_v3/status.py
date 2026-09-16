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

# 翻页轮数上限。workflow 列表既没有 trigger_id 过滤也没有排序参数，只能按策略拉全量自己匹配，
# 给个上限避免策略历史任务堆积后把状态页拖死。
MAX_PAGES = 20


def iter_paged(fetch, items_key: str):
    """
    按 {offset, limit} 逐页取数。

    ⚠️ NodeMan 的分页参数分两套，不能混用：

    - `plugin/workflow/list`、`plugin/workflow/operation/list`、`process/list` 用 `{offset, limit}`，
      且 `limit` 必填、必须落在 `(0, 500]`
    - `deploy_policy/list` 用 `{count, start, limit}`

    传错不会报错 —— gin 没开 `EnableDecoderDisallowUnknownFields`，未知字段被静默忽略，
    于是 `offset` 恒为 0，翻页永远停在第一页。

    终止条件用「本页条数不足 limit」而不是 `total`：这两个接口的 `total` 由**顶层** `only_count`
    控制，`only_count` 为假时 `total` 可能回 0，拿它当边界会在第一页就退出。
    """
    offset = 0
    for _page_index in range(MAX_PAGES):
        items = (fetch(offset) or {}).get(items_key) or []
        if not items:
            return
        yield items
        if len(items) < PAGE_LIMIT:
            return
        offset += PAGE_LIMIT
    logger.warning(f"[nodeman_v3] paged query hit MAX_PAGES={MAX_PAGES}, results may be truncated")


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
                "task_id": status.operation_id,
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
    operation_id: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "bk_host_id": self.bk_host_id,
            "state": self.state,
            "state_name": str(NodeManV3TargetState(self.state).label),
            "applied_generation": self.applied_generation,
            "process_status": self.process_status,
            "operation_id": self.operation_id,
            "message": self.message,
        }


class CollectorStatusReader:
    """
    V3 采集项状态回读。

    与 V2 状态页最根本的差别：**不能把 bkunifylogbeat 进程 running 当成采集项已生效**。
    同机多个采集项共用一个进程，进程活着只说明别的采集项在跑；本采集项有没有生效，
    取决于这台主机上有没有本策略的那份子配置（文件名带 deploy_policy_id）。

    状态来源分两层：

    - **权威层**：节点管理的 workflow → operation（per-host），给出最近一轮下发在每台主机上的
      成败。链路是 execute 返回 trigger_id → plugin/workflow/list 按 deploy_policy_id 反查
      workflow_id → plugin/workflow/operation/list 按 workflow_id 拿到每台主机的 operation
      （PluginDeploymentInfo.bk_host_id）。
    - **本地层**：NodeManV3SubConfigTarget 记录每台主机当前生效的是第几代期望态，用于区分
      「已生效且最新」与「已生效但旧版」——这个区分节点管理给不出来，它只知道最近一轮任务的成败，
      不知道上一代配置是不是还留在机器上。

    进程状态只作为**否定证据**使用：进程不 running 时节点管理压根不会下发子配置，还会把已有记录删掉
    （analyze_specific_plugin_sub_config_template.go:113-117、:228-236）。这是采集器重启期间的
    常态，不是下发失败，所以这种情况不能翻红，否则每次采集器升级都会让整页告警。
    """

    def __init__(self, collector_config, plugin_name: str = LogPluginInfo.NAME):
        self.collector_config = collector_config
        self.plugin_name = plugin_name
        self.bk_biz_id = collector_config.bk_biz_id

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

    def resolve_workflow_id(self) -> str:
        """
        把最近一次 execute 的 trigger_id 解析成 workflow_id。

        deploy_policy/execute 只返回 trigger_id，而 per-host 详情、日志与重试都要 workflow_id。
        plugin/workflow/list 的精确条件里没有 trigger_id，只能按 deploy_policy_id 过滤后
        在返回项里匹配 trigger_id。解析结果回写 NodeManV3Workflow，避免每次开状态页都查一遍。
        """
        binding = self.binding
        if not binding or not binding.deploy_policy_id:
            return ""

        workflow = (
            NodeManV3Workflow.objects.filter(operation__binding=binding)
            .order_by("-operation__generation", "-created_at")
            .first()
        )
        if not workflow:
            return ""
        if workflow.workflow_id:
            return workflow.workflow_id

        client = get_client(self.bk_biz_id)
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
                if item.get("trigger_id") == workflow.trigger_id and item.get("workflow_id"):
                    workflow.workflow_id = item["workflow_id"]
                    workflow.save(update_fields=["workflow_id", "updated_at", "updated_by"])
                    return workflow.workflow_id

        # 解析不到不是错误：execute 之后 workflow 可能还没落库，下次开页面再试
        logger.info(
            f"[nodeman_v3] workflow not resolved yet, trigger_id={workflow.trigger_id}, "
            f"deploy_policy_id={binding.deploy_policy_id}"
        )
        return ""

    # ------------------------------------------------------------------
    # 节点管理侧事实
    # ------------------------------------------------------------------
    def fetch_host_operations(self, workflow_id: str) -> dict[int, dict]:
        """
        按主机拿到最近一轮下发的 operation。

        返回 {bk_host_id: {"operation_id": ..., "state": ..., "raw": ...}}。
        """
        if not workflow_id:
            return {}

        client = get_client(self.bk_biz_id)
        operations: dict[int, dict] = {}
        for items in iter_paged(
            lambda offset: client.list_workflow_operations(
                {
                    "workflow_id": workflow_id,
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
                    "operation_id": item.get("operation_id") or "",
                    "state": state,
                    "instance_ids": item.get("instance_ids") or [],
                }
                current = operations.get(int(bk_host_id))
                # 同一主机会有多个 operation：策略至少带两个 spec（装插件 + 下子配置），
                # 各自生成一条。直接覆盖等于按接口返回顺序随机取一条，会把失败那条盖掉而显示成功。
                # 取最坏的那条：只要有一步没成，这台主机就不算下发成功
                if current is None or _operation_severity(candidate["state"]) > _operation_severity(current["state"]):
                    operations[int(bk_host_id)] = candidate
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

        workflow_id = self.resolve_workflow_id()
        host_operations = self.fetch_host_operations(workflow_id)

        # 本轮 workflow 对应的是哪一代期望态，取自本地 operation 记录而不是节点管理：
        # 对方不知道我们的 generation，只有我们自己知道这次 execute 推的是第几代
        workflow = (
            NodeManV3Workflow.objects.filter(operation__binding=binding, workflow_id=workflow_id)
            .select_related("operation")
            .first()
            if workflow_id
            else None
        )
        dispatched_generation = workflow.operation.generation if workflow else 0

        rows = list(NodeManV3SubConfigTarget.objects.filter(binding=binding))
        now = timezone.now()
        for row in rows:
            if not row.is_desired:
                # 已移出范围的行不该再认领新一代：它的 generation 是「移出时生效的是哪一代」，
                # 推进它会让待删除主机在页面上显示成已生效最新
                continue
            operation = host_operations.get(row.bk_host_id)
            if not operation:
                continue
            normalized = NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(operation["state"])
            if normalized != NodeManV3OperationStatus.SUCCESS:
                continue
            if dispatched_generation <= row.generation:
                continue
            row.generation = dispatched_generation
            row.applied_at = now
            row.save(update_fields=["generation", "applied_at", "updated_at", "updated_by"])

        return self._assemble(binding, rows, host_operations)

    def _assemble(
        self,
        binding: NodeManV3Binding,
        rows: list[NodeManV3SubConfigTarget],
        host_operations: dict[int, dict],
    ) -> dict[int, HostStatus]:
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
            bk_host_id: self._classify(binding, row, host_operations, process_status)
            for bk_host_id, row in conservative.items()
        }

    def _classify(
        self,
        binding: NodeManV3Binding,
        row: NodeManV3SubConfigTarget,
        host_operations: dict[int, dict],
        process_status: dict[int, str],
    ) -> HostStatus:
        operation = host_operations.get(row.bk_host_id) or {}
        normalized = NODEMAN_V3_LIFE_CYCLE_STATE_MAPPING.get(operation.get("state"))
        proc = process_status.get(row.bk_host_id, "")
        status = HostStatus(
            bk_host_id=row.bk_host_id,
            state=NodeManV3TargetState.ABSENT,
            applied_generation=row.generation,
            process_status=proc,
            operation_id=operation.get("operation_id", ""),
        )

        if not row.is_desired:
            # 已移出采集范围。删除是异步的，在确认主机上没有残留之前不能说它「不存在」
            status.state = NodeManV3TargetState.PENDING_REMOVAL
            status.message = _("已移出采集目标，等待节点管理删除子配置")
            return status

        if normalized in (NodeManV3OperationStatus.PENDING, NodeManV3OperationStatus.RUNNING):
            status.state = NodeManV3TargetState.DISPATCHING
            return status

        if normalized == NodeManV3OperationStatus.FAILED:
            if proc and proc != PROCESS_STATUS_RUNNING:
                # 采集器进程不 running 时节点管理本来就不会下发子配置，这不是采集项配置错了。
                # 判成失败会让每次采集器升级/重启窗口整页翻红，真正的故障反而被淹没
                status.state = NodeManV3TargetState.ABSENT
                status.message = _("采集器进程未运行，子配置暂不下发")
                return status
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
            "pending": counts[NodeManV3TargetState.DISPATCHING],
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
        workflow_id = self.resolve_workflow_id()
        operation = self.fetch_host_operations(workflow_id).get(bk_host_id)
        if not operation:
            return {"bk_host_id": bk_host_id, "instances": [], "logs": {}, "config_files": self._verify(bk_host_id)}

        client = get_client(self.bk_biz_id)
        instances = (client.list_workflow_operation_instances({"operation_id": [operation["operation_id"]]}) or {}).get(
            "oper_inst_data"
        ) or []

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

    def retry_hosts(self, bk_host_ids: list[int], retry_mod: str = "failed") -> str:
        """
        按主机重试最近一轮下发。

        重试的是节点管理侧那一轮 workflow，不是重新推期望态：期望态没变时重推会被指纹短路，
        而这里要做的恰恰是「配置是对的、执行失败了，再跑一次」。
        """
        workflow_id = self.resolve_workflow_id()
        if not workflow_id:
            # 失败关闭：拿不到 workflow_id 就没法定位要重试哪一批，静默成功会让用户
            # 以为已经重试过了
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("尚未解析到 workflow_id，无法重试"))
            )

        host_operations = self.fetch_host_operations(workflow_id)
        operation_ids = [
            host_operations[bk_host_id]["operation_id"]
            for bk_host_id in bk_host_ids
            if bk_host_id in host_operations and host_operations[bk_host_id].get("operation_id")
        ]
        if not operation_ids:
            raise NodeManV3CapabilityBlocked(
                NodeManV3CapabilityBlocked.MESSAGE.format(err=_("目标主机在最近一轮任务中没有执行记录"))
            )

        binding = self.binding
        operation = binding.operations.order_by("-generation", "-created_at").first() if binding else None
        client = get_client(self.bk_biz_id, operation_id=str(operation.id) if operation else "")
        client.retry_workflow_operation(
            {"workflow_id": workflow_id, "retry_mod": retry_mod, "operation_ids": operation_ids}
        )
        return workflow_id
