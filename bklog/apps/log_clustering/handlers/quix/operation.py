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

import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.functional import cached_property

from apps.api import TransferApi
from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    BkFaraConflictException,
    BkFaraNotConfiguredException,
    QuixClusteringConfigInvalidException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.quix.adapter import build_binding
from apps.log_clustering.handlers.quix.bkfara import BkFaraClient, build_clustering_payload, build_create_task_payload
from apps.log_clustering.handlers.quix.config import get_quix_config
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_search.constants import InnerTag
from apps.log_search.models import LogIndexSet
from apps.utils.log import logger

POLL_INTERVAL_SECONDS = 15
MAX_RETRY_DELAY_SECONDS = 300
MAX_STEP_RETRIES = 5
WAIT_TIMEOUT_SECONDS = 30 * 60
# 待采用确认的步骤依赖 BKBase 回执，回执到位前持续低频检查，不按等待超时判失败
RECEIPT_POLL_INTERVAL_SECONDS = 5 * 60
STEP_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 旧范围内待办已投递、结果已入库、原源消费已确认，才能切换绑定
DRAINED_STATUS_KEYS = ("can_unbind", "storage_complete", "outbox_drained", "source_committed")

# BKBase 日志聚类状态中运行记录状态的字段，完整 schema 待 BKBase 确认
CLUSTERING_STATE_KEY = "state"
CLUSTERING_STATE_STOPPED = "STOPPED"

# 配置、凭据或控制版本问题，重试同一请求不会成功，需要人工处理后续跑
NON_RETRYABLE_EXCEPTIONS = (
    BkFaraNotConfiguredException,
    BkFaraConflictException,
    QuixClusteringConfigInvalidException,
    QuixClusteringParamsInvalidException,
)


def runtime_adoption_confirmed(status: dict) -> bool:
    """
    BKBase 是否回执所有相关 Runtime 实例已采用当前下发的聚类配置
    配置层证据（Databus 引用、资源 phase=Ok）不能代替采用回执；BKBase 提供可核验的回执前一律视为未确认
    """
    return False


def runtime_detach_confirmed(status: dict) -> bool:
    """
    BKBase 是否回执所有相关 Runtime 实例已恢复原存储绑定
    binding_removed=true 只能来自该回执；BKBase status 中的 binding_removed 固定为 false，提供可核验的回执前一律视为未确认
    """
    return False


def is_worker_ready(clustering: dict) -> bool:
    """所有目标 Worker 已加载目标模型；成员列表包含历史实例，不能按条数判断"""
    target_model_ref = clustering.get("target_model_ref")
    return (
        clustering.get("state") == "RUNNING"
        and bool(target_model_ref)
        and clustering.get("all_ready_model_ref") == target_model_ref
    )


