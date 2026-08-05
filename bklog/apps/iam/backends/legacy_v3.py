from __future__ import annotations

from iam import Action, MultiActionRequest, Request, Resource, Subject
from iam.exceptions import AuthAPIError

from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, to_definition_id
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.base import PermissionProvider


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
