"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# V3Client — IAM V3 SDK 客户端（iam_v3 包内自包含）
#
# 继承 SDK IAM 基类，覆盖 _do_policy_query / _do_policy_query_by_actions：
#   1. V1→V2 迁移兼容（V1 双查 + biz→space 替换 + OR 合并）
#   2. Action 语义别名（new_dashboard → manage_dashboard + manage_datasource）
#
# 设计要点（旧 CompatibleIAM 兼容层已删除，本类是其替代）：
#   - 不依赖 Django settings / GlobalConfig
#   - 不依赖 bkmonitor.iam.action.get_action_by_id
#   - 使用注入的 NameCodec 做 action_id 编解码
#   - enable_v1_compat 由构造参数控制（代替 DB 配置读取）
#   - ACTION_COMPATIBLE_ALIASES 使用 Business ID
# ---------------------------------------------------------------------------

from __future__ import annotations

import copy
import logging

from iam import Action, IAM, MultiActionRequest, Request, Resource, Subject
from iam.exceptions import AuthAPIError

from ..iam_engine.provider.codec import NameCodec

logger = logging.getLogger(__name__)

# 动作语义兼容别名（Business ID）：
# 键动作在后端不单独鉴权，可由值中任一等价的"空间级"管理动作放行。
# 典型场景 new_dashboard（新建仪表盘）：后端创建仪表盘按仪表盘管理角色
# （manage_dashboard / manage_datasource）放行，但前端会单独查询 new_dashboard 权限。
# 这里让 new_dashboard 的鉴权结果 OR 合并等价管理动作的策略，使前端判定与后端一致。
# 注意：仅允许别名到同为空间级资源的动作；不要别名到实例级动作。
ACTION_COMPATIBLE_ALIASES: dict[str, list[str]] = {
    "new_dashboard": ["manage_dashboard", "manage_datasource"],
}


