import enum
import logging
from datetime import datetime
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, Field, field_validator

from .constants import JobTaskActionEnum, JobTaskLogStatusEnum, JobTaskStatusEnum, MetricPluginStatus

logger = logging.getLogger(__name__)


class VersionTuple(NamedTuple):
    """
    版本号
    """

    major: int
    minor: int


class JobPluginBuiltInDimension(NamedTuple):
    """Job 插件下发时固定注入的内置维度声明。"""

    field_name: str
    description: str


JOB_PLUGIN_BUILT_IN_DIMENSIONS = [
    JobPluginBuiltInDimension("bk_collect_config_id", "采集配置ID"),
    JobPluginBuiltInDimension("bk_target_cloud_id", "云区域ID"),
    JobPluginBuiltInDimension("bk_target_ip", "目标IP"),
    JobPluginBuiltInDimension("bk_target_host_id", "目标主机ID"),
]


def parse_version(version: str) -> VersionTuple:
    """解析版本字符串为 VersionTuple。

    支持两种格式：
    - 非零填充："1.10"
    - 零填充："000001.000010"

    Args:
        version: 版本字符串，格式为 "major.minor"。

    Returns:
        解析后的版本元组。

    Raises:
        ValueError: 当版本格式非法时抛出。
    """
    if not version:
        raise ValueError("版本号不能为空")

    raw = str(version).strip()
    parts = raw.split(".")
    if len(parts) != 2:
        raise ValueError(f"版本格式错误，应为 major.minor: {raw!r}")

    major_str, minor_str = parts
    if not major_str.isdigit() or not minor_str.isdigit():
        raise ValueError(f"版本格式错误，major/minor 必须为非负整数: {raw!r}")

    return VersionTuple(major=int(major_str), minor=int(minor_str))


def format_version_padded(version: VersionTuple) -> str:
    """将 VersionTuple 格式化为用于排序的零填充版本字符串。

    格式固定为 6+1+6："{major:06d}.{minor:06d}"，便于直接使用字典序进行版本排序。

    Args:
        version: 版本元组。

    Returns:
        零填充后的版本字符串。

    Raises:
        ValueError: 当版本号为负数或超过 6 位上限时抛出。
    """
    major = int(version.major)
    minor = int(version.minor)
    if major < 0 or minor < 0:
        raise ValueError(f"版本号不能为负数: {version!r}")
    if major > 999_999 or minor > 999_999:
        raise ValueError(f"版本号超过可支持范围(0~999999): {version!r}")
    return f"{major:06d}.{minor:06d}"


class MetricPluginDeploymentScope(BaseModel):
    """指标插件部署范围定义"""

    node_type: str = Field(title="节点类型")
    nodes: list[dict[str, Any]] = Field(title="节点列表")


class MetricPluginParams(BaseModel):
    """
    指标插件参数定义
    """

    name: str = Field(title="参数名称", min_length=1, max_length=255)
    alias: str = Field(title="参数别名", default="", max_length=255)
    description: str = Field(title="参数说明", default="")
    type: str = Field(title="参数类型", default="text", min_length=1, max_length=32)
    required: bool = Field(title="是否必填", default=False)
    default: Any = Field(title="默认值", default=None)
    visible: bool = Field(title="是否可见", default=True)
    mode: str = Field(title="参数模式", default="", max_length=32)
    file_base64: str = Field(title="文件内容(base64)", default="")
    election: list[dict[str, Any]] = Field(title="选项列表", default_factory=list)
    options: dict[str, Any] = Field(title="选项", default_factory=dict)


class MetricPluginMetricField(BaseModel):
    """
    指标字段定义
    """

    name: str = Field(title="字段名称", min_length=1, max_length=255)
    type: Literal["string", "double", "int"] = Field(title="字段类型", default="string")
    description: str = Field(title="字段说明", default="")
    monitor_type: Literal["dimension", "metric"] = Field(title="监控类型")
    unit: str = Field(title="单位", default="none")
    is_active: bool = Field(title="是否活跃", default=True)
    is_diff_metric: bool = Field(title="是否差值指标", default=False)
    source_name: str = Field(title="来源名称", default="")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """兼容处理：将 int 类型转换为 double。"""
        if v == "int":
            return "double"
        return v


