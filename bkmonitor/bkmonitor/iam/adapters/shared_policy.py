"""Monitor value-object adapter for the shared BKLog migration engine.

Actions, codecs, resolvers and query-policy ASTs remain Monitor-owned. Decision
and scope merging are exclusively implemented by the shared engine.
"""

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.core.requests import AuthRequest as SharedRequest, BatchAuthRequest, Subject as SharedSubject
from iam_engine.core.types import AuthResult, AuthorizedResourceScope
from iam_engine.core.types import BatchAuthResult as SharedBatchResult, BatchAuthResultItem
from iam_engine.provider.bundle import ProviderBundle
from iam_engine.provider.composition.union import UnionDecisionPolicy, UnionScopePolicy
from iam_engine.provider.router import ModeRouter

from ..iam_engine.core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByResourceRequest,
    ResourceAuthResult,
    Subject,
    VisibleResult,
    to_action_id,
)
from ..iam_engine.provider.composition.base import CompositionPolicy


def _subject(subject):
    return SharedSubject(id=subject.id, type=subject.type, tenant_id=subject.tenant_id, attributes=subject.attributes)


def _result(provider, call):
    try:
        value = call()
        if value is True:
            return AuthResult.allow(provider.name)
        if value is False:
            return AuthResult.deny(provider.name)
        return AuthResult.error(provider.name, "provider returned a non-boolean decision", "InvalidProviderResult")
    except Exception as error:
        return AuthResult.error(provider.name, str(error) or type(error).__name__, type(error).__name__)


class MonitorAuthAdapter:
    """Translate requests/results only; never combine provider decisions here."""

    def __init__(self, provider):
        self.provider = provider

    def is_allowed(self, request):
        subject = Subject(
            id=request.subject.id,
            type=request.subject.type,
            tenant_id=request.subject.tenant_id,
            attributes=request.subject.attributes,
        )
        resources = request.resources
        if len(resources) > 1:
            raise ValueError("Monitor single authorization requires at most one resource")
        return _result(
            self.provider,
            lambda: self.provider.is_allowed(
                AuthRequest(
                    subject=subject,
                    action_id=request.action_id,
                    resource=resources[0] if resources else None,
                    environment=request.environment,
                )
            ),
        )

    def batch_is_allowed(self, request):
        items = []
        subject = Subject(
            id=request.subject.id,
            type=request.subject.type,
            tenant_id=request.subject.tenant_id,
            attributes=request.subject.attributes,
        )
        for action_id in request.action_ids:
            resources = tuple(group[0] for group in request.resource_groups)
            try:
                result = self.provider.batch_by_resource(
                    BatchByResourceRequest(
                        subject=subject,
                        action_id=action_id,
                        resources=resources,
                        environment=request.environment,
                    )
                )
                returned = {(item.action_id, item.resource_id): item.allowed for item in result.items}
                for resource in resources:
                    key = (to_action_id(action_id), str(resource.id))
                    value = returned.get(key)
                    decision = (
                        AuthResult.allow(self.provider.name)
                        if value is True
                        else AuthResult.deny(self.provider.name)
                        if value is False
                        else AuthResult.error(self.provider.name, "missing batch result", "IncompleteBatchResult")
                    )
                    items.append(BatchAuthResultItem(key[0], key[1], decision))
            except Exception as error:
                items.extend(
                    BatchAuthResultItem(
                        to_action_id(action_id),
                        str(resource.id),
                        AuthResult.error(
                            self.provider.name,
                            str(error) or type(error).__name__,
                            type(error).__name__,
                        ),
                    )
                    for resource in resources
                )
        return SharedBatchResult(tuple(items))


