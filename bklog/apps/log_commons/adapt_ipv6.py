# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import ipaddress
from typing import Any, Dict, List

from apps.api import CCApi
from apps.log_commons.exceptions import CCMissingBkHostIDException, SearchHostException
from bkm_ipchooser.constants import CommonEnum
from django.conf import settings


def get_ip_field(ip: str) -> str:
    """
    获取ip确认是v4还是v6, 选择CC的字段
    """
    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        version = 4

    return {
        4: "bk_host_innerip",
        6: "bk_host_innerip_v6",
    }.get(version, "bk_host_innerip")


def fill_bk_host_id(
    ip_list: List[Dict[str, Any]], bk_biz_id: int = settings.BLUEKING_BK_BIZ_ID
) -> List[Dict[str, Any]]:
    """
    补充bk_host_id
    :param ip_list: 主机列表
    :param bk_biz_id: 业务ID, 默认为蓝鲸默认业务
    :return: ip_list
    """
    if not settings.ENABLE_DHCP:
        return ip_list
    # 拆分出需要填充 bk_host_id 的ip
    no_need_fill_ip_list = []
    need_fill_ip_list = []
    need_fill_ip_list_map = {}
    for i in ip_list:
        if i.get("bk_host_id"):
            no_need_fill_ip_list.append(i)
        else:
            need_fill_ip_list.append(i)
    # 如果都存在 bk_host_id 则不需要填充
    if not need_fill_ip_list:
        return ip_list
    params = {
        "bk_biz_id": bk_biz_id,
        "host_property_filter": {
            "condition": "OR",
            "rules": [],
        },
        "fields": CommonEnum.SIMPLE_HOST_FIELDS.value,
        "no_request": True,
        "page": {"limit": len(need_fill_ip_list), "start": 0},
    }
    # 做这个标记处理是兼容TransmitServer中的ip可能是ipv6的ip
    for i in range(len(need_fill_ip_list)):
        bk_cloud_id = need_fill_ip_list[i]["bk_cloud_id"]
        ip = need_fill_ip_list[i]["ip"]
        params["host_property_filter"]["rules"].append(
            {
                "condition": "AND",
                "rules": [
                    {
                        "field": "bk_cloud_id",
                        "operator": "equal",
                        "value": bk_cloud_id,
                    },
                    {
                        "field": get_ip_field(ip),
                        "operator": "equal",
                        "value": ip,
                    },
                ],
            }
        )
        need_fill_ip_list_map[f"{bk_cloud_id}_{ip}"] = i
    result = CCApi.list_biz_hosts(params)
    if not result or not result["info"]:
        raise SearchHostException()
    try:
        for i in result["info"]:
            bk_cloud_id = i["bk_cloud_id"]
            ip = i.get("bk_host_innerip", "")
            ipv6 = i.get("bk_host_innerip_v6", "")
            key = f"{bk_cloud_id}_{ip}" if f"{bk_cloud_id}_{ip}" in need_fill_ip_list_map else f"{bk_cloud_id}_{ipv6}"
            need_fill_ip_list[need_fill_ip_list_map[key]]["bk_host_id"] = i["bk_host_id"]
    except KeyError:
        raise CCMissingBkHostIDException()

    return no_need_fill_ip_list + need_fill_ip_list


def fill_ip_and_cloud_id(
    ip_list: List[Dict[str, Any]], bk_biz_id: int = settings.BLUEKING_BK_BIZ_ID
) -> List[Dict[str, Any]]:
    """
    如果只有bk_host_id, 在针对ENABLE_DHCP为False的情况下, 需要补充ip和bk_cloud_id
    :param ip_list: 主机列表
    :param bk_biz_id: 业务ID, 默认为蓝鲸默认业务
    :return: ip_list
    """
    if settings.ENABLE_DHCP:
        return ip_list
    # ENABLE_DHCP为False的情况下, 只有bk_host_id, 需要补充ip和bk_cloud_id
    need_fill_ip_list = []
    no_need_fill_ip_list = []
    for _ip in ip_list:
        if "ip" in _ip and "bk_cloud_id" in _ip:
            no_need_fill_ip_list.append(_ip)
        else:
            need_fill_ip_list.append(_ip)
    if not need_fill_ip_list:
        return ip_list
    params = {
        "bk_biz_id": bk_biz_id,
        "host_property_filter": {
            "condition": "OR",
            "rules": [],
        },
        "fields": CommonEnum.SIMPLE_HOST_FIELDS.value,
        "no_request": True,
        "page": {"limit": len(need_fill_ip_list), "start": 0},
    }
    for _ip in need_fill_ip_list:
        params["host_property_filter"]["rules"].append(
            {
                "field": "bk_host_id",
                "operator": "equal",
                "value": _ip["bk_host_id"],
            }
        )
    result = CCApi.list_biz_hosts(params)
    if not result or not result["info"]:
        raise SearchHostException()
    need_fill_ip_list = [
        {
            "bk_host_id": _ip["bk_host_id"],
            "ip": _ip.get("bk_host_innerip", ""),
            "bk_cloud_id": _ip["bk_cloud_id"],
        }
        for _ip in result["info"]
    ]
    return no_need_fill_ip_list + need_fill_ip_list
