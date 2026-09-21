import datetime
import re
import time

from django.utils import timezone


def get_systime_ms():
    """
    获取系统时间戳，毫秒

    Returns:
        int: 系统时间戳，毫秒
    """
    return int(time.time() * 1000)


TIME_ABBREVIATION_MATCH = re.compile(r"^[-+]?[0-9]*\.?[0-9]+[smhdwMy]")


def localtime(value: datetime.datetime) -> datetime.datetime:
    """将datetime对象转换为本地(业务)时区

    Args:
        value: datetime obj

    Returns:
        datetime.datetime: 带本地(业务)时区的datetime对象
    :return: 返回带本地(业务)时区的datetime对象
    """
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return timezone.make_aware(value)


def strftime_local(value: datetime.datetime, _format: str = "%Y-%m-%d %H:%M:%S%z") -> str:
    """转成业务时区字符串

    Args:
        value: datetime obj
        _format: 格式化字符串

    Returns:
        str: 业务时区字符串
    """
    return localtime(value).strftime(_format)
