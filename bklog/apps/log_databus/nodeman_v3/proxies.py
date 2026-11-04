"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
----------------------------------------------------------------------------------------------------
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

from collections.abc import Iterator

from django.utils.translation import gettext as _

from apps.log_databus.nodeman_v3.client import get_client
from apps.log_databus.nodeman_v3.exceptions import NodeManV3APIError

PAGE_LIMIT = 1000


def _list_hosts(client, conditions: dict) -> Iterator[dict]:
    offset = 0
    while True:
        data = client.list_hosts(
            {"page": {"offset": offset, "limit": PAGE_LIMIT}, "exact_include_conditions": conditions}
        )
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机列表缺少 items 数组")))
        try:
            total = int(data["total"])
        except (KeyError, TypeError, ValueError):
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机列表缺少有效 total"))) from None
        if total < 0:
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机列表 total 不能为负数")))

        items = data["items"]
        if any(not isinstance(item, dict) for item in items):
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机列表包含无效主机记录")))
        if not items and offset < total:
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机列表分页未返回完整结果")))
        yield from items
        offset += len(items)
        if offset >= total:
            return


def _networkarea_id(host: dict) -> int:
    try:
        networkarea_id = int(host["info"]["bk_networkarea_id"])
        if networkarea_id >= 0:
            return networkarea_id
    except (KeyError, TypeError, ValueError):
        pass
    raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("主机缺少有效管控区域 ID")))


def get_host_biz_proxies(bk_biz_id: int) -> list[dict]:
    """按接口文档查询指定业务的 Proxy，转换为上报地址入口的兼容字段。"""
    client = get_client(bk_biz_id)
    conditions = {"bk_biz_id": [bk_biz_id], "node_role": ["proxy"]}
    proxies = []
    seen_host_ids = set()
    for host in _list_hosts(client, conditions):
        if (host.get("state") or {}).get("node_role") != "proxy":
            continue
        area_id = _networkarea_id(host)
        if area_id == 0:
            continue
        try:
            host_id = int(host["bk_host_id"])
        except (KeyError, TypeError, ValueError):
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=_("Proxy 缺少有效主机 ID"))) from None
        if host_id in seen_host_ids:
            continue
        seen_host_ids.add(host_id)

        info = host["info"]
        # advertise 地址面向下游；export/login 地址不能用作客户端上报地址。
        addresses = [
            info.get("advertise_ip"),
            info.get("advertise_ip_v6"),
            *(info.get("bk_host_innerip_list") or []),
            *(info.get("bk_host_innerip_v6_list") or []),
        ]
        ip = next((address.strip() for address in addresses if isinstance(address, str) and address.strip()), "")
        if not ip:
            continue
        if ":" in ip and not ip.startswith("["):
            ip = f"[{ip}]"
        proxies.append({"bk_cloud_id": area_id, "conn_ip": ip})
    return proxies
