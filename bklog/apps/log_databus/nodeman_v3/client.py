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

from dataclasses import dataclass, field
from typing import Any

from apps.api.modules.bk_node_v3 import BKNodeV3Api
from apps.log_databus.nodeman_v3.audit import record_outbound_audit
from apps.log_databus.nodeman_v3.exceptions import (
    NodeManV3APIError,
    NodeManV3TransportError,
    NodeManV3UnknownResultError,
)
from apps.utils.log import logger

API_VERSION = "v3"


@dataclass
class NodeManV3RequestContext:
    """
    一次 V3 调用的上下文。

    写请求必须带 operation_id：控制面用它把「本地 operation 记录」与「NodeMan 侧的实际动作」串起来，
    否则写结果未知时无法判断该动作到底有没有生效。
    """

    bk_biz_id: int
    bk_tenant_id: str = ""
    operation_id: str = ""

    def resolve_tenant_id(self) -> str:
        if self.bk_tenant_id:
            return self.bk_tenant_id
        from apps.log_search.models import Space

        return Space.get_tenant_id(bk_biz_id=self.bk_biz_id)


@dataclass
class NodeManV3Client:
    """
    节点管理 V3 客户端。

    与 V2 的差异不只是路径：V3 返回体是 {code, message, request_id, error, data}，没有蓝鲸标准的
    result 字段，而 DataAPI 对缺少 result 的返回会直接当成成功（apps/api/base.py:413-415）。
    因此这里统一用 raw=True 取回整个信封自己判定 code，不能依赖 DataAPI 的成功判定。
    """

    context: NodeManV3RequestContext
    _tenant_id: str = field(default="", init=False)

    @property
    def tenant_id(self) -> str:
        if not self._tenant_id:
            self._tenant_id = self.context.resolve_tenant_id()
        return self._tenant_id

    def _call(self, api, action: str, payload: dict[str, Any], *, write: bool) -> Any:
        if write and not self.context.operation_id:
            raise ValueError(f"operation_id is required for NodeMan V3 write request: {action}")

        try:
            envelope = api(payload, raw=True, bk_tenant_id=self.tenant_id)
        except Exception as err:  # pylint: disable=broad-except
            record_outbound_audit(
                api_version=API_VERSION,
                action=action,
                method="POST",
                outcome="transport_error",
                bk_tenant_id=self.tenant_id,
                bk_biz_id=self.context.bk_biz_id,
                operation_id=self.context.operation_id,
                error=str(err),
            )
            logger.exception(f"[nodeman_v3] request failed, action={action}, err={err}")
            if write:
                # 传输层失败无法区分「没到服务端」与「已生效但响应丢了」，按结果未知上报，
                # 不在当次请求里重试，交给下一次显式收敛（收敛路径的写操作都是可重放的）
                raise NodeManV3UnknownResultError(NodeManV3UnknownResultError.MESSAGE.format(err=f"{action}: {err}"))
            raise NodeManV3TransportError(NodeManV3TransportError.MESSAGE.format(err=f"{action}: {err}"))

        code = (envelope or {}).get("code", 0)
        if code not in (0, None):
            message = (envelope or {}).get("message", "")
            record_outbound_audit(
                api_version=API_VERSION,
                action=action,
                method="POST",
                outcome="api_error",
                bk_tenant_id=self.tenant_id,
                bk_biz_id=self.context.bk_biz_id,
                operation_id=self.context.operation_id,
                error=f"code={code}, message={message}",
            )
            err = f"{action}: code={code}, message={message}"
            if write:
                raise NodeManV3UnknownResultError(NodeManV3UnknownResultError.MESSAGE.format(err=err))
            raise NodeManV3APIError(NodeManV3APIError.MESSAGE.format(err=err))

        record_outbound_audit(
            api_version=API_VERSION,
            action=action,
            method="POST",
            outcome="success",
            bk_tenant_id=self.tenant_id,
            bk_biz_id=self.context.bk_biz_id,
            operation_id=self.context.operation_id,
        )
        return (envelope or {}).get("data")

    # ------------------------------------------------------------------
    # 部署策略
    # ------------------------------------------------------------------
    def create_deploy_policy(self, payload: dict[str, Any]) -> dict:
        return self._call(BKNodeV3Api.create_deploy_policy, "deploy_policy/create", payload, write=True) or {}

    def update_deploy_policy(self, payload: dict[str, Any]) -> dict:
        return self._call(BKNodeV3Api.update_deploy_policy, "deploy_policy/update", payload, write=True) or {}

    def execute_deploy_policy(self, deploy_policy_id: int) -> dict:
        payload = {"deploy_policy_id": deploy_policy_id}
        return self._call(BKNodeV3Api.execute_deploy_policy, "deploy_policy/execute", payload, write=True) or {}

    def list_deploy_policies(self, payload: dict[str, Any]) -> dict:
        return self._call(BKNodeV3Api.list_deploy_policies, "deploy_policy/list", payload, write=False) or {}

    # ------------------------------------------------------------------
    # 子配置
    # ------------------------------------------------------------------
    def remove_subconfig(self, plugins: list[dict[str, Any]]) -> dict:
        payload = {"plugin": plugins}
        return self._call(BKNodeV3Api.remove_subconfig, "plugin/remove_subconfig", payload, write=True) or {}

    def list_config_files(self, bk_host_id: int, plugin_name: str) -> dict:
        payload = {"bk_host_id": bk_host_id, "plugin_name": plugin_name}
        return self._call(BKNodeV3Api.list_config_files, "plugin/list_config_files", payload, write=False) or {}

    def list_release_plugin_brief(self, payload: dict[str, Any]) -> dict:
        return (
            self._call(
                BKNodeV3Api.list_release_plugin_brief,
                "package/release/plugin/list/brief",
                payload,
                write=False,
            )
            or {}
        )

    # ------------------------------------------------------------------
    # 进程与 workflow
    # ------------------------------------------------------------------
    def list_processes(self, payload: dict[str, Any]) -> dict:
        return self._call(BKNodeV3Api.list_processes, "process/list", payload, write=False) or {}

    def list_workflows(self, payload: dict[str, Any]) -> dict:
        return self._call(BKNodeV3Api.list_workflows, "plugin/workflow/list", payload, write=False) or {}

    def list_workflow_operations(self, payload: dict[str, Any]) -> dict:
        return (
            self._call(BKNodeV3Api.list_workflow_operations, "plugin/workflow/operation/list", payload, write=False)
            or {}
        )

    def list_operation_instance_status_distribution(self, trigger_ids: list[str]) -> dict:
        payload = {"trigger_id": trigger_ids}
        return (
            self._call(
                BKNodeV3Api.list_workflow_operation_instance_status_distribution,
                "plugin/workflow/operation/instance/status_distribution/list",
                payload,
                write=False,
            )
            or {}
        )

    def retry_workflow_operation(self, payload: dict[str, Any]) -> dict:
        return (
            self._call(BKNodeV3Api.retry_workflow_operation, "plugin/workflow/operation/retry", payload, write=True)
            or {}
        )

    def terminate_workflow_operation(self, payload: dict[str, Any]) -> dict:
        return (
            self._call(
                BKNodeV3Api.terminate_workflow_operation,
                "plugin/workflow/operation/terminate",
                payload,
                write=True,
            )
            or {}
        )


def get_client(bk_biz_id: int, operation_id: str = "", bk_tenant_id: str = "") -> NodeManV3Client:
    return NodeManV3Client(
        context=NodeManV3RequestContext(bk_biz_id=bk_biz_id, bk_tenant_id=bk_tenant_id, operation_id=operation_id)
    )
