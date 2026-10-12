from __future__ import annotations

import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urlencode

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import V4ClientError, V4ResponseError

logger = logging.getLogger("iam.v4.model_client")

# list_* 接口的每页上限由 IAM V4 契约固定为 100。
MAX_PAGE_SIZE = 100
# 分页保护：超过该页数说明返回的 count 与 results 不自洽，宁可报错也不要死循环。
MAX_PAGES = 1000


class V4ModelClient(V4Client):
    """IAM V4 权限模型管理 API 客户端。

    只服务模型注册与收敛，不参与运行时鉴权；复用 V4Client 的网关认证、租户头和错误映射。
    """

    @classmethod
    def from_settings(cls, *, username: str, bk_tenant_id: str) -> V4ModelClient:
        return cls(V4Options.from_settings(), username=username, bk_tenant_id=bk_tenant_id)

    # ------------------------------------------------------------------ system

    def retrieve_system(self) -> dict[str, Any] | None:
        """系统不存在时返回 None，而不是抛错，交给收敛逻辑决定是创建还是更新。"""
        try:
            data = self._request("GET", self._system_path())
        except V4ClientError as error:
            if error.status_code == HTTPStatus.NOT_FOUND:
                return None
            raise
        return self._expect_object(data, scope="retrieve_system")

    def create_system(self, payload: dict[str, Any]) -> str:
        data = self._request(
            "POST",
            self.options.model_base_path,
            body={**payload, "id": self.options.system_id},
            expected_statuses={HTTPStatus.CREATED},
        )
        created = self._expect_object(data, scope="create_system")
        return str(created.get("id") or self.options.system_id)

    def update_system(self, payload: dict[str, Any]) -> None:
        self._request("PUT", self._system_path(), body=payload, expected_statuses={HTTPStatus.NO_CONTENT})

    # ----------------------------------------------------------- resource type

    def list_resource_types(self) -> list[dict[str, Any]]:
        return self._list_paged(self._system_path("resource-types/"), scope="list_resource_types")

    def batch_create_resource_types(self, resource_types: Sequence[dict[str, Any]]) -> list[str]:
        return self._batch_create(self._system_path("resource-types/"), resource_types, scope="resource_types")

    def update_resource_type(self, resource_type_id: str, payload: dict[str, Any]) -> None:
        self._request(
            "PUT",
            self._system_path(f"resource-types/{quote(resource_type_id, safe='')}/"),
            body=payload,
            expected_statuses={HTTPStatus.NO_CONTENT},
        )

    # ----------------------------------------------------------------- action

    def list_actions(self) -> list[dict[str, Any]]:
        return self._list_paged(self._system_path("actions/"), scope="list_actions")

    def batch_create_actions(self, actions: Sequence[dict[str, Any]]) -> list[str]:
        return self._batch_create(self._system_path("actions/"), actions, scope="actions")

    def update_action(self, action_id: str, payload: dict[str, Any]) -> None:
        self._request(
            "PUT",
            self._system_path(f"actions/{quote(action_id, safe='')}/"),
            body=payload,
            expected_statuses={HTTPStatus.NO_CONTENT},
        )

    # ------------------------------------------------------------------- role

    def list_roles(self) -> list[dict[str, Any]]:
        return self._list_paged(self._system_path("roles/"), scope="list_roles")

    def batch_create_roles(self, roles: Sequence[dict[str, Any]]) -> list[str]:
        return self._batch_create(self._system_path("roles/"), roles, scope="roles")

    def update_role(self, role_id: str, payload: dict[str, Any]) -> None:
        self._request(
            "PUT",
            self._role_path(role_id),
            body=payload,
            expected_statuses={HTTPStatus.NO_CONTENT},
        )

    def batch_create_role_actions(self, role_id: str, actions: Sequence[dict[str, Any]]) -> list[str]:
        return self._batch_create(f"{self._role_path(role_id)}actions/", actions, scope=f"roles[{role_id}].actions")

    def batch_delete_role_actions(self, role_id: str, action_ids: Sequence[str]) -> None:
        ids = [str(action_id) for action_id in action_ids if str(action_id)]
        if not ids:
            return
        path = f"{self._role_path(role_id)}actions/?{urlencode({'ids': ','.join(ids)})}"
        self._request("DELETE", path, expected_statuses={HTTPStatus.NO_CONTENT})

    # ---------------------------------------------------------------- internal

    def _system_path(self, suffix: str = "") -> str:
        return f"{self.options.model_base_path}{quote(self.options.system_id, safe='')}/{suffix}"

    def _role_path(self, role_id: str) -> str:
        return self._system_path(f"roles/{quote(role_id, safe='')}/")

    def _batch_create(self, path: str, items: Sequence[dict[str, Any]], *, scope: str) -> list[str]:
        if not items:
            return []
        data = self._request("POST", path, body=list(items), expected_statuses={HTTPStatus.CREATED})
        if not isinstance(data, list):
            raise V4ResponseError(f"IAM V4 {scope} batch create response must be a list")
        return [str(item) for item in data]

    def _list_paged(self, path: str, *, scope: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"page": page, "page_size": MAX_PAGE_SIZE})
            data = self._expect_object(self._request("GET", f"{path}?{query}"), scope=scope)

            page_results = data.get("results")
            if not isinstance(page_results, list):
                raise V4ResponseError(f"IAM V4 {scope} response requires a results list")
            for item in page_results:
                if not isinstance(item, dict):
                    raise V4ResponseError(f"IAM V4 {scope} result item must be an object")
                results.append(item)

            count = data.get("count")
            if not isinstance(count, int):
                raise V4ResponseError(f"IAM V4 {scope} response requires an integer count")
            if len(results) >= count or not page_results:
                return results

        raise V4ResponseError(f"IAM V4 {scope} pagination exceeded {MAX_PAGES} pages")

    @staticmethod
    def _expect_object(data: Any, *, scope: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise V4ResponseError(f"IAM V4 {scope} response must be an object")
        return data
