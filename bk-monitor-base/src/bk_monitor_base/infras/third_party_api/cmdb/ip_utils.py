import ipaddress
from functools import partial
from typing import Any


def is_ip(ip: str, _version: int | None = None) -> bool:
    """
    判断是否为合法 IP
    :param ip:
    :param _version: 是否为合法版本，缺省表示 both
    :return:
    """
    try:
        ip_address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if _version is None:
        return True
    return ip_address.version == _version


# 判断是否为合法 IPv6
is_v6 = partial(is_ip, _version=6)

# 判断是否为合法 IPv4
is_v4 = partial(is_ip, _version=4)


def exploded_ip(ip: str) -> str:
    """
    如果 ip 为合法的 IPv6，转为标准格式
    :param ip:
    :return:
    """
    if is_v6(ip):
        return ipaddress.ip_address(ip).exploded
    return ip


def compressed_ip(ip: str) -> str:
    """
    如果 ip 为合法的 IPv6，转为压缩格式
    :param ip:
    :return:
    """
    if is_v6(ip):
        return ipaddress.ip_address(ip).compressed
    return ip


def ipv6s_formatter(ips: list[str]) -> list[str]:
    """
    将 IPv6 列表转为标准格式
    :param ips:
    :return:
    """
    return [exploded_ip(ip) for ip in ips]


def ipv6_formatter(data: dict[str, Any], ipv6_field_names: list[str]):
    """
    将 data 中 ipv6_field_names 转为 IPv6 标准格式
    :param data: 可能包含 v6 的字典数据
    :param ipv6_field_names:IPv6 字段
    :return:
    """
    for ipv6_field_name in ipv6_field_names:
        ipv6_val: str | None = data.get(ipv6_field_name)
        if ipv6_val is None:
            data[ipv6_field_name] = None
            continue
        data[ipv6_field_name] = exploded_ip(ipv6_val)


def ipv4_to_v6(ipv4: str) -> str:
    """
    IPv4 转为 IPv6
    :param ipv4: IPv4
    :return: IPv6 标准形式
    """
    ipv4_address: ipaddress.IPv4Address = ipaddress.IPv4Address(ipv4)
    prefix6to4: int = int(ipaddress.IPv6Address("2002::"))
    ipv6_address: ipaddress.IPv6Address = ipaddress.IPv6Address(prefix6to4 | (int(ipv4_address) << 80))
    return ipv6_address.exploded


def join_host_port(host: str, port: int) -> str:
    """
    拼接 host:port
    """
    if is_v6(host):
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def split_inner_host(bk_host_innerip_str: str) -> str:
    if not bk_host_innerip_str:
        return ""
    bk_host_innerip = [member for member in bk_host_innerip_str.split(",") if member][0]
    if not bk_host_innerip:
        return ""
    return bk_host_innerip
