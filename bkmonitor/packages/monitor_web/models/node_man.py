import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.utils import timezone


class NodeManResourceType(models.TextChoices):
    COLLECT_CONFIG = "COLLECT_CONFIG", "采集配置"
    APM_PLATFORM_CONFIG = "APM_PLATFORM_CONFIG", "APM 平台配置"
    APM_APPLICATION_CONFIG = "APM_APPLICATION_CONFIG", "APM 应用配置"
    APM_LOG_TRACE_CONFIG = "APM_LOG_TRACE_CONFIG", "APM 行日志配置"
    CUSTOM_REPORT = "CUSTOM_REPORT", "自定义上报"
    PING_SERVER = "PING_SERVER", "拨测服务"
    PROXY_PLUGIN_DEPLOYMENT = "PROXY_PLUGIN_DEPLOYMENT", "Proxy 插件部署"
    OFFICIAL_PLUGIN_DEPLOYMENT = "OFFICIAL_PLUGIN_DEPLOYMENT", "官方插件部署"
    MONITOR_PLUGIN = "MONITOR_PLUGIN", "监控插件"


class NodeManBackendType(models.TextChoices):
    NODEMAN_V3 = "NODEMAN_V3", "NodeMan V3"


class NodeManBindingState(models.TextChoices):
    ACTIVE = "ACTIVE", "生效"
    DELETING = "DELETING", "删除中"
    ORPHANED = "ORPHANED", "待清理孤儿"


class NodeManOperationType(models.TextChoices):
    INSTALL = "install", "安装"
    UPGRADE = "upgrade", "升级"
    APPLY = "apply", "应用配置"
    START = "start", "启动"
    STOP = "stop", "停止"
    RESTART = "restart", "重启"
    UNINSTALL = "uninstall", "卸载"
    RETRY = "retry", "重试"
    TERMINATE = "terminate", "终止"
    RECONCILE = "reconcile", "收敛"
    PACKAGE_IMPORT = "package_import", "导入插件包"
    PLUGIN_DEBUG = "plugin_debug", "插件调试"
    PLUGIN_EXPORT = "plugin_export", "插件导出"
    PLUGIN_RETIRE = "plugin_retire", "插件退役"


class NodeManOperationStatus(models.TextChoices):
    PENDING = "pending", "等待中"
    DISPATCHING = "dispatching", "下发中"
    RUNNING = "running", "执行中"
    SUCCESS = "success", "成功"
    PARTIAL_FAILED = "partial_failed", "部分失败"
    FAILED = "failed", "失败"
    CANCELLED = "cancelled", "已取消"
    UNKNOWN = "unknown", "结果未知"


class NodeManWorkflowStatus(models.TextChoices):
    PENDING = "pending", "等待中"
    RUNNING = "running", "执行中"
    SUCCESS = "success", "成功"
    PARTIAL_FAILED = "partial_failed", "部分失败"
    FAILED = "failed", "失败"
    CANCELLED = "cancelled", "已取消"
    UNKNOWN = "unknown", "结果未知"


class NodeManWorkflowDispatchStatus(models.TextChoices):
    PREPARED = "prepared", "待提交"
    SUBMITTING = "submitting", "提交中"
    SUBMITTED = "submitted", "已提交"
    DEFINITE_FAILED = "definite_failed", "明确提交失败"
    UNKNOWN = "unknown", "提交结果未知"


class StaleNodeManGenerationError(RuntimeError):
    pass


def _identity_component(components: dict, name: str) -> str:
    if name not in components:
        raise ValueError(f"{name} is required")
    value = components[name]
    if value is None or value == "":
        raise ValueError(f"{name} is required")
    return str(value)


