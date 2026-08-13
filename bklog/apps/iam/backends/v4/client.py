"""IAM V4 开放接口的 HTTP 客户端。

这里没有复用项目统一的 `apps.api.base.DataAPI`，是因为 IAM V4 的契约与 `DataAPI` 的三条硬性前提冲突，
迁移过去会直接功能不可用或把鉴权变成 fail-open：

1. 请求体必须是 dict：`DataAPI._send_request` 对 POST 走 `json.dumps(non_file_data)`，而 `non_file_data`
   来自 `_split_file_data` 的 `data.items()`；而 `add_authorization` 要求顶层是 JSON 数组。
2. 只接受 HTTP 200：`DataAPI` 以 `HTTP_STATUS_OK` 判定 HTTP 层成功，非 200 一律转 `DataAPIException`；
   而 `add_authorization` 成功返回 201。
3. 响应体必须是合法 JSON：`DataAPI` 对无法 `json()` 的响应抛「结果格式非json」；而上面 201 的成功响应体为空。

只读接口同样不宜迁移：`DataAPI` 在响应缺少 `result` 字段时会补 `result = True`，而 IAM V4 的失败可能是
HTTP 200 带 `{"error": {...}}`（见 `_request` 中对 `payload["error"]` 的处理），迁过去会被判成功，
鉴权因此 fail-open。此外 `DataAPIException` 无法区分 timeout / 429 / 5xx，而授权重试分类依赖
`V4TimeoutError` / `V4RateLimitError` / `V4ResponseError` 这套类型区分。
"""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from typing import Any
from urllib.parse import urljoin

import requests
from requests.exceptions import RequestException, Timeout

from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import (
    V4ClientError,
    V4RateLimitError,
    V4ResponseError,
    V4TimeoutError,
    V4TransportError,
)
from apps.iam.error_summary import sanitize_error_summary

logger = logging.getLogger("iam.v4.client")


