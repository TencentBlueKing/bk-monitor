import hashlib
import logging
from typing import Any

logger = logging.getLogger("metadata")


def object_md5(info: Any) -> str:
    """
    传入一个字典或者数组， 计算得出其MD5哈希值
    :param info: 需要计算哈希值的内容
    :return: "asdfasdfasf"
    """

    if isinstance(info, dict):
        info_str = _trans_dict_to_str(info)

    elif isinstance(info, list):
        info_str = _trans_list_to_str(info)

    elif isinstance(info, bytes):
        info_str = info

    else:
        info_str = str(info)

    logger.debug(f"info->[{info}] is strinfy to->[{info_str}]")

    m = hashlib.md5()
    if isinstance(info_str, str):
        m.update(info_str.encode("utf8"))
    else:
        m.update(info_str)
    return m.hexdigest()


def _trans_list_to_str(l: list[Any]) -> str:
    """
    将一个列表序列化为字符串
    :param l: 需要序列化的列表
    :return: str
    """

    temp_list = []

    for list_obj in l:
        # 判断是否还是字典
        if isinstance(list_obj, dict):
            temp_list.append(_trans_dict_to_str(list_obj))

        elif isinstance(list_obj, list):
            temp_list.append(_trans_list_to_str(list_obj))

        # 字符串，整形等其他的方案可以直接添加
        else:
            temp_list.append(list_obj)

    return "".join([str(element) for element in temp_list])


def _trans_dict_to_str(d: dict[Any, Any]) -> str:
    """
    将一个字典序列化为字符串
    :param d: 需要序列化的字典
    :return: str
    """

    # 判断是否字典
    key_list = list(d.keys())
    key_list.sort()

    result_list = []
    for key in key_list:
        # 如果是字典，继续递归
        if isinstance(d[key], dict):
            result_list.append(f"{key}={_trans_dict_to_str(d[key])}")

        # 否则，遍历所有的内容，看看是否有字典
        elif isinstance(d[key], list):
            result_list.append(f"{key}={_trans_list_to_str(d[key])}")

        # 如果是整形或者字符串
        else:
            result_list.append(f"{key}={d[key]}")

    return "&".join(result_list)
