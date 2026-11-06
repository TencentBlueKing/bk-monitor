from enum import Enum


class ObjectSelectType(str, Enum):
    INST = "inst"
    GROUP = "group"
    TOPO = "topo"
    LOG_THEME = "log_theme"
    ACCESS_OBJECT = "access_object"
    SERVICE_TEMPLATE = "service_template"  # 服务模板
    SET_TEMPLATE = "set_template"  # 集群模板


class TargetInstType(str, Enum):
    """目标实例类型"""

    HOST = "host"
    SERVICE_INSTANCE = "service_instance"


class TemplateObjId(str, Enum):
    """模板对象ID"""

    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"  # 服务模板
    SET_TEMPLATE = "SET_TEMPLATE"  # 集群模板


class TargetFieldType(str, Enum):
    """下发服务实例时目标字段类型"""

    SERVICE_TOPO = "service_topo_node"
    SERVICE_SET_TEMPLATE = "service_set_template"
    SERVICE_SERVICE_TEMPLATE = "service_service_template"


class TargetInstIDName(str, Enum):
    """目标实例ID名称"""

    SERVICE_TEMPLATE_ID = "service_template_id"  # 服务模板
    SET_TEMPLATE_ID = "set_template_id"  # 集群模板
    BK_INST_ID = "bk_inst_id"  # 动态拓扑


class BkGroupType(str, Enum):
    """实例所在分组类型"""

    GROUP = "group"
    TOPO = "topo"  # 动态拓扑，其组内实例为主机
    TOPO_SERVICE = "topo_service"  # 动态拓扑，其组内实例为服务实例
    SERVICE_TEMPLATE = "service_template"  # 服务模板
    SET_TEMPLATE = "set_template"  # 集群模板


TEMPLATE_CHOICES = [member for member in ObjectSelectType]


# bk_os_type 操作系统类型
class OSType(str, Enum):
    LINUX = "Linux"
    WINDOWS = "Windows"
    AIX = "AIX"


class EventSourceType(Enum):
    """消息事件的发送者"""

    CONTROLLER = "CONTROLLER"


class ResourceType(str, Enum):
    HOST_RELATION = "host_relation"
