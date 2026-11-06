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


def get_backend_es7_init_settings() -> tuple[str | None, str | None, str, str]:
    """
    初始化写入的 ES7 集群信息：(host, rest_port, username, password)
    宿主项目（bkmonitor）在 settings 中解析好凭据（含 KMS），独立运行时回退到环境变量
    """
    from django.conf import settings

    if hasattr(settings, "BACKEND_ES7_HOST"):
        return (
            settings.BACKEND_ES7_HOST,
            settings.BACKEND_ES7_REST_PORT,
            settings.BACKEND_ES7_USER,
            settings.BACKEND_ES7_PASSWORD,
        )
    return (
        os.environ.get("BK_MONITOR_ES7_HOST"),
        os.environ.get("BK_MONITOR_ES7_REST_PORT"),
        os.environ.get("BK_MONITOR_ES7_USER", ""),
        os.environ.get("BK_MONITOR_ES7_PASSWORD", ""),
    )


def get_influxdb_init_settings() -> tuple[list[Any], str | None, str, str]:
    """
    初始化写入的 InfluxDB 主机信息：(ip_list, port, username, password)
    宿主项目（bkmonitor）在 settings 中解析好凭据（含 KMS），独立运行时回退到环境变量
    """
    from django.conf import settings

    if hasattr(settings, "INFLUXDB_INIT_IP_LIST"):
        return (
            settings.INFLUXDB_INIT_IP_LIST,
            settings.INFLUXDB_INIT_PORT,
            settings.INFLUXDB_INIT_USER,
            settings.INFLUXDB_INIT_PASSWORD,
        )
    return (
        get_env_list("BK_INFLUXDB_BKMONITORV3_IP") or get_env_list("INFLUXDB_BKMONITORV3_IP"),
        os.getenv("BK_MONITOR_INFLUXDB_PORT") or os.getenv("INFLUXDB_BKMONITORV3_PORT"),
        os.getenv("BK_MONITOR_INFLUXDB_USER") or os.getenv("INFLUXDB_BKMONITORV3_USER", ""),
        os.getenv("BK_MONITOR_INFLUXDB_PASSWORD") or os.getenv("INFLUXDB_BKMONITORV3_PASS", ""),
    )
