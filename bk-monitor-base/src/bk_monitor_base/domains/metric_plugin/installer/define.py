from enum import Enum
from typing import Any, TypedDict


class TaskDeployStep(str, Enum):
    """正式部署任务步骤枚举

    定义了采集插件正式部署过程中的各个步骤，用于任务状态跟踪和日志记录。
    """

    # 安装流程步骤
    TRANSFER_PLUGIN = "TRANSFER_PLUGIN"
    TRANSFER_BKMONITORBEAT_CONFIG = "TRANSFER_BKMONITORBEAT_CONFIG"
    CHMOD_PLUGIN = "CHMOD_PLUGIN"
    RESTART_BKMONITORBEAT = "RESTART_BKMONITORBEAT"

    # 卸载/清理流程步骤
    REMOVE_PLUGIN = "REMOVE_PLUGIN"
    REMOVE_CONFIG = "REMOVE_CONFIG"

    # 重试流程步骤（卸载后安装）
    RETRY_UNINSTALL = "RETRY_UNINSTALL"
    RETRY_INSTALL = "RETRY_INSTALL"


TASK_DEPLOY_STEP_NAME_MAP: dict[str, str] = {
    TaskDeployStep.TRANSFER_PLUGIN.value: "下发插件文件到目标主机",
    TaskDeployStep.TRANSFER_BKMONITORBEAT_CONFIG.value: "下发 bkmonitorbeat 子配置",
    TaskDeployStep.CHMOD_PLUGIN.value: "插件二进制文件授权",
    TaskDeployStep.RESTART_BKMONITORBEAT.value: "重启 bkmonitorbeat 服务",
    TaskDeployStep.REMOVE_PLUGIN.value: "删除插件文件目录",
    TaskDeployStep.REMOVE_CONFIG.value: "删除 bkmonitorbeat 子配置文件",
    TaskDeployStep.RETRY_UNINSTALL.value: "重试卸载阶段",
    TaskDeployStep.RETRY_INSTALL.value: "重试安装阶段",
}

JOB_COLLECT_LOG_STATUS_NAME_MAP: dict[str, str] = {
    "running": "执行中",
    "success": "执行成功",
    "failed": "执行失败",
}


class InstanceTargetParams(TypedDict):
    """
    实例目标参数返回
    Args:
        collector_params: 采集器参数
        plugin_params: 插件参数
    """

    collector_params: dict[str, Any]
    plugin_params: dict[str, Any]


class TargetChangeAnalysis(TypedDict):
    """目标变更分析结果

    根据版本差异分析出各目标实例的操作类型：
    - targets_to_add: 仅下发（新增的目标，旧版本不存在）
    - targets_to_remove: 仅清理（删除的目标，新版本不存在）
    - targets_to_update: 清理+下发（更新的目标，新旧版本都存在但配置有变化）
    - targets_unchanged: 无变化（新旧版本都存在且配置相同）
    """

    targets_to_add: list[dict[str, Any]]  # 仅下发：新增的目标
    targets_to_remove: list[dict[str, Any]]  # 仅清理：删除的目标
    targets_to_update: list[dict[str, Any]]  # 清理+下发：更新的目标
    targets_unchanged: list[dict[str, Any]]  # 无变化：配置相同的目标


class InstanceStatusInfo(TypedDict, total=False):
    """单个实例的状态信息"""

    task_id: int  # 任务实例ID
    status: str  # 任务状态: pending/running/success/failed/canceled/unknown
    current_step: str  # 当前执行步骤
    error_message: str  # 错误信息
    detail: dict[str, Any]  # 详细信息（当 with_detail=True 时返回）


class InstallerStatusResult(TypedDict, total=False):
    """安装器 status 方法的返回结果

    Note:
        - 当指定 instance_id 时，返回 instance_status 字段
        - 当不指定 instance_id 时，返回 instance_statuses 字段
    """

    deployment_status: str  # 部署状态
    instance_count: int  # 实例总数
    instance_status: dict[str, InstanceStatusInfo]  # 指定实例的状态（单个实例查询时）


class JobCollectLogEntry(TypedDict, total=False):
    """Job 采集日志条目原始结构。"""

    step: str
    status: str
    messages: str
    job_instance_id: int | None
    timestamp: str
    extra: dict[str, Any]


class JobCollectLogDetail(TypedDict, total=False):
    """Job 采集日志详情原始结构。"""

    task_id: int
    instance_id: str
    status: str
    current_step: str
    error_message: str
    task_log: list[JobCollectLogEntry]