class QuixClusteringOperationRunner:
    """
    逐步执行控制操作；每步成功后落库，等待外部状态时返回下次调度的延迟，由异步任务重新调度
    步骤必须可重入：外部写调用沿用操作内固定的幂等键，已保存的结果不再重复申请
    """

    STEPS = {
        ClusteringOperationTypeEnum.ENABLE.value: [
            "create_task",
            "wait_task_ready",
            "configure_clustering",
            "wait_worker_ready",
            "metadata_set",
            "wait_adoption",
            "confirm_adoption",
        ],
        # Quix 保持运行；旧范围收尾后才提交新过滤规则，过渡期新增日志不参与聚类，记为覆盖缺口
        ClusteringOperationTypeEnum.UPDATE.value: [
            "drain",
            "wait_drained",
            "finish",
            "metadata_set",
            "wait_adoption",
            "confirm_adoption",
        ],
        # 候选边界只固定一次；结果入库并实际恢复原存储绑定后，才向 BKFara 提交最终完成确认
        ClusteringOperationTypeEnum.DISABLE.value: [
            "check_binding",
            "drain",
            "wait_boundary",
            "stop_draining",
            "wait_drained",
            "finish",
            "detach",
            "wait_detached",
            "confirm_detached",
            "stop_completed",
        ],
        # 复用原任务、Topic、消费组和运行态模型，继续原消费位置
        ClusteringOperationTypeEnum.REOPEN.value: [
            "refresh_control_version",
            "restart",
            "wait_worker_ready",
            "attach",
            "wait_adoption",
            "resume",
            "confirm_adoption",
        ],
    }
    RECEIPT_STEPS = {"confirm_adoption", "confirm_detached"}

    def __init__(self, operation_id: str):
        self.operation = LogClusteringOperation.objects.get(operation_id=operation_id)
        self.runtime = LogClusteringRuntime.objects.get(index_set_id=self.operation.index_set_id)

    @cached_property
    def bkfara(self) -> BkFaraClient:
        return BkFaraClient()

    @cached_property
    def quix_config(self) -> dict:
        return get_quix_config()

    def run(self) -> int | None:
        """执行到需要等待或结束为止，返回下次调度的延迟秒数，None 表示无需再调度"""
        # 与关闭接替操作使用同一行锁：重新读取后领取执行，不能复活已取消的操作。
        # 远端调用期间标为 RUNNING，关闭只能接替已经结束本轮执行的失败/待回执操作。
        with transaction.atomic():
            self.operation = LogClusteringOperation.objects.select_for_update().get(pk=self.operation.pk)
            if self.operation.status not in ClusteringOperationStatusEnum.runnable_statuses():
                return None
            self.runtime.refresh_from_db()
            self.operation.status = ClusteringOperationStatusEnum.RUNNING.value
            self.operation.save(update_fields=["status", "updated_at", "updated_by"])

        for step in self._remaining_steps():
            self.operation.step = step
            self.operation.save(update_fields=["step", "updated_at", "updated_by"])
            try:
                done = getattr(self, f"_step_{step}")()
            except Exception as e:  # pylint: disable=broad-except
                return self._handle_error(step, e)
            if not done:
                return self._await_receipt(step) if step in self.RECEIPT_STEPS else self._wait(step)
            self.operation.retry_count = 0
            if self.operation.status == ClusteringOperationStatusEnum.AWAITING_RECEIPT.value:
                self.operation.status = ClusteringOperationStatusEnum.RUNNING.value
                self.operation.save(update_fields=["status", "updated_at", "updated_by"])
            self.operation.record_step(step, ClusteringOperationStatusEnum.SUCCESS.value)

        # 收尾与操作成功同一事务提交，中途退出后续跑不会重复提升已清空的待生效配置
        try:
            with transaction.atomic():
                getattr(self, f"_finish_{self.operation.operation_type}")()
                self.operation.status = ClusteringOperationStatusEnum.SUCCESS.value
                self.operation.next_retry_at = None
                self.operation.finished_at = timezone.now()
                self.operation.save(
                    update_fields=["status", "next_retry_at", "finished_at", "updated_at", "updated_by"]
                )
        except Exception as e:  # pylint: disable=broad-except
            self.operation.status = ClusteringOperationStatusEnum.RUNNING.value
            return self._handle_error("finish", e)
        return None

    def _remaining_steps(self) -> list[str]:
        finished = {
            item["step"]
            for item in self.operation.steps
            if item["status"] == ClusteringOperationStatusEnum.SUCCESS.value
        }
        return [step for step in self.STEPS[self.operation.operation_type] if step not in finished]

    def _wait(self, step: str) -> int | None:
        started = self._wait_started_at(step)
        if started is None:
            self.operation.record_step(step, ClusteringOperationStatusEnum.RUNNING.value)
        elif (timezone.now() - started).total_seconds() > WAIT_TIMEOUT_SECONDS:
            return self._fail(step, f"waiting for {step} timed out after {WAIT_TIMEOUT_SECONDS}s")
        return self._schedule(POLL_INTERVAL_SECONDS)

    def _wait_started_at(self, step: str) -> datetime.datetime | None:
        for item in reversed(self.operation.steps):
            if item["step"] != step:
                continue
            # 失败后续跑重新计时，不能沿用上一轮的等待起点
            if item["status"] == ClusteringOperationStatusEnum.FAILED.value:
                return None
            if item["status"] == ClusteringOperationStatusEnum.RUNNING.value:
                return datetime.datetime.strptime(item["time"], STEP_TIME_FORMAT).replace(tzinfo=datetime.timezone.utc)
        return None

    def _await_receipt(self, step: str) -> int:
        self.operation.status = ClusteringOperationStatusEnum.AWAITING_RECEIPT.value
        self.operation.save(update_fields=["status", "updated_at", "updated_by"])
        last_step = self.operation.steps[-1] if self.operation.steps else {}
        if (last_step.get("step"), last_step.get("status")) != (
            step,
            ClusteringOperationStatusEnum.AWAITING_RECEIPT.value,
        ):
            self.operation.record_step(step, ClusteringOperationStatusEnum.AWAITING_RECEIPT.value)
        return self._schedule(RECEIPT_POLL_INTERVAL_SECONDS)

    def _handle_error(self, step: str, error: Exception) -> int | None:
        logger.exception("[quix_clustering] operation(%s) step(%s) failed", self.operation.operation_id, step)
        self.operation.retry_count += 1
        self.operation.last_error = f"{step}: {error}"
        if isinstance(error, NON_RETRYABLE_EXCEPTIONS) or self.operation.retry_count >= MAX_STEP_RETRIES:
            return self._fail(step, self.operation.last_error)
        self.operation.save(update_fields=["retry_count", "last_error", "updated_at", "updated_by"])
        return self._schedule(min(POLL_INTERVAL_SECONDS * 2**self.operation.retry_count, MAX_RETRY_DELAY_SECONDS))

    def _fail(self, step: str, message: str) -> None:
        self.operation.status = ClusteringOperationStatusEnum.FAILED.value
        self.operation.last_error = message
        self.operation.next_retry_at = None
        self.operation.save(
            update_fields=["status", "last_error", "retry_count", "next_retry_at", "updated_at", "updated_by"]
        )
        self.operation.record_step(step, ClusteringOperationStatusEnum.FAILED.value, message)
        return None

    def _schedule(self, delay: int) -> int:
        self.operation.next_retry_at = timezone.now() + datetime.timedelta(seconds=delay)
        self.operation.save(update_fields=["next_retry_at", "updated_at", "updated_by"])
        return delay

    def _save_runtime(self, **fields):
        for field, value in fields.items():
            setattr(self.runtime, field, value)
        self.runtime.save(update_fields=[*fields, "updated_at", "updated_by"])

    def _metadata_params(self, **params) -> dict:
        return {"bk_tenant_id": self.runtime.bk_tenant_id, "table_id": self.runtime.table_id, **params}

    def _step_create_task(self) -> bool:
        if self.runtime.bkfara_task_id:
            return True
        payload = self.operation.get_request_payload(
            "create_task", lambda: build_create_task_payload(self.runtime.index_set_id, self.quix_config)
        )
        result = self.bkfara.create_task(payload, self.operation.get_idempotency_key("create_task"))
        self._save_runtime(bkfara_task_id=result["task_id"])
        return True

    def _step_wait_task_ready(self) -> bool:
        task = self.bkfara.get_task(self.runtime.bkfara_task_id)
        if task.get("status") != "READY" or not task.get("trained_model_ref"):
            return False
        self._save_runtime(control_version=task["control_version"], generation=task["current_generation"])
        return True

    def _step_configure_clustering(self) -> bool:
        payload = self.operation.get_request_payload(
            "configure_clustering",
            lambda: build_clustering_payload(
                self.runtime.bkfara_task_id, self.runtime.control_version, self.quix_config
            ),
        )
        self.bkfara.configure_clustering(
            self.runtime.bkfara_task_id, payload, self.operation.get_idempotency_key("configure_clustering")
        )
        return True

    def _step_wait_worker_ready(self) -> bool:
        clustering = self.bkfara.get_clustering(self.runtime.bkfara_task_id)
        if not is_worker_ready(clustering):
            return False
        if self.operation.operation_type == ClusteringOperationTypeEnum.REOPEN.value:
            # 重开沿用 metadata 中的原绑定；BKFara 侧绑定变化时不能静默覆盖本地记录，需人工确认后处理
            if (clustering["kafka"], clustering["input_revision"]) != (
                self.runtime.kafka_binding,
                self.runtime.input_revision,
            ):
                raise QuixClusteringParamsInvalidException(
                    QuixClusteringParamsInvalidException.MESSAGE.format(
                        detail="bkfara clustering binding changed after restart"
                    )
                )
            return True
        self._save_runtime(kafka_binding=clustering["kafka"], input_revision=clustering["input_revision"])
        return True

    def _step_metadata_set(self) -> bool:
        clustering_config = self.runtime.pending_config or self.runtime.active_config
        params = self.operation.get_request_payload(
            "metadata_set",
            lambda: self._metadata_params(
                binding=build_binding(self.runtime, clustering_config, self.quix_config.get("max_message_bytes")),
                kafka_resource=self.quix_config["kafka_resource"],
                pattern_resource=self.quix_config["pattern_resource"],
            ),
        )
        result = TransferApi.set_log_clustering_config(params)
        self._save_runtime(sink=result["sink"])
        return True

    def _step_wait_adoption(self) -> bool:
        # 配置层就绪：Databus 引用聚类 Sink 且资源就绪；任一远端状态查询失败都视为未就绪
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        sink_phase = ((status.get("sink_resource") or {}).get("status") or {}).get("phase")
        return not status.get("errors") and bool(status.get("sink_referenced")) and sink_phase == "Ok"

    def _step_confirm_adoption(self) -> bool:
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        return not status.get("errors") and runtime_adoption_confirmed(status)

    def _promote_pending_config(self, **fields):
        # 待生效配置已提升过时不能再次提升，否则会把空配置写入生效配置
        if self.runtime.pending_config is not None:
            fields.update(active_config=self.runtime.pending_config, pending_config=None)
        self._save_runtime(**fields)

    def _operate_metadata(self, action: str) -> bool:
        TransferApi.operate_log_clustering(self._metadata_params(action=action))
        return True

    @property
    def _binding_attached(self) -> bool:
        """日志链路是否引用聚类 Sink；只有关闭会在首步判定，其余操作必然已绑定"""
        return self.operation.request_snapshot.get("binding_attached", True)

    def _step_check_binding(self) -> bool:
        # 关闭可能接替失败或待确认的操作：已绑定时重新取候选边界；未绑定时跳过 BKBase 收尾，沿用已有候选边界
        attached = False
        if self.runtime.sink:
            status = TransferApi.get_log_clustering_status(self._metadata_params())
            attached = bool(status.get("configured")) and bool(status.get("attached"))
        if attached:
            self._save_runtime(candidate_boundary=None, outbox_boundary=None)
        self.operation.request_snapshot = {**self.operation.request_snapshot, "binding_attached": attached}
        self.operation.save(update_fields=["request_snapshot", "updated_at", "updated_by"])
        return True

    def _step_drain(self) -> bool:
        return self._operate_metadata("drain") if self._binding_attached else True

    def _step_finish(self) -> bool:
        return self._operate_metadata("finish") if self._binding_attached else True

    def _step_wait_drained(self) -> bool:
        if not self._binding_attached:
            return True
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        clustering_status = status.get("clustering_status") or {}
        if not all(clustering_status.get(key) for key in DRAINED_STATUS_KEYS):
            return False
        # can_unbind 只表示可以技术切换，coverage_complete=false 时说明旧范围内有跳过的日志
        if not any(gap["operation_id"] == self.operation.operation_id for gap in self.runtime.coverage_gaps):
            self.runtime.coverage_gaps.append(
                {
                    "operation_id": self.operation.operation_id,
                    "operation_type": self.operation.operation_type,
                    "started_at": self._step_finished_at("drain"),
                    "ended_at": None,
                    "coverage_complete": clustering_status.get("coverage_complete"),
                }
            )
        self._save_runtime(
            coverage_gaps=self.runtime.coverage_gaps,
            outbox_boundary=clustering_status.get("outbox_boundary"),
        )
        return True

    def _step_wait_boundary(self) -> bool:
        if self.runtime.candidate_boundary is not None:
            return True
        if not self._binding_attached:
            # 从未绑定到日志链路时候选 Topic 没有写入过数据，结束位置即各分区起点
            partitions = self.runtime.kafka_binding.get("partitions") or self.quix_config["kafka"]["partitions"]
            self._save_runtime(candidate_boundary={str(partition): 0 for partition in range(partitions)})
            return True
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        clustering_status = status.get("clustering_status") or {}
        if not clustering_status.get("boundary_ready") or clustering_status.get("boundary") is None:
            return False
        # boundary 是候选 Topic 范围，outbox_boundary 是原日志 Topic 范围，两者不能混用
        self._save_runtime(
            candidate_boundary=clustering_status["boundary"],
            outbox_boundary=clustering_status.get("outbox_boundary"),
        )
        return True

    def _step_stop_draining(self) -> bool:
        if not self.runtime.bkfara_task_id:
            return True
        self.bkfara.stop_clustering(self.runtime.bkfara_task_id, self.runtime.candidate_boundary)
        return True

    def _step_detach(self) -> bool:
        return self._operate_metadata("detach") if self._binding_attached else True

    def _step_wait_detached(self) -> bool:
        # 配置层就绪：Databus 已改回原存储绑定；任一远端状态查询失败都视为未就绪
        if not self._binding_attached:
            return True
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        databus_phase = ((status.get("databus_resource") or {}).get("status") or {}).get("phase")
        return (
            not status.get("errors")
            and bool(status.get("raw_sink_referenced"))
            and not status.get("sink_referenced")
            and databus_phase == "Ok"
        )

    def _step_confirm_detached(self) -> bool:
        # 未绑定过日志链路时解绑是既成事实；已绑定时需要 BKBase 回执，回执前不能向 BKFara 提交 binding_removed
        if not self._binding_attached:
            return True
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        return not status.get("errors") and runtime_detach_confirmed(status)

    def _step_stop_completed(self) -> bool:
        if not self.runtime.bkfara_task_id:
            return True
        boundary = self.runtime.candidate_boundary
        self.bkfara.stop_clustering(
            self.runtime.bkfara_task_id,
            boundary,
            completion={"input_boundary": boundary, "storage_complete": True, "binding_removed": True},
        )
        return True

    def _step_refresh_control_version(self) -> bool:
        task = self.bkfara.get_task(self.runtime.bkfara_task_id)
        self._save_runtime(control_version=task["control_version"])
        return True

    def _step_restart(self) -> bool:
        self.bkfara.restart_clustering(
            self.runtime.bkfara_task_id, self.runtime.control_version, self.operation.get_idempotency_key("restart")
        )
        return True

    def _step_attach(self) -> bool:
        return self._operate_metadata("attach")

    def _step_resume(self) -> bool:
        # 同一绑定的旧运行记录仍为 STOPPED 时才需要 resume，新配置会自动建立运行记录
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        state = (status.get("clustering_status") or {}).get(CLUSTERING_STATE_KEY)
        if status.get("errors") or not state:
            return False
        if state == CLUSTERING_STATE_STOPPED:
            return self._operate_metadata("resume")
        return True

    def _finish_reopen(self):
        self._save_runtime(
            phase=ClusteringRuntimePhaseEnum.RUNNING.value, candidate_boundary=None, outbox_boundary=None
        )
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=True)
        LogIndexSet.set_tag(self.runtime.index_set_id, InnerTag.CLUSTERING.value)

    def _finish_disable(self):
        self._close_coverage_gap()
        self._save_runtime(phase=ClusteringRuntimePhaseEnum.STOPPED.value, coverage_gaps=self.runtime.coverage_gaps)
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=False)
        LogIndexSet.delete_tag_by_name(self.runtime.index_set_id, InnerTag.CLUSTERING.value)

    def _step_finished_at(self, step: str) -> str | None:
        for item in reversed(self.operation.steps):
            if item["step"] == step and item["status"] == ClusteringOperationStatusEnum.SUCCESS.value:
                return item["time"]
        return None

    def _close_coverage_gap(self):
        ended_at = timezone.now().strftime(STEP_TIME_FORMAT)
        for gap in self.runtime.coverage_gaps:
            if gap["operation_id"] == self.operation.operation_id and gap["ended_at"] is None:
                gap["ended_at"] = ended_at

    def _finish_update(self):
        self._close_coverage_gap()
        self._promote_pending_config(
            phase=ClusteringRuntimePhaseEnum.RUNNING.value, coverage_gaps=self.runtime.coverage_gaps
        )

    def _finish_enable(self):
        self._promote_pending_config(phase=ClusteringRuntimePhaseEnum.RUNNING.value)
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=True)
        LogIndexSet.set_tag(self.runtime.index_set_id, InnerTag.CLUSTERING.value)
