from bk_monitor_base.infras.exception.std_error import StdError


class BaseError(StdError):
    """bk-monitor-base 异常基类 各领域异常应继承该基类来实现"""

    SYSTEM_CODE: str = "68"


class ModuleErrorCodes:
    """模块错误码"""

    API: str = "01"
    OBJECT_MODEL: str = "02"
    STRATEGY_CONFIG: str = "03"
    DYNAMIC_GROUP: str = "04"
    COLLECT_NODE: str = "05"
