import enum

JOB_TIMEOUT = 60 * 10  # 10 分钟


class PluginType(enum.StrEnum):
    EXPORTER = "exporter"
    SCRIPT = "script"
    JMX = "jmx"
    DATADOG = "datadog"
    PUSHGATEWAY = "pushgateway"
    BUILT_IN = "built_in"
    LOG = "log"
    PROCESS = "process"
    SNMP_TRAP = "snmp_trap"
    SNMP = "snmp"
    K8S = "k8s"


class VersionType(enum.StrEnum):
    """
    版本类型
    """

    # 主版本号
    MAJOR = "major"
    # 次版本号
    MINOR = "minor"


class MetricPluginStatus(enum.StrEnum):
    """
    指标插件状态
    """

    # 调试中
    DEBUG = "debug"
    # 已发布
    RELEASE = "release"
    # 未注册
    UNREGISTER = "unregister"


class ETLConfig(enum.StrEnum):
    """
    清洗模板配置
    """

    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"
    BK_STANDARD = "bk_standard"
    BK_EXPORTER = "bk_exporter"
    BK_STANDARD_V2_EVENT = "bk_standard_v2_event"


class TargetNodeType(enum.StrEnum):
    """
    目标节点类型
    """

    # 拓扑节点
    TOPO = "TOPO"
    # 主机
    HOST = "HOST"
    # 动态分组
    DYNAMIC_GROUP = "DYNAMIC_GROUP"
    # 集群模板
    SET_TEMPLATE = "SET_TEMPLATE"
    # 服务模板
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"


class InstanceType(enum.StrEnum):
    """
    实例类型
    """

    # 主机
    HOST = "HOST"
    # 服务实例
    SERVICE = "SERVICE"


class CollectStatus(enum.StrEnum):
    SUCCESS = "SUCCESS"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    NODATA = "NODATA"


class JobTaskStatusEnum(enum.StrEnum):
    """Job 任务状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败
    CANCELED = "canceled"  # 已取消


class JobTaskLogStatusEnum(enum.StrEnum):
    """Job 任务日志状态枚举"""

    RUNNING = "running"  # 执行中
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败


class JobTaskActionEnum(enum.StrEnum):
    """Job 任务操作类型枚举"""

    INSTALL = "install"  # 安装
    UNINSTALL = "uninstall"  # 卸载
    UPDATE = "update"  # 更新（清理+下发）
    RETRY = "retry"  # 重试
    START = "start"  # 启动（下发配置+重启）
    STOP = "stop"  # 停止（删除配置+重启）


class HostOSType(enum.StrEnum):
    """
    主机操作系统类型（来自 CMDB 主机信息）
    """

    LINUX = "linux"
    WINDOWS = "windows"
    AIX = "aix"


class HostOSArch(enum.StrEnum):
    """
    主机操作系统架构（来自 CMDB 主机信息）
    """

    X86_64 = "x86_64"
    AARCH64 = "aarch64"
    POWERPC = "powerpc"


SNMP_TRAP_DEFAULT_DIMENSIONS = [
    "version",
    "community",
    "enterprise",
    "generic_trap",
    "specific_trap",
    "snmptrapoid",
    "display_name",
    "agent_address",
    "agent_port",
    "server_ip",
    "server_port",
]

# 日志插件默认维度
LOG_DEFAULT_DIMENSIONS = [
    "event_name",
    "file_path",
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_biz_id",
    "bk_set_id",
    "bk_module_id",
]

# 进程插件内置维度
PROCESS_BUILD_IN_DIMENSIONS = [
    "bk_target_host_id",
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_target_topo_level",
    "bk_target_topo_id",
    "bk_target_service_category_id",
    "bk_collect_config_id",
    "bk_biz_id",
]
