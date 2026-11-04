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

from apps.log_databus.nodeman_v3.client import get_client

# 单业务 Proxy 数量远小于接口单页上限
PAGE_LIMIT = 1000


def _report_ip(info: dict) -> str:
    # advertise 地址面向下游；export/login 地址不能用作客户端上报地址。
    addresses = [
        info.get("advertise_ip"),
        info.get("advertise_ip_v6"),
        *(info.get("bk_host_innerip_list") or []),
        *(info.get("bk_host_innerip_v6_list") or []),
    ]
    ip = next((address.strip() for address in addresses if isinstance(address, str) and address.strip()), "")
    return f"[{ip}]" if ":" in ip else ip


def get_host_biz_proxies(bk_biz_id: int) -> list[dict]:
    """按接口文档查询指定业务的 Proxy，转换为上报地址入口的兼容字段。"""
    data = get_client(bk_biz_id).list_hosts(
        {
            "page": {"offset": 0, "limit": PAGE_LIMIT},
            "exact_include_conditions": {"bk_biz_id": [bk_biz_id], "node_role": ["proxy"]},
        }
    )
    proxies = []
    for host in data.get("items") or []:
        info = host.get("info") or {}
        area_id = info.get("bk_networkarea_id")
        ip = _report_ip(info)
        # 默认云区域由调用方按数据库配置补充
        if area_id and ip:
            proxies.append({"bk_cloud_id": area_id, "conn_ip": ip})
    return proxies
