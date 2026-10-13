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
# 错误处理与 BKLog 完全相同，直接保留公共 V4ClientError 分类。
# ---------------------------------------------------------------------------

from iam_engine.v4.client import V4Client as SharedV4Client


class V4Client(SharedV4Client):
    """Use the common native HTTP client; only Monitor model-management endpoints remain local."""

    def _path(self, key):
        return getattr(self.options, key).format(system_id=self.options.system_id)

    def _model_path(self, suffix=""):
        return self._path("model_base_path").rstrip("/") + f"/{self.options.system_id}/" + suffix

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

    def get_auth_token(self):
        return self.retrieve_system_auth_token()

    def _post(self, path, body, extra_headers=None):
        return {"data": self._request("POST", path, body=body, extra_headers=extra_headers)}

    def _get(self, path, params=None):
        return {"data": self._request("GET", path, params=params)}

    def _put(self, path, body):
        return {"data": self._request("PUT", path, body=body)}

    def _delete(self, path, body=None, params=None):
        return {"data": self._request("DELETE", path, body=body, params=params)}