class MetricPluginMetricGroup(BaseModel):
    """
    指标组定义
    """

    table_name: str = Field(title="表名", min_length=1, max_length=255)
    table_desc: str = Field(title="表描述", default="")
    fields: list[MetricPluginMetricField] = Field(title="字段列表", default_factory=list)
    rules: list[str] = Field(title="分组规则", default_factory=list)


class MetricPlugin(BaseModel):
    """指标插件的实体定义

    Note:
        1. 支持版本管理，使用两段式版本号，主版本号和次版本号。如果主版本号发生变化，表示插件的核心配置发生变化，需要重新下发。
        2. 支持插件状态管理，插件状态分为调试中/已发布。
        3. 支持插件参数定义，用于定义插件在后续采集下发时的可用参数。
        4. 支持插件的指标配置，用于定义插件的指标和维度信息。
        5. bk_tenant_id + id 唯一标识一个插件。
    """

    bk_tenant_id: str = Field(title="租户ID", min_length=1, max_length=64)
    bk_biz_id: int = Field(
        title="归属业务ID",
        description="该业务拥有该插件的管理权限，并且有资格查询插件的所有数据。如果为0则表示不归属与任何业务。",
    )
    is_global: bool = Field(title="是否全局插件", description="全局插件可以被所有业务使用", default=False)
    is_internal: bool = Field(
        title="是否内置插件", description="内置插件由系统管理员创建，不能被删除或修改", default=False
    )
    id: str = Field(title="插件ID", min_length=1, max_length=64)
    type: str = Field(title="插件类型", min_length=1, max_length=32)
    name: str = Field(title="插件名称", min_length=1, max_length=255)
    description_md: str = Field(title="描述", default="")
    logo: str = Field(title="logo(文件路径或在线URL)", default="")
    created_at: datetime = Field(title="创建时间", default_factory=datetime.now)
    updated_at: datetime = Field(title="更新时间", default_factory=datetime.now)
    created_by: str = Field(title="创建用户", default="", max_length=255)
    updated_by: str = Field(title="更新用户", default="", max_length=255)

    label: str = Field(title="标签", default="", max_length=64)
    metrics: list[MetricPluginMetricGroup] = Field(
        title="指标配置",
        description="定义了指标和维度信息。当开启指标自动发现后，该字段会被自动刷新。",
        default_factory=list,
    )
    enable_metric_discovery: bool = Field(
        title="自动发现指标开关", description="开启后，插件会自动发现指标。", default=False
    )

    params: list[MetricPluginParams] = Field(
        title="参数配置", description="用于定义插件在后续采集下发时的可用参数。", default_factory=list
    )
    define: dict[str, Any] = Field(
        title="插件定义",
        description="插件核心配置，不同类型插件的定义不同。比如脚本采集的脚本内容，exporter的二进制路径等。",
        default_factory=dict,
    )
    is_support_remote: bool = Field(title="是否支持远程采集", default=False)
    related_params: dict[str, Any] = Field(
        title="关联参数",
        description="用于记录插件的一些关键的周边模块/系统参数，比如插件的数据ID等",
        default_factory=dict,
    )

    version: VersionTuple = Field(
        title="版本",
        description="主版本号和次版本号，在插件更新时自动递增。当插件配置及是否支持远程采集发生变化时，主版本号加1，否则次版本号加1。用于判断插件是否需要重新下发。",
        default=VersionTuple(major=1, minor=0),
    )
    version_log: str = Field(title="版本日志", description="记录插件的版本更新日志", default="")
    status: MetricPluginStatus = Field(
        title="状态", description="当前版本是调试中/已发布", default=MetricPluginStatus.DEBUG
    )

    def read_logo(self) -> bytes:
        """读取 logo 并返回二进制内容。"""
        import base64

        if not self.logo:
            raise ValueError("logo is empty")

        if ";base64," in self.logo:
            _, base64_data = self.logo.split(";base64,", 1)
        elif "," in self.logo:
            _, base64_data = self.logo.split(",", 1)
        else:
            raise ValueError("invalid logo format")
        try:
            return base64.b64decode(base64_data, validate=True)
        except Exception:
            logger.exception("failed to decode logo base64 data")
            return b""

    def version_str(self) -> str:
        """
        获取版本字符串
        """
        return f"{self.version.major}.{self.version.minor}"


