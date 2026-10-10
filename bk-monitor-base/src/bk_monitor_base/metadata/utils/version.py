import logging
import re
from distutils.version import StrictVersion

logger = logging.getLogger(__name__)


def get_validated_version(version: str) -> str:
    """
    获取版本中的前三个数字
    :param version: 版本
    :return: 前三个数字
    """
    version = re.sub(r"[^\d.]", "", version)
    return ".".join(version.split(".")[:3])


def compare_versions(v1: str, v2: str) -> int:
    """
    比较两个版本
    :param v1: 版本1
    :param v2: 版本2
    :return: 1 表示 v1 >= v2, -1 表示 v1 < v2, 0 表示无法比较
    """
    try:
        validated_v1 = get_validated_version(v1)
        validated_v2 = get_validated_version(v2)
        if not validated_v1 or not validated_v2:
            logger.exception(f"can not compare string version: v1({v1}) and v2({v2})")
            return 0
        version1 = StrictVersion(validated_v1)
        version2 = StrictVersion(validated_v2)
        if version1 >= version2:
            return 1
        else:
            return -1
    except Exception as e:
        logger.exception(e)
        return 0


def get_max_version(default_version: str, version_list: list[str]) -> str:
    """
    获取版本列表中的最大版本
    如果版本列表为空，则返回默认版本
    :param default_version: 默认版本
    :param version_list: 版本列表
    :return: 最大版本
    """
    max_version = default_version
    for version in version_list:
        if compare_versions(max_version, version) < 0:
            max_version = version
    return max_version
