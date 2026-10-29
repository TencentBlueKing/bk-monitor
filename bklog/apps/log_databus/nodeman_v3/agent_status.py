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
from apps.log_databus.nodeman_v3.constants import HOST_NODE_STATUS_RUNNING

PAGE_LIMIT = 500


def get_agent_status(bk_biz_id: int, bk_host_ids: list[int]) -> dict[int, bool]:
    """
    查询主机 Agent 状态，返回 {bk_host_id: 是否在线}。

    V3 只返回节点管理注册过的主机，未返回的主机按不在线处理；只有 running 视为在线，
    starting/upgrade 等中间态不能当成在线。
    """
    if not bk_host_ids:
        return {}

    result = {bk_host_id: False for bk_host_id in bk_host_ids}
    client = get_client(bk_biz_id)
    for chunk_start in range(0, len(bk_host_ids), PAGE_LIMIT):
        chunk = bk_host_ids[chunk_start : chunk_start + PAGE_LIMIT]
        data = client.list_hosts(
            {
                # topo/host/list 的分页字段是 offset，不是 {count, start}
                "page": {"offset": 0, "limit": PAGE_LIMIT},
                "exact_include_conditions": {"bk_host_id": chunk, "bk_biz_id": [bk_biz_id]},
            }
        )
        for item in (data or {}).get("items") or []:
            try:
                bk_host_id = int(item.get("bk_host_id"))
            except (TypeError, ValueError):
                continue
            if bk_host_id not in result:
                continue
            node_status = (item.get("state") or {}).get("node_status") or ""
            result[bk_host_id] = node_status == HOST_NODE_STATUS_RUNNING

    return result