class SharedMigrationPolicy(CompositionPolicy):
    """Compatibility façade for Monitor consumers, backed by shared ModeRouter."""

    def __init__(self, providers, *, mode_provider):
        super().__init__(providers)
        self.mode_provider = mode_provider
        self.router = ModeRouter(
            mode_provider,
            {AuthMode(provider.name): ProviderBundle(auth=MonitorAuthAdapter(provider)) for provider in providers},
            pair_executor=lambda left, right: (left(), right()),
        )

    def _selected(self, resources=(), *, application=False):
        mode = self.mode_provider.get_mode(resources)
        modes = DEFAULT_DUAL_STACK.application_candidates(mode) if application else DEFAULT_DUAL_STACK.modes_for(mode)
        return [self.get_provider(item.value) for item in modes if any(p.name == item.value for p in self.providers)]

    def is_allowed(self, request):
        return self.decide(request).allowed

    def decide(self, request):
        return self.router.is_allowed(
            SharedRequest(
                subject=_subject(request.subject),
                action_id=request.action_id,
                resources=(request.resource,) if request.resource is not None else (),
                environment=request.environment,
            )
        )

    def batch_by_resource(self, request):
        if not request.resources:
            return BatchAuthResult()
        result = self.router.batch_is_allowed(
            BatchAuthRequest(
                subject=_subject(request.subject),
                action_ids=(request.action_id,),
                resource_groups=tuple((resource,) for resource in request.resources),
                environment=request.environment,
            )
        )
        resource_types = {str(r.id): r.type for r in request.resources}
        return BatchAuthResult(
            tuple(
                ResourceAuthResult(
                    item.action_id,
                    resource_types[item.resource_id],
                    item.resource_id,
                    item.decision.allowed,
                )
                for item in result.items
            )
        )

    def batch_by_action(self, request):
        # Resource-free actions cannot be represented by BatchAuthRequest's nonempty groups.
        # Snapshot the mode once, including invalid-mode rejection, for the entire batch.
        try:
            mode = self.mode_provider.get_mode((request.resource,) if request.resource else ())
        except InvalidAuthModeError:
            return BatchAuthResult(
                tuple(
                    ResourceAuthResult(
                        to_action_id(a),
                        request.resource.type if request.resource else "",
                        str(request.resource.id) if request.resource else "",
                        False,
                    )
                    for a in request.action_ids
                )
            )

        class Snapshot:
            def get_mode(self, resources=()):
                return mode

        router = ModeRouter(Snapshot(), self.router.bundles, pair_executor=self.router.pair_executor)
        return BatchAuthResult(
            tuple(
                ResourceAuthResult(
                    to_action_id(action),
                    request.resource.type if request.resource else "",
                    str(request.resource.id) if request.resource else "",
                    router.is_allowed(
                        SharedRequest(
                            subject=_subject(request.subject),
                            action_id=action,
                            resources=(request.resource,) if request.resource else (),
                            environment=request.environment,
                        )
                    ).allowed,
                )
                for action in request.action_ids
            )
        )

    def get_apply_url(self, request):
        for provider in self._selected(request.resources, application=True):
            try:
                url = provider.get_apply_url(request)
                if url:
                    return url
            except Exception:
                continue
        return ""

    def get_apply_data(self, action_ids, resources, subject):
        for provider in self._selected(tuple(resources), application=True):
            try:
                data = provider.get_apply_data(action_ids, resources, subject)
                if data:
                    return data
            except Exception:
                continue
        return None

    def has_any_permission(self, subject, action_id):
        try:
            providers = self._selected()
        except InvalidAuthModeError:
            return False
        return UnionDecisionPolicy.decide(
            tuple(_result(p, lambda p=p: p.has_any_permission(subject, action_id)) for p in providers)
        ).allowed

    def filter_visible_resources(self, subject, action_id, candidates):
        if not candidates:
            return VisibleResult()
        try:
            providers = self._selected(candidates)
        except InvalidAuthModeError:
            return VisibleResult()
        if not providers:
            return VisibleResult()
        scopes = []
        resource_type = candidates[0].type
        for provider in providers:
            try:
                result = provider.filter_visible_resources(subject, action_id, candidates)
                scopes.append(
                    AuthorizedResourceScope.wildcard(resource_type, provider_name=provider.name)
                    if result.all_granted
                    else AuthorizedResourceScope.concrete(
                        resource_type, set(result.visible_ids), provider_name=provider.name
                    )
                )
            except Exception as error:
                scopes.append(
                    AuthorizedResourceScope.error(
                        resource_type,
                        provider_name=provider.name,
                        reason=str(error) or type(error).__name__,
                        error_type=type(error).__name__,
                    )
                )
        scope = UnionScopePolicy.merge(tuple(scopes))
        return VisibleResult(scope.is_wildcard, tuple(str(r.id) for r in candidates if str(r.id) in scope.ids))

    def query_policies(self, subject, action_id):
        return self._query("query_policy", subject, action_id)

    def _query(self, method, subject, action_id):
        results, errors = [], []
        for provider in self._selected():
            try:
                value = getattr(provider, method)(subject, action_id)
                if value is not None:
                    results.append(value)
            except Exception as error:
                errors.append(error)
        if errors and not results:
            raise errors[0]
        return results

    def query_policies_by_actions(self, subject, action_ids):
        results = {to_action_id(action): [] for action in action_ids}
        errors, succeeded = [], False
        for provider in self._selected():
            try:
                values = provider.query_policy_by_actions(subject, action_ids)
                succeeded = True
                for action_id, expression in values.items():
                    if expression is not None and action_id in results:
                        results[action_id].append(expression)
            except Exception as error:
                errors.append(error)
        if errors and not succeeded:
            raise errors[0]
        return results
