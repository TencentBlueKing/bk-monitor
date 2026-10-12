"""
开关控制上层调用 Base 时的具体行为
"""

from collections.abc import Callable
from typing import Any, TypeVar

from bk_monitor_base.config import get_config

# 定义泛型类型变量，用于保持返回值类型
T = TypeVar("T")


def is_use_new_base() -> bool:
    """
    检查是否使用新的 Base 模块

    Returns:
        bool: 如果配置项 `enable_base_compatible_switch` 为 True，则返回 True，否则返回 False
    """
    config = get_config()
    return config.common.enable_base_compatible_switch


def enable_base_metadata() -> bool:
    """
    检查是否使用 Base METADATA模块

    Returns:
        bool: 如果配置项 `enable_base_metadata` 为 True，则返回 True，否则返回 False
    """
    config = get_config()
    return config.common.enable_base_metadata


def base_switch(
    legacy: Callable[..., T],
    current: Callable[..., T],
    params: tuple[Any, ...] = (),
) -> T:
    """
    Base 模块调用开关函数

    根据配置项 `enable_base_compatible_switch` 的值，选择调用旧的或新的 Base 模块函数。

    Args:
        legacy: 旧的 Base 模块调用函数
        current: 新的 Base 模块调用函数
        params: 传递给函数的参数，使用元组形式传递

    Returns:
        函数执行结果

    Examples:
        >>> from bk_monitor_base.infras.switch import base_switch
        >>> from bk_monitor_base.strategy import save_alarm_strategy
        >>> result = base_switch(
        ...     legacy=StrategyApi.save_alarm_strategy_v2,
        ...     current=save_alarm_strategy,
        ...     params=(obj,)
        ... )
    """

    if is_use_new_base():
        return current(*params)
    else:
        return legacy(*params)


__all__ = ["base_switch", "is_use_new_base", "enable_base_metadata"]
