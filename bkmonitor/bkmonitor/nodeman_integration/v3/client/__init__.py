import json
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from bkmonitor.utils.user import get_admin_username

from ..audit import NodeManV3AuditEvent, record_outbound_audit


class NodeManV3ClientError(Exception):
    """Base error for NodeMan V3 client requests."""


class NodeManV3TransportError(NodeManV3ClientError):
    """The request was rejected or failed before a usable API response."""


class NodeManV3UnknownResultError(NodeManV3TransportError):
    """A write may have been accepted, but no conclusive result was returned."""


class NodeManV3APIError(NodeManV3ClientError):
    def __init__(self, *, code, message: str, request_id: str | None = None):
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"NodeMan V3 API error {code}: {message}")


@dataclass(frozen=True)
class NodeManV3RequestContext:
    bk_tenant_id: str
    bk_biz_id: int | None
    monitor_operation_id: str | None = None


class NodeManV3HTTPClient:
    API_VERSION = "v3"
    DEFAULT_TIMEOUT = 300

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
        audit_recorder: Callable[[NodeManV3AuditEvent], None] = record_outbound_audit,
    ):
        self.base_url = (base_url or settings.BKNODEMAN_API_BASE_URL).rstrip("/")
        if not self.base_url:
            raise ImproperlyConfigured("BKNODEMAN_API_BASE_URL is required for NodeMan V3")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.audit_recorder = audit_recorder

    def post(
        self,
        action: str,
        payload: dict,
        *,
        context: NodeManV3RequestContext,
        write: bool,
    ):
        normalized_action = action.strip("/")
        if not normalized_action.startswith("api/v3/"):
            raise ValueError(f"NodeMan V3 action must start with api/v3/: {action!r}")
        if write and not context.monitor_operation_id:
            raise ValueError("monitor_operation_id is required for NodeMan V3 write requests")
        self._validate_business(payload, context)

        url = urljoin(f"{self.base_url}/", normalized_action)
        headers = self._headers(context)
        self._audit(normalized_action, context, outcome="dispatching")

        try:
            response = self.session.request(
                method="POST",
                url=url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            request_id = self._request_id(error.response)
            self._audit(
                normalized_action,
                context,
                outcome="failed",
                error_code=status_code,
                request_id=request_id,
            )
            error_class = (
                NodeManV3UnknownResultError if write and status_code and status_code >= 500 else NodeManV3TransportError
            )
            raise error_class(f"NodeMan V3 HTTP error {status_code} for {normalized_action}") from error
        except requests.RequestException as error:
            self._audit(
                normalized_action, context, outcome="unknown" if write else "failed", error_code=type(error).__name__
            )
            error_class = NodeManV3UnknownResultError if write else NodeManV3TransportError
            raise error_class(f"NodeMan V3 transport error for {normalized_action}: {error}") from error

        request_id = self._request_id(response)
        try:
            response_data = response.json()
        except ValueError as error:
            self._audit(
                normalized_action,
                context,
                outcome="unknown" if write else "failed",
                error_code="invalid_json",
                request_id=request_id,
            )
            error_class = NodeManV3UnknownResultError if write else NodeManV3TransportError
            raise error_class(f"NodeMan V3 returned invalid JSON for {normalized_action}") from error

        if not isinstance(response_data, dict):
            self._audit(
                normalized_action,
                context,
                outcome="unknown" if write else "failed",
                error_code="invalid_response",
                request_id=request_id,
            )
            error_class = NodeManV3UnknownResultError if write else NodeManV3TransportError
            raise error_class(f"NodeMan V3 returned a non-object response for {normalized_action}")

        code = response_data.get("code", 0)
        if response_data.get("result") is False or code not in (0, None):
            message = response_data.get("message") or response_data.get("errors") or "unknown error"
            self._audit(normalized_action, context, outcome="failed", error_code=code, request_id=request_id)
            raise NodeManV3APIError(code=code, message=message, request_id=request_id)

        self._audit(normalized_action, context, outcome="success", request_id=request_id)
        return response_data.get("data")

    @staticmethod
    def _validate_business(payload: dict, context: NodeManV3RequestContext) -> None:
        if context.bk_biz_id is None or "bk_biz_id" not in payload:
            return
        request_biz_id = payload["bk_biz_id"]
        if isinstance(request_biz_id, list):
            matches = request_biz_id == [context.bk_biz_id]
        else:
            matches = request_biz_id == context.bk_biz_id
        if not matches:
            raise ValueError(
                f"request bk_biz_id {request_biz_id!r} does not match context bk_biz_id {context.bk_biz_id!r}"
            )

    @staticmethod
    def _headers(context: NodeManV3RequestContext) -> dict[str, str]:
        authorization = {
            "bk_app_code": settings.APP_CODE,
            "bk_app_secret": settings.SECRET_KEY,
            "bk_username": get_admin_username(bk_tenant_id=context.bk_tenant_id),
        }
        return {
            "x-bkapi-authorization": json.dumps(authorization),
            "X-Bk-Tenant-Id": context.bk_tenant_id,
        }

    @staticmethod
    def _request_id(response) -> str | None:
        if response is None:
            return None
        return response.headers.get("x-bkapi-request-id")

    def _audit(
        self,
        action: str,
        context: NodeManV3RequestContext,
        *,
        outcome: str,
        error_code=None,
        request_id: str | None = None,
    ) -> None:
        self.audit_recorder(
            NodeManV3AuditEvent(
                api_version=self.API_VERSION,
                action=action,
                method="POST",
                monitor_operation_id=context.monitor_operation_id,
                bk_tenant_id=context.bk_tenant_id,
                bk_biz_id=context.bk_biz_id,
                outcome=outcome,
                error_code=error_code,
                request_id=request_id,
            )
        )


class NodeManV3ServiceClient:
    def __init__(self, client: NodeManV3HTTPClient):
        self.client = client

    def _read(self, action: str, payload: dict, *, context: NodeManV3RequestContext):
        return self.client.post(action, payload, context=context, write=False)

    def _write(self, action: str, payload: dict, *, context: NodeManV3RequestContext):
        return self.client.post(action, payload, context=context, write=True)
