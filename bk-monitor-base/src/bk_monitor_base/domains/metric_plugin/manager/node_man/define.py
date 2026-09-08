import enum


class NodemanPluginParamsMode(str, enum.Enum):
    """
    参数模式
    """

    # 采集器参数
    COLLECTOR = "collector"
    # 命令行选项参数
    OPT_CMD = "opt_cmd"
    # 命令行位置参数
    POS_CMD = "pos_cmd"
    # 环境变量
    ENV = "env"
    # 维度注入
    DMS_INSERT = "dms_insert"


class NodemanPluginParamsType(str, enum.Enum):
    """
    参数类型
    """

    TEXT = "text"
    PASSWORD = "password"
    SWITCH = "switch"
    FILE = "file"
    ENCRYPT = "encrypt"
    HOST = "host"
    SERVICE = "service"
    CODE = "code"
    LIST = "list"
    CUSTOM = "custom"
