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
# V4Client — IAM v4 APIGW HTTP 客户端
#
# 所有配置通过构造参数注入（解耦 Django settings）。
# 错误处理：HTTP 异常 → ProviderUnavailable；IAM 业务错误 → ProviderError。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any


from iam_engine.exceptions import ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)


class V4Client:
    """IAM v4 APIGW 客户端。"""

    def __init__(self, base_url, system_id, app_code, app_secret, timeout=10, bk_tenant_id="system", api_paths=None):
        from iam_engine.v4.client import V4Client as SharedClient
        from iam_engine.v4.config import V4Options, load_v4_paths, normalize_timeout_seconds
        from types import SimpleNamespace

        paths = load_v4_paths(SimpleNamespace())
        paths.update(api_paths or {})
        options = V4Options(
            app_code=app_code,
            app_secret=app_secret,
            gateway_url=base_url,
            system_id=system_id,
            timeout_seconds=normalize_timeout_seconds(timeout),
            batch_chunk_size=100,
            batch_max_workers=4,
            **paths,
        )
        self._system_id = system_id
        self._transport = SharedClient(options, bk_tenant_id=bk_tenant_id)

    def _path(self, key):
        return getattr(self._transport.options, key).format(system_id=self._system_id)

    def _model_path(self, suffix=""):
        return self._path("model_base_path").rstrip("/") + f"/{self._system_id}/" + suffix

    # ============================================================
    # 鉴权
    # ============================================================

    def direct_auth(self, subject_id: str, action_id: str, resource: dict | None = None) -> bool:
        """POST /auth/ — 单资源鉴权。"""
        path = self._path("auth_path")
        body: dict[str, Any] = {"subject": {"type": "user", "id": subject_id}, "action_id": action_id}
        if resource:
            body["resource"] = resource
        resp = self._post(path, body)
        return self._transport._extract_allowed(resp["data"])

    def direct_auth_by_resources(self, subject_id: str, action_id: str, resources: list[dict]) -> dict[str, bool]:
        """POST /auth-by-resources/ — 同 action 多 resource 批量鉴权（≤20）。"""
        path = self._path("auth_by_resources_path")
        body = {
            "subject": {"type": "user", "id": subject_id},
            "action_id": action_id,
            "resources": resources,
        }
        resp = self._post(path, body)
        return self._transport._extract_resource_results(
            resp["data"], expected_resource_ids=[r["id"] for r in resources]
        )

    def direct_auth_by_actions(
        self, subject_id: str, action_ids: list[str], resource: dict | None = None
    ) -> dict[str, bool]:
        """POST /auth-by-actions/ — 同 resource 多 action 批量鉴权（≤20）。"""
        path = f"/api/v1/open/rbac/authorization/systems/{self._system_id}/auth-by-actions/"
        body: dict[str, Any] = {"subject": {"type": "user", "id": subject_id}, "action_ids": action_ids}
        if resource:
            body["resource"] = resource
        resp = self._post(path, body)
        return self._transport._extract_resource_results(
            [{"resource_id": item["action_id"], "allowed": item["allowed"]} for item in resp["data"]],
            expected_resource_ids=action_ids,
        )

    def add_authorization(self, authorizations: list[dict], operator: str) -> None:
        """POST /mgmt/systems/{sys}/authorizations/ — 单批角色授权（调用方负责分片）。

        典型场景：用户创建资源后自动授予该资源相关的角色权限。

        Args:
            authorizations: [{
                "subject": {"type": "user", "id": "user1"},
                "role_id": "space_admin",
                "related_resource_type_id": "space",   # 空串表示无关资源类型
                "resources": [{"type": "space", "id": "1"}],  # id="*" 表示无限制授权
                "expired_at": <unix ts, 最大 365 天后>,
            }, ...]
            operator: 操作人用户名（写入 X-Bkiam-Operator 请求头）

        Raises:
            ProviderUnavailable: HTTP 层异常
            ProviderError: IAM 业务错误
        """
        if not authorizations:
            return
        self._call(lambda: self._transport.add_authorization(items=authorizations, operator=operator))

    def get_authorized_resources(self, subject_id: str, action_id: str) -> list[dict]:
        """POST /relation/authorized-resources/ — 查询用户对某 action 有权限的资源列表。

        平台仅建议用于顶层资源类型（第一层）的反向列举；实测对子资源类型
        action 同样可调用（平台不拒绝），返回结果按授权形态可能包含多种
        条目（同一 action 可同时出现多个 type 条目）：
          - 顶层资源 action（如 space）：返回 {"type": "space", "ids": [...]}，
            ids 含 "*"（任意资源）或具体空间 ID；
          - 子资源 action（如 grafana_dashboard）：可能同时返回
            {"type": "<子资源类型>", "ids": [实例 ID 或 "*"]}（显式实例 / 通配授权）
            与 {"type": "space", "ids": [父空间 ID]}（父级授权，表示该空间下
            所有子资源均有权限）；
          - 资源无关 action（无 resource_type）：返回空列表。

        Args:
            subject_id: 用户名
            action_id: 操作 ID（方言 ID）

        Returns:
            list[{"type": <方言 rt_id>, "ids": [<方言 rid> 或 "*"]}]
            "*" 表示该资源类型下任意资源都有权限；父资源 ids 表示该父资源下所有子资源都有权限。
        """
        path = self._path("authorized_resources_path")
        body = {
            "subject": {"type": "user", "id": subject_id},
            "action_id": action_id,
        }
        resp = self._post(path, body)
        data = resp.get("data")
        if not isinstance(data, list):
            raise ProviderError("Invalid IAM V4 authorized-resources response")
        result, seen = [], set()
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("type"), str) or item["type"] in seen:
                raise ProviderError("Invalid or duplicate IAM V4 authorized resource type")
            seen.add(item["type"])
            normalized = self._call(
                lambda: self._transport._extract_authorized_resource_scope([item], resource_type=item["type"])
            )
            result.append(normalized)
        return result

    # ============================================================
    # 模型管理 — System
    # ============================================================

    def create_system(self, data: dict) -> dict:
        return self._post(self._path("model_base_path"), data)

    def retrieve_system(self) -> dict:
        return self._get(self._model_path())

    def update_system(self, data: dict) -> dict:
        return self._put(self._model_path(), data)

    # ============================================================
    # 模型管理 — Action
    # ============================================================

    def list_actions(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            self._model_path("actions/"),
            params={"page": page, "page_size": page_size},
        )

    def batch_create_actions(self, actions: list[dict]) -> dict:
        return self._post(self._model_path("actions/"), actions)

    def update_action(self, action_id: str, data: dict) -> dict:
        return self._put(self._model_path(f"actions/{action_id}/"), data)

    def delete_action(self, action_id: str) -> dict:
        return self._delete(self._model_path(f"actions/{action_id}/"))

    # ============================================================
    # 模型管理 — ResourceType
    # ============================================================

    def list_resource_types(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            self._model_path("resource-types/"),
            params={"page": page, "page_size": page_size},
        )

    def batch_create_resource_types(self, rts: list[dict]) -> dict:
        return self._post(self._model_path("resource-types/"), rts)

    def update_resource_type(self, rt_id: str, data: dict) -> dict:
        return self._put(self._model_path(f"resource-types/{rt_id}/"), data)

    def delete_resource_type(self, rt_id: str) -> dict:
        return self._delete(self._model_path(f"resource-types/{rt_id}/"))

    # ============================================================
    # 模型管理 — Role
    # ============================================================

    def list_roles(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            self._model_path("roles/"),
            params={"page": page, "page_size": page_size},
        )

    def batch_create_roles(self, roles: list[dict]) -> dict:
        return self._post(self._model_path("roles/"), roles)

    def update_role(self, role_id: str, data: dict) -> dict:
        return self._put(self._model_path(f"roles/{role_id}/"), data)

    def delete_role(self, role_id: str) -> dict:
        return self._delete(self._model_path(f"roles/{role_id}/"))

    def batch_create_role_actions(self, role_id: str, actions: list[dict]) -> dict:
        return self._post(self._model_path(f"roles/{role_id}/actions/"), actions)

    def batch_delete_role_actions(self, role_id: str, actions: list[dict]) -> dict:
        # v4 平台约定：ids 通过 query string 传递，用 "," 连接：?ids=action1,action2
        ids = [a["id"] for a in actions if a.get("id")]
        if not ids:
            return {}
        return self._delete(
            self._model_path(f"roles/{role_id}/actions/"),
            params={"ids": ",".join(ids)},
        )

    # ============================================================
    # 权限申请 URL
    # ============================================================

    def generate_perm_apply_url(self, permissions: list[dict]) -> str:
        path = self._path("apply_url_path")
        body = {"system_id": self._system_id, "permissions": permissions}
        try:
            resp = self._post(path, body)
            return (resp.get("data") or {}).get("url", "")
        except ProviderError:
            logger.warning("[iam_v4:apply_url_fail] request failed")
            return ""

    # ============================================================
    # Auth Token（回调鉴权用）
    # ============================================================

    def get_auth_token(self) -> str:
        return self._call(self._transport.retrieve_system_auth_token)

    # ============================================================
    # HTTP 底层
    # ============================================================

    @staticmethod
    def _call(call):
        from iam_engine.v4.exceptions import V4ClientError, V4RateLimitError, V4TimeoutError, V4TransportError

        try:
            return call()
        except (V4TimeoutError, V4TransportError, V4RateLimitError) as error:
            raise ProviderUnavailable("IAM V4 transport unavailable", code=error.status_code) from error
        except V4ClientError as error:
            if error.status_code and error.status_code >= 500:
                raise ProviderUnavailable("IAM V4 upstream unavailable", code=error.status_code) from error
            raise ProviderError("IAM V4 request or response invalid", code=error.status_code) from error

    def _post(self, path, body, extra_headers=None):
        return {
            "data": self._call(lambda: self._transport._request("POST", path, body=body, extra_headers=extra_headers))
        }

    def _get(self, path, params=None):
        return {"data": self._call(lambda: self._transport._request("GET", path, params=params))}

    def _put(self, path, body):
        return {"data": self._call(lambda: self._transport._request("PUT", path, body=body))}

    def _delete(self, path, body=None, params=None):
        return {"data": self._call(lambda: self._transport._request("DELETE", path, body=body, params=params))}