class V4Client:
    """通过 bkiam APIGateway 调用 IAM V4 开放接口的 HTTP 客户端。"""

    def __init__(self, options: V4Options, *, username: str = "", bk_tenant_id: str = "") -> None:
        self.options = options
        self.username = username
        self.bk_tenant_id = bk_tenant_id

    def direct_auth(
        self,
        *,
        subject: dict[str, str],
        action_id: str,
        resource: dict[str, Any] | None = None,
    ) -> bool:
        body: dict[str, Any] = {
            "subject": subject,
            "action_id": action_id,
        }
        if resource is not None:
            body["resource"] = resource
        data = self._request(
            "POST",
            self.options.auth_path.format(system_id=self.options.system_id),
            body=body,
        )
        return self._extract_allowed(data)

    def direct_auth_by_resources(
        self,
        *,
        subject: dict[str, str],
        action_id: str,
        resources: list[dict[str, Any]],
    ) -> dict[str, bool]:
        body = {
            "subject": subject,
            "action_id": action_id,
            "resources": resources,
        }
        data = self._request(
            "POST",
            self.options.auth_by_resources_path.format(system_id=self.options.system_id),
            body=body,
        )
        return self._extract_resource_results(data, expected_resource_ids=[item["id"] for item in resources])

    def list_authorized_resource(
        self,
        *,
        subject: dict[str, str],
        action_id: str,
        resource_type: str = "space",
    ) -> dict[str, Any]:
        """查询用户对某个 Action 的第一层顶级资源范围。

        返回结构：
        - {"type": "<resource_type>", "ids": ["*"]} 表示通配全部顶层资源
        - {"type": "<resource_type>", "ids": ["1", "2"]} 表示显式 ID 列表
        - {"type": "<resource_type>", "ids": []} 表示有效空权限
        """
        body = {
            "subject": subject,
            "action_id": action_id,
        }
        data = self._request(
            "POST",
            self.options.authorized_resources_path.format(system_id=self.options.system_id),
            body=body,
        )
        return self._extract_authorized_resource_scope(data, resource_type=resource_type)

    def retrieve_system_auth_token(self, system_id: str | None = None) -> str:
        sid = system_id or self.options.system_id
        path = self.options.auth_token_path.format(system_id=sid)
        data = self._request("GET", path)
        if not isinstance(data, dict):
            raise V4ResponseError("IAM V4 auth-token response must be an object")
        token = data.get("auth_token")
        if not token:
            raise V4ResponseError("IAM V4 auth-token response missing auth_token")
        return str(token)

    def generate_perm_apply_url(self, *, permissions: list[dict[str, Any]]) -> str:
        body = {
            "system_id": self.options.system_id,
            "permissions": permissions,
        }
        data = self._request("POST", self.options.apply_url_path, body=body)
        if not isinstance(data, dict):
            raise V4ResponseError("IAM V4 apply response must be an object")
        url = data.get("url")
        if not url:
            raise V4ResponseError("IAM V4 apply response missing url")
        return str(url)

    def add_authorization(self, *, items: list[dict[str, Any]], operator: str) -> None:
        """为主体新增角色授权。

        IAM V4 当前契约单次最多接收 20 个授权项，每项最多 20 个资源，
        并以 HTTP 201 空响应表示成功。
        """
        normalized_operator = str(operator or "").strip()
        if not normalized_operator:
            raise ValueError("IAM V4 authorization requires a non-empty operator")
        if not 1 <= len(items) <= 20:
            raise ValueError("IAM V4 authorization items must contain 1 to 20 entries")
        for item in items:
            resources = item.get("resources") if isinstance(item, dict) else None
            if not isinstance(resources, list) or not 1 <= len(resources) <= 20:
                raise ValueError("each IAM V4 authorization item must contain 1 to 20 resources")

        result = self._request(
            "POST",
            self.options.add_authorization_path.format(system_id=self.options.system_id),
            body=items,
            extra_headers={"X-Bkiam-Operator": normalized_operator},
            expected_statuses={HTTPStatus.CREATED},
        )
        if result is not None:
            raise V4ResponseError("IAM V4 add-authorization response must be empty")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict | list | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_statuses: set[int] | None = None,
    ) -> Any:
        if not self.options.gateway_url:
            logger.error("IAM V4 gateway is not configured; set BKAPP_IAM_V4_API_BASE_URL to the bkiam APIGateway root")
            raise V4TransportError("IAM V4 gateway is not configured (BKAPP_IAM_V4_API_BASE_URL)")
        tenant_id = str(self.bk_tenant_id or "").strip()
        if not tenant_id:
            raise V4TransportError("IAM V4 request requires a non-empty bk_tenant_id")

        url = urljoin(self.options.gateway_url.rstrip("/") + "/", path.lstrip("/"))
        headers = {
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": json.dumps(
                {
                    "bk_app_code": self.options.app_code,
                    "bk_app_secret": self.options.app_secret,
                    "bk_username": self.username,
                }
            ),
            "X-Bk-Tenant-Id": tenant_id,
        }
        headers.update(extra_headers or {})
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                timeout=self.options.timeout_seconds,
            )
        except Timeout as error:
            raise V4TimeoutError("IAM V4 request timeout") from error
        except RequestException as error:
            raise V4TransportError(str(error) or "IAM V4 transport error") from error

        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            raise V4RateLimitError("IAM V4 rate limited", status_code=response.status_code)

        status_is_expected = (
            response.status_code in expected_statuses
            if expected_statuses is not None
            else HTTPStatus.OK <= response.status_code < HTTPStatus.MULTIPLE_CHOICES
        )
        if not status_is_expected:
            reason = self._extract_error_reason(response)
            raise V4ClientError(
                reason or f"IAM V4 HTTP {response.status_code}",
                status_code=response.status_code,
            )

        if response.status_code == HTTPStatus.NO_CONTENT or not response.content:
            return None

        try:
            payload = response.json()
        except ValueError as error:
            raise V4ResponseError("IAM V4 response is not valid JSON") from error

        if isinstance(payload, dict) and "error" in payload:
            error_body = payload["error"]
            reason = error_body.get("message") if isinstance(error_body, dict) else str(error_body)
            raise V4ClientError(reason or "IAM V4 request failed", status_code=response.status_code)

        if not isinstance(payload, dict) or "data" not in payload:
            raise V4ResponseError("IAM V4 response missing data field")

        return payload["data"]

    @staticmethod
    def _extract_allowed(data: Any) -> bool:
        if not isinstance(data, dict) or "allowed" not in data:
            raise V4ResponseError("IAM V4 auth response missing allowed field")
        allowed = data["allowed"]
        if not isinstance(allowed, bool):
            raise V4ResponseError("IAM V4 auth response allowed must be boolean")
        return allowed

    @staticmethod
    def _extract_resource_results(data: Any, *, expected_resource_ids: list[str]) -> dict[str, bool]:
        if not isinstance(data, list):
            raise V4ResponseError("IAM V4 batch auth response must be a list")

        expected_resource_ids = [str(resource_id) for resource_id in expected_resource_ids]
        expected_resource_id_set = set(expected_resource_ids)
        results: dict[str, bool] = {}
        for item in data:
            if not isinstance(item, dict):
                raise V4ResponseError("IAM V4 batch auth item must be an object")
            resource_id = item.get("resource_id")
            allowed = item.get("allowed")
            if resource_id is None or not isinstance(allowed, bool):
                raise V4ResponseError("IAM V4 batch auth item missing resource_id/allowed")
            resource_id = str(resource_id)
            if resource_id in results:
                raise V4ResponseError(f"duplicate IAM V4 batch result for resource={resource_id}")
            results[resource_id] = allowed

        unknown_ids = [resource_id for resource_id in results if resource_id not in expected_resource_id_set]
        if unknown_ids:
            raise V4ResponseError(f"unknown IAM V4 batch results for resources={unknown_ids}")

        missing_ids = [resource_id for resource_id in expected_resource_ids if resource_id not in results]
        if missing_ids:
            raise V4ResponseError(f"missing IAM V4 batch results for resources={missing_ids}")

        return results

    @staticmethod
    def _extract_authorized_resource_scope(data: Any, *, resource_type: str) -> dict[str, Any]:
        if not isinstance(data, list):
            raise V4ResponseError("IAM V4 authorized-resources response must be a list")

        matched_items = []
        for item in data:
            if not isinstance(item, dict):
                raise V4ResponseError("IAM V4 authorized-resources item must be an object")
            item_type = item.get("type")
            ids = item.get("ids")
            if item_type is None or ids is None:
                raise V4ResponseError("IAM V4 authorized-resources item missing type/ids")
            if not isinstance(ids, list):
                raise V4ResponseError("IAM V4 authorized-resources ids must be a list")
            item_type = str(item_type)
            if item_type != resource_type:
                raise V4ResponseError(
                    f"IAM V4 authorized-resources returned unexpected type={item_type}, expected={resource_type}"
                )
            matched_items.append(item)

        if not matched_items:
            return {"type": resource_type, "ids": []}

        if len(matched_items) > 1:
            raise V4ResponseError(f"IAM V4 authorized-resources returned duplicate type={resource_type}")

        raw_ids = matched_items[0]["ids"]
        normalized_ids: list[str] = []
        has_wildcard = False
        for raw_id in raw_ids:
            if raw_id is None or isinstance(raw_id, dict | list):
                raise V4ResponseError("IAM V4 authorized-resources contains invalid id")
            resource_id = str(raw_id)
            if resource_id == "*":
                has_wildcard = True
                continue
            if not resource_id:
                raise V4ResponseError("IAM V4 authorized-resources contains empty id")
            normalized_ids.append(resource_id)

        if has_wildcard:
            if normalized_ids:
                raise V4ResponseError("IAM V4 authorized-resources cannot mix wildcard and concrete ids")
            return {"type": resource_type, "ids": ["*"]}

        # 协议层仍返回列表并先去重，授权范围会在 Provider 层按集合语义消费。
        deduped_ids = list(dict.fromkeys(normalized_ids))
        return {"type": resource_type, "ids": deduped_ids}

    @staticmethod
    def _extract_error_reason(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return sanitize_error_summary(response.text)
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return sanitize_error_summary(error.get("message") or error.get("code") or "")
            return sanitize_error_summary(payload.get("message") or "")
        return sanitize_error_summary(response.text)
