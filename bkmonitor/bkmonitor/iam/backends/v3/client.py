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
# 继承 SDK IAM 基类，在 _do_policy_query 中保留 Action 语义别名：
# new_dashboard → manage_dashboard + manage_datasource
#
# 设计要点：
#   - 不依赖 Django settings / GlobalConfig
#   - 不依赖 bkmonitor.iam.action.get_action_by_id
#   - 使用注入的 NameCodec 做 action_id 编解码
#   - ACTION_COMPATIBLE_ALIASES 使用 Business ID
# ---------------------------------------------------------------------------

from __future__ import annotations

import copy
import logging
import json
import threading

from cachetools import TTLCache, cachedmethod

from iam import Action, IAM, MultiActionRequest, Request, Resource, Subject
from iam.exceptions import AuthAPIError

from iam_engine.provider.codec import NameCodec

logger = logging.getLogger(__name__)

# 动作语义兼容别名（Business ID）：
# 仅在单 Action 策略查询（_do_policy_query）层生效——把键动作的策略
# 用值列表中动作的策略 OR 合并后返回；直接鉴权（is_allowed / batch_by_resource /
# batch_by_action）走 IAM 平台，平台不做别名合并，会按原动作查。
#
# 典型场景 new_dashboard（新建仪表盘）：后端创建走 manage_dashboard / manage_datasource
# 空间级角色放行，但前端"能否新建仪表盘"UI 查询 new_dashboard 的策略 AST；
# 这里让 policy_query(new_dashboard) 回落到 manage_dashboard / manage_datasource
# 的 AST 或运算，使 UI 判定与后端行为一致。
#
# 注意：仅允许别名到同为空间级资源的动作；不要别名到实例级动作。
ACTION_COMPATIBLE_ALIASES: dict[str, list[str]] = {
    "new_dashboard": ["manage_dashboard", "manage_datasource"],
}


class V3Client(IAM):
    """IAM V3 SDK 客户端。

    覆盖 _do_policy_query，批量查询沿用 SDK 实现，
    保留 action 语义别名逻辑，策略查询使用 SDK 当前协议。
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
    ):
        """初始化 V3 客户端。

        Args:
            app_code: 蓝鲸应用 ID
            app_secret: 蓝鲸应用密钥
            bk_apigateway_url: IAM APIGW 基础地址
            system_id: V3 系统 ID（如 "bk_monitorv3"）
            codec: NameCodec 实例，用于 action_id 编解码
            bk_tenant_id: 租户 ID
        """
        super().__init__(app_code, app_secret, bk_apigateway_url, bk_tenant_id=bk_tenant_id)
        self._system_id = system_id
        self._codec = codec
        # SDK 默认缓存跨实例共享且忽略租户；在租户/凭据独立的客户端内持有缓存。
        self._allowed_cache = TTLCache(maxsize=1024, ttl=10)
        self._policy_cache = TTLCache(maxsize=1024, ttl=60)
        self._cache_lock = threading.RLock()

    def _request_cache_key(self, request):
        return json.dumps(request.to_dict(), sort_keys=True)

    @cachedmethod(lambda self: self._allowed_cache, key=_request_cache_key, lock=lambda self: self._cache_lock)
    def is_allowed_with_cache(self, request):
        return self.is_allowed(request)

    @cachedmethod(lambda self: self._policy_cache, key=_request_cache_key, lock=lambda self: self._cache_lock)
    def _do_policy_query_with_cache(self, request):
        return self._do_policy_query(request)

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

    def _do_policy_query(self, request, with_resources: bool = True):
        policies = super()._do_policy_query(request, with_resources)
        return self._merge_alias_policies(request, policies, with_resources)