class MetricPluginDeploymentVersion(BaseModel):
    """
    指标插件部署版本定义

    Note:
        该模型定义了插件部署项每次变更的详细信息，包括插件版本、参数、目标节点、远程节点、目标实例、远程实例等。

        1. 每次采集变更都会新建一条记录，版本号从1开始递增。
        2. 只有支持远程采集插件且配置了远程节点时，才会按照远程节点进行采集下发，否则采集节点与目标节点一致。
        3. target_instances和remote_instances字段用于记录实际下发目标实例，目前仅作为一个记录字段，实际下发目标实例由下发时记录。
    """

    deployment_id: int = Field(title="部署ID")
    bk_tenant_id: str = Field(title="租户ID", min_length=1, max_length=64)
    bk_biz_id: int = Field(
        title="归属业务ID",
        description="该业务拥有该插件的管理权限，并且有资格查询插件的所有数据。如果为0则表示不归属与任何业务。",
    )
    plugin_version: VersionTuple = Field(title="插件版本")
    version: int = Field(title="部署版本号", ge=1, description="部署版本号，从1开始递增")
    target_scope: MetricPluginDeploymentScope = Field(
        title="采集目标范围", description="采集目标范围，如果非远程采集，采集目标范围与插件部署范围一致"
    )
    target_instances: list[dict[str, Any]] = Field(title="目标实例", default_factory=list)
    remote_scope: MetricPluginDeploymentScope | None = Field(
        title="远程部署范围", description="如果非空，则为远程采集", default=None
    )
    remote_instances: list[dict[str, Any]] = Field(title="远程实例", default_factory=list)
    params: dict[str, Any] = Field(title="部署参数", default_factory=dict)
    created_at: datetime = Field(title="创建时间", default_factory=datetime.now)
    created_by: str = Field(title="创建用户", default="", max_length=255)


class MetricPluginDeploymentStatusEnum(str, enum.Enum):
    """指标插件部署状态枚举"""

    # 初始化（未下发）
    INITIALIZING = "initializing"

    # 停止中
    STOPPING = "stopping"
    # 启动中
    STARTING = "starting"
    # 部署中
    DEPLOYING = "deploying"

    # 运行中
    RUNNING = "running"
    # 已停止
    STOPPED = "stopped"
    # 失败
    FAILED = "failed"


class MetricPluginDeployment(BaseModel):
    """指标插件部署项定义

    Note:
        1. 每个部署项对应一个插件，一个插件可以有多个部署项。
        2. 部署项创建后不允许修改使用的插件，只能修改使用的插件版本。
        3. 每个部署项都有一个当前版本和若干历史版本。
    """

    bk_tenant_id: str = Field(title="租户ID", min_length=1, max_length=64)
    bk_biz_id: int = Field(title="业务ID")
    id: int = Field(title="部署ID")
    name: str = Field(title="部署名称", min_length=1, max_length=255)
    related_params: dict[str, Any] = Field(
        title="关联参数",
        description="用于记录部署项的一些关键的周边模块/系统参数，比如节点管理的订阅ID，插件ID等",
        default_factory=dict,
    )
    status: str = Field(
        MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        title="状态",
        description="仅定义了基础的开始和结束状态，中间状态可以自定义",
    )
    plugin_id: str = Field(title="插件ID", min_length=1, max_length=64)
    created_at: datetime = Field(title="创建时间", default_factory=datetime.now)
    updated_at: datetime = Field(title="更新时间", default_factory=datetime.now)
    created_by: str = Field("", title="创建用户", max_length=255)
    updated_by: str = Field("", title="更新用户", max_length=255)