class V3Client(IAM):
    """IAM V3 SDK 客户端。

    覆盖 _do_policy_query / _do_policy_query_by_actions，
    注入 V1→V2 兼容逻辑和 action 语义别名逻辑。
    通过构造参数注入 system_id 和 codec，不依赖 Django settings。
    """

    def __init__(
        self,
        app_code: str,
        app_secret: str,
        bk_apigateway_url: str,
        system_id: str,
        codec: NameCodec,
        bk_tenant_id: str = "",
        enable_v1_compat: bool = True,
    ):
        """初始化 V3 客户端。

        Args:
            app_code: 蓝鲸应用 ID
            app_secret: 蓝鲸应用密钥
            bk_apigateway_url: IAM APIGW 基础地址
            system_id: V3 系统 ID（如 "bk_monitorv3"）
            codec: NameCodec 实例，用于 action_id 编解码
            bk_tenant_id: 租户 ID
            enable_v1_compat: 是否启用 V1→V2 兼容模式（默认 True，后续可关闭）
        """
        super().__init__(app_code, app_secret, bk_apigateway_url, bk_tenant_id=bk_tenant_id)
        self._system_id = system_id
        self._codec = codec
        self._enable_v1_compat = enable_v1_compat

    # ================================================================
    # SDK 对象构造（封装 IAM SDK 原生类型，Provider 不直接 import SDK）
    # ================================================================

    def make_action(self, dialect_action_id: str) -> Action:
        """创建 SDK Action 对象。"""
        return Action(id=dialect_action_id)

    def make_subject(self, username: str) -> Subject:
        """创建 SDK Subject（user 类型）。"""
        return Subject("user", username)

    def make_resource(
        self,
        resource_type: str,
        resource_id: str,
        ancestors: tuple[Resource, ...] = (),
        attribute: dict | None = None,
    ) -> Resource:
        """创建 SDK Resource，遵循 V3 _bk_iam_path_ 约定。

        Args:
            resource_type: 资源类型（方言 ID）
            resource_id: 资源实例 ID（方言 ID）
            ancestors: 祖先资源链，用于构建 _bk_iam_path_
            attribute: 额外属性
        """
        attr = dict(attribute or {})
        if ancestors:
            path_parts = [f"/{a.type},{a.id}/" for a in ancestors]
            attr["_bk_iam_path_"] = "".join(path_parts)
        return Resource(
            system=self._system_id,
            type=resource_type,
            id=resource_id,
            attribute=attr,
        )

    def make_request(
        self,
        username: str,
        action_id: str,
        resources: list[Resource] = None,
    ) -> Request:
        """创建 SDK Request。"""
        return Request(
            system=self._system_id,
            subject=self.make_subject(username),
            action=self.make_action(action_id),
            resources=resources or [],
            environment=None,
        )

    def make_multi_action_request(
        self,
        username: str,
        action_ids: list[str],
    ) -> MultiActionRequest:
        """创建 SDK MultiActionRequest。"""
        return MultiActionRequest(
            system=self._system_id,
            subject=self.make_subject(username),
            actions=[self.make_action(aid) for aid in action_ids],
            resources=[],
            environment=None,
        )

    def query_system(self) -> tuple[bool, str, dict | None]:
        """查询 V3 系统注册信息。"""
        ok, message, data = self._client.query(self._system_id)
        return ok, message, data

    def health_check(self) -> dict:
        """V3 IAM 平台连通性检查。"""
        try:
            ok, message, _data = self.query_system()
            return {"status": "ok" if ok else "error", "message": message}
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}

    # ================================================================
    # V1→V2 兼容模式
    # ================================================================

    def _has_v1_actions(self) -> bool:
        """检查 IAM 平台是否仍注册了 V1 操作 ID。"""
        ok, message, data = self._client.query(self._system_id)
        if not ok:
            return False
        return "view_business" in [action["id"] for action in data["actions"]]

    def _patch_policy_expression(self, expression: dict | None) -> None:
        """将 V1 业务资源表达式（biz）转换为 V2 空间资源（space）。"""
        if not expression:
            return
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self._patch_policy_expression(sub_expr)
        else:
            if expression["field"] == "biz.id":
                expression["field"] = "space.id"
            if "biz" in expression["value"]:
                expression["value"] = expression["value"].replace("biz", "space")

    # ================================================================
    # Action 语义别名
    # ================================================================

    def _merge_alias_policies(self, request, policies, with_resources: bool = True) -> dict | None:
        """用等价管理动作的策略补充当前动作的鉴权策略（OR 合并）。

        通过注入的 codec 解析 action_id，不再依赖 get_action_by_id。
        """
        # request.action.id 是 V3 平台 ID → 解码为 Business ID
        biz_action_id = self._codec.decode_action(request.action.id)

        for biz_alias_id in ACTION_COMPATIBLE_ALIASES.get(biz_action_id, []):
            # Business ID → V3 平台 ID
            v3_alias_id = self._codec.encode_action(biz_alias_id)

            alias_request = copy.copy(request)
            alias_request.action = Action(id=v3_alias_id)
            try:
                alias_policies = self._do_policy_query(alias_request, with_resources)
            except AuthAPIError:
                logger.exception("[V3Client] 查询别名动作策略失败, action_id=%s", v3_alias_id)
                continue
            if not alias_policies:
                continue
            policies = alias_policies if not policies else {"op": "OR", "content": [policies, alias_policies]}
        return policies

    # ================================================================
    # _do_policy_query — 覆盖基类，注入 V1 兼容 + alias 逻辑
    # ================================================================

    def _do_policy_query(self, request, with_resources: bool = True):
        # 未开启兼容模式 → 标准查询 + alias
        if not self._enable_v1_compat:
            policies = super()._do_policy_query(request, with_resources)
            return self._merge_alias_policies(request, policies, with_resources)

        data = request.to_dict()
        logger.debug(f"the request: {data}")

        # NOTE: 不向服务端传任何 resource，用于统一类资源的批量鉴权
        # 将会返回所有策略，然后遍历资源列表和策略列表逐一计算
        if not with_resources:
            data["resources"] = []

        ok, message, policies = self._client.policy_query(data)

        # ---- V1 兼容双查 ----
        if data["action"]["id"].endswith("_v2"):
            v1_data = copy.deepcopy(data)

            # 替换 action_id（去掉 _v2 后缀）
            v1_data["action"]["id"] = v1_data["action"]["id"].replace("_v2", "")

            # 替换资源名称：space → biz（CMDB）
            for resource in v1_data["resources"]:
                if resource["type"] == "space":
                    resource["system"] = "bk_cmdb"
                    resource["type"] = "biz"
                iam_path = resource.get("attribute", {}).get("_bk_iam_path_", "")
                if "space" in iam_path:
                    resource["attribute"]["_bk_iam_path_"] = iam_path.replace("space", "biz")

            v1_ok, v1_message, v1_policies = self._client.policy_query(v1_data)
            self._patch_policy_expression(v1_policies)

            if v1_policies:
                if not policies:
                    policies = v1_policies
                else:
                    policies = {"op": "OR", "content": [policies, v1_policies]}

        # ---- Action 语义别名（OR 合并） ----
        policies = self._merge_alias_policies(request, policies, with_resources)

        if not policies and not ok:
            raise AuthAPIError(message)
        return policies

    # ================================================================
    # _do_policy_query_by_actions — 覆盖基类，注入 V1 兼容（批量）
    # ================================================================

    def _do_policy_query_by_actions(self, request, with_resources: bool = True):
        if not self._enable_v1_compat:
            return super()._do_policy_query_by_actions(request, with_resources)

        data = request.to_dict()
        logger.debug(f"the request: {data}")

        if not with_resources:
            data["resources"] = []

        ok, message, action_policies = self._client.policy_query_by_actions(data)

        # ---- V1 兼容双查（批量） ----
        v2_actions = [action["id"] for action in data["actions"] if action["id"].endswith("_v2")]

        if v2_actions:
            v1_data = copy.deepcopy(data)

            # 替换 action_id（去掉 _v2 后缀）
            v1_data["actions"] = [{"id": action_id.replace("_v2", "")} for action_id in v2_actions]

            v1_ok, v1_message, v1_action_policies = self._client.policy_query_by_actions(v1_data)
            for v1_policy in v1_action_policies or []:
                v1_policy["action"]["id"] += "_v2"
                self._patch_policy_expression(v1_policy["condition"])

                for policy in action_policies:
                    if v1_policy["action"]["id"] != policy["action"]["id"]:
                        continue
                    if not v1_policy["condition"]:
                        continue
                    if not policy["condition"]:
                        policy["condition"] = v1_policy["condition"]
                    else:
                        policy["condition"] = {
                            "op": "OR",
                            "content": [policy["condition"], v1_policy["condition"]],
                        }

        if not ok:
            raise AuthAPIError(message)
        return action_policies
