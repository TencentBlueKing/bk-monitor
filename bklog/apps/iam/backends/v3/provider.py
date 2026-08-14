from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from iam import Resource
from iam.exceptions import AuthAPIError

from apps.iam import metrics
from apps.iam.backends.v3.apply import V3ApplicationBuilder
from apps.iam.backends.v3.codec import V3RequestCodec
from apps.iam.backends.v3.scope import V3AuthorizedScopeQuery
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance
from apps.iam.iam_engine.core.types import AuthorizedResourceScope, AuthResult, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.base import PermissionProvider


class V3PermissionProvider(PermissionProvider):
    """通过 Engine Provider 契约封装现有的 IAM V3 客户端。"""

    name = "v3"
    # V3 没有"列出已授权资源"的接口，授权范围要靠候选 ID 逐个求值。
    requires_candidate_ids = V3AuthorizedScopeQuery.requires_candidate_ids

    def __init__(
        self,
        client,
        system_id: str,
        *,
        codec: V3RequestCodec | None = None,
        action_resolver: Callable[[Any], Any] | None = None,
    ) -> None:
        self.client = client
        self.system_id = system_id
        self.codec = codec or V3RequestCodec(system_id)
        self.application_builder = V3ApplicationBuilder(client, system_id, action_resolver=action_resolver)
        self.scope_query = V3AuthorizedScopeQuery(client, system_id, codec=self.codec)

    def is_allowed(self, request: AuthRequest) -> AuthResult:
        start_at = time.time()
        try:
            allowed = self.client.is_allowed(self.codec.encode_auth_request(request))
        except AuthAPIError as error:
            metrics.observe_provider_latency(self.name, metrics.AUTH_API_IS_ALLOWED, start_at, ok=False)
            return AuthResult.error(
                provider_name=self.name,
                reason=str(error) or "IAM V3 request failed",
                error_type=type(error).__name__,
            )

        metrics.observe_provider_latency(self.name, metrics.AUTH_API_IS_ALLOWED, start_at, ok=True)
        if allowed:
            return AuthResult.allow(provider_name=self.name)
        return AuthResult.deny(provider_name=self.name)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        start_at = time.time()
        try:
            raw_result = self.client.batch_resource_multi_actions_allowed(
                self.codec.encode_batch_request(request),
                self.codec.encode_resource_groups(request),
            )
        except AuthAPIError as error:
            result = self._batch_error_result(request, error)
            metrics.observe_batch_latency(self.name, start_at, result.items)
            return result

        normalized_result = {
            str(resource_id): {str(action_id): allowed for action_id, allowed in action_results.items()}
            for resource_id, action_results in raw_result.items()
        }
        items = []
        for action_id, resource_id in request.iter_keys():
            action_results = normalized_result.get(resource_id, {})
            if action_id not in action_results:
                result = AuthResult.error(
                    provider_name=self.name,
                    reason=f"missing IAM V3 batch result for action={action_id}, resource={resource_id}",
                    error_type="IncompleteBatchResult",
                )
            elif action_results[action_id]:
                result = AuthResult.allow(provider_name=self.name)
            else:
                result = AuthResult.deny(provider_name=self.name)
            items.append(BatchAuthResultItem(action_id, resource_id, result))
        # 逐条结果构造完才记耗时：请求成功但部分条目缺失也要计入 error，口径与 V4 一致。
        metrics.observe_batch_latency(self.name, start_at, items)
        return BatchAuthResult(items=tuple(items))

    def list_authorized_resources(
        self,
        *,
        action_id: str,
        resource_type: str = "space",
        subject: dict[str, str] | None = None,
        candidate_ids: frozenset[str] | None = None,
    ) -> AuthorizedResourceScope:
        start_at = time.time()
        # V3 没有列出已授权资源的接口，耗时包含 policy_query 之后的本地表达式求值，这正是该路径的真实开销。
        scope = self.scope_query.list_authorized_resources(
            action_id=action_id,
            resource_type=resource_type,
            subject=subject,
            candidate_ids=candidate_ids,
        )
        metrics.observe_provider_latency(self.name, metrics.AUTH_API_SPACE_SCOPE, start_at, ok=scope.ok)
        return scope

    def get_apply_data(
        self,
        actions: list[Any],
        resources: list[ResourceInstance] | None = None,
    ) -> tuple[dict[str, Any], str]:
        """接收引擎类型的无权限申请入口，内部转换为 V3 SDK 资源。"""

        sdk_resources = [self.codec.encode_resource(resource) for resource in (resources or [])]
        return self.application_builder.get_apply_data(actions, sdk_resources)

    def get_apply_url(
        self,
        action_ids: list[Any],
        resources: list[Resource] | None = None,
        system_id: str = "",
    ) -> str:
        """V3 原生的申请链接入口，参数保持 V3 SDK 类型。"""

        return self.application_builder.get_apply_url(action_ids, resources, system_id)

    def _batch_error_result(self, request: BatchAuthRequest, error: AuthAPIError) -> BatchAuthResult:
        reason = str(error) or "IAM V3 batch request failed"
        return BatchAuthResult(
            items=tuple(
                BatchAuthResultItem(
                    action_id,
                    resource_id,
                    AuthResult.error(self.name, reason=reason, error_type=type(error).__name__),
                )
                for action_id, resource_id in request.iter_keys()
            )
        )