class PluginMajorParams(BaseModel):
    """插件核心配置参数校验"""

    params: list[MetricPluginParams] = Field(title="参数配置列表", default_factory=list)
    define: dict[str, Any] = Field(title="插件定义", default_factory=dict)
    is_support_remote: bool = Field(title="是否支持远程采集", default=False)


class PluginMinorParams(BaseModel):
    """插件次要配置参数校验"""

    name: str = Field(title="插件名称", min_length=1, max_length=255)
    description_md: str = Field(title="描述", default="")
    label: str = Field(title="标签", min_length=1, max_length=64)
    logo: str = Field(title="logo(文件路径或在线URL)", default="")
    metrics: list[MetricPluginMetricGroup] = Field(title="指标配置列表", default_factory=list)
    enable_metric_discovery: bool = Field(title="是否开启指标自动发现", default=False)


class CreatePluginParams(PluginMajorParams, PluginMinorParams):
    """创建插件参数校验"""

    id: str = Field(title="插件ID", min_length=1, max_length=64)
    type: str = Field(title="插件类型", min_length=1, max_length=32)
    is_global: bool = Field(title="是否全局插件", default=False)
    is_internal: bool = Field(title="是否内置插件", default=False)

    version: VersionTuple = Field(title="初始版本号", default=VersionTuple(major=1, minor=0))
    status: MetricPluginStatus = Field(title="状态", default=MetricPluginStatus.DEBUG)
    version_log: str = Field(title="版本日志", default="")


class CreatePluginVersionParams(PluginMajorParams, PluginMinorParams):
    """创建插件版本参数校验"""

    version: VersionTuple | None = Field(title="指定版本号", default=None)
    status: MetricPluginStatus = Field(title="状态", default=MetricPluginStatus.DEBUG)
    version_log: str = Field(title="版本日志", default="")


class UpdatePluginVersionParams(PluginMinorParams):
    """更新插件版本参数校验"""

    version_log: str = Field(title="版本日志", default="")


class DeployPluginParams(BaseModel):
    """指标插件部署参数"""

    plugin_version: VersionTuple = Field(title="插件版本")
    params: dict[str, Any] = Field(title="部署参数", default_factory=dict)
    target_scope: MetricPluginDeploymentScope = Field(title="采集目标范围")
    remote_scope: MetricPluginDeploymentScope | None = Field(title="远程部署范围", default=None)


class CreateOrUpdateDeploymentParams(DeployPluginParams):
    """创建或更新插件部署项参数"""

    id: int | None = Field(title="部署ID", default=None)
    name: str = Field(title="部署名称", min_length=1, max_length=255)
    plugin_id: str = Field(title="插件ID", min_length=1, max_length=64)


class RetryDeployPluginParams(BaseModel):
    """重试指标插件部署参数"""

    deployment_id: int = Field(title="部署ID")
    instance_scope: MetricPluginDeploymentScope | None = Field(title="实例范围", default=None)


class JobTaskLogEntry(BaseModel):
    """任务日志条目"""

    step: str = Field(title="步骤名称")
    status: JobTaskLogStatusEnum = Field(title="步骤状态")
    messages: str = Field(title="日志消息", default="")
    job_instance_id: int | None = Field(title="作业平台任务实例ID", default=None)
    timestamp: str = Field(title="时间戳", default="")
    extra: dict[str, Any] = Field(title="额外信息", default_factory=dict)


