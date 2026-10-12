import datetime
from decimal import Decimal
from enum import Enum


class TimeUnit(str, Enum):
    SEC = "sec"
    MIN = "min"


def time_converter(duration: int | str) -> int:
    """
    时间转换器：支持传入int/str类型，都返回int
    :param duration: 时长
    :return:
    """
    duration = int(duration) if str(duration).isdigit() else duration
    if isinstance(duration, str):
        duration = duration.lower()
        total_seconds = Decimal("0")
        prev_num = []
        for character in duration:
            if character.isalpha():
                if prev_num:
                    num = Decimal("".join(prev_num))
                    if character == "d":
                        total_seconds += num * 60 * 60 * 24
                    elif character == "h":
                        total_seconds += num * 60 * 60
                    elif character == "m":
                        total_seconds += num * 60
                    elif character == "s":
                        total_seconds += num
                    prev_num = []
            elif character.isnumeric() or character == ".":
                prev_num.append(character)
        return int(total_seconds)
    else:
        return duration


def get_precise_timestamp():
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond:06d}"


def format_time_str(value: int, unit: TimeUnit):
    """拼凑为声明式时间字段,下发最终都是转换为秒级"""
    return f"{value * 60}s" if unit == TimeUnit.MIN else f"{value}s"