def build_nodeman_resource_key(resource_type: str, **components) -> str:
    """Build the stable business identity required by the V3 binding contract."""

    resource_type = NodeManResourceType(resource_type)
    if resource_type == NodeManResourceType.APM_PLATFORM_CONFIG:
        if components:
            raise ValueError(f"unexpected identity components: {sorted(components)}")
        return "platform"

    if resource_type in {
        NodeManResourceType.COLLECT_CONFIG,
        NodeManResourceType.APM_APPLICATION_CONFIG,
        NodeManResourceType.APM_LOG_TRACE_CONFIG,
    }:
        allowed = {"object_id"}
        key = _identity_component(components, "object_id")
    elif resource_type == NodeManResourceType.CUSTOM_REPORT:
        allowed = {"data_id"}
        key = f"data_id:{_identity_component(components, 'data_id')}"
    elif resource_type in {NodeManResourceType.PING_SERVER, NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT}:
        allowed = {"bk_cloud_id", "bk_host_id", "plugin_name"}
        key = (
            f"cloud:{_identity_component(components, 'bk_cloud_id')}:"
            f"host:{_identity_component(components, 'bk_host_id')}:"
            f"plugin:{_identity_component(components, 'plugin_name')}"
        )
    elif resource_type == NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT:
        allowed = {"bk_host_id", "plugin_name"}
        key = (
            f"host:{_identity_component(components, 'bk_host_id')}:"
            f"plugin:{_identity_component(components, 'plugin_name')}"
        )
    else:
        allowed = {"plugin_id"}
        key = _identity_component(components, "plugin_id")

    unexpected = set(components) - allowed
    if unexpected:
        raise ValueError(f"unexpected identity components: {sorted(unexpected)}")
    if len(key) > 255:
        raise ValueError("resource key exceeds 255 characters")
    return key


class NodeManIntegrationBinding(models.Model):
    resource_type = models.CharField("资源类型", max_length=64, choices=NodeManResourceType.choices)
    resource_key = models.CharField("资源标识", max_length=255)
    owner_bk_tenant_id = models.CharField("资源所属租户", max_length=128)
    execution_bk_tenant_id = models.CharField("执行租户", max_length=128)
    bk_biz_id = models.BigIntegerField("业务 ID", default=0)
    backend_type = models.CharField(
        "执行后端", max_length=32, choices=NodeManBackendType.choices, default=NodeManBackendType.NODEMAN_V3
    )
    state = models.CharField(
        "状态", max_length=16, choices=NodeManBindingState.choices, default=NodeManBindingState.ACTIVE
    )
    generation = models.PositiveBigIntegerField("期望代次", default=1)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "resource_type",
                    "owner_bk_tenant_id",
                    "execution_bk_tenant_id",
                    "bk_biz_id",
                    "resource_key",
                ),
                name="uniq_nodeman_binding_identity",
            )
        ]
        indexes = [models.Index(fields=("state", "updated_at"), name="idx_nodeman_binding_state")]

    def clean(self):
        super().clean()
        errors = {}
        if not self.resource_key:
            errors["resource_key"] = "resource_key cannot be empty"
        if not self.owner_bk_tenant_id:
            errors["owner_bk_tenant_id"] = "owner_bk_tenant_id cannot be empty"
        if not self.execution_bk_tenant_id:
            errors["execution_bk_tenant_id"] = "execution_bk_tenant_id cannot be empty"
        if self.bk_biz_id is None or self.bk_biz_id < 0:
            errors["bk_biz_id"] = "bk_biz_id must be a non-negative integer"
        if self.resource_type == NodeManResourceType.APM_PLATFORM_CONFIG:
            if self.resource_key != "platform":
                errors["resource_key"] = "APM platform binding must use resource_key='platform'"
            if self.bk_biz_id != 0:
                errors["bk_biz_id"] = "APM platform binding must use global bk_biz_id=0"
        if errors:
            raise ValidationError(errors)

    def advance_generation(self, *, expected_generation: int) -> None:
        if not self.pk:
            raise ValueError("binding must be saved before advancing generation")
        updated_at = timezone.now()
        updated = (
            type(self)
            .objects.filter(pk=self.pk, generation=expected_generation)
            .update(
                generation=F("generation") + 1,
                updated_at=updated_at,
            )
        )
        if updated != 1:
            raise StaleNodeManGenerationError(f"binding {self.pk} is no longer at generation {expected_generation}")
        self.generation = expected_generation + 1
        self.updated_at = updated_at


class MonitorNodeManOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    binding = models.ForeignKey(
        NodeManIntegrationBinding,
        related_name="operations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    config_meta_id = models.BigIntegerField("采集配置 ID", null=True, blank=True)
    deployment_config_version_id = models.BigIntegerField("采集部署版本 ID", null=True, blank=True)
    operation_type = models.CharField("操作类型", max_length=32, choices=NodeManOperationType.choices)
    generation = models.PositiveBigIntegerField("操作代次")
    request_summary = models.JSONField("请求摘要", default=dict)
    target_count = models.PositiveIntegerField("目标数量", default=0)
    status = models.CharField(
        "状态", max_length=32, choices=NodeManOperationStatus.choices, default=NodeManOperationStatus.DISPATCHING
    )
    parent_operation = models.ForeignKey(
        "self",
        related_name="derived_operations",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    error_summary = models.TextField("错误摘要", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("binding", "generation"), name="idx_nodeman_operation_binding"),
            models.Index(fields=("status", "updated_at"), name="idx_nodeman_operation_status"),
        ]

    _ALLOWED_TRANSITIONS = {
        NodeManOperationStatus.PENDING: {NodeManOperationStatus.DISPATCHING, NodeManOperationStatus.CANCELLED},
        NodeManOperationStatus.DISPATCHING: {
            NodeManOperationStatus.RUNNING,
            NodeManOperationStatus.SUCCESS,
            NodeManOperationStatus.PARTIAL_FAILED,
            NodeManOperationStatus.FAILED,
            NodeManOperationStatus.CANCELLED,
            NodeManOperationStatus.UNKNOWN,
        },
        NodeManOperationStatus.RUNNING: {
            NodeManOperationStatus.SUCCESS,
            NodeManOperationStatus.PARTIAL_FAILED,
            NodeManOperationStatus.FAILED,
            NodeManOperationStatus.CANCELLED,
            NodeManOperationStatus.UNKNOWN,
        },
        NodeManOperationStatus.UNKNOWN: {
            NodeManOperationStatus.RUNNING,
            NodeManOperationStatus.SUCCESS,
            NodeManOperationStatus.PARTIAL_FAILED,
            NodeManOperationStatus.FAILED,
            NodeManOperationStatus.CANCELLED,
        },
    }
    _TERMINAL_STATUSES = {
        NodeManOperationStatus.SUCCESS,
        NodeManOperationStatus.PARTIAL_FAILED,
        NodeManOperationStatus.FAILED,
        NodeManOperationStatus.CANCELLED,
    }

    def transition_to(self, status: str, *, save: bool = True) -> None:
        status = NodeManOperationStatus(status)
        current_status = NodeManOperationStatus(self.status)
        if status not in self._ALLOWED_TRANSITIONS.get(current_status, set()):
            raise ValidationError(f"cannot transition NodeMan operation from {current_status} to {status}")

        update_fields = ["status", "updated_at"]
        self.status = status
        if status in {NodeManOperationStatus.DISPATCHING, NodeManOperationStatus.RUNNING} and not self.started_at:
            self.started_at = timezone.now()
            update_fields.append("started_at")
        if status in self._TERMINAL_STATUSES:
            self.finished_at = timezone.now()
            update_fields.append("finished_at")
        if save:
            self.save(update_fields=update_fields)


class MonitorNodeManWorkflow(models.Model):
    monitor_operation = models.ForeignKey(
        MonitorNodeManOperation,
        related_name="workflows",
        on_delete=models.CASCADE,
    )
    workflow_id = models.CharField("NodeMan Workflow ID", max_length=128, null=True, blank=True)
    batch_index = models.PositiveIntegerField("批次序号")
    target_summary = models.JSONField("目标摘要", default=dict)
    target_count = models.PositiveIntegerField("目标数量", default=0)
    dispatch_status = models.CharField(
        "分发状态",
        max_length=32,
        choices=NodeManWorkflowDispatchStatus.choices,
        default=NodeManWorkflowDispatchStatus.PREPARED,
    )
    dispatch_error = models.TextField("分发错误", blank=True, default="")
    raw_status = models.CharField("NodeMan 原始状态", max_length=64, blank=True, default="")
    normalized_status = models.CharField(
        "归一状态", max_length=16, choices=NodeManWorkflowStatus.choices, default=NodeManWorkflowStatus.PENDING
    )
    last_synced_at = models.DateTimeField("最近同步时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ("batch_index",)
        constraints = [
            models.UniqueConstraint(
                fields=("monitor_operation", "workflow_id"),
                name="uniq_nodeman_workflow_operation_id",
            ),
            models.UniqueConstraint(
                fields=("monitor_operation", "batch_index"),
                name="uniq_nodeman_workflow_batch",
            ),
        ]
        indexes = [models.Index(fields=("normalized_status", "updated_at"), name="idx_nodeman_workflow_status")]


class NodeManExecutionLease(models.Model):
    execution_bk_tenant_id = models.CharField("执行租户", max_length=128)
    bk_host_id = models.BigIntegerField("执行主机 ID")
    plugin_name = models.CharField("插件名", max_length=128)
    holder_operation = models.ForeignKey(
        MonitorNodeManOperation,
        related_name="execution_leases",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    lease_generation = models.PositiveBigIntegerField("租约代次", default=0)
    acquired_at = models.DateTimeField("获取时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("execution_bk_tenant_id", "bk_host_id", "plugin_name"),
                name="uniq_nodeman_execution_lease_key",
            )
        ]
        indexes = [models.Index(fields=("holder_operation", "updated_at"), name="idx_nodeman_lease_holder")]


class CollectDeploymentTarget(models.Model):
    binding = models.ForeignKey(
        NodeManIntegrationBinding,
        related_name="collect_targets",
        on_delete=models.CASCADE,
    )
    config_meta_id = models.BigIntegerField("采集配置 ID")
    generation = models.PositiveBigIntegerField("期望代次")
    identity_key = models.CharField("目标稳定标识", max_length=255)
    observed_target = models.JSONField("被观测对象", default=dict)
    service_instance_id = models.BigIntegerField("服务实例 ID", null=True, blank=True)
    execution_bk_host_id = models.BigIntegerField("执行主机 ID")
    remote_target = models.JSONField("远程采集映射", default=dict)
    plugin_name = models.CharField("Exporter 插件名", max_length=128)
    node_man_plugin_instance_id = models.CharField("NodeMan 插件实例标识", max_length=255, blank=True, default="")
    bkmonitorbeat_config_instance_id = models.CharField(
        "bkmonitorbeat 配置实例标识", max_length=255, blank=True, default=""
    )
    desired_present = models.BooleanField("期望存在", default=True)
    desired_enabled = models.BooleanField("期望启用", default=True)
    desired_revision = models.CharField("期望版本", max_length=128, blank=True, default="")
    desired_fingerprint = models.CharField("期望快照指纹", max_length=64, blank=True, default="")
    applied_present = models.BooleanField("最近应用存在状态", null=True, blank=True)
    applied_enabled = models.BooleanField("最近应用启用状态", null=True, blank=True)
    applied_revision = models.CharField("最近应用版本", max_length=128, blank=True, default="")
    applied_fingerprint = models.CharField("最近应用快照指纹", max_length=64, blank=True, default="")
    last_operation = models.ForeignKey(
        MonitorNodeManOperation,
        related_name="collect_targets",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    error_summary = models.TextField("错误摘要", blank=True, default="")
    last_applied_at = models.DateTimeField("最近应用时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("binding", "identity_key"),
                name="uniq_collect_target_identity",
            )
        ]
        indexes = [models.Index(fields=("binding", "generation"), name="idx_collect_target_generation")]

    def clean(self):
        super().clean()
        if self.binding.resource_type != NodeManResourceType.COLLECT_CONFIG:
            raise ValidationError({"binding": "CollectDeploymentTarget binding must be COLLECT_CONFIG"})
