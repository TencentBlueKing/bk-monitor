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

from apps.utils.log import logger

# 出站审计日志前缀。BKL-5 的「物理机采集路径无 V2 NodeMan 出站」门禁靠这条日志做运行期取证，
# 因此前缀不要随意改名。
NODEMAN_OUTBOUND_AUDIT_PREFIX = "[nodeman_outbound_audit]"


def record_outbound_audit(
    *,
    api_version: str,
    action: str,
    method: str,
    outcome: str,
    bk_tenant_id: str = "",
    bk_biz_id: int | None = None,
    operation_id: str = "",
    error: str = "",
) -> None:
    """
    记录一次节点管理出站调用。

    只记录元数据，不记录请求体与响应体：子配置内容里可能带业务日志路径与 Redis 口令等敏感信息。
    """
    payload = {
        "api_version": api_version,
        "action": action,
        "method": method,
        "outcome": outcome,
        "bk_tenant_id": bk_tenant_id,
        "bk_biz_id": bk_biz_id,
        "operation_id": operation_id,
    }
    if error:
        payload["error"] = error
    logger.info(f"{NODEMAN_OUTBOUND_AUDIT_PREFIX} {payload}")
