from collections.abc import Callable
from typing import ClassVar

from bk_monitor_base.infras.declaratives.constants import ThreadLocalKey
from bk_monitor_base.infras.threading.local import set_local_param


class BaseDetector:
    """detector 的抽象基类"""

    detector_name: ClassVar[str]
    detect_objs: ClassVar[list[Callable]]

    def __init_subclass__(cls, **kwargs):
        # 为Detector_name提供默认值为类名
        if "detector_name" not in cls.__dict__:
            cls.detector_name = cls.__name__
        super().__init_subclass__(**kwargs)
        set_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, cls.detector_name)
