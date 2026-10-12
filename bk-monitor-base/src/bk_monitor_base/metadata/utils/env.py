import logging
import os
from typing import Any

logger = logging.getLogger("metadata")


def get_env_list(env_prefix: str) -> list[Any]:
    """
    获取可以遍历的环境变量信息，并通过一个数组的方式返回
    例如，获取IP0 ~ IPn环境变量, 调用get_env_list(env_prefix="IP"), 返回["1.1.1.1", "2.2.2.2"]
    :param env_prefix: 环境变量前缀
    :return: ["info", "info"]
    """
    index = 0
    result: list[Any] = []
    while True:
        current_name = f"{env_prefix}{index}"
        current_value: Any = os.getenv(current_name)

        # 此轮已经不能再获取新的变量了，可以返回
        # 此处，我们相信变量不存在跳跃的情况
        if current_value is None:
            break

        result.append(current_value)
        index += 1

    logger.info(f"env->[{env_prefix}] got total env count->[{index}]")
    return result
