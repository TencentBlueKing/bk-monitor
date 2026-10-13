"""Monitor value-object adapter for the shared BKLog migration engine.

Actions, codecs, resolvers and query-policy ASTs remain Monitor-owned. Decision
and scope merging are exclusively implemented by the shared engine.
"""

from iam_engine.core.requests import Subject as SharedSubject
from iam_engine.core.types import AuthResult
from iam_engine.core.types import BatchAuthResult as SharedBatchResult, BatchAuthResultItem

from iam_engine.provider.requests import (
    AuthRequest,
    BatchByResourceRequest,
    Subject,
    to_action_id,
)


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
