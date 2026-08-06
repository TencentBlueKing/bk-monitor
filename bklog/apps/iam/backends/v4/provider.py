from __future__ import annotations

from typing import Any

from iam import Resource

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import V4ClientError
from apps.iam.handlers.actions import ActionMeta, get_action_by_id
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, to_definition_id
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem
from apps.iam.iam_engine.provider.base import PermissionProvider


def _chunked(items: list, chunk_size: int):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


class V4PermissionProvider(PermissionProvider):
    name = "v4"

    def __init__(
        self,
        client: V4Client,
        *,
        codec: BklogNameCodec | None = None,
        batch_chunk_size: int | None = None,
    ) -> None:
        self.client = client
        self.codec = codec or BklogNameCodec()
        self.batch_chunk_size = batch_chunk_size or client.options.batch_chunk_size

    @classmethod
    def from_settings(cls, *, username: str, bk_tenant_id: str) -> V4PermissionProvider:
        options = V4Options.from_settings()
        client = V4Client(options, username=username, bk_tenant_id=bk_tenant_id)
        return cls(client)

    def is_allowed(self, request: AuthRequest) -> AuthResult:
        subject = self._build_subject(request)
        action_id = self.codec.encode_action(to_definition_id(request.action_id))
        try:
            if request.resources:
                resource = self.codec.encode_resource_for_auth(request.resources[0])
                allowed = self.client.direct_auth(subject=subject, action_id=action_id, resource=resource)
            else:
                allowed = self.client.direct_auth(subject=subject, action_id=action_id)
        except V4ClientError as error:
            return AuthResult.error(
                provider_name=self.name,
                reason=error.reason,
                error_type=error.error_type,
            )

        if allowed:
            return AuthResult.allow(provider_name=self.name)
        return AuthResult.deny(provider_name=self.name)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        subject = self._build_subject(request)
        resources_by_id = self._collect_resources(request)
        items: list[BatchAuthResultItem] = []

        for action_ref in request.action_ids:
            action_id = to_definition_id(action_ref)
            encoded_action_id = self.codec.encode_action(action_id)
            matched_resources = self._resources_for_action(action_ref, resources_by_id)
            action = get_action_by_id(action_ref)

            if action.related_resource_types and not matched_resources:
                items.extend(
                    [
                        BatchAuthResultItem(
                            action_id,
                            resource_id,
                            AuthResult.error(
                                self.name,
                                reason=f"missing resource for action={action_id}",
                                error_type="IncompleteBatchResult",
                            ),
                        )
                        for current_action_id, resource_id in request.iter_keys()
                        if current_action_id == action_id
                    ]
                )
                continue

            if not matched_resources:
                try:
                    allowed = self.client.direct_auth(subject=subject, action_id=encoded_action_id)
                except V4ClientError as error:
                    items.extend(self._error_items_for_action(action_id, request, error))
                    continue

                for resource_id in self._resource_ids_for_action(action_id, request):
                    result = AuthResult.allow(self.name) if allowed else AuthResult.deny(self.name)
                    items.append(BatchAuthResultItem(action_id, resource_id, result))
                continue

            encoded_resources = [self.codec.encode_resource_for_auth(resource) for resource in matched_resources]
            action_results: dict[str, AuthResult] = {}
            for chunk in _chunked(encoded_resources, self.batch_chunk_size):
                try:
                    chunk_results = self.client.direct_auth_by_resources(
                        subject=subject,
                        action_id=encoded_action_id,
                        resources=chunk,
                    )
                except V4ClientError as error:
                    for resource in chunk:
                        action_results[str(resource["id"])] = AuthResult.error(
                            self.name,
                            reason=error.reason,
                            error_type=error.error_type,
                        )
                    continue

                for resource_id, allowed in chunk_results.items():
                    action_results[resource_id] = AuthResult.allow(self.name) if allowed else AuthResult.deny(self.name)

            for resource_id in self._resource_ids_for_action(action_id, request):
                result = action_results.get(resource_id)
                if result is None:
                    result = AuthResult.error(
                        self.name,
                        reason=f"missing IAM V4 batch result for action={action_id}, resource={resource_id}",
                        error_type="IncompleteBatchResult",
                    )
                items.append(BatchAuthResultItem(action_id, resource_id, result))

        return BatchAuthResult(items=tuple(items))

    def get_apply_data(
        self,
        actions: list[ActionMeta | str],
        resources: list[Resource] | None = None,
    ) -> tuple[dict[str, Any], str]:
        resources = resources or []
        permissions = []
        for action in actions:
            action = get_action_by_id(action)
            encoded_action_id = self.codec.encode_action(action.id)
            permission: dict[str, Any] = {"action_id": encoded_action_id, "resources": []}
            if action.related_resource_types and resources:
                for resource in resources:
                    engine_resource = self._from_iam_resource(resource)
                    permission["resources"].append(self.codec.encode_resource_for_apply(engine_resource))
            permissions.append(permission)

        try:
            apply_url = self.client.generate_perm_apply_url(permissions=permissions)
        except V4ClientError as error:
            raise RuntimeError(error.reason) from error

        return (
            {
                "provider": self.name,
                "system_id": self.client.options.system_id,
                "permissions": permissions,
            },
            apply_url,
        )

    @staticmethod
    def _build_subject(request: AuthRequest | BatchAuthRequest) -> dict[str, str]:
        return {"type": request.subject.type, "id": request.subject.id}

    @staticmethod
    def _collect_resources(request: BatchAuthRequest) -> dict[str, ResourceInstance]:
        resources: dict[str, ResourceInstance] = {}
        for resource_group in request.resource_groups:
            resource = resource_group[0]
            resources[str(resource.id)] = resource
        return resources

    def _resources_for_action(
        self,
        action_ref: ActionMeta | str,
        resources_by_id: dict[str, ResourceInstance],
    ) -> list[ResourceInstance]:
        action = get_action_by_id(action_ref)
        if not action.related_resource_types:
            return []

        allowed_types = {resource_type.id for resource_type in action.related_resource_types}
        matched = []
        for resource in resources_by_id.values():
            resource_type = self.codec.encode_resource_type(to_definition_id(resource.type))
            if resource_type in allowed_types:
                matched.append(resource)
        return matched

    @staticmethod
    def _resource_ids_for_action(action_id: str, request: BatchAuthRequest) -> list[str]:
        return [resource_id for current_action_id, resource_id in request.iter_keys() if current_action_id == action_id]

    def _error_items_for_action(
        self,
        action_id: str,
        request: BatchAuthRequest,
        error: V4ClientError,
    ) -> list[BatchAuthResultItem]:
        result = AuthResult.error(self.name, reason=error.reason, error_type=error.error_type)
        return [
            BatchAuthResultItem(action_id, resource_id, result)
            for current_action_id, resource_id in request.iter_keys()
            if current_action_id == action_id
        ]

    @staticmethod
    def _from_iam_resource(resource: Resource) -> ResourceInstance:
        attributes = dict(resource.attribute or {})
        return ResourceInstance(
            system=resource.system,
            type=resource.type,
            id=str(resource.id),
            name=attributes.get("name", ""),
            attributes=attributes,
        )
