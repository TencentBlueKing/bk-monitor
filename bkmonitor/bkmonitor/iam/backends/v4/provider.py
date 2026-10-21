"""Monitor V4 capabilities, directly implementing the same Provider contract as BKLog."""

from __future__ import annotations
import logging
from bkmonitor.iam.action import canonicalize_action_id
from iam_engine.core.requests import AuthRequest, BatchAuthRequest, to_definition_id
from iam_engine.core.types import AuthStatus, AuthResult, BatchAuthResult, BatchAuthResultItem, AuthorizedResourceScope
from iam_engine.provider.base import PermissionProvider
from iam_engine.provider.requests import VisibleResult, to_action_id
from iam_engine.exceptions import ProviderUnavailable
from iam_engine.utils import chunked
from bkmonitor.iam.concurrency import map_chunks_concurrently
from bkmonitor.iam.backends.v4.apply import V4ApplicationBuilder

logger = logging.getLogger(__name__)


class V4PermissionProvider(PermissionProvider):
    name = "v4"
    requires_candidate_ids = False

    def __init__(
        self,
        client,
        *,
        codec,
        schema,
        resolver=None,
        client_factory=None,
        system_id,
        tenant_id="system",
        username="",
        batch_chunk_size=20,
        batch_max_workers=4,
    ):
        self._client_instance = client
        self.client_factory = client_factory
        self.schema = schema
        self.codec = codec
        self.resolver = resolver
        self.tenant_id = tenant_id
        self.username = username
        self.system_id = system_id
        self.batch_chunk_size = batch_chunk_size
        self.batch_max_workers = batch_max_workers
        self.application_builder = V4ApplicationBuilder(self)

    @property
    def client(self):
        return self._get_client("")

    def _get_client(self, tenant_id=""):
        if self.client_factory is not None:
            return self.client_factory(tenant_id)
        return self._client_instance

    def _resolve(self, resource, *, tenant_id=""):
        if self.resolver is None:
            return resource
        return self.resolver.resolve(resource, tenant_id=tenant_id or self.tenant_id)

    def get_apply_data(self, actions, resources=None):
        return self.application_builder.get_apply_data(actions, resources or [])

    def _action_has_resource(self, action_id):
        return bool(self.schema.actions[canonicalize_action_id(to_definition_id(action_id))].resource_type)

    @staticmethod
    def _decision(name, allowed):
        if allowed is True:
            return AuthResult.allow(name)
        if allowed is False:
            return AuthResult.deny(name)
        return AuthResult.error(name, "provider returned a non-boolean decision", "InvalidProviderResult")

    def _error(self, error):
        return AuthResult.error(self.name, str(error) or type(error).__name__, type(error).__name__)

    @property
    def _client(self):
        return self.client

    def is_allowed(self, request: AuthRequest) -> AuthResult:
        try:
            if len(request.resources) > 1:
                raise ValueError("Monitor authorization requires at most one resource")
            client = self._get_client(request.subject.tenant_id)
            resource = (
                self.codec.encode_resource_for_auth(
                    self._resolve(request.resources[0], tenant_id=request.subject.tenant_id)
                )
                if request.resources and self._action_has_resource(request.action_id)
                else None
            )
            result = client.direct_auth(
                subject={"type": request.subject.type, "id": request.subject.id},
                action_id=self.codec.encode_action(canonicalize_action_id(to_definition_id(request.action_id))),
                resource=resource,
            )
            return self._decision(self.name, result)
        except Exception as error:
            return self._error(error)

    def batch_is_allowed(self, request: BatchAuthRequest) -> BatchAuthResult:
        items = []
        for action_ref in request.action_ids:
            action_id = canonicalize_action_id(to_definition_id(action_ref))
            groups = request.resource_groups
            try:
                if any(len(g) != 1 for g in groups):
                    raise ValueError("Monitor authorization requires one resource per group")
                client = self._get_client(request.subject.tenant_id)
                if not self._action_has_resource(action_id):
                    decision = self._decision(
                        self.name,
                        client.direct_auth(
                            subject={"type": request.subject.type, "id": request.subject.id},
                            action_id=self.codec.encode_action(action_id),
                        ),
                    )
                    items.extend(BatchAuthResultItem(action_id, str(g[0].id), decision) for g in groups)
                    continue
                resources = [
                    self.codec.encode_resource_for_auth(self._resolve(g[0], tenant_id=request.subject.tenant_id))
                    for g in groups
                ]
            except Exception as error:
                items.extend(BatchAuthResultItem(action_id, str(g[0].id), self._error(error)) for g in groups)
                continue

            def check_page(page_indices):
                page_items = []
                page = [resources[i] for i in page_indices]
                try:
                    raw = client.direct_auth_by_resources(
                        subject={"type": request.subject.type, "id": request.subject.id},
                        action_id=self.codec.encode_action(action_id),
                        resources=page,
                    )
                    for index in page_indices:
                        rid = resources[index]["id"]
                        result = (
                            self._decision(self.name, raw[rid])
                            if rid in raw
                            else AuthResult.error(
                                self.name,
                                f"missing IAM V4 batch result for action={action_id}, resource={rid}",
                                "IncompleteBatchResult",
                            )
                        )
                        page_items.append(BatchAuthResultItem(action_id, str(groups[index][0].id), result))
                except Exception as error:
                    page_items.extend(
                        BatchAuthResultItem(action_id, str(groups[i][0].id), self._error(error)) for i in page_indices
                    )
                return page_items

            pages = list(chunked(tuple(range(len(resources))), self.batch_chunk_size))
            for page_result in map_chunks_concurrently(pages, check_page, max_workers=self.batch_max_workers):
                items.extend(page_result)
        return BatchAuthResult(tuple(items))

    def list_authorized_resources(self, *, action_id, resource_type="space", subject=None, candidate_ids=None):
        request_subject = subject or {"type": "user", "id": self.username}
        try:
            raw = self.client.list_authorized_resource(
                subject=request_subject,
                action_id=self.codec.encode_action(canonicalize_action_id(to_definition_id(action_id))),
                resource_type=self.codec.encode_resource_type(resource_type),
            )
        except Exception as error:
            return AuthorizedResourceScope.error(
                resource_type, provider_name=self.name, reason=str(error), error_type=type(error).__name__
            )
        ids = raw.get("ids", [])
        if "*" in ids:
            return AuthorizedResourceScope.wildcard(resource_type, provider_name=self.name)
        return AuthorizedResourceScope.concrete(
            resource_type, {self.codec.decode_resource_id(resource_type, i) for i in ids}, provider_name=self.name
        )

    def has_any_permission(self, subject, action_id):
        action = self.schema.actions[canonicalize_action_id(to_action_id(action_id))]
        if not action.resource_type:
            result = self.is_allowed(AuthRequest(subject, action_id))
            if result.status is AuthStatus.ERROR:
                raise ProviderUnavailable(result.reason)
            return result.allowed
        resource_type = action.resource_type
        while self.schema.resource_types[resource_type].ancestor:
            resource_type = self.schema.resource_types[resource_type].ancestor
        scope = self.list_authorized_resources(
            action_id=action_id, resource_type=resource_type, subject={"type": subject.type, "id": subject.id}
        )
        if not scope.ok:
            raise ProviderUnavailable(scope.reason)
        return scope.is_wildcard or bool(scope.ids)

    def filter_visible_resources(self, subject, action_id, candidates):
        if not candidates:
            return VisibleResult()
        resource_type = canonicalize_action_id(to_definition_id(candidates[0].type))
        if not self.schema.resource_types[resource_type].ancestor:
            scope = self.list_authorized_resources(
                action_id=action_id, resource_type=resource_type, subject={"type": subject.type, "id": subject.id}
            )
            if not scope.ok:
                raise ProviderUnavailable(scope.reason)
            return VisibleResult(scope.is_wildcard, tuple(r.id for r in candidates if str(r.id) in scope.ids))
        result = self.batch_is_allowed(BatchAuthRequest(subject, (action_id,), tuple((r,) for r in candidates)))
        if any(item.result.status is AuthStatus.ERROR for item in result.items):
            raise ProviderUnavailable("IAM V4 resource visibility query failed")
        return VisibleResult(False, tuple(item.resource_id for item in result.items if item.result.allowed))

    def health_check(self) -> dict:
        """探活检查。

        调用 v4 平台 retrieve_system 验证连通性和系统注册状态。

        Returns:
            dict: ``{"status": "ok"|"error", "provider": "v4", ...}``
        """
        try:
            system = self._client.retrieve_system()
            if system is None:
                return {"status": "error", "provider": self.name, "error": "system is not registered"}
            return {
                "status": "ok",
                "provider": self.name,
                "remote_id": system.get("id", ""),
            }
        except Exception as e:
            return {"status": "error", "provider": self.name, "error": str(e)[:200]}
