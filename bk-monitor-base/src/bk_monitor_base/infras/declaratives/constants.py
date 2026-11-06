from enum import Enum
from typing import final


@final
class ThreadLocalKey:
    # NOTE: CONTROLLER_NAME changed to DECLARATIVE_DEPARTMENT_NAME
    CONTROLLER_NAME: str = "declarative_department_name"
    DECLARATIVE_DEPARTMENT_NAME: str = "declarative_department_name"
    BK_TENANT_ID: str = "bk_tenant_id"


class TargetObjectType:
    """
    目标对象类型
    """

    SERVICE: str = "SERVICE"
    HOST: str = "HOST"


class TargetNodeType:
    """
    目标节点类型
    """

    TOPO: str = "TOPO"  # 动态实例（拓扑）
    INSTANCE: str = "INSTANCE"  # 静态实例
    SERVICE_TEMPLATE: str = "SERVICE_TEMPLATE"  # 服务模板
    SET_TEMPLATE: str = "SET_TEMPLATE"  # 集群模板


class BkObject(str, Enum):
    HOST = "host"
    BIZ = "biz"
    UPTIME_CHECK = "uptimecheck"
    BUILT_IN_OTHER_MONITOR_OBJECT = "Others"


ES_QUERY_MAX_VALUE = 10000

# ES Resource Store
ES_RESOURCE_STORE = "bk_monitor_base.infras.declaratives.store.es_db.ESStore"


class StrategyTargetType(str, Enum):
    GENERAL = "general"
    NON_HOST = "non_host"
    HARDWARE = "hardware"
    UPTIME_CHECK = "uptime_check"
    K8S = "k8s"
    SERVICE_TEMPLATE = "service_template"  # 服务模板
    SET_TEMPLATE = "set_template"  # 集群模板
    SERVICE_TOPO = "service_topo"  # 服务实例拓扑


class SyncStatus(str, Enum):
    INIT = "同步未开始"
    PENDING = "延迟同步"
    UPDATED = "已同步更新"
    OUTDATED = "同步更新失败"
    DELETED = "对应条目已经在监控平台被删除"


class SyncDisplayStatus(str, Enum):
    NOT_ENABLED = "NOT_ENABLED"
    SUCCESS = "SUCCESS"
    EXECUTING = "EXECUTING"
    FAILED = "FAILED"
    ABNORMAL = "ABNORMAL"  # 异常
    SKIP_EXECUTE = "SKIP_EXECUTE"  # 跳过执行
    NO_TARGETS = "NO_TARGETS"  # 无监控目标

    @classmethod
    def get_abnormal_sub_status_list(cls):
        """获取所有异常子状态"""
        return [status for status in SyncAbnormalSubStatus]


class SyncAbnormalSubStatus(str, Enum):
    # ABNORMAL 的子状态
    UNASSOCIATED_COLLECT = "UNASSOCIATED_COLLECT"  # 未关联采集任务
    INST_ALL_DISABLED = "INST_ALL_DISABLED"  # 监控目标全部被禁用
    BIZ_INST_ALL_DISABLED = "BIZ_INST_ALL_DISABLED"  # 某业务下监控目标全部被禁用


SYNC_STATUS_TRANSLATE = {
    SyncStatus.UPDATED: SyncDisplayStatus.SUCCESS,
    SyncStatus.INIT: SyncDisplayStatus.EXECUTING,
    SyncStatus.OUTDATED: SyncDisplayStatus.FAILED,
    SyncStatus.DELETED: SyncDisplayStatus.FAILED,
}
