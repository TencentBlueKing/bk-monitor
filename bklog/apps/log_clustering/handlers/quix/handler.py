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

from django.utils.translation import gettext as _

from apps.log_clustering.constants import (
    CLUSTERING_CONFIG_EXCLUDE,
    DEFAULT_CLUSTERING_FIELDS,
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
    RegexRuleTypeEnum,
)
from apps.log_clustering.exceptions import ClusteringConfigHasExistException, QuixClusteringParamsInvalidException
from apps.log_clustering.handlers.dataflow.constants import OnlineTaskTrainingArgs
from apps.log_clustering.handlers.quix.adapter import build_clustering_config, build_index_names
from apps.log_clustering.handlers.quix.bkfara import BkFaraClient
from apps.log_clustering.handlers.quix.config import get_quix_config
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Space
from apps.models import model_to_dict
from apps.utils.log import logger
from bkm_space.utils import space_uid_to_bk_biz_id

# 只影响页面展示的业务配置，更新时直接保存，不触发链路变更
BUSINESS_UPDATE_FIELDS = (
    "min_members",
    "predefined_varibles",
    "delimeter",
    "max_log_length",
    "is_case_sensitive",
    "regex_rule_type",
    "regex_template_id",
)

# 开启流程中各步骤对应到现有接入状态的三段展示
ACCESS_STATUS_STEPS = {
    "flow_create": ("create_task", "wait_task_ready", "configure_clustering", "wait_worker_ready"),
    "flow_run": ("metadata_set", "wait_adoption"),
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
        self._save_business_config(collector_config, params, clustering_fields, filter_rules)
        run_quix_clustering_operation.delay(operation.operation_id)
        return self._access_response(operation)

    def update(self, params: dict) -> str | None:
        """更新过滤规则，返回操作ID；规则无变化时只保存业务配置并返回 None"""
        from apps.log_clustering.tasks.quix import run_quix_clustering_operation

        runtime = LogClusteringRuntime.objects.get(index_set_id=self.index_set_id)
        filter_rules = params.get("filter_rules", [])
        clustering_fields = params.get("clustering_fields") or runtime.active_config["input_mapping"]["log"]
        clustering_config = build_clustering_config(clustering_fields, filter_rules)
        if clustering_config["input_mapping"] != runtime.active_config["input_mapping"]:
            raise QuixClusteringParamsInvalidException(
                QuixClusteringParamsInvalidException.MESSAGE.format(
                    detail=_("首版仅支持修改过滤规则，不支持修改聚类字段")
                )
            )

        operation = None
        if runtime.phase == ClusteringRuntimePhaseEnum.UPDATING.value and runtime.pending_config == clustering_config:
            # 相同规则再次提交时续跑失败的更新，沿用已固定的排空范围
            operation = self._resume_failed_operation(ClusteringOperationTypeEnum.UPDATE.value)
        elif clustering_config != runtime.active_config:
            runtime, operation = LogClusteringRuntime.start_operation(
                self.index_set_id,
                ClusteringOperationTypeEnum.UPDATE.value,
                {"filter_rules": filter_rules},
                allowed_phases=(ClusteringRuntimePhaseEnum.RUNNING.value,),
            )
            runtime.pending_config = clustering_config
            runtime.phase = ClusteringRuntimePhaseEnum.UPDATING.value
            runtime.save(update_fields=["pending_config", "phase", "updated_at", "updated_by"])

        ClusteringConfig.objects.filter(index_set_id=self.index_set_id).update(
            filter_rules=filter_rules, **{field: params[field] for field in BUSINESS_UPDATE_FIELDS if field in params}
        )
        if not operation:
            return None
        run_quix_clustering_operation.delay(operation.operation_id)
        return operation.operation_id

    def disable(self) -> str:
        """关闭聚类，原日志链路继续入库；返回操作ID"""
        from apps.log_clustering.tasks.quix import run_quix_clustering_operation

        runtime = LogClusteringRuntime.objects.get(index_set_id=self.index_set_id)
        operation = None
        if runtime.phase == ClusteringRuntimePhaseEnum.DISABLING.value:
            # 续跑沿用已固定的候选边界
            operation = self._resume_failed_operation(ClusteringOperationTypeEnum.DISABLE.value)
        if not operation:
            runtime, operation = LogClusteringRuntime.start_operation(
                self.index_set_id,
                ClusteringOperationTypeEnum.DISABLE.value,
                {},
                allowed_phases=(ClusteringRuntimePhaseEnum.RUNNING.value,),
            )
            runtime.phase = ClusteringRuntimePhaseEnum.DISABLING.value
            runtime.candidate_boundary = None
            runtime.outbox_boundary = None
            runtime.save(update_fields=["phase", "candidate_boundary", "outbox_boundary", "updated_at", "updated_by"])
        run_quix_clustering_operation.delay(operation.operation_id)
        return operation.operation_id

    def get_access_status(self) -> dict:
        from apps.log_clustering.handlers.clustering_config import ClusteringConfigHandler

        status_code = ClusteringConfigHandler.AccessStatusCode
        runtime = LogClusteringRuntime.objects.get(index_set_id=self.index_set_id)
        operation = LogClusteringOperation.objects.filter(index_set_id=self.index_set_id).order_by("-id").first()
        result = {"access_finished": runtime.phase == ClusteringRuntimePhaseEnum.RUNNING.value}
        for section, steps in ACCESS_STATUS_STEPS.items():
            result[section] = self._section_status(status_code, operation, steps)
        result["data_check"] = (
            {"status": status_code.SUCCESS, "message": _("步骤完成")}
            if result["access_finished"]
            else {"status": status_code.PENDING, "message": _("等待执行")}
        )
        result["quix"] = {
            "phase": runtime.phase,
            "coverage_gaps": runtime.coverage_gaps,
            "operation": self._format_operation(operation),
            "bkfara": self._get_bkfara_clustering(runtime),
        }
        return result

    @staticmethod
    def _get_bkfara_clustering(runtime: LogClusteringRuntime) -> dict | None:
        """BKFara 原始运行状态；逻辑停止、Pod 退出和预留释放由页面分别展示"""
        if not runtime.bkfara_task_id:
            return None
        try:
            return BkFaraClient().get_clustering(runtime.bkfara_task_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("[quix_clustering] index_set(%s) get bkfara status failed: %s", runtime.index_set_id, e)
            return {"error": str(e)}

    def _resume_failed_operation(self, operation_type: str) -> LogClusteringOperation | None:
        operation = LogClusteringOperation.objects.filter(
            index_set_id=self.index_set_id,
            operation_type=operation_type,
            status=ClusteringOperationStatusEnum.FAILED.value,
        ).first()
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

    def _access_response(self, operation: LogClusteringOperation) -> dict:
        clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)
        return {
            **model_to_dict(clustering_config, exclude=CLUSTERING_CONFIG_EXCLUDE),
            "operation_id": operation.operation_id,
        }

    @staticmethod
    def _section_status(status_code, operation: LogClusteringOperation | None, steps: tuple) -> dict:
        if operation is None or operation.operation_type != ClusteringOperationTypeEnum.ENABLE.value:
            return {"status": status_code.SUCCESS, "message": _("步骤完成")}
        finished = {
            item["step"] for item in operation.steps if item["status"] == ClusteringOperationStatusEnum.SUCCESS.value
        }
        if all(step in finished for step in steps):
            return {"status": status_code.SUCCESS, "message": _("步骤完成")}
        if operation.step in steps:
            if operation.status == ClusteringOperationStatusEnum.FAILED.value:
                return {"status": status_code.FAILED, "message": operation.last_error}
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
