import logging
from typing import Any

from bk_monitor_base.uptime_check import UptimeCheckTaskProtocol
from django.conf import settings

from core.drf_resource import resource

logger = logging.getLogger(__name__)


def get_uptime_check_task_url_list(task: dict[str, Any]) -> list[str]:
    """拼接拨测地址"""
    protocol: str = task["protocol"]
    config: dict[str, Any] = task["config"]
    bk_biz_id: int = task["bk_biz_id"]

    if protocol == UptimeCheckTaskProtocol.HTTP.value:
        # 针对HTTP协议
        if config.get("urls"):
            url_list = [config["urls"]]
        else:
            url_list = config.get("url_list", [])
        return url_list

    if not config.get("hosts", []):
        if config.get("node_list"):
            params = {
                "hosts": config["node_list"],
                "output_fields": config.get("output_fields", settings.UPTIMECHECK_OUTPUT_FIELDS),
                "bk_biz_id": bk_biz_id,
            }
            node_instance = resource.uptime_check.topo_template_host(**params)
        else:
            node_instance = []

        host_instance = config.get("url_list", []) + config.get("ip_list", [])
        if node_instance:
            target_host = node_instance + host_instance
        else:
            target_host = host_instance
    else:
        # 兼容旧版hosts逻辑
        # 针对其他协议
        if len(config["hosts"]) and config["hosts"][0].get("bk_obj_id"):
            # 如果是动态拓扑，拿到所有的IP
            params = {
                "hosts": config["hosts"],
                "output_fields": ["bk_host_innerip"],
                "bk_biz_id": bk_biz_id,
            }
            target_host = resource.uptime_check.topo_template_host(**params)
        else:
            target_host = [host["ip"] for host in config["hosts"] if host.get("ip")]

    # 拼接拨测地址
    if protocol == UptimeCheckTaskProtocol.ICMP.value:
        return target_host
    else:
        return ["[{}]:{}".format(host, config["port"]) for host in target_host]


def get_uptime_check_task_available(task_id: int) -> float | None:
    """获取拨测任务可用率

    Args:
        task_id: 任务ID

    Returns:
        float | None: 可用率
    """
    try:
        available_data: float | None = resource.uptime_check.get_recent_task_data(
            {"task_id": task_id, "type": "available"}
        )["available"]
    except Exception as e:
        logger.exception(f"get available failed: {str(e)}")
        available_data = None
    return available_data


def get_uptime_check_task_duration(task_id: int) -> float | None:
    """获取拨测任务响应时长

    Args:
        task_id: 任务ID

    Returns:
        float | None: 响应时长
    """
    try:
        duration_data: float | None = resource.uptime_check.get_recent_task_data(
            {"task_id": task_id, "type": "task_duration"}
        )["task_duration"]
    except Exception as e:
        logger.exception(f"get task duration failed: {str(e)}")
        duration_data = None
    return duration_data
