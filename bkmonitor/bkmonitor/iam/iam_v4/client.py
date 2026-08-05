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

import json
import logging
from typing import Any

import requests

from ..iam_engine.core.exceptions import ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)


class V4Client:
    """IAM v4 APIGW 客户端。"""

    def __init__(self, base_url: str, system_id: str, app_code: str, app_secret: str, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._system_id = system_id
        self._timeout = timeout
        self._auth_header = {
            "X-Bkapi-Authorization": json.dumps({"bk_app_code": app_code, "bk_app_secret": app_secret})
        }

    # ============================================================
    # 鉴权
    # ============================================================

    def direct_auth(self, subject_id: str, action_id: str, resource: dict | None = None) -> bool:
        """POST /auth/ — 单资源鉴权。"""
        path = f"/api/v1/open/rbac/authorization/systems/{self._system_id}/auth/"
        body: dict[str, Any] = {"subject": {"type": "user", "id": subject_id}, "action_id": action_id}
        if resource:
            body["resource"] = resource
        resp = self._post(path, body)
        return resp["data"]["allowed"]

    def direct_auth_by_resources(self, subject_id: str, action_id: str, resources: list[dict]) -> dict[str, bool]:
        """POST /auth-by-resources/ — 同 action 多 resource 批量鉴权（≤20）。"""
        path = f"/api/v1/open/rbac/authorization/systems/{self._system_id}/auth-by-resources/"
        body = {
            "subject": {"type": "user", "id": subject_id},
            "action_id": action_id,
            "resources": resources,
        }
        resp = self._post(path, body)
        return {item["resource_id"]: item["allowed"] for item in resp["data"]}

    def direct_auth_by_actions(
        self, subject_id: str, action_ids: list[str], resource: dict | None = None
    ) -> dict[str, bool]:
        """POST /auth-by-actions/ — 同 resource 多 action 批量鉴权（≤20）。"""
        path = f"/api/v1/open/rbac/authorization/systems/{self._system_id}/auth-by-actions/"
        body: dict[str, Any] = {"subject": {"type": "user", "id": subject_id}, "action_ids": action_ids}
        if resource:
            body["resource"] = resource
        resp = self._post(path, body)
        return {item["action_id"]: item["allowed"] for item in resp["data"]}

    def add_authorization(self, authorizations: list[dict], operator: str) -> None:
        """POST /mgmt/systems/{sys}/authorizations/ — 批量角色授权（每批最多 20 条）。

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
        path = f"/api/v1/open/rbac/mgmt/systems/{self._system_id}/authorizations/"
        headers = {"X-Bkiam-Operator": operator}
        # 平台单批上限 20，超出自动分片；保持简单——串行，避免与业务侧线程池策略冲突
        batch_size = 20
        for i in range(0, len(authorizations), batch_size):
            chunk = authorizations[i : i + batch_size]
            self._post(path, chunk, extra_headers=headers)

    def get_authorized_resources(self, subject_id: str, action_id: str) -> list[dict]:
        """POST /relation/authorized-resources/ — 查询用户对某 action 有权限的资源列表。

        仅建议用于顶层资源类型（第一层），否则平台会拒绝请求。

        Args:
            subject_id: 用户名
            action_id: 操作 ID（方言 ID）

        Returns:
            list[{"type": <方言 rt_id>, "ids": [<方言 rid> 或 "*"]}]
            "*" 表示该资源类型下的任意资源都有权限；父资源 ids 表示"该父资源下所有子资源"都有权限。
        """
        path = f"/api/v1/open/rbac/authorization/systems/{self._system_id}/relation/authorized-resources/"
        body = {
            "subject": {"type": "user", "id": subject_id},
            "action_id": action_id,
        }
        resp = self._post(path, body)
        return resp.get("data") or []

    # ============================================================
    # 模型管理 — System
    # ============================================================

    def create_system(self, data: dict) -> dict:
        return self._post("/api/v1/open/rbac/model/systems/", data)

    def retrieve_system(self) -> dict:
        return self._get(f"/api/v1/open/rbac/model/systems/{self._system_id}/")

    def update_system(self, data: dict) -> dict:
        return self._put(f"/api/v1/open/rbac/model/systems/{self._system_id}/", data)

    # ============================================================
    # 模型管理 — Action
    # ============================================================

    def list_actions(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            f"/api/v1/open/rbac/model/systems/{self._system_id}/actions/",
            params={"page": page, "page_size": page_size},
        )

    def batch_create_actions(self, actions: list[dict]) -> dict:
        return self._post(f"/api/v1/open/rbac/model/systems/{self._system_id}/actions/", actions)

    def update_action(self, action_id: str, data: dict) -> dict:
        return self._put(f"/api/v1/open/rbac/model/systems/{self._system_id}/actions/{action_id}/", data)

    def delete_action(self, action_id: str) -> dict:
        return self._delete(f"/api/v1/open/rbac/model/systems/{self._system_id}/actions/{action_id}/")

    # ============================================================
    # 模型管理 — ResourceType
    # ============================================================

    def list_resource_types(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            f"/api/v1/open/rbac/model/systems/{self._system_id}/resource-types/",
            params={"page": page, "page_size": page_size},
        )

    def batch_create_resource_types(self, rts: list[dict]) -> dict:
        return self._post(f"/api/v1/open/rbac/model/systems/{self._system_id}/resource-types/", rts)

    def update_resource_type(self, rt_id: str, data: dict) -> dict:
        return self._put(f"/api/v1/open/rbac/model/systems/{self._system_id}/resource-types/{rt_id}/", data)

    def delete_resource_type(self, rt_id: str) -> dict:
        return self._delete(f"/api/v1/open/rbac/model/systems/{self._system_id}/resource-types/{rt_id}/")

    # ============================================================
    # 模型管理 — Role
    # ============================================================

    def list_roles(self, page: int = 1, page_size: int = 100) -> dict:
        return self._get(
            f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/",
            params={"page": page, "page_size": page_size},
        )

    def batch_create_roles(self, roles: list[dict]) -> dict:
        return self._post(f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/", roles)

    def update_role(self, role_id: str, data: dict) -> dict:
        return self._put(f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/{role_id}/", data)

    def delete_role(self, role_id: str) -> dict:
        return self._delete(f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/{role_id}/")

    def batch_create_role_actions(self, role_id: str, actions: list[dict]) -> dict:
        return self._post(f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/{role_id}/actions/", actions)

    def batch_delete_role_actions(self, role_id: str, actions: list[dict]) -> dict:
        # v4 平台约定：ids 通过 query string 传递，用 "," 连接：?ids=action1,action2
        ids = [a["id"] for a in actions if a.get("id")]
        if not ids:
            return {}
        return self._delete(
            f"/api/v1/open/rbac/model/systems/{self._system_id}/roles/{role_id}/actions/",
            params={"ids": ",".join(ids)},
        )

    # ============================================================
    # 权限申请 URL
    # ============================================================

    def generate_perm_apply_url(self, permissions: list[dict]) -> str:
        path = "/api/v1/open/application/permission-apply-urls/"
        body = {"system_id": self._system_id, "permissions": permissions}
        try:
            resp = self._post(path, body)
            return (resp.get("data") or {}).get("url", "")
        except Exception:
            logger.exception("[iam_v4:apply_url_fail] permissions=%s", permissions)
            return ""

    # ============================================================
    # Auth Token（回调鉴权用）
    # ============================================================

    def get_auth_token(self) -> str:
        path = f"/api/v1/open/rbac/model/systems/{self._system_id}/auth-token/"
        resp = self._get(path)
        return resp["data"]["auth_token"]

    # ============================================================
    # HTTP 底层
    # ============================================================

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _post(self, path: str, body: dict, extra_headers: dict | None = None) -> dict:
        headers = {**self._auth_header}
        if extra_headers:
            headers.update(extra_headers)
        try:
            resp = requests.post(self._url(path), json=body, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
        except requests.Timeout:
            raise ProviderUnavailable(f"IAM v4 timeout: POST {path}")
        except requests.HTTPError:
            raise ProviderUnavailable(
                f"IAM v4 HTTP {resp.status_code}: POST {path}: {_safe_truncate(resp)}",
                code=resp.status_code,
            )
        return _safe_json(resp)

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = requests.get(self._url(path), headers=self._auth_header, params=params, timeout=self._timeout)
            resp.raise_for_status()
        except requests.Timeout:
            raise ProviderUnavailable(f"IAM v4 timeout: GET {path}")
        except requests.HTTPError:
            raise ProviderUnavailable(
                f"IAM v4 HTTP {resp.status_code}: GET {path}: {_safe_truncate(resp)}",
                code=resp.status_code,
            )
        return _safe_json(resp)

    def _put(self, path: str, body: dict) -> dict:
        try:
            resp = requests.put(self._url(path), json=body, headers=self._auth_header, timeout=self._timeout)
            resp.raise_for_status()
        except requests.Timeout:
            raise ProviderUnavailable(f"IAM v4 timeout: PUT {path}")
        except requests.HTTPError:
            raise ProviderUnavailable(
                f"IAM v4 HTTP {resp.status_code}: PUT {path}: {_safe_truncate(resp)}",
                code=resp.status_code,
            )
        return _safe_json(resp)

    def _delete(self, path: str, body: dict | None = None, params: dict | None = None) -> dict:
        try:
            kwargs = {"headers": self._auth_header, "timeout": self._timeout}
            if body:
                kwargs["json"] = body
            if params:
                kwargs["params"] = params
            resp = requests.delete(self._url(path), **kwargs)
            resp.raise_for_status()
        except requests.Timeout:
            raise ProviderUnavailable(f"IAM v4 timeout: DELETE {path}")
        except requests.HTTPError:
            raise ProviderUnavailable(
                f"IAM v4 HTTP {resp.status_code}: DELETE {path}: {_safe_truncate(resp)}",
                code=resp.status_code,
            )
        return _safe_json(resp)


def _safe_json(resp) -> dict:
    text = resp.text.strip() if hasattr(resp, "text") else ""
    if not text:
        return {}
    data = resp.json()
    if data.get("code", 0) != 0:
        raise ProviderError(data.get("message", "IAM v4 API error"), code=data.get("code"))
    return data


def _safe_truncate(resp, max_len: int = 500) -> str:
    try:
        return resp.text[:max_len]
    except Exception:
        return "<unreadable>"
