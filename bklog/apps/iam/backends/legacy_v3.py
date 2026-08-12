from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from iam import Action, MultiActionRequest, Request, Resource, Subject
from iam.exceptions import AuthAPIError

from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, to_definition_id
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.base import PermissionProvider
from apps.iam.iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant


class LegacyV3GrantError(RuntimeError):
    """IAM V3 授权接口以 false 返回值表示的明确失败。"""


class LegacyV3Adapter(PermissionProvider):
    """通过 Engine Provider 契约封装现有的 IAM V3 客户端。"""

    name = "v3"

    def __init__(self, iam_client, system_id: str) -> None:
        self.iam_client = iam_client
        self.system_id = system_id

    def is_allowed(self, request: AuthRequest) -> AuthResult:
        try:
            allowed = self.iam_client.is_allowed(self._make_request(request))
        except AuthAPIError as error:
            return AuthResult.error(
                provider_name=self.name,
                reason=str(error) or "IAM V3 request failed",
                error_type=type(error).__name__,
            )

        if allowed:
            return AuthResult.allow(provider_name=self.name)
        return AuthResult.deny(provider_name=self.name)

    def _make_request(self, request: AuthRequest) -> Request:
        return Request(
            system=self.system_id,
            subject=Subject(request.subject.type, request.subject.id),
            action=Action(to_definition_id(request.action_id)),
            resources=[self._make_resource(resource) for resource in request.resources],
            environment=dict(request.environment) or None,
        )

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        v3_request = MultiActionRequest(
            system=self.system_id,
            subject=Subject(request.subject.type, request.subject.id),
            actions=[Action(to_definition_id(action_id)) for action_id in request.action_ids],
            resources=[],
            environment=dict(request.environment) or None,
        )
        resource_groups = [
            [self._make_resource(resource) for resource in resource_group] for resource_group in request.resource_groups
        ]

        try:
            raw_result = self.iam_client.batch_resource_multi_actions_allowed(v3_request, resource_groups)
        except AuthAPIError as error:
            return self._batch_error_result(request, error)

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
        return BatchAuthResult(items=tuple(items))

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

    def _make_resource(self, resource: ResourceInstance) -> Resource:
        attributes = dict(resource.attributes)
        if resource.name:
            attributes.setdefault("name", resource.name)

        return Resource(
            resource.system or self.system_id,
            to_definition_id(resource.type),
            str(resource.id),
            attributes,
        )


class LegacyV3AuthorizationWriter:
    """把 V3 SDK 的返回值归一为可被状态机识别的授权写入器。"""

    def __init__(self, iam_client) -> None:
        self.iam_client = iam_client

    def prepare_resource_creator_actions(
        self, application: Mapping[str, Any], *, expired_at: int | None = None
    ) -> PreparedAuthorizationGrant:
        del expired_at
        return PreparedAuthorizationGrant(payload=dict(application))

    def grant_prepared(self, grant: PreparedAuthorizationGrant) -> Any:
        result = self.iam_client.grant_resource_creator_actions(dict(grant.payload))
        if isinstance(result, tuple) and result and result[0] is False:
            message = str(result[1]) if len(result) > 1 else "IAM V3 creator grant failed"
            raise LegacyV3GrantError(message)
        return result

    def grant_resource_creator_actions(self, application: Mapping[str, Any]) -> Any:
        return self.grant_prepared(self.prepare_resource_creator_actions(application))

    @staticmethod
    def classify_failure(error: Exception) -> GrantFailureKind:
        if isinstance(error, ValueError):
            return GrantFailureKind.FAILED_FINAL
        return GrantFailureKind.RETRY_WAIT
