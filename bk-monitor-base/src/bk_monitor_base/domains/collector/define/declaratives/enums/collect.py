from enum import Enum


class ObjectModelEnum(str, Enum):
    HOST = "cw-Host"
    BIZ = "cw-biz"
    WEB_SERVICE = "cw-web_service"
    OTHER = "cw-Others"


class SaveCollectApi(str, Enum):
    OBJECT_TYPE = "HOST"
    NODE_TYPE = "INSTANCE"


class TargetObjectType(str, Enum):
    HOST = "HOST"
    SERVICE = "SERVICE"


class TargetNodeType(str, Enum):
    INSTANCE = "INSTANCE"
    TOPO = "TOPO"
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"
    SET_TEMPLATE = "SET_TEMPLATE"


class TaskToggleStatus(str, Enum):
    ENABLED = "enable"
    DISABLED = "disable"


class PluginType(str, Enum):
    EXPORTER = "Exporter"
    JMX = "JMX"
    DATADOG = "DataDog"
    LOG = "Log"
    PUSHGATEWAY = "Pushgateway"
    SCRIPT = "Script"
    BUILTIN = "Built-In"
    SNMP = "SNMP"
    BKPull = "BK-Pull"
    IPMI = "IPMI"
    ORACLE = "ORACLE"
    WMI = "WMI"
    PROCESS = "Process"
    HARDWARE_PLUGIN = "HARDWARE_PLUGIN"
    MYSQL = "MYSQL"
    DB2 = "DB2"


class CollectType(str, Enum):
    SNMP_TRAP_COLLECT = "SnmpTrapCollect"
    BK_PLUGIN_COLLECT = "BkPluginCollect"
    EXTENSION_COLLECT = "ExtensionCollect"
    PROCESS_COLLECT = "ProcessCollect"
    SOURCE_COLLECT = "SourceCollect"
    HARDWARE_COLLECT = "HardwareCollect"
    HARDWARE_PLUGIN_COLLECT = "HardwarePluginCollect"
    # NOTE: 已废弃，声明式硬件采集统一走CW_SNMP
    HARDWARE_PLUGIN_COLLECT_V2 = "HARDWARE_PLUGIN_COLLECT"
    # 基于bk-pull重写的硬件类型插件
    CW_SNMP = "CW_SNMP"
    CW_IPMI = "CW_IPMI"
    CW_BLACKBOX = "CW_BLACKBOX"
    Redfish = "Redfish"
    SMI_S = "SMI-S"


class TaskAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    # 任务启停
    ENABLE = "enable"
    DISABLE = "disable"
    # 重试
    RETRY = "retry"
    # 升级
    UPGRADE = "upgrade"


class TaskStatus(str, Enum):
    """
    bk_monitor_base.models.declaratives.v1alpha1.collect.CollectConfig中的status的枚举值
    默认为PENDING
    """

    CREATE_SUCCEED = "创建成功"
    CREATE_FAILED = "创建失败"
    STOP_SUCCEED = "停用成功"
    STOP_FAILED = "停用失败"
    DEPLOY_SUCCEED = "部署成功"
    DEPLOY_FAILED = "部署失败"
    UPDATE_SUCCEED = "修改成功"
    UPDATE_FAILED = "修改失败"
    REMOVE_SUCCEED = "删除成功"
    REMOVE_FAILED = "删除失败"
    RETRYING = "重试中"
    PENDING = "等待中"
    STOPPING = "停用中"
    STARTING = "启用中"
    DEPLOYING = "部署中"
    PREPARING = "准备中"
    REMOVING = "删除中"
    SKIP_EXECUTION = "跳过执行"


class BkMonitorTaskStatus(str, Enum):
    """下发至监控平台的采集任务状态显示名"""

    CREATE_SUCCEED = "创建成功"
    CREATE_FAILED = "创建失败"
    UPDATE_FAILED = "修改失败"
    DEPLOY_SUCCEED = "部署成功"
    DEPLOYING = "部署中"
    DEPLOY_FAILED = "部署失败"
    STOP_SUCCEED = "停用成功"
    STOPPING = "停用中"
    STOP_FAILED = "停用失败"
    PENDING = "等待中"
    STARTING = "启用中"
    PREPARING = "准备中"


class BkTaskAction(str, Enum):
    INSTALL = "INSTALL"
    STOP = "STOP"
    UPDATE = "UPDATE"


