from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

from django.conf import settings

from apps.iam.backends.v4.apply import build_apply_data
from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.codec import BklogNameCodec, V4ResourceCodec
from apps.iam.backends.v4.concurrency import map_chunks_concurrently
from apps.iam.backends.v4.config import V4Options, normalize_batch_chunk_size, normalize_batch_max_workers
from apps.iam.backends.v4.exceptions import V4ClientError
from apps.iam.iam_engine.core.requests import (
    ActionDefinition,
    AuthRequest,
    BatchAuthRequest,
    DefinitionRef,
    ResourceInstance,
    ResourceTypeDefinition,
    to_definition_id,
)
from apps.iam.iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem, AuthorizedResourceScope
from apps.iam.iam_engine.provider.base import PermissionProvider


WILDCARD_RESOURCE_ID = "*"


class V4PermissionProvider(PermissionProvider):
    name = "v4"
    # IAM V4 的 authorized-resources 直接返回完整范围，不需要调用方预先加载候选。
    requires_candidate_ids = False

    def __init__(
        self,
        client: V4Client,
        *,
        codec: V4ResourceCodec | None = None,
        action_resolver: Callable[[str], ActionDefinition] | None = None,
        batch_chunk_size: int | None = None,
        batch_max_workers: int | None = None,
    ) -> None:
        self.client = client
        self.codec = codec or BklogNameCodec()
        self.action_resolver = action_resolver
        configured_chunk_size = client.options.batch_chunk_size if batch_chunk_size is None else batch_chunk_size
        self.batch_chunk_size = normalize_batch_chunk_size(configured_chunk_size)
        configured_workers = client.options.batch_max_workers if batch_max_workers is None else batch_max_workers
        self.batch_max_workers = normalize_batch_max_workers(configured_workers)

    @classmethod
    def from_settings(
        cls,
        *,
        username: str,
        bk_tenant_id: str,
        action_resolver: Callable[[str], ActionDefinition] | None = None,
    ) -> V4PermissionProvider:
        options = V4Options.from_settings()
        client = V4Client(options, username=username, bk_tenant_id=bk_tenant_id)
        return cls(client, action_resolver=action_resolver)

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
        action_refs = list(request.action_ids)
        # 多 Action 已在外层并发，内层分片改为串行，避免线程池成倍嵌套。
        chunk_max_workers = self.batch_max_workers if len(action_refs) == 1 else 1
        per_action_items = map_chunks_concurrently(
            action_refs,
            lambda action_ref: self._batch_auth_one_action(
                subject=subject,
                action_ref=action_ref,
                request=request,
                resources_by_id=resources_by_id,
                chunk_max_workers=chunk_max_workers,
            ),
            max_workers=self.batch_max_workers,
        )
        items = [item for action_items in per_action_items for item in action_items]
        return BatchAuthResult(items=tuple(items))

    def _batch_auth_one_action(
        self,
        *,
        subject: dict[str, str],
        action_ref: DefinitionRef,
        request: BatchAuthRequest,
        resources_by_id: dict[str, ResourceInstance],
        chunk_max_workers: int,
    ) -> list[BatchAuthResultItem]:
        # apps.utils.db 在模块级导入了 feature_toggle 模型，而本模块由 apps.iam 的 AppConfig 在应用加载前导入
        from apps.utils.db import array_chunk

        action_id = to_definition_id(action_ref)
        encoded_action_id = self.codec.encode_action(action_id)
        action = self._resolve_action(action_ref)
        matched_resources = self._resources_for_action(action_ref, resources_by_id)

        if action.related_resource_types and not matched_resources:
            return [
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

        if not matched_resources:
            try:
                allowed = self.client.direct_auth(subject=subject, action_id=encoded_action_id)
            except V4ClientError as error:
                return list(self._error_items_for_action(action_id, request, error))

            return [
                BatchAuthResultItem(
                    action_id,
                    resource_id,
                    AuthResult.allow(self.name) if allowed else AuthResult.deny(self.name),
                )
                for resource_id in self._resource_ids_for_action(action_id, request)
            ]

        encoded_resources = [self.codec.encode_resource_for_auth(resource) for resource in matched_resources]
        encoded_to_local_id = {
            encoded["id"]: str(resource.id) for resource, encoded in zip(matched_resources, encoded_resources)
        }
        chunks = array_chunk(encoded_resources, self.batch_chunk_size)
        action_results: dict[str, AuthResult] = {}

        def _auth_chunk(chunk: list[dict[str, Any]]) -> dict[str, AuthResult]:
            chunk_action_results: dict[str, AuthResult] = {}
            try:
                chunk_results = self.client.direct_auth_by_resources(
                    subject=subject,
                    action_id=encoded_action_id,
                    resources=chunk,
                )
            except V4ClientError as error:
                for resource in chunk:
                    local_resource_id = encoded_to_local_id[str(resource["id"])]
                    chunk_action_results[local_resource_id] = AuthResult.error(
                        self.name,
                        reason=error.reason,
                        error_type=error.error_type,
                    )
                return chunk_action_results

            for resource_id, allowed in chunk_results.items():
                local_resource_id = encoded_to_local_id[resource_id]
                chunk_action_results[local_resource_id] = (
                    AuthResult.allow(self.name) if allowed else AuthResult.deny(self.name)
                )
            return chunk_action_results

        for chunk_results in map_chunks_concurrently(
            chunks,
            _auth_chunk,
            max_workers=chunk_max_workers,
        ):
            action_results.update(chunk_results)

        items: list[BatchAuthResultItem] = []
        for resource_id in self._resource_ids_for_action(action_id, request):
            result = action_results.get(resource_id)
            if result is None:
                result = AuthResult.error(
                    self.name,
                    reason=f"missing IAM V4 batch result for action={action_id}, resource={resource_id}",
                    error_type="IncompleteBatchResult",
                )
            items.append(BatchAuthResultItem(action_id, resource_id, result))
        return items

    def list_authorized_resources(
        self,
        *,
        action_id: str,
        resource_type: str = "space",
        subject: dict[str, str] | None = None,
        candidate_ids: frozenset[str] | None = None,
    ) -> AuthorizedResourceScope:
        # V4 由 IAM 直接返回完整授权范围，候选集只用于调用方后续求交，这里忽略。
        del candidate_ids
        encoded_action_id = self.codec.encode_action(to_definition_id(action_id))
        encoded_resource_type = self.codec.encode_resource_type(resource_type)
        request_subject = subject or {"type": "user", "id": self.client.username}
        if not str(request_subject.get("id") or "").strip():
            return AuthorizedResourceScope.error(
                encoded_resource_type,
                provider_name=self.name,
                reason="IAM V4 authorized-resources requires a non-empty subject id",
                error_type="InvalidSubject",
            )
        try:
            payload = self.client.list_authorized_resource(
                subject=request_subject,
                action_id=encoded_action_id,
                resource_type=encoded_resource_type,
            )
        except V4ClientError as error:
            return AuthorizedResourceScope.error(
                encoded_resource_type,
                provider_name=self.name,
                reason=error.reason,
                error_type=error.error_type,
            )

        ids = payload.get("ids") or []
        if ids == [WILDCARD_RESOURCE_ID]:
            return AuthorizedResourceScope.wildcard(encoded_resource_type, provider_name=self.name)
        if not ids:
            return AuthorizedResourceScope.empty(encoded_resource_type, provider_name=self.name)
        decoded_ids = {self.codec.decode_resource_id(encoded_resource_type, resource_id) for resource_id in ids}
        return AuthorizedResourceScope.concrete(encoded_resource_type, decoded_ids, provider_name=self.name)

    def get_apply_data(
        self,
        actions: list[ActionDefinition | str],
        resources: list[ResourceInstance] | None = None,
    ) -> tuple[dict[str, Any], str]:
        resources = resources or []
        permissions = []
        action_resources: list[tuple[ActionDefinition, list[ResourceInstance]]] = []
        for action_ref in actions:
            action = self._resolve_action(action_ref)
            encoded_action_id = self.codec.encode_action(action.id)
            permission: dict[str, Any] = {"action_id": encoded_action_id, "resources": []}
            matched_resources = self._match_resources(action.related_resource_types, resources)
            permission["resources"].extend(
                self.codec.encode_resource_for_apply(resource) for resource in matched_resources
            )
            permissions.append(permission)
            action_resources.append((action, matched_resources))

        try:
            apply_url = self.client.generate_perm_apply_url(permissions=permissions)
        except V4ClientError as error:
            raise RuntimeError(error.reason) from error

        # 展示数据与 V3 同构，前端不需要区分当前是哪一代；permissions 只用于生成 apply_url，
        # 属于发给 IAM 的请求体，留在日志里即可，不进对外的无权限响应。
        apply_data = build_apply_data(
            system_id=self.client.options.system_id,
            system_name=settings.BK_IAM_SYSTEM_NAME,
            codec=self.codec,
            action_resources=action_resources,
        )
        return {"provider": self.name, **apply_data}, apply_url

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
        action_ref: DefinitionRef,
        resources_by_id: dict[str, ResourceInstance],
    ) -> list[ResourceInstance]:
        action = self._resolve_action(action_ref)
        if not action.related_resource_types:
            return []

        return self._match_resources(action.related_resource_types, list(resources_by_id.values()))

    def _resolve_action(self, action_ref: DefinitionRef) -> ActionDefinition:
        if isinstance(action_ref, str):
            if self.action_resolver is None:
                raise ValueError(f"action resolver is required for action={action_ref}")
            return self.action_resolver(action_ref)
        return cast(ActionDefinition, action_ref)

    def _match_resources(
        self,
        related_resource_types: Sequence[ResourceTypeDefinition],
        resources: list[ResourceInstance],
    ) -> list[ResourceInstance]:
        if not related_resource_types:
            return []

        allowed_resources = {
            (resource_type.system_id, self.codec.encode_resource_type(resource_type.id))
            for resource_type in related_resource_types
        }
        return [
            resource
            for resource in resources
            if (resource.system, self.codec.encode_resource_type(to_definition_id(resource.type))) in allowed_resources
        ]

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
