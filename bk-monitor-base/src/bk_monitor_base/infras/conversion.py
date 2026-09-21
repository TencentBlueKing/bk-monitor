"""类型转换工具模块。

提供安全的类型转换函数，用于将各种类型的值转换为目标类型。
"""

from typing import Any


def safe_int(value: Any, default: int = 0) -> int:
    """安全地将值转换为整数。

    支持将字符串、浮点数、整数等类型转换为整数。如果转换失败，返回默认值。

    Args:
        value: 待转换的值，可以是 int、str、float、None 等类型
        default: 转换失败时返回的默认值，默认为 0

    Returns:
        转换后的整数值，如果转换失败则返回默认值

    Examples:
        >>> safe_int("123")
        123
        >>> safe_int("123.45")
        123
        >>> safe_int(123.45)
        123
        >>> safe_int("abc")
        0
        >>> safe_int("abc", default=-1)
        -1
        >>> safe_int(None)
        0
        >>> safe_int("")
        0
    """
    if value is None:
        return default

    # 如果是整数，直接返回
    if isinstance(value, int):
        return value

    # 如果是字符串，尝试转换
    if isinstance(value, str):
        # 去除首尾空格
        value = value.strip()
        if not value:
            return default

        # 尝试直接转换为整数
        try:
            return int(value)
        except ValueError:
            # 如果失败，尝试先转换为浮点数再转整数（处理 "123.45" 这种情况）
            try:
                return int(float(value))
            except (ValueError, OverflowError):
                return default

    # 如果是浮点数，转换为整数
    if isinstance(value, float):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return default

    # 如果是布尔值，转换为整数
    if isinstance(value, bool):
        return int(value)

    # 其他类型尝试直接转换
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return default
