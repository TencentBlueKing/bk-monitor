from enum import Enum

# 默认的间隔, 默认为60秒
DEFAULT_EVALUATION_INTERVAL = "60s"
DEFAULT_RULE_TYPE = "prometheus"


class RecordRuleStatus(Enum):
    """预计算状态"""

    CREATED = "created"
    RUNNING = "running"
    DELETED = "deleted"


class BkDataFlowStatus(Enum):
    """流程状态"""

    NO_ACCESS = "no-access"
    NO_CREATE = "no-create"
    NO_START = "no-start"

    ACCESSING = "accessing"
    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"

    ACCESS_FAILED = "access-failed"
    CREATE_FAILED = "create-failed"
    START_FAILED = "start-failed"
    STOP_FAILED = "stop-failed"