class JobTaskInstance(BaseModel):
    """Job 任务实例定义

    用于业务层操作的 Pydantic 模型，与 ORM 模型分离。
    只有需要持久化时才调用 save() 方法写入数据库。

    Note:
        1. 每个任务实例对应一个目标实例（主机、容器、Pod 等）
        2. 任务状态包括：等待执行、执行中、执行成功、执行失败、已取消
        3. 任务日志记录每个执行步骤的详细信息
    """

    # 数据库主键，None 表示尚未持久化
    id: int | None = Field(title="任务实例ID", default=None)

    # 基础信息
    bk_tenant_id: str = Field(title="租户ID", max_length=64)
    bk_biz_id: int = Field(title="业务ID")

    # 任务信息
    action: JobTaskActionEnum = Field(title="操作类型")
    status: JobTaskStatusEnum = Field(title="任务状态", default=JobTaskStatusEnum.PENDING)

    # 目标实例信息
    instance_id: str = Field(title="实例标识", max_length=255)
    instance_info: dict[str, Any] = Field(title="实例信息", default_factory=dict)
    collect_instance_info: dict[str, Any] = Field(title="采集执行实例信息", default_factory=dict)

    # 任务步骤和日志
    current_step: str = Field(title="当前步骤", default="")
    task_log: list[JobTaskLogEntry] = Field(title="任务日志", default_factory=list)

    # 执行参数
    execute_params: dict[str, Any] = Field(title="执行参数", default_factory=dict)

    # 错误信息
    error_message: str = Field(title="错误信息", default="")

    # 时间信息
    created_at: datetime | None = Field(title="创建时间", default=None)
    created_by: str = Field(title="创建用户", default="", max_length=255)
    updated_at: datetime | None = Field(title="更新时间", default=None)
    started_at: datetime | None = Field(title="开始执行时间", default=None)
    finished_at: datetime | None = Field(title="完成时间", default=None)

    def start_task(self) -> None:
        """开始执行任务"""
        self.status = JobTaskStatusEnum.RUNNING
        self.started_at = datetime.now()

    def success_task(self) -> None:
        """任务成功

        Args:
            success: 是否成功
            error_message: 错误信息（失败时）
        """
        self.status = JobTaskStatusEnum.SUCCESS
        self.finished_at = datetime.now()

    def cancel_task(self, reason: str = "") -> None:
        """取消任务

        Args:
            reason: 取消原因
        """
        self.status = JobTaskStatusEnum.CANCELED
        self.error_message = reason
        self.finished_at = datetime.now()

    def fail_task(self, error_message: str) -> None:
        """任务失败

        Args:
            error_message: 错误信息
        """
        self.status = JobTaskStatusEnum.FAILED
        self.error_message = error_message
        self.finished_at = datetime.now()

    def add_log_entry(
        self,
        step: str,
        status: JobTaskLogStatusEnum,
        messages: str,
        job_instance_id: int | None = None,
        **extra: Any,
    ) -> None:
        """添加日志条目

        Args:
            step: 步骤名称
            status: 步骤状态（枚举值）
            messages: 日志消息
            job_instance_id: 作业平台任务实例ID
            extra: 额外信息
        """
        self.current_step = step
        log_entry = JobTaskLogEntry(
            step=step,
            status=status,
            messages=messages,
            job_instance_id=job_instance_id,
            timestamp=datetime.now().isoformat(),
            extra=extra if extra else {},
        )

        # 检查是否已存在相同步骤的日志，存在则更新，否则添加
        for i, entry in enumerate(self.task_log):
            if entry.step == step:
                self.task_log[i] = log_entry
                return

        self.task_log.append(log_entry)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        Returns:
            dict: 任务实例信息
        """
        return {
            "task_id": self.id,
            "instance_id": self.instance_id,
            "instance_info": self.instance_info,
            "collect_instance_info": self.collect_instance_info,
            "action": self.action.value,
            "status": self.status.value,
            "task_log": [entry.model_dump() for entry in self.task_log],
            "current_step": self.current_step,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    def is_finished(self) -> bool:
        """判断任务是否已完成（成功、失败或取消）"""
        return self.status in [JobTaskStatusEnum.SUCCESS, JobTaskStatusEnum.FAILED, JobTaskStatusEnum.CANCELED]

    def is_running(self) -> bool:
        """判断任务是否正在执行"""
        return self.status == JobTaskStatusEnum.RUNNING

    def is_pending(self) -> bool:
        """判断任务是否等待执行"""
        return self.status == JobTaskStatusEnum.PENDING