class BkTaskStatus(str, Enum):
    """
    下发至监控平台的采集任务状态值
    """

    # status
    STOPPED = "STOPPED"
    STARTED = "STARTED"
    DEPLOYING = "DEPLOYING"
    STOPPING = "STOPPING"
    STARTING = "STARTING"
    PENDING = "PENDING"
    # task_status
    FAILED = "FAILED"
    SUCCEED = "SUCCESS"


class ReconcileStatus(str, Enum):
    # 待处理或处理中
    PENDING = "PENDING"
    # 完成
    COMPLETED = "COMPLETED"


class CollectSetTaskStatus(str, Enum):
    ALL_SUCCEED = "全部成功"
    ALL_FAILED = "全部失败"
    PARTIALLY_SUCCEED = "部分成功"
    IN_PROGRESS = "正在执行"
    UN_RELATED = "--"


class JobStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"


BkTaskStatusMap: dict[BkTaskStatus, dict[BkTaskStatus, TaskStatus]] = {
    # status + task_status
    BkTaskStatus.STOPPED: {
        BkTaskStatus.SUCCEED: TaskStatus.STOP_SUCCEED,
        BkTaskStatus.STOPPED: TaskStatus.STOP_SUCCEED,
        BkTaskStatus.FAILED: TaskStatus.STOP_FAILED,
        BkTaskStatus.PENDING: TaskStatus.REMOVING,
    },
    BkTaskStatus.STARTED: {
        BkTaskStatus.SUCCEED: TaskStatus.DEPLOY_SUCCEED,
        BkTaskStatus.FAILED: TaskStatus.DEPLOY_FAILED,
        BkTaskStatus.PENDING: TaskStatus.PENDING,
    },
    BkTaskStatus.DEPLOYING: {BkTaskStatus.DEPLOYING: TaskStatus.DEPLOYING},
    BkTaskStatus.STOPPING: {BkTaskStatus.STOPPING: TaskStatus.STOPPING},
    BkTaskStatus.STARTING: {BkTaskStatus.STARTING: TaskStatus.STARTING},
    BkTaskStatus.PENDING: {BkTaskStatus.PENDING: TaskStatus.PENDING},
}

SUCCEED_TASK_STATUS_TO_FAILED: dict[TaskStatus, TaskStatus] = {
    TaskStatus.CREATE_SUCCEED: TaskStatus.STOP_SUCCEED,
    TaskStatus.UPDATE_SUCCEED: TaskStatus.CREATE_FAILED,
    TaskStatus.DEPLOY_SUCCEED: TaskStatus.UPDATE_FAILED,
    TaskStatus.STOP_SUCCEED: TaskStatus.DEPLOY_FAILED,
}

FAILED_STATUS_SET = {
    TaskStatus.CREATE_FAILED,
    TaskStatus.UPDATE_FAILED,
    TaskStatus.DEPLOY_FAILED,
    TaskStatus.STOP_FAILED,
}
SUCCESS_STATUS_SET = {
    TaskStatus.CREATE_SUCCEED,
    TaskStatus.UPDATE_SUCCEED,
    TaskStatus.DEPLOY_SUCCEED,
    TaskStatus.STOP_SUCCEED,
}

INTERMEDIATE_STATUS_SET = {
    TaskStatus.DEPLOYING,
    TaskStatus.STOPPING,
    TaskStatus.STARTING,
    TaskStatus.PREPARING,
    TaskStatus.REMOVING,
    TaskStatus.RETRYING,
    TaskStatus.PENDING,
}

#
DISABLE_RETRY_STATUS_SET = {
    TaskStatus.CREATE_SUCCEED,
    TaskStatus.STOP_SUCCEED,
    TaskStatus.DEPLOY_SUCCEED,
    TaskStatus.UPDATE_SUCCEED,
    TaskStatus.RETRYING,
    TaskStatus.DEPLOYING,
    TaskStatus.PENDING,
    TaskStatus.REMOVING,
}

EXCLUDE_BLUEKING_COLLECT_MAPPING = {
    PluginType.PROCESS.value: CollectType.PROCESS_COLLECT,
    PluginType.ORACLE.value: CollectType.EXTENSION_COLLECT,
    PluginType.MYSQL.value: CollectType.EXTENSION_COLLECT,
    PluginType.DB2.value: CollectType.EXTENSION_COLLECT,
    PluginType.WMI.value: CollectType.EXTENSION_COLLECT,
    PluginType.HARDWARE_PLUGIN.value: CollectType.HARDWARE_PLUGIN_COLLECT,
}
