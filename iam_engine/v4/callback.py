"""V4 callback protocol on the IAM SDK ResourceProvider dispatch extension point.

The SDK processors only call local providers. Authentication is deliberately
separate: the V4 callback never asks the V3 SDK for a token or logs credentials.
"""

import base64
import binascii
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from iam.contrib.django.dispatcher import DjangoBasicResourceApiDispatcher
from iam.contrib.django.dispatcher.dispatchers import fail_response

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.v4.client import V4Client

logger = logging.getLogger("iam.v4.callback")


class V3ResourceApiDispatcher(DjangoBasicResourceApiDispatcher):
    """Keep the V3 SDK protocol intact, but do not call a disabled protocol."""

    def __init__(self, iam, system, *, mode_loader):
        super().__init__(iam, system)
        self.mode_loader = mode_loader

    def _dispatch(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID", "")
        try:
            mode = AuthMode(self.mode_loader())
            if AuthMode.V3 not in DEFAULT_DUAL_STACK.modes_for(mode):
                return fail_response(503, "IAM V3 is disabled", request_id)
        except Exception:
            return fail_response(400, "Invalid IAM permission mode", request_id)
        return super()._dispatch(request)


class V4CallbackIAM:
    """Shared callback authentication; products supply only their credential source."""

    def __init__(self, *, options_loader, mode_loader, bk_tenant_id="", client_factory=V4Client):
        self.options_loader = options_loader
        self.mode_loader = mode_loader
        self.bk_tenant_id = bk_tenant_id
        self.client_factory = client_factory

    def get_token(self, system, *, bk_tenant_id=None, mode=None):
        try:
            selected = AuthMode(self.mode_loader()) if mode is None else AuthMode(mode)
            if AuthMode.V4 not in DEFAULT_DUAL_STACK.modes_for(selected):
                return False, "IAM V4 is disabled", ""
            tenant = self.bk_tenant_id if bk_tenant_id is None else bk_tenant_id
            options = self.options_loader(tenant)
            if system != options.system_id:
                return False, "unknown IAM V4 system", ""
            identity = json.dumps(
                [tenant, system, options.gateway_url, options.app_code, options.app_secret,
                 options.auth_token_path, options.auth_token_cache_seconds],
                separators=(",", ":"),
            )
            key = "iam:v4:callback:token:" + hashlib.sha256(identity.encode()).hexdigest()
            ttl = options.auth_token_cache_seconds
            if ttl > 0:
                try:
                    token = cache.get(key)
                except Exception as error:
                    logger.warning("token cache read failed: %s", type(error).__name__)
                    token = None
                if isinstance(token, str) and token:
                    return True, "success", token
            client = self.client_factory(options, bk_tenant_id=tenant)
            token = client.retrieve_system_auth_token(system)
            if not isinstance(token, str) or not token:
                return False, "empty auth_token from IAM V4", ""
            if ttl > 0:
                try:
                    cache.set(key, token, ttl)
                except Exception as error:
                    # A cache outage does not invalidate a successfully fetched token.
                    logger.warning("token cache write failed: %s", type(error).__name__)
            return True, "success", token
        except Exception as error:
            logger.warning("callback token unavailable: %s", type(error).__name__)
            return False, "IAM V4 callback token unavailable", ""

    def is_basic_auth_allowed(self, system, authorization, *, bk_tenant_id=None, mode=None):
        if not isinstance(authorization, str):
            return False
        scheme, separator, encoded = authorization.partition(" ")
        if not separator or scheme.lower() != "basic":
            return False
        try:
            username, separator, password = base64.b64decode(encoded, validate=True).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return False
        if not separator or username != "bk_iam" or not password:
            return False
        ok, _, token = self.get_token(system, bk_tenant_id=bk_tenant_id, mode=mode)
        return bool(ok and hmac.compare_digest(password.encode(), token.encode()))


class V4ResourceApiDispatcher(DjangoBasicResourceApiDispatcher):
    """Validate V4 input, then reuse the SDK's local ResourceProvider processors."""

    def __init__(self, iam, system, *, root_resource_type="space"):
        super().__init__(iam, system)
        self.root_resource_type = root_resource_type

    @staticmethod
    def _response(payload, status, request_id):
        response = JsonResponse(payload, status=status)
        if request_id:
            response["X-Request-Id"] = request_id
        return response

    def _error(self, status, code, message, request_id):
        return self._response({"error": {"code": code, "message": message}}, status, request_id)

    @staticmethod
    def _tenant(request):
        tenant = request.META.get("HTTP_X_BK_TENANT_ID", "").strip()
        if getattr(settings, "ENABLE_MULTI_TENANT_MODE", False) and not tenant:
            raise ValueError("X-Bk-Tenant-Id is required")
        return tenant or settings.BK_APP_TENANT_ID

    def _get_options(self, request):
        options = super()._get_options(request)
        options["bk_tenant_id"] = self._tenant(request)
        return options

    @staticmethod
    def _integer(value, field):
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise ValueError(f"{field} must be an integer")
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(f"{field} must be an integer") from error

    def _normalize(self, data):
        if not isinstance(data, dict):
            raise ValueError("request body must be an object")
        if not all(isinstance(data.get(key), str) and data[key] for key in ("type", "method")):
            raise ValueError("method and type are required strings")
        result = dict(data)
        filters = data.get("filter", {})
        if not isinstance(filters, dict):
            raise ValueError("filter must be an object")
        filters = dict(filters)
        result["filter"] = filters
        if data["method"] == "list_instance":
            page = data.get("page")
            if not isinstance(page, dict):
                raise ValueError("page is required and must be an object")
            if "limit" in page or "offset" in page:
                limit = self._integer(page.get("limit"), "page.limit")
                offset = self._integer(page.get("offset"), "page.offset")
            else:
                number = self._integer(page.get("page"), "page.page")
                limit = self._integer(page.get("page_size"), "page.page_size")
                if number < 1:
                    raise ValueError("page.page must be greater than 0")
                offset = (number - 1) * limit
            if not 1 <= limit <= 1000 or offset < 0:
                raise ValueError("page size must be between 1 and 1000; offset must be nonnegative")
            result["page"] = {"limit": limit, "offset": offset}
            parent = filters.get("parent")
            if parent is not None and (
                not isinstance(parent, dict)
                or not all(isinstance(parent.get(key), str) and parent[key] for key in ("type", "id"))
            ):
                raise ValueError("filter.parent must contain string type and id")
            if parent and (parent["type"] != self.root_resource_type or data["type"] == self.root_resource_type):
                raise ValueError("unsupported parent resource type")
            keyword = filters.get("keyword", "")
            if not isinstance(keyword, str):
                raise ValueError("filter.keyword must be a string")
            if keyword:
                filters["search"] = {data["type"]: [keyword]}
                filters["resource_type_chain"] = [{"id": self.root_resource_type}]
                if data["type"] != self.root_resource_type:
                    filters["resource_type_chain"].append({"id": data["type"]})
        elif data["method"] == "fetch_instance_info":
            ids = filters.get("ids")
            requires = data.get("requires", filters.get("attrs", []))
            if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(item, str) for item in ids):
                raise ValueError("filter.ids must be a string array with at most 1000 items")
            if not isinstance(requires, list) or any(not isinstance(item, str) for item in requires):
                raise ValueError("requires must be a string array")
            filters["attrs"] = requires
        return result

    def _dispatch(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID", "")
        try:
            mode = AuthMode(self.iam.mode_loader())
            if AuthMode.V4 not in DEFAULT_DUAL_STACK.modes_for(mode):
                return self._error(503, "UNAVAILABLE", "IAM V4 is disabled", request_id)
            tenant = self._tenant(request)
        except ValueError as error:
            return self._error(400, "INVALID_ARGUMENT", str(error), request_id)
        except Exception:
            return self._error(503, "UNAVAILABLE", "IAM callback configuration unavailable", request_id)
        if request.method != "POST":
            return self._error(405, "INVALID_ARGUMENT", "POST is required", request_id)
        if not self.iam.is_basic_auth_allowed(
            self.system, request.META.get("HTTP_AUTHORIZATION", ""), bk_tenant_id=tenant, mode=mode
        ):
            return self._error(401, "UNAUTHENTICATED", "basic auth failed", request_id)
        try:
            data = self._normalize(json.loads(request.body))
        except (ValueError, TypeError) as error:
            return self._error(400, "INVALID_ARGUMENT", str(error), request_id)
        if data["type"] not in self._provider:
            return self._error(404, "NOT_FOUND", "unsupported resource type", request_id)
        if data["method"] not in ("list_instance", "fetch_instance_info"):
            return self._error(404, "NOT_FOUND", "unsupported method", request_id)
        try:
            processor = getattr(self, "_dispatch_" + data["method"])
            response = processor(request, data, request_id)
            payload = json.loads(response.content)
            return self._response({"data": payload["data"]}, 200, request_id)
        except NotImplementedError:
            return self._error(404, "NOT_FOUND", "unsupported resource method", request_id)
        except Exception as error:
            logger.error("callback failed: %s", type(error).__name__)
            return self._error(500, "INTERNAL", "internal server error", request_id)
