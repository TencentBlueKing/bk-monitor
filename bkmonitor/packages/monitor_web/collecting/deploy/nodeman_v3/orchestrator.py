from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.client.workflow import WorkflowClient
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3ResultState
from monitor_web.collecting.constant import CollectStatus
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
    build_nodeman_resource_key,
)
from monitor_web.nodeman_integration.v3.operation import NodeManV3OperationService

from .validation import NodeManV3CapabilityBlocked


class NodeManV3Orchestrator:
    PAGE_SIZE = 500

    def __init__(
        self,
        *,
        workflow_client=None,
        poll_scheduler: Callable[[str], None] | None = None,
    ):
        self._workflow_client = workflow_client
        self.poll_scheduler = poll_scheduler or NodeManV3OperationService._schedule_poll

    @property
    def workflow_client(self):
        if self._workflow_client is None:
            self._workflow_client = WorkflowClient(NodeManV3HTTPClient())
        return self._workflow_client

    def uninstall(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "collection deletion requires the DeployPolicy reverse field while enabled remains true; "
            "DeployPolicy Delete only detaches management and must not be used"
        )

    def stop(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "stop requires the DeployPolicy reverse field while enabled remains true and Scope stays unchanged"
        )

    def start(self, **kwargs):
        del kwargs
        raise NodeManV3CapabilityBlocked(
            "start requires the DeployPolicy forward field while enabled remains true and Scope stays unchanged"
        )

    def retry(self, *, collect_config, instance_ids: list[str] | None = None):
        workflow_operations = self._workflow_operations(collect_config)
        selected = self._select_retry_operations(workflow_operations, instance_ids)
        if not selected:
            return None
        requests = [
            {
                "workflow_id": workflow_id,
                "retry_mod": "PARTIAL",
                "operation_ids": [item["operation_id"] for item in operations],
            }
            for workflow_id, operations in selected.items()
        ]
        return self._dispatch_control(
            collect_config,
            operation_type=NodeManOperationType.RETRY,
            requests=requests,
            submit=lambda payload, context: self.workflow_client.retry_operation(payload, context=context),
        )

    def revoke(self, *, collect_config, instance_ids: list[int] | None = None):
        workflow_operations = self._workflow_operations(collect_config)
        selected = self._select_terminate_operations(workflow_operations, instance_ids)
        if not selected:
            return None
        requests = [
            {
                "workflow_id": workflow_id,
                "operation_ids": [item["operation_id"] for item in operations],
            }
            for workflow_id, operations in selected.items()
        ]
        return self._dispatch_control(
            collect_config,
            operation_type=NodeManOperationType.TERMINATE,
            requests=requests,
            submit=lambda payload, context: self.workflow_client.terminate_operation(payload, context=context),
        )

    def status(self, *, collect_config, args=(), kwargs=None):
        del args, kwargs
        workflow_operations = self._workflow_operations(collect_config)
        instances = []
        for workflow_id, operations in workflow_operations.items():
            for operation in operations:
                deployment = operation.get("plugin_deployment_info") or {}
                instance_ids = operation.get("instance_ids") or []
                instance_id = str(instance_ids[-1]) if instance_ids else operation.get("operation_id", "")
                lifecycle = (operation.get("latest_oper_inst_brief_data") or {}).get("life_cycle") or {}
                addresses = deployment.get("bk_host_innerip_list") or deployment.get("bk_host_innerip_v6_list") or []
                ip = addresses[0] if addresses else ""
                latest_action = (operation.get("latest_oper_inst_brief_data") or {}).get(
                    "latest_action_inst_brief_data"
                ) or {}
                instances.append(
                    {
                        "instance_id": instance_id,
                        "ip": ip,
                        "bk_cloud_id": deployment.get("bk_networkarea_id", 0),
                        "bk_host_id": deployment.get("bk_host_id"),
                        "bk_host_name": ip,
                        "bk_supplier_id": "0",
                        "task_id": workflow_id,
                        "status": self._collect_status(lifecycle.get("state")),
                        "plugin_version": deployment.get("plugin_version", ""),
                        "log": latest_action.get("name", ""),
                        "action": getattr(collect_config, "last_operation", "").lower(),
                        "steps": {},
                        "bk_module_ids": [],
                        "instance_name": ip,
                    }
                )
        return [{"child": instances, "node_path": _("主机"), "label_name": "", "is_label": False}]

    def instance_status(self, *, collect_config, instance_id: str):
        result = self.workflow_client.get_operation_instance_log(
            {"oper_inst_id": str(instance_id)},
            context=self._read_context(collect_config),
        )
        return {"log_detail": self._format_log(result)}

    def _workflow_operations(self, collect_config) -> dict[str, list[dict]]:
        source_workflows = self._source_workflows(collect_config)
        result = {}
        for workflow in source_workflows:
            result[workflow.workflow_id] = self._list_operations(
                workflow.workflow_id,
                context=self._read_context(collect_config),
            )
        return result

    def _source_workflows(self, collect_config) -> list[MonitorNodeManWorkflow]:
        binding = self._binding(collect_config)
        if binding is None:
            return []
        operation = binding.operations.order_by("-created_at").first()
        if operation is None:
            return []
        if operation.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN:
            raise NodeManV3UnknownResultError(
                "the latest NodeMan write result is unknown; workflow control cannot be replayed safely"
            )
        workflows = list(operation.workflows.order_by("batch_index"))
        direct = [workflow for workflow in workflows if workflow.workflow_id]
        if direct:
            return direct
        if any(workflow.trigger_id for workflow in workflows):
            raise NodeManV3CapabilityBlocked(
                "DeployPolicy Execute returns trigger_id, but the aggregate DeployPolicy Workflow contract is not defined"
            )
        return []

    def _list_operations(self, workflow_id: str, *, context: NodeManV3RequestContext) -> list[dict]:
        operations = []
        offset = 0
        while True:
            response = self.workflow_client.list_operations(
                {
                    "only_count": False,
                    "page": {"offset": offset, "limit": self.PAGE_SIZE},
                    "workflow_id": workflow_id,
                },
                context=context,
            )
            page = response.get("operations", []) if isinstance(response, dict) else []
            operations.extend(page)
            offset += len(page)
            total = response.get("total", len(page)) if isinstance(response, dict) else len(page)
            if not page or offset >= total:
                break
        return operations

    @staticmethod
    def _select_retry_operations(workflows, instance_ids):
        wanted = {str(value) for value in instance_ids} if instance_ids is not None else None
        selected = defaultdict(list)
        for workflow_id, operations in workflows.items():
            for operation in operations:
                state = NodeManV3Orchestrator._operation_state(operation)
                operation_instances = {str(value) for value in operation.get("instance_ids") or ()}
                if wanted is not None:
                    if wanted & operation_instances:
                        selected[workflow_id].append(operation)
                elif state in {"failed", "timeout"}:
                    selected[workflow_id].append(operation)
        return selected

    @staticmethod
    def _select_terminate_operations(workflows, instance_ids):
        wanted = {str(value) for value in instance_ids} if instance_ids is not None else None
        selected = defaultdict(list)
        for workflow_id, operations in workflows.items():
            for operation in operations:
                state = NodeManV3Orchestrator._operation_state(operation)
                operation_instances = {str(value) for value in operation.get("instance_ids") or ()}
                if wanted is not None:
                    if wanted & operation_instances:
                        selected[workflow_id].append(operation)
                elif state in {"init", "launched", "running"}:
                    selected[workflow_id].append(operation)
        return selected

    @staticmethod
    def _operation_state(operation: dict) -> str:
        return (
            ((operation.get("latest_oper_inst_brief_data") or {}).get("life_cycle") or {}).get("state") or ""
        ).lower()

    def _dispatch_control(self, collect_config, *, operation_type: str, requests: Sequence[dict], submit: Callable):
        binding = self._binding(collect_config)
        if binding is None:
            return None
        with transaction.atomic():
            locked = NodeManIntegrationBinding.objects.select_for_update().get(pk=binding.pk)
            operation = MonitorNodeManOperation.objects.create(
                binding=locked,
                config_meta_id=collect_config.pk,
                deployment_config_version_id=collect_config.deployment_config_id,
                operation_type=operation_type,
                generation=locked.generation,
                request_summary={"source_workflow_ids": [request["workflow_id"] for request in requests]},
                status=NodeManOperationStatus.DISPATCHING,
                started_at=timezone.now(),
            )
            workflows = [
                MonitorNodeManWorkflow.objects.create(
                    monitor_operation=operation,
                    batch_index=index,
                    target_summary={"source_workflow_id": request["workflow_id"]},
                    dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
                )
                for index, request in enumerate(requests)
            ]
            transaction.on_commit(lambda: self._submit_control(operation, workflows, requests=requests, submit=submit))
        return {"operation_id": str(operation.pk)}

    def _submit_control(self, operation, workflows, *, requests, submit):
        context = NodeManV3RequestContext(
            bk_tenant_id=operation.binding.execution_bk_tenant_id,
            bk_biz_id=operation.binding.bk_biz_id,
            monitor_operation_id=str(operation.pk),
        )
        submitted = False
        for index, (workflow, request) in enumerate(zip(workflows, requests, strict=True)):
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTING
            workflow.save(update_fields=("dispatch_status", "updated_at"))
            try:
                submit(request, context)
            except NodeManV3UnknownResultError as error:
                self._mark_control_unknown(operation, workflows[index:], error)
                raise
            except Exception as error:
                self._mark_control_failure(operation, workflows[index:], error, submitted=submitted)
                if submitted:
                    self.poll_scheduler(str(operation.pk))
                raise
            workflow.workflow_id = request["workflow_id"]
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
            workflow.normalized_status = NodeManWorkflowStatus.RUNNING
            workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
            submitted = True
        operation.transition_to(NodeManOperationStatus.RUNNING)
        self.poll_scheduler(str(operation.pk))

    @staticmethod
    def _mark_control_unknown(operation, workflows, error):
        now = timezone.now()
        current, *remaining = workflows
        current.dispatch_status = NodeManWorkflowDispatchStatus.UNKNOWN
        current.normalized_status = NodeManWorkflowStatus.UNKNOWN
        current.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
        current.dispatch_error = str(error)
        current.save(
            update_fields=(
                "dispatch_status",
                "normalized_status",
                "result_state",
                "dispatch_error",
                "updated_at",
            )
        )
        for workflow in remaining:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
            workflow.dispatch_error = "not submitted after an earlier write became uncertain"
            workflow.updated_at = now
        if remaining:
            MonitorNodeManWorkflow.objects.bulk_update(
                remaining,
                fields=("dispatch_status", "normalized_status", "dispatch_error", "updated_at"),
            )
        operation.status = NodeManOperationStatus.UNKNOWN
        operation.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
        operation.error_summary = str(error)
        operation.save(update_fields=("status", "result_state", "error_summary", "updated_at"))

    @staticmethod
    def _mark_control_failure(operation, workflows, error, *, submitted):
        for workflow in workflows:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
            workflow.dispatch_error = str(error)
            workflow.save(update_fields=("dispatch_status", "normalized_status", "dispatch_error", "updated_at"))
        operation.error_summary = str(error)
        operation.save(update_fields=("error_summary", "updated_at"))
        operation.transition_to(NodeManOperationStatus.RUNNING if submitted else NodeManOperationStatus.FAILED)

    @staticmethod
    def _collect_status(raw_state: str | None) -> str:
        return {
            "init": CollectStatus.PENDING,
            "launched": CollectStatus.PENDING,
            "running": CollectStatus.RUNNING,
            "success": CollectStatus.SUCCESS,
            "failed": CollectStatus.FAILED,
            "timeout": CollectStatus.FAILED,
            "terminated": CollectStatus.FAILED,
        }.get((raw_state or "").lower(), CollectStatus.UNKNOWN)

    @staticmethod
    def _format_log(result) -> str:
        if not isinstance(result, dict):
            return _("未找到日志")
        lines = []
        for action_id, action in (result.get("oper_inst_logs") or {}).items():
            lines.append(f"{'=' * 20}{action.get('display_name_zh') or action_id}{'=' * 20}")
            for item in (action.get("message") or {}).get("logs") or ():
                text = item.get("text_zh") or item.get("text_en")
                if text:
                    lines.append(text)
        for item in (result.get("extra_execution_logs") or {}).get("logs") or ():
            text = item.get("text_zh") or item.get("text_en")
            if text:
                lines.append(text)
        return "\n".join(lines) if lines else _("未找到日志")

    @staticmethod
    def _binding(collect_config):
        resource_key = build_nodeman_resource_key(
            NodeManResourceType.COLLECT_CONFIG,
            object_id=collect_config.pk,
        )
        return NodeManIntegrationBinding.objects.filter(
            resource_type=NodeManResourceType.COLLECT_CONFIG,
            resource_key=resource_key,
            owner_bk_tenant_id=collect_config.bk_tenant_id,
            execution_bk_tenant_id=collect_config.bk_tenant_id,
            bk_biz_id=collect_config.bk_biz_id,
        ).first()

    @staticmethod
    def _read_context(collect_config) -> NodeManV3RequestContext:
        return NodeManV3RequestContext(
            bk_tenant_id=collect_config.bk_tenant_id,
            bk_biz_id=collect_config.bk_biz_id,
        )
