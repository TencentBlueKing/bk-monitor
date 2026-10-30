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

from django.db import transaction
from django.utils.translation import gettext as _

from apps.log_clustering.constants import (
    CLUSTERING_CONFIG_EXCLUDE,
    DEFAULT_CLUSTERING_FIELDS,
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
    RegexRuleTypeEnum,
)
from apps.log_clustering.exceptions import ClusteringConfigHasExistException
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.handlers.quix.adapter import build_clustering_config, build_index_names
from apps.log_clustering.handlers.quix.config import get_quix_config
from apps.log_clustering.handlers.quix.operation import QuixClusteringOperationRunner
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Space
from apps.models import model_to_dict
from bkm_space.utils import space_uid_to_bk_biz_id

# 开启流程中各步骤对应到现有接入状态的三段展示
ACCESS_STATUS_STEPS = {
    "flow_create": ("create_task", "wait_task_ready", "wait_worker_ready"),
    "flow_run": ("metadata_set", "wait_adoption", "confirm_adoption"),
}


class QuixClusteringHandler:
    """轻量化聚类（BKBase LogClusteringSink + BKFara Quix）的业务入口"""

    def __init__(self, log_index_set: LogIndexSet):
        self.index_set = log_index_set
        self.index_set_id = log_index_set.index_set_id

    def enable(self, params: dict) -> dict:
        from apps.log_clustering.tasks.quix import run_quix_clustering_operation

        has_exist = ClusteringConfigHasExistException(
            ClusteringConfigHasExistException.MESSAGE.format(index_set_id=self.index_set_id)
        )
        if LogClusteringRuntime.objects.filter(index_set_id=self.index_set_id).exists():
            # 开启失败后再次提交时续跑原操作，沿用已申请的任务和幂等键
            operation = self._resume_failed_operation(ClusteringOperationTypeEnum.ENABLE.value)
            if not operation:
                raise has_exist
            run_quix_clustering_operation.delay(operation.operation_id)
            return self._access_response(operation)
        if ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id, raise_exception=False):
            # 已通过其他链路接入聚类的索引集不能直接切换
            raise has_exist

        clustering_fields = params.get("clustering_fields") or DEFAULT_CLUSTERING_FIELDS
        filter_rules = params.get("filter_rules", [])
        # 先完成参数与环境配置校验，再落库并申请外部资源
        clustering_config = build_clustering_config(clustering_fields, filter_rules)
        get_quix_config()

        collector_config = CollectorConfig.objects.get(collector_config_id=self.index_set.collector_config_id)
        pattern_index, state_index = build_index_names(self.index_set_id)
        # 业务配置与可调度操作一起提交，保存失败时不能由定时恢复任务继续开启。
        with transaction.atomic():
            _runtime, operation = LogClusteringRuntime.start_operation(
                self.index_set_id,
                ClusteringOperationTypeEnum.ENABLE.value,
                {"clustering_fields": clustering_fields, "filter_rules": filter_rules},
                defaults={
                    "bk_biz_id": collector_config.bk_biz_id,
                    "bk_tenant_id": Space.get_tenant_id(space_uid=self.index_set.space_uid),
                    "collector_config_id": collector_config.collector_config_id,
                    "table_id": collector_config.table_id,
                    "bk_data_id": collector_config.bk_data_id,
                    "phase": ClusteringRuntimePhaseEnum.ENABLING.value,
                    "pending_config": clustering_config,
                    "pattern_index": pattern_index,
                    "state_index": state_index,
                },
            )
            business_config = self._save_business_config(collector_config, params, clustering_fields, filter_rules)
            operation.request_snapshot["model_parameters"] = DataFlowHandler.get_clustering_training_params(
                business_config
            )
            operation.save(update_fields=["request_snapshot", "updated_at", "updated_by"])
        run_quix_clustering_operation.delay(operation.operation_id)
        return self._access_response(operation)

    def get_access_status(self) -> dict:
        from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler

        status_code = ClusteringConfigHandler.AccessStatusCode
        runtime = LogClusteringRuntime.objects.get(index_set_id=self.index_set_id)
        operation = LogClusteringOperation.objects.filter(index_set_id=self.index_set_id).order_by("-id").first()
        result = {"access_finished": runtime.phase == ClusteringRuntimePhaseEnum.RUNNING.value}
        for section in ACCESS_STATUS_STEPS:
            result[section] = self._section_status(status_code, operation, self._section_steps(operation, section))
        result["data_check"] = (
            {"status": status_code.SUCCESS, "message": _("步骤完成")}
            if result["access_finished"]
            else {"status": status_code.PENDING, "message": _("等待执行")}
        )
        result["quix"] = {
            "phase": runtime.phase,
            "operation": self._format_operation(operation),
        }
        return result

    @transaction.atomic
    def _resume_failed_operation(self, operation_type: str) -> LogClusteringOperation | None:
        operation = (
            LogClusteringOperation.objects.select_for_update()
            .filter(
                index_set_id=self.index_set_id,
                operation_type=operation_type,
                status=ClusteringOperationStatusEnum.FAILED.value,
            )
            .first()
        )
        if operation:
            operation.status = ClusteringOperationStatusEnum.PENDING.value
            operation.retry_count = 0
            operation.save(update_fields=["status", "retry_count", "updated_at", "updated_by"])
        return operation

    def _save_business_config(self, collector_config, params, clustering_fields, filter_rules):
        clustering_config, _created = ClusteringConfig.objects.update_or_create(
            index_set_id=self.index_set_id,
            defaults={
                "collector_config_id": collector_config.collector_config_id,
                "collector_config_name_en": collector_config.collector_config_name_en,
                "bk_biz_id": space_uid_to_bk_biz_id(self.index_set.space_uid),
                "clustering_fields": clustering_fields,
                "filter_rules": filter_rules,
                "min_members": params.get("min_members", OnlineTaskTrainingArgs.MIN_MEMBERS),
                "max_dist_list": OnlineTaskTrainingArgs.MAX_DIST_LIST,
                "delimeter": params.get("delimeter", OnlineTaskTrainingArgs.DELIMETER),
                "max_log_length": params.get("max_log_length", OnlineTaskTrainingArgs.MAX_LOG_LENGTH),
                "is_case_sensitive": params.get("is_case_sensitive", OnlineTaskTrainingArgs.IS_CASE_SENSITIVE),
                "signature_enable": True,
                "category_id": self.index_set.category_id,
                "log_bk_data_id": collector_config.bk_data_id,
                "new_cls_strategy_enable": params.get("new_cls_strategy_enable", False),
                "normal_strategy_enable": params.get("normal_strategy_enable", False),
                "access_finished": False,
            },
        )
        regex_template = RegexTemplateHandler().list_templates(space_uid=self.index_set.space_uid)[0]
        clustering_config.regex_template_id = regex_template["id"]
        clustering_config.predefined_varibles = regex_template["predefined_varibles"]
        clustering_config.regex_rule_type = RegexRuleTypeEnum.TEMPLATE.value
        clustering_config.save()
        return clustering_config

    def _access_response(self, operation: LogClusteringOperation) -> dict:
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)
        return {
            **model_to_dict(clustering_config, exclude=CLUSTERING_CONFIG_EXCLUDE),
            "operation_id": operation.operation_id,
        }

    @staticmethod
    def _section_steps(operation: LogClusteringOperation | None, section: str) -> tuple:
        if operation is None:
            return ()
        if operation.operation_type == ClusteringOperationTypeEnum.ENABLE.value:
            return ACCESS_STATUS_STEPS[section]
        # 非开启操作不涉及任务创建，整个操作的进度展示在链路运行段
        if section == "flow_create":
            return ()
        return tuple(QuixClusteringOperationRunner.STEPS.get(operation.operation_type, ()))

    @staticmethod
    def _section_status(status_code, operation: LogClusteringOperation | None, steps: tuple) -> dict:
        if not steps or operation.status == ClusteringOperationStatusEnum.SUCCESS.value:
            return {"status": status_code.SUCCESS, "message": _("步骤完成")}
        finished = {
            item["step"] for item in operation.steps if item["status"] == ClusteringOperationStatusEnum.SUCCESS.value
        }
        if all(step in finished for step in steps):
            return {"status": status_code.SUCCESS, "message": _("步骤完成")}
        if operation.step in steps:
            if operation.status == ClusteringOperationStatusEnum.FAILED.value:
                return {"status": status_code.FAILED, "message": operation.last_error}
            if operation.status == ClusteringOperationStatusEnum.AWAITING_RECEIPT.value:
                return {"status": status_code.RUNNING, "message": _("配置已下发，待采用确认")}
            return {"status": status_code.RUNNING, "message": operation.step}
        return {"status": status_code.PENDING, "message": _("等待执行")}

    @staticmethod
    def _format_operation(operation: LogClusteringOperation | None) -> dict | None:
        if operation is None:
            return None
        return {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "status": operation.status,
            "step": operation.step,
            "steps": operation.steps,
            "retry_count": operation.retry_count,
            "last_error": operation.last_error,
        }
