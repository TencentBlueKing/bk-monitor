from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import requests
from requests.exceptions import RequestException, Timeout

from apps.api.base import get_request_api_headers
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import (
    V4ClientError,
    V4RateLimitError,
    V4ResponseError,
    V4TimeoutError,
    V4TransportError,
)


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

    def _request(self, method: str, path: str, *, body: dict | list | None = None) -> Any:
        url = urljoin(self.options.gateway_url.rstrip("/") + "/", path.lstrip("/"))
        headers = {
            "Content-Type": "application/json",
            "X-Bkapi-Authorization": get_request_api_headers({"bk_username": self.username}),
            "X-Bk-Tenant-Id": self.bk_tenant_id,
        }
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

        if response.status_code == 429:
            raise V4RateLimitError("IAM V4 rate limited", status_code=response.status_code)

        if not (200 <= response.status_code < 300):
            reason = self._extract_error_reason(response)
            error_type = V4RateLimitError if response.status_code == 429 else V4ClientError
            raise error_type(reason or f"IAM V4 HTTP {response.status_code}", status_code=response.status_code)

        if response.status_code == 204 or not response.content:
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

        missing_ids = [resource_id for resource_id in expected_resource_ids if resource_id not in results]
        if missing_ids:
            raise V4ResponseError(f"missing IAM V4 batch results for resources={missing_ids}")

        return results

    @staticmethod
    def _extract_error_reason(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error.get("code") or "")
            return str(payload.get("message") or "")
        return response.text
