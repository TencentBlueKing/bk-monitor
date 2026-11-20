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

from apps.api import BkFaraApi, TransferApi
from apps.exceptions import ApiRequestError
from apps.log_clustering.constants import (
    QUIX_SIGNATURE_FIELD,
    SIGNATURE_FIELD,
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    QuixClusteringConfigInvalidException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.quix.adapter import build_binding, build_store_targets
from apps.log_clustering.handlers.quix.payload import build_create_task_payload
from apps.log_clustering.handlers.quix.config import get_quix_config
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE
from apps.log_search.constants import InnerTag
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_search.models import LogIndexSet, Scenario
from bkm_space.utils import parse_space_uid
from apps.utils.log import logger

POLL_INTERVAL_SECONDS = 15
MAX_RETRY_DELAY_SECONDS = 300
MAX_STEP_RETRIES = 5
WAIT_TIMEOUT_SECONDS = 30 * 60
STEP_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# 配置、凭据或控制版本问题，重试同一请求不会成功，需要人工处理后续跑
NON_RETRYABLE_EXCEPTIONS = (
    QuixClusteringConfigInvalidException,
    QuixClusteringParamsInvalidException,
)


def link_is_ready(status: dict) -> bool:
    """metadata 汇总的链路状态：Databus 已引用聚类 Sink，且两者均为 Ok。"""
    return not status.get("errors") and bool(status.get("ready"))


class ModelParameterRejected(Exception):
    """本次 PATCH 已明确拒绝，可结束操作并接受下一次修改。"""


class QuixClusteringOperationRunner:
    """
    逐步执行控制操作；每步成功后落库，等待外部状态时返回下次调度的延迟，由异步任务重新调度
    步骤必须可重入：外部写调用沿用操作内固定的幂等键，已保存的结果不再重复申请
    """

    STEPS = {
        ClusteringOperationTypeEnum.ENABLE.value: [
            "create_task",
            "read_binding",
            "metadata_set",
            "register_query_routes",
        ],
        # 同时修改模型和过滤时，先由 BKFara 接受模型参数，再下发过滤配置。
        ClusteringOperationTypeEnum.UPDATE.value: [
            "update_model_parameters",
            "confirm_model_parameters",
            "metadata_set",
            "register_query_routes",
        ],
        ClusteringOperationTypeEnum.UPDATE_MODEL.value: [
            "update_model_parameters",
            "confirm_model_parameters",
        ],
        # Databus 恢复原存储绑定后即可停 Worker，允许放弃尚未处理的聚类积压。
        ClusteringOperationTypeEnum.DISABLE.value: [
            "disable_clustering",
            "clear_local_clustering",
            "detach",
            "wait_detached",
            "stop_completed",
        ],
        # 复用原任务、Topic、消费组和运行态模型，继续原消费位置
        ClusteringOperationTypeEnum.REOPEN.value: [
            "restart",
            "check_reopen_binding",
            "enable_clustering",
            # 重新声明当前集群的 Pattern/结果表并接入 Databus，关闭期间切过存储也能跟随
            "metadata_set",
            "register_query_routes",
        ],
    }

    def __init__(self, operation_id: str):
        self.operation = LogClusteringOperation.objects.get(operation_id=operation_id)
        self.runtime = LogClusteringRuntime.objects.get(index_set_id=self.operation.index_set_id)

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
            except ModelParameterRejected as e:
                with transaction.atomic():
                    self._save_runtime(phase=ClusteringRuntimePhaseEnum.RUNNING.value, pending_config=None)
                    self.operation.finished_at = timezone.now()
                    self._fail(step, str(e), status=ClusteringOperationStatusEnum.CANCELED.value)
                return None
            except Exception as e:  # pylint: disable=broad-except
                return self._handle_error(step, e)
            if not done:
                return self._wait(step)
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

    def _handle_error(self, step: str, error: Exception) -> int | None:
        logger.exception("[quix_clustering] operation(%s) step(%s) failed", self.operation.operation_id, step)
        self.operation.retry_count += 1
        self.operation.last_error = f"{step}: {error}"
        if isinstance(error, NON_RETRYABLE_EXCEPTIONS) or self.operation.retry_count >= MAX_STEP_RETRIES:
            return self._fail(step, self.operation.last_error)
        self.operation.save(update_fields=["retry_count", "last_error", "updated_at", "updated_by"])
        return self._schedule(min(POLL_INTERVAL_SECONDS * 2**self.operation.retry_count, MAX_RETRY_DELAY_SECONDS))

    def _fail(self, step: str, message: str, status=ClusteringOperationStatusEnum.FAILED.value) -> None:
        self.operation.status = status
        self.operation.last_error = message
        self.operation.next_retry_at = None
        self.operation.save(
            update_fields=[
                "status",
                "last_error",
                "retry_count",
                "next_retry_at",
                "finished_at",
                "updated_at",
                "updated_by",
            ]
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

        def create_payload():
            payload = build_create_task_payload(
                self.runtime.index_set_id, self.quix_config, self.operation.request_snapshot.get("model_parameters")
            )
            source = TransferApi.get_data_id(
                {"bk_data_id": self.runtime.bk_data_id, "no_request": True}, bk_tenant_id=self.runtime.bk_tenant_id
            )
            cluster_id = ((source.get("mq_config") or {}).get("cluster_config") or {}).get("cluster_id")
            if type(cluster_id) is not int or cluster_id <= 0:
                raise QuixClusteringConfigInvalidException(
                    f"Invalid Kafka cluster ID for DataID {self.runtime.bk_data_id}"
                )
            return {**payload, "kafka_cluster_id": cluster_id}

        payload = self.operation.get_request_payload("create_task", create_payload)
        try:
            result = BkFaraApi.create_task(
                {**payload, "Idempotency-Key": self.operation.get_idempotency_key("create_task")}
            )
        except ApiRequestError as exc:
            if exc.http_status == 422:
                raise QuixClusteringParamsInvalidException(str(exc)) from exc
            raise
        config = dict(self.runtime.pending_config or {})
        if "kafka_cluster_id" in payload:
            config["kafka_cluster_id"] = payload["kafka_cluster_id"]
        self._save_runtime(bkfara_task_id=result["task_id"], pending_config=config)
        return True

    def _step_read_binding(self) -> bool:
        if (
            self.runtime.kafka_binding
            and self.runtime.input_revision is not None
            and self.runtime.generation is not None
        ):
            return True
        task = BkFaraApi.get_task({"task_id": self.runtime.bkfara_task_id})
        if task.get("current_generation") is None:
            return False
        clustering = BkFaraApi.get_clustering({"task_id": self.runtime.bkfara_task_id})
        if "kafka_cluster_id" in (self.runtime.pending_config or {}) and not (
            clustering.get("runtime_status") or {}
        ).get("ready"):
            return False
        if not clustering.get("kafka") or clustering.get("input_revision") is None:
            return False
        self._save_runtime(
            control_version=task["control_version"],
            generation=task["current_generation"],
            kafka_binding=clustering["kafka"],
            input_revision=clustering["input_revision"],
        )
        return True

    def _step_metadata_set(self) -> bool:
        clustering_config = self.runtime.pending_config or self.runtime.active_config
        params = self.operation.get_request_payload(
            "metadata_set",
            lambda: self._clustering_config_params(
                binding=build_binding(self.runtime, clustering_config, self.quix_config.get("max_message_bytes")),
                runtime_cluster=self.quix_config["runtime_cluster"],
                result_mode=clustering_config.get("result_mode", "update_original"),
            ),
        )
        result = TransferApi.set_log_clustering_config(params.copy())
        self._save_runtime(sink=result["sink"])
        return True

    def _clustering_config_params(self, result_mode: str, **params) -> dict:
        """聚类配置请求：Pattern 表与独立结果表的名称和集群由日志平台决定。"""
        config = self.runtime.pending_config or self.runtime.active_config
        if "kafka_cluster_id" in config:
            params["kafka_cluster_id"] = config["kafka_cluster_id"]
        elif self.operation.operation_type == ClusteringOperationTypeEnum.ENABLE.value:
            # 升级前已创建、尚未首次下发的任务继续沿用旧开启流程。
            params["kafka_resource"] = self.quix_config["kafka_resource"]
        else:
            params["kafka_resource"] = self._last_applied_kafka_resource()
        targets = build_store_targets(self.runtime, result_mode)
        params.update(result_mode=result_mode, pattern_store=targets["pattern"])
        if result_mode == "append":
            params["result_store"] = targets["clustered"]
        return self._metadata_params(**params)

    def _last_applied_kafka_resource(self) -> dict:
        # metadata_set 成功后，后续路由发布仍可能失败，按步骤回执选取快照。
        history = (
            LogClusteringOperation.objects.filter(
                index_set_id=self.runtime.index_set_id,
                request_payloads__metadata_set__binding__task_id=self.runtime.bkfara_task_id,
            )
            .order_by("-pk")
            .values_list("steps", "request_payloads")
        )
        for steps, payloads in history.iterator():
            if any(
                step["step"] == "metadata_set" and step["status"] == ClusteringOperationStatusEnum.SUCCESS.value
                for step in steps
            ):
                return payloads["metadata_set"]["kafka_resource"]
        raise QuixClusteringConfigInvalidException(
            f"找不到聚类任务 {self.runtime.bkfara_task_id} 已成功下发的 Kafka 引用"
        )

    def _step_register_query_routes(self) -> bool:
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        errors = status.get("errors") or []
        if errors:
            # 记录 metadata 返回的具体原因，按步骤重试上限结束。
            raise RuntimeError("; ".join(f"{error['source']}: {error['message']}" for error in errors))
        if not link_is_ready(status):
            return False
        # 路由指向本次下发给 metadata 的表与集群
        request = self.operation.request_payloads["metadata_set"]
        index_set = LogIndexSet.objects.get(index_set_id=self.runtime.index_set_id)
        clustered = request.get("result_store") or {
            "table_id": self.runtime.table_id,
            "cluster_id": index_set.storage_cluster_id,
        }
        space_type, space_id = parse_space_uid(index_set.space_uid)
        clustered_label = BaseIndexSetHandler.get_data_label(index_set.index_set_id, clustered_rt=True)
        pattern_label = f"{BaseIndexSetHandler.get_data_label(index_set.index_set_id)}_pattern"
        # 每个 Data Label 关联独立的虚拟 RT；原表回写时也不能改写源日志 RT 的标签。
        routes = [
            (
                clustered_label,
                clustered,
                {"query_alias_settings": [{"field_name": QUIX_SIGNATURE_FIELD, "query_alias": SIGNATURE_FIELD}]},
            ),
            (pattern_label, request["pattern_store"], {}),
        ]
        for label, target, extra in routes:
            TransferApi.bulk_create_or_update_log_router(
                {
                    "space_type": space_type,
                    "space_id": space_id,
                    "data_label": label,
                    "table_info": [
                        {
                            "table_id": f"{label}.__default__",
                            "is_enable": True,
                            "origin_table_id": target["table_id"],
                            "storage_type": STORAGE_CLUSTER_TYPE,
                            "source_type": Scenario.LOG,
                            "cluster_id": target["cluster_id"],
                            "index_set": target["table_id"].replace(".", "_"),
                            "options": [{"name": "need_add_time", "value_type": "bool", "value": "true"}],
                            **extra,
                        }
                    ],
                }
            )
        if clustered["table_id"] == self.runtime.table_id:
            # 默认回写时普通检索路由同步补上 signature 别名。
            BaseIndexSetHandler.sync_router(index_set, raise_exception=True)
        return True

    def _promote_pending_config(self, **fields):
        # 待生效配置已提升过时不能再次提升，否则会把空配置写入生效配置
        if self.runtime.pending_config is not None:
            fields.update(active_config=self.runtime.pending_config, pending_config=None)
        self._save_runtime(**fields)

    def _step_update_model_parameters(self) -> bool:
        if not self.operation.request_snapshot.get("update_model"):
            return True

        def build_payload():
            current = BkFaraApi.get_task_parameters({"task_id": self.runtime.bkfara_task_id})
            return {
                "task_id": self.runtime.bkfara_task_id,
                "expected_control_version": current["control_version"],
                "training": {"parameters": self.operation.request_snapshot["model_parameters"]},
            }

        # 固定版本和请求体；超时重试沿用幂等键，不创建任务或重置已有模型。
        payload = self.operation.get_request_payload("update_model_parameters", build_payload)
        try:
            BkFaraApi.update_task_parameters(
                {**payload, "Idempotency-Key": self.operation.get_idempotency_key("update_model_parameters")}
            )
        except ApiRequestError as exc:
            if exc.http_status == 409:
                current = BkFaraApi.get_task_parameters({"task_id": self.runtime.bkfara_task_id})
                actual = (current.get("training") or {}).get("parameters") or {}
                if all(actual.get(key) == value for key, value in payload["training"]["parameters"].items()):
                    return True
            elif exc.http_status != 422:
                raise
            raise ModelParameterRejected(str(exc)) from exc
        return True

    def _step_confirm_model_parameters(self) -> bool:
        if not self.operation.request_snapshot.get("update_model"):
            return True
        current = BkFaraApi.get_task_parameters({"task_id": self.runtime.bkfara_task_id})
        expected = self.operation.request_snapshot["model_parameters"]
        actual = (current.get("training") or {}).get("parameters") or {}
        if any(actual.get(key) != value for key, value in expected.items()):
            return False
        # 这里只确认任务配置已提交。已有模型的增量训练及 Worker 采用由 BKFara 负责，
        # 不能把历史 adoptions 或当前 Worker READY 当成新参数训练完成的证明。
        with transaction.atomic():
            business_fields = dict(self.operation.request_snapshot.get("business_fields") or {})
            if business_fields:
                ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(**business_fields)
            self._save_runtime(control_version=current["control_version"])
        return True

    def _finish_update(self):
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(
            clustering_fields=(self.runtime.pending_config or self.runtime.active_config)["input_mapping"]["log"],
            filter_rules=self.operation.request_snapshot["filter_rules"],
        )
        self._promote_pending_config(phase=ClusteringRuntimePhaseEnum.RUNNING.value)

    def _finish_update_model(self):
        self._save_runtime(phase=ClusteringRuntimePhaseEnum.RUNNING.value)

    def _operate_metadata(self, action: str) -> bool:
        TransferApi.operate_log_clustering(self._metadata_params(action=action))
        return True

    def _step_disable_clustering(self) -> bool:
        # sink 在 metadata 写入确认后才保存，且解绑不清空。因此只有从未绑定的任务才能跳过。
        # 本地 attached 是目标状态，不能用于判定 Runtime 是否已解绑。
        return self._operate_metadata("disable") if self.runtime.sink else True

    @transaction.atomic
    def _step_clear_local_clustering(self) -> bool:
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=False)
        LogIndexSet.delete_tag_by_name(self.runtime.index_set_id, InnerTag.CLUSTERING.value)
        return True

    def _step_detach(self) -> bool:
        return self._operate_metadata("detach") if self.runtime.sink else True

    def _step_wait_detached(self) -> bool:
        if not self.runtime.sink:
            return True
        status = TransferApi.get_log_clustering_status(self._metadata_params())
        return not status.get("errors") and bool(status.get("detached"))

    def _step_stop_completed(self) -> bool:
        if not self.runtime.bkfara_task_id:
            return True
        result = BkFaraApi.stop_clustering(
            {
                "task_id": self.runtime.bkfara_task_id,
                "Idempotency-Key": self.operation.get_idempotency_key("stop"),
                "completion": {"binding_removed": True, "storage_complete": False},
            }
        )
        return result.get("state") == "STOPPED"

    def _step_restart(self) -> bool:
        if self.operation.request_snapshot.get("worker_kept_running"):
            return True

        def build_payload():
            task = BkFaraApi.get_task({"task_id": self.runtime.bkfara_task_id})
            return {"task_id": self.runtime.bkfara_task_id, "expected_control_version": task["control_version"]}

        payload = self.operation.get_request_payload("restart", build_payload)
        result = BkFaraApi.restart_clustering(
            {**payload, "Idempotency-Key": self.operation.get_idempotency_key("restart")}
        )
        self._save_runtime(control_version=result["control_version"])
        return True

    def _step_check_reopen_binding(self) -> bool:
        clustering = BkFaraApi.get_clustering({"task_id": self.runtime.bkfara_task_id})
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

    def _step_enable_clustering(self) -> bool:
        return self._operate_metadata("enable")

    def _finish_reopen(self):
        self._save_runtime(phase=ClusteringRuntimePhaseEnum.RUNNING.value, candidate_boundary=None)
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=True)
        LogIndexSet.set_tag(self.runtime.index_set_id, InnerTag.CLUSTERING.value)

    def _finish_disable(self):
        self._save_runtime(phase=ClusteringRuntimePhaseEnum.STOPPED.value)

    def _finish_enable(self):
        self._promote_pending_config(phase=ClusteringRuntimePhaseEnum.RUNNING.value)
        ClusteringConfig.objects.filter(index_set_id=self.runtime.index_set_id).update(access_finished=True)
        LogIndexSet.set_tag(self.runtime.index_set_id, InnerTag.CLUSTERING.value)
