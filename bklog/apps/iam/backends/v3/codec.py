from __future__ import annotations

from iam import Action, MultiActionRequest, Request, Resource, Subject

from apps.iam.iam_engine.core.requests import (
    AuthRequest,
    BatchAuthRequest,
    DefinitionRef,
    ResourceInstance,
    Subject as EngineSubject,
    to_definition_id,
)


class V3RequestCodec:
    """把引擎请求编码成 IAM V3 SDK 的请求对象。"""

    def __init__(self, system_id: str) -> None:
        self.system_id = system_id

    def encode_subject(self, subject: EngineSubject) -> Subject:
        return Subject(subject.type, subject.id)

    def encode_action(self, action_ref: DefinitionRef) -> Action:
        return Action(to_definition_id(action_ref))

    def encode_resource(self, resource: ResourceInstance) -> Resource:
        attributes = dict(resource.attributes)
        if resource.name:
            attributes.setdefault("name", resource.name)

        return Resource(
            resource.system or self.system_id,
            to_definition_id(resource.type),
            str(resource.id),
            attributes,
        )

    def encode_auth_request(self, request: AuthRequest) -> Request:
        return Request(
            system=self.system_id,
            subject=self.encode_subject(request.subject),
            action=self.encode_action(request.action_id),
            resources=[self.encode_resource(resource) for resource in request.resources],
            environment=dict(request.environment) or None,
        )

    def encode_batch_request(self, request: BatchAuthRequest) -> MultiActionRequest:
        return MultiActionRequest(
            system=self.system_id,
            subject=self.encode_subject(request.subject),
            actions=[self.encode_action(action_id) for action_id in request.action_ids],
            resources=[],
            environment=dict(request.environment) or None,
        )

    def encode_resource_groups(self, request: BatchAuthRequest) -> list[list[Resource]]:
        return [
            [self.encode_resource(resource) for resource in resource_group]
            for resource_group in request.resource_groups
        ]
