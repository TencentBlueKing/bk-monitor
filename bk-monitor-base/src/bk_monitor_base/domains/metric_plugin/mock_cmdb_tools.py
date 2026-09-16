# TODO: 暂时放这里，后续考虑放到对应工具类中
from typing import Any

from bk_monitor_base.domains.cmdb_instance.operations import search_instances
from bk_monitor_base.domains.metric_plugin.constants import HostOSArch, HostOSType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType

OS_TYPE_MAPPING = {
    "1": HostOSType.LINUX.value,
    "linux": HostOSType.LINUX.value,
    "2": HostOSType.WINDOWS.value,
    "windows": HostOSType.WINDOWS.value,
    "3": HostOSType.AIX.value,
    "aix": HostOSType.AIX.value,
}

OS_ARCH_MAPPING = {
    "x86": HostOSArch.X86_64.value,
    "x86_64": HostOSArch.X86_64.value,
    "amd64": HostOSArch.X86_64.value,
    "x64": HostOSArch.X86_64.value,
    "arm": HostOSArch.AARCH64.value,
    "aarch64": HostOSArch.AARCH64.value,
    "arm64": HostOSArch.AARCH64.value,
}


def _normalize_os_type(value: Any) -> str | None:
    if value is None:
        return None
    return OS_TYPE_MAPPING.get(str(value).strip().lower())


def _normalize_os_arch(value: Any) -> str | None:
    if value is None:
        return None
    return OS_ARCH_MAPPING.get(str(value).strip().lower())


def _build_host_info(source: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(fallback or {})
    merged.update(source)

    host_info = dict(merged)
    host_info["bk_host_id"] = merged.get("bk_host_id") or merged.get("bk_inst_id")
    host_info["ip"] = merged.get("ip") or merged.get("bk_host_innerip") or merged.get("bk_host_outerip")
    host_info["os_type"] = _normalize_os_type(merged.get("os_type") or merged.get("bk_os_type"))
    host_info["os_arch"] = _normalize_os_arch(
        merged.get("os_arch") or merged.get("bk_os_arch") or merged.get("bk_cpu_architecture")
    )
    return host_info


def _search_host_instance(bk_host: dict[str, Any]) -> dict[str, Any] | None:
    bk_host_id = bk_host.get("bk_host_id")
    if bk_host_id is not None:
        total, instances = search_instances(bk_obj_id="host", bk_inst_ids=[int(bk_host_id)], size=1)
        if total and instances:
            return instances[0]

        total, instances = search_instances(bk_obj_id="host", query={"bk_host_id": bk_host_id}, size=1)
        if total and instances:
            return instances[0]

    ip = bk_host.get("ip")
    if not ip:
        return None

    query_base: dict[str, Any] = {}
    if bk_host.get("bk_cloud_id") is not None:
        query_base["bk_cloud_id"] = bk_host["bk_cloud_id"]

    for ip_field in ("ip", "bk_host_innerip", "bk_host_outerip"):
        total, instances = search_instances(
            bk_obj_id="host",
            query={**query_base, ip_field: ip},
            size=1,
        )
        if total and instances:
            return instances[0]

    return None


def get_host_info(bk_host: dict[str, Any]) -> dict[str, Any] | None:
    """获取主机信息

    Args:
        bk_host: 采集主机 例 {"bk_cloud_id":0,"ip":"127.0.0.1"} 或 {"bk_host_id": 1}
    Returns:
        主机信息：os_type、os_arch、bk_host_id 等
    Raises:
        FoundHostError: 未找到主机信息
    """
    target_host = _build_host_info(bk_host)
    if target_host.get("os_type") and target_host.get("os_arch"):
        return target_host

    host_instance = _search_host_instance(bk_host)
    if not host_instance:
        return None

    target_host = _build_host_info(bk_host, host_instance)
    if not target_host.get("os_type") or not target_host.get("os_arch"):
        return None
    return target_host


def get_os_type_by_collect_host(collect_host: dict[str, Any]) -> OSType | None:
    """通过采集主机信息获取操作系统类型

    Args:
        collect_host: 采集主机 例 {"bk_cloud_id":0,"ip":"127.0.0.1"} 或 {"bk_host_id": 1}
    Returns:
        操作系统类型
    Raises:
        ParseOsTypeError: 解析操作系统类型失败
    """
    bk_host_info = get_host_info(collect_host)
    if not bk_host_info:
        return None
    os_type = bk_host_info.get("os_type")
    os_arch = bk_host_info.get("os_arch")
    if not os_type or not os_arch:
        return None
    os_type = str(os_type).lower()
    os_arch = str(os_arch).lower()
    if os_type == HostOSType.LINUX.value:
        if os_arch == HostOSArch.X86_64.value:
            return OSType.LINUX
        elif os_arch == HostOSArch.AARCH64.value:
            return OSType.LINUX_AARCH64
    elif os_type == HostOSType.WINDOWS.value:
        return OSType.WINDOWS
    elif os_type == HostOSType.AIX.value:
        return OSType.AIX
    return None
