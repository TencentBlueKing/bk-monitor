import logging
from typing import Any, Self, final

from django.db import models
from django.utils.translation import gettext_lazy as _
from typing_extensions import override

from bk_monitor_base.config.all import get_config
from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID, OLD_MONITOR_SAAS_DB_NAME
from bk_monitor_base.infras.db_models.fields import SymmetricJSONField, TextJSONField
from bk_monitor_base.infras.db_models.manger import OldModelManager
from bk_monitor_base.infras.third_party_api.cmdb import api as cmdb_api

from .define import (
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckNodeIPType,
    UptimeCheckTask,
    UptimeCheckTaskProtocol,
    UptimeCheckTaskStatus,
)

logger = logging.getLogger(__name__)

# 拨测模型是否使用旧模型
if get_config().domains.uptime_check.use_old_model:
    models_manager: models.Manager[Any] = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)
    managed = False
else:
    models_manager = models.Manager()
    managed = True

# IP类型选项
NODE_IP_TYPE_CHOICES = [(0, "all"), (4, "IPv4"), (6, "IPv6")]
NODE_IP_TYPE_DICT = {status: desc for (status, desc) in NODE_IP_TYPE_CHOICES}
UPTIME_CHECK_TASK_STATUS_NAME_MAP = {
    UptimeCheckTaskStatus.NEW_DRAFT.value: _("未保存"),
    UptimeCheckTaskStatus.RUNNING.value: _("运行中"),
    UptimeCheckTaskStatus.STOPED.value: _("未启用"),
    UptimeCheckTaskStatus.STARTING.value: _("启动中"),
    UptimeCheckTaskStatus.STOPING.value: _("停止中"),
    UptimeCheckTaskStatus.START_FAILED.value: _("启动失败"),
    UptimeCheckTaskStatus.STOP_FAILED.value: _("停止失败"),
}


@final
class UptimeCheckNodeModel(models.Model):
    """
    拨测节点模型

    代表一个用于执行拨测任务的节点,可以是业务节点或通用节点
    """

    bk_tenant_id = models.CharField("租户ID", default=DEFAULT_TENANT_ID, max_length=128)
    bk_biz_id = models.IntegerField("业务ID", default=0, db_index=True)
    is_common = models.BooleanField("是否为通用节点", default=False, db_index=True)
    biz_scope: list[int] = TextJSONField("指定业务可见范围", default=list, help_text="示例: [1, 2, 3]")  # pyright: ignore[reportAssignmentType]
    ip_type = models.IntegerField("IP类型", default=4, choices=NODE_IP_TYPE_CHOICES)
    name = models.CharField("节点名称", max_length=50)

    ip = models.CharField("IP地址", blank=True, null=True, default="", max_length=64)
    bk_host_id = models.IntegerField("主机ID", null=True, blank=True)
    plat_id = models.IntegerField("云区域ID", blank=True, null=True, default=0)
    location: dict[str, Any] = TextJSONField(
        "地区", default=dict, help_text='示例: {"country": "中国", "city": "北京"}'
    )  # pyright: ignore[reportAssignmentType]
    carrieroperator = models.CharField("外网运营商", max_length=50, blank=True, null=True, default="")

    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_user = models.CharField("修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = models_manager

    @final
    class Meta:
        verbose_name = _("拨测节点")
        verbose_name_plural = _("拨测节点")
        db_table = "monitor_uptimechecknode"
        app_label = "uptime_check"

        indexes = [models.Index(fields=["name", "bk_biz_id"])]
        managed = managed

    @override
    def __str__(self) -> str:  # type: ignore[override]
        return f"拨测节点({self.name})"

    @classmethod
    def create_or_update_from_define(cls, node: UptimeCheckNode, operator: str) -> Self:
        """从定义创建或更新拨测节点

        Args:
            node: 拨测节点定义
            operator: 操作人

        Returns:
            Self: 创建或更新的拨测节点
        """

        # 如果节点有bk_host_id且没有ip，则通过bk_host_id查询ip和云区域ID
        if node.bk_host_id and not node.ip:
            ip_tuple = cls._get_ip_by_host_id(node.bk_tenant_id, node.bk_biz_id, node.bk_host_id)
            if ip_tuple:
                node.ip, node.plat_id = ip_tuple

        if node.id:
            node_model = cls.objects.get(id=node.id)
            node_model.is_common = node.is_common
            node_model.biz_scope = node.biz_scope
            node_model.ip_type = node.ip_type
            node_model.name = node.name
            node_model.bk_host_id = node.bk_host_id
            node_model.ip = node.ip
            node_model.plat_id = node.plat_id
            node_model.location = node.location
            node_model.carrieroperator = node.carrieroperator
            node_model.update_user = operator
            node_model.save()
        else:
            # 要求新节点必须使用bk_host_id
            if not node.bk_host_id:
                raise ValueError("拨测节点必须使用bk_host_id")

            node_model = cls.objects.create(
                bk_tenant_id=node.bk_tenant_id,
                bk_biz_id=node.bk_biz_id,
                is_common=node.is_common,
                biz_scope=node.biz_scope,
                ip_type=node.ip_type,
                name=node.name,
                bk_host_id=node.bk_host_id,
                ip=node.ip,
                plat_id=node.plat_id,
                location=node.location,
                carrieroperator=node.carrieroperator,
                create_user=operator,
                update_user=operator,
            )
        return node_model

    def to_define(self) -> UptimeCheckNode:
        """转换为定义"""
        return UptimeCheckNode(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            id=self.pk,
            name=self.name,
            bk_host_id=self.bk_host_id,
            ip=self.ip,
            plat_id=self.plat_id,
            location=self.location,
            carrieroperator=self.carrieroperator or "",
            is_common=self.is_common,
            biz_scope=self.biz_scope,
            ip_type=UptimeCheckNodeIPType(self.ip_type),
            create_user=self.create_user,
            create_time=self.create_time,
            update_user=self.update_user,
            update_time=self.update_time,
        )

    @classmethod
    def _get_ip_by_host_id(cls, bk_tenant_id: str, bk_biz_id: int, bk_host_id: int) -> tuple[str, int] | None:
        """根据主机ID查询IP和云区域ID

        Args:
            bk_host_id: 主机ID

        Returns:
            tuple[str, int] | None: IP和云区域ID，如果获取失败则返回None
        """
        hosts = cmdb_api.get_host_by_ip(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            bk_host_ids=[bk_host_id],
            fields=[
                "bk_host_id",
                "bk_host_innerip",
                "bk_host_outerip",
                "bk_host_innerip_v6",
                "bk_host_outerip_v6",
                "bk_cloud_id",
            ],
        )
        if not hosts:
            raise ValueError(f"主机ID为{bk_host_id}的主机不存在")
        host = hosts[0]

        ip: str | None = host.bk_host_innerip or host.bk_host_innerip_v6
        if not ip:
            return None
        return ip, host.bk_cloud_id

    def set_host_id(self) -> int | None:
        """
        补全更新bk_host_id

        通过CMDB API根据IP和云区域ID查询主机，并更新节点的bk_host_id

        Returns:
            主机ID，如果获取失败则返回None
        """
        # 如果已有host_id，直接返回
        if self.bk_host_id:
            return self.bk_host_id

        # 如果节点没有IP，无法查询
        if not self.ip:
            logger.warning(f"拨测节点{self.name}没有IP地址，无法回填host_id")
            return None

        try:
            # 通过IP查询主机
            hosts = cmdb_api.get_host_by_ip(
                bk_tenant_id=self.bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                ips=[{"ip": self.ip, "bk_cloud_id": self.plat_id or -1}],
            )

            if hosts:
                bk_host_id = hosts[0].bk_host_id
                if bk_host_id:
                    # 更新节点的 host_id
                    UptimeCheckNodeModel.objects.filter(id=self.pk).update(bk_host_id=bk_host_id)
                    self.bk_host_id = bk_host_id
                    logger.info(f"拨测节点{self.name}（{self.ip}|{self.plat_id}）成功回填host_id: {bk_host_id}")
                    return bk_host_id
                else:
                    logger.warning(f"拨测节点{self.name}（{self.ip}|{self.plat_id}）查询到主机但无host_id")
            else:
                logger.info(f"拨测节点{self.name}（{self.ip}|{self.plat_id}）回填host_id失败，不存在对应cmdb主机实例")
        except Exception as e:
            logger.warning(
                f"拨测节点{self.name}（{self.ip}|{self.plat_id}）回填host_id失败: {e}",
                exc_info=True,
            )

        return None


@final
class UptimeCheckTaskSubscription(models.Model):
    """
    拨测任务订阅关系模型

    记录拨测任务与节点管理订阅的关联关系
    """

    uptimecheck_id = models.IntegerField("拨测任务id", default=0)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    bk_biz_id = models.IntegerField("业务ID", default=0)
    node_man_backend = models.CharField("节点管理后端", max_length=16, default="v2")
    node_man_policy_fingerprint = models.CharField("节点管理策略指纹", max_length=64, default="", blank=True)
    node_man_trigger_id = models.CharField("节点管理触发ID", max_length=128, default="", blank=True)
    node_man_operation_status = models.CharField("节点管理操作状态", max_length=32, default="", blank=True)
    node_man_result_state = models.CharField("节点管理写入结果状态", max_length=32, default="", blank=True)
    node_man_error = models.TextField("节点管理错误", default="", blank=True)

    objects = models_manager

    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_user = models.CharField("修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    @final
    class Meta:
        db_table = "monitor_uptimechecktasksubscription"
        app_label = "uptime_check"
        # 每个任务针对每个业务只能有一个item
        unique_together = (("uptimecheck_id", "bk_biz_id"),)
        managed = managed


@final
class UptimeCheckTaskNodeRelation(models.Model):
    """
    拨测任务与节点的多对多关联表

    显式声明 through 模型以便精确控制 db_table / db_column，
    确保与旧监控平台（monitor app）遗留表结构兼容。
    旧表名：monitor_uptimechecktask_nodes
    旧列名：uptimechecktask_id / uptimechecknode_id（模型名不含 Model 后缀）
    """

    # 使用 db_column 显式指定列名，避免 Django 使用带 Model 后缀的列名
    task = models.ForeignKey(  # pyright: ignore[reportUnknownVariableType]
        "UptimeCheckTaskModel",
        on_delete=models.CASCADE,
        db_column="uptimechecktask_id",
        verbose_name="拨测任务",
    )
    node = models.ForeignKey(
        UptimeCheckNodeModel,
        on_delete=models.CASCADE,
        db_column="uptimechecknode_id",
        verbose_name="拨测节点",
    )

    objects = models_manager

    @final
    class Meta:
        db_table = "monitor_uptimechecktask_nodes"
        app_label = "uptime_check"
        managed = managed
        unique_together = (("task", "node"),)


@final
class UptimeCheckTaskModel(models.Model):
    """
    拨测任务模型

    定义一个拨测任务,包含协议、配置、关联节点等信息
    """

    @final
    class Protocol:
        """协议类型"""

        TCP = "TCP"
        UDP = "UDP"
        HTTP = "HTTP"
        ICMP = "ICMP"

    PROTOCOL_CHOICES = (
        (Protocol.TCP, "TCP"),
        (Protocol.UDP, "UDP"),
        (Protocol.HTTP, "HTTP(S)"),
        (Protocol.ICMP, "ICMP"),
    )

    STATUS_CHOICES: tuple[tuple[str, str], ...] = tuple(UPTIME_CHECK_TASK_STATUS_NAME_MAP.items())

    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    name = models.CharField("任务名称", max_length=128, db_index=True)
    protocol = models.CharField("协议", choices=PROTOCOL_CHOICES, max_length=10)
    labels = models.JSONField("自定义标签", default=dict, null=True, blank=True)
    indepentent_dataid = models.BooleanField("独立业务数据ID", default=False)
    check_interval = models.PositiveIntegerField("拨测周期(分钟)", default=5)
    location: dict[str, str] = models.JSONField("地区", default=dict)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]

    nodes: models.QuerySet[UptimeCheckNodeModel] = models.ManyToManyField(  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
        UptimeCheckNodeModel,
        through="UptimeCheckTaskNodeRelation",
        verbose_name="拨测节点",
        related_name="tasks",
    )
    status = models.CharField(
        "当前状态",
        max_length=20,
        choices=STATUS_CHOICES,
        default=UptimeCheckTaskStatus.NEW_DRAFT.value,
    )
    config: dict[str, Any] = SymmetricJSONField("拨测配置", null=True, blank=True)  # pyright: ignore[reportAssignmentType]

    groups: models.QuerySet["UptimeCheckGroupModel"]  # pyright: ignore[reportUninitializedInstanceVariable]

    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_user = models.CharField("修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = models_manager

    @final
    class Meta:
        verbose_name = _("拨测任务")
        verbose_name_plural = _("拨测任务")
        db_table = "monitor_uptimechecktask"
        app_label = "uptime_check"

        managed = managed

    @classmethod
    def create_or_update_from_define(cls, task: UptimeCheckTask, operator: str) -> Self:
        """从定义创建或更新拨测任务

        Args:
            task: 拨测任务定义
            operator: 操作人

        Returns:
            Self: 创建或更新的拨测任务
        """

        nodes = UptimeCheckNodeModel.objects.filter(id__in=task.node_ids, is_deleted=False).filter(
            models.Q(bk_biz_id=task.bk_biz_id) | models.Q(is_common=True)
        )
        groups = UptimeCheckGroupModel.objects.filter(bk_biz_id=task.bk_biz_id, id__in=task.group_ids)

        if task.id:
            task_model = cls.objects.get(bk_biz_id=task.bk_biz_id, pk=task.id)
            task_model.name = task.name
            task_model.protocol = task.protocol
            task_model.labels = task.labels
            task_model.indepentent_dataid = task.independent_dataid
            task_model.check_interval = task.check_interval
            task_model.location = task.location
            task_model.config = task.config
            task_model.update_user = operator
            task_model.save()
            task_model.nodes.set(nodes)  # pyright: ignore[reportAttributeAccessIssue]
            task_model.groups.set(groups)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            task_model = cls.objects.create(
                bk_biz_id=task.bk_biz_id,
                name=task.name,
                protocol=task.protocol,
                labels=task.labels,
                indepentent_dataid=task.independent_dataid,
                check_interval=task.check_interval,
                location=task.location,
                config=task.config,
                create_user=operator,
                update_user=operator,
            )
            task_model.nodes.set(nodes)  # pyright: ignore[reportAttributeAccessIssue]
            task_model.groups.set(groups)  # pyright: ignore[reportAttributeAccessIssue]
        return task_model

    def to_define(
        self,
        *,
        include_node_ids: bool = True,
        include_group_ids: bool = True,
    ) -> UptimeCheckTask:
        """转换为定义对象。

        Args:
            include_node_ids: 是否加载关联节点 ID 列表。
                              设为 False 时跳过 M2M 查询，node_ids 返回空列表。
            include_group_ids: 是否加载关联分组 ID 列表。
                               设为 False 时跳过 M2M 查询，group_ids 返回空列表。

        Notes:
            - 对于被 only()/defer() 标记为 deferred 的普通字段，直接使用 define 默认值，
              避免访问 deferred 字段触发额外 SQL（N+1 问题）。
            - M2M 关联字段（node_ids/group_ids）通过显式参数控制，而非 deferred 机制，
              因为 M2M 字段不参与 only()/defer() 的字段裁剪。
        """
        # 节点 ID：由调用方通过 include_node_ids 参数决定是否加载
        if include_node_ids:
            node_id_list = getattr(self, "node_id_list", None)
            node_ids = (
                [node.pk for node in node_id_list]
                if node_id_list is not None
                # 没有预加载时回退到单次 values_list 查询
                else list(self.nodes.values_list("pk", flat=True))
            )
        else:
            node_ids = []

        # 分组 ID：由调用方通过 include_group_ids 参数决定是否加载
        if include_group_ids:
            group_id_list = getattr(self, "group_id_list", None)
            group_ids = (
                [group.pk for group in group_id_list]
                if group_id_list is not None
                else list(self.groups.values_list("pk", flat=True))
            )
        else:
            group_ids = []

        # 获取当前实例被 only()/defer() 标记的延迟字段集合
        deferred = self.get_deferred_fields()

        return UptimeCheckTask(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
            id=self.pk,
            bk_biz_id=self.bk_biz_id,
            name=self.name,
            protocol=UptimeCheckTaskProtocol(self.protocol),
            config={} if "config" in deferred else (self.config or {}),
            labels={} if "labels" in deferred else (self.labels or {}),
            independent_dataid=False if "indepentent_dataid" in deferred else self.indepentent_dataid,
            check_interval=5 if "check_interval" in deferred else self.check_interval,
            location={} if "location" in deferred else self.location,
            node_ids=node_ids,
            group_ids=group_ids,
            status=UptimeCheckTaskStatus(self.status),
            create_user=None if "create_user" in deferred else self.create_user,
            create_time=None if "create_time" in deferred else self.create_time,
            update_user=None if "update_user" in deferred else self.update_user,
            update_time=None if "update_time" in deferred else self.update_time,
        )

    @property
    def full_table_name(self) -> str:
        """获取完整的结果表名称"""
        return f"{self.bk_biz_id}_uptimecheck_{self.protocol.lower()}"

    @property
    def temp_conf_name(self) -> str:
        """
        测试流程临时配置文件名
        filename = {bizid}_{pk}_uptimecheckbeat.yml
        """
        return f"{self.bk_biz_id}_{self.pk}_uptimecheckbeat.yml"

    @override
    def __str__(self) -> str:
        return f"拨测任务({self.name})"


@final
class UptimeCheckTaskCollectorLog(models.Model):
    """
    拨测任务采集日志模型

    记录下发拨测任务时,节点管理中相关节点的执行日志
    """

    task_id = models.IntegerField("拨测任务ID")
    error_log: dict[str, Any] = models.JSONField("错误日志", default=dict)  # pyright: ignore[reportAssignmentType, reportUnknownVariableType]
    is_deleted = models.BooleanField("已删除", default=False)
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)
    nodeman_task_id = models.IntegerField("节点管理任务ID", default=0)

    objects = models_manager

    @final
    class Meta:
        db_table = "monitor_uptimechecktaskcollectorlog"
        app_label = "uptime_check"
        managed = managed


@final
class UptimeCheckGroupTaskRelation(models.Model):
    """
    拨测分组与任务的多对多关联表

    显式声明 through 模型以便精确控制 db_table / db_column，
    确保与旧监控平台（monitor app）遗留表结构兼容。
    旧表名：monitor_uptimecheckgroup_tasks
    旧列名：uptimecheckgroup_id / uptimechecktask_id（模型名不含 Model 后缀）
    """

    group = models.ForeignKey(  # pyright: ignore[reportUnknownVariableType]
        "UptimeCheckGroupModel",
        on_delete=models.CASCADE,
        db_column="uptimecheckgroup_id",
        verbose_name="拨测分组",
    )
    task = models.ForeignKey(
        UptimeCheckTaskModel,
        on_delete=models.CASCADE,
        db_column="uptimechecktask_id",
        verbose_name="拨测任务",
    )

    objects = models_manager

    @final
    class Meta:
        db_table = "monitor_uptimecheckgroup_tasks"
        app_label = "uptime_check"
        managed = managed
        unique_together = (("group", "task"),)


@final
class UptimeCheckGroupModel(models.Model):
    """
    拨测任务分组模型

    用于组织和管理多个拨测任务
    """

    name = models.CharField("分组名称", max_length=50)
    tasks = models.ManyToManyField(  # pyright: ignore[reportUnknownVariableType]
        UptimeCheckTaskModel,
        through="UptimeCheckGroupTaskRelation",
        verbose_name="拨测任务",
        related_name="groups",
    )
    logo = models.TextField("图片base64形式", default="", blank=True)
    bk_biz_id = models.IntegerField("业务ID", default=0)

    objects = models_manager

    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_user = models.CharField("修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    @final
    class Meta:
        verbose_name = _("拨测分组")
        verbose_name_plural = _("拨测分组")
        db_table = "monitor_uptimecheckgroup"
        app_label = "uptime_check"

        managed = managed

    @override
    def __str__(self) -> str:
        return f"拨测分组({self.name})"

    def to_define(self) -> UptimeCheckGroup:
        """转换为定义。

        Returns:
            UptimeCheckGroup: 拨测分组定义
        """
        return UptimeCheckGroup(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
            id=self.pk,
            bk_biz_id=self.bk_biz_id,
            name=self.name,
            logo=self.logo or "",
            task_ids=[int(task_id) for task_id in self.tasks.values_list("pk", flat=True)],
            create_user=self.create_user,
            create_time=self.create_time,
            update_user=self.update_user,
            update_time=self.update_time,
        )

    @classmethod
    def create_or_update_from_define(cls, group: UptimeCheckGroup, operator: str) -> Self:
        """从定义创建或更新拨测分组。

        Args:
            group: 拨测分组定义
            operator: 操作人

        Returns:
            Self: 创建或更新后的拨测分组模型实例
        """
        tasks = UptimeCheckTaskModel.objects.filter(bk_biz_id=group.bk_biz_id, id__in=group.task_ids)

        if group.id:
            group_model = cls.objects.get(bk_biz_id=group.bk_biz_id, pk=group.id)
            group_model.name = group.name
            group_model.logo = group.logo
            group_model.update_user = operator
            group_model.save()
            group_model.tasks.set(tasks)
        else:
            group_model = cls.objects.create(
                bk_biz_id=group.bk_biz_id,
                name=group.name,
                logo=group.logo,
                create_user=operator,
                update_user=operator,
            )
            group_model.tasks.set(tasks)

        return group_model
