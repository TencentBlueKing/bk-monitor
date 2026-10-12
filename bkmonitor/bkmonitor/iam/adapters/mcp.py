"""MCP's SDK-shaped envelopes are routed through the same migration policy.

No IAM SDK network client is created here. A degraded rejection must not trigger
the MCP native-permission fallback; an explicit union ALLOW still wins.
"""

from ..iam_engine.core.exceptions import ProviderUnavailable
from ..iam_engine.core.types import ApplyURLRequest, AuthRequest, ResourceInstance, Subject
from .v3.codec import MonitorV3Codec


class MonitorMCPClient:
    def __init__(self, framework, tenant_id):
        self.framework = framework
        self.tenant_id = tenant_id
        self.codec = MonitorV3Codec()

    @staticmethod
    def resource(resource):
        attributes = resource.attribute or {}
        # Keep the trusted instance scope; the product resolver supplies parents.
        return ResourceInstance(
            type=resource.type,
            id=str(resource.id),
            system=resource.system,
            name=attributes.get("name", ""),
            attributes=attributes,
        )

    def is_allowed(self, query):
        if len(query.resources) > 1:
            raise ValueError("MCP checks exactly one resource")
        decision = self.framework.router.decide(
            AuthRequest(
                subject=Subject(id=query.subject.id, tenant_id=self.tenant_id),
                action_id=self.codec.decode_action(query.action.id),
                resource=self.resource(query.resources[0]) if query.resources else None,
                environment=query.environment or {},
            )
        )
        if not decision.allowed and decision.degraded:
            raise ProviderUnavailable("IAM could not return an explicit denial")
        return decision.allowed

    def _application_request(self, application):
        data = application.to_dict()
        action_ids, resources = [], []
        for action in data["actions"]:
            action_ids.append(self.codec.decode_action(action["id"]))
            for related in action.get("related_resource_types", []):
                for nodes in related.get("instances", []):
                    if nodes:
                        node = nodes[-1]
                        resources.append(
                            ResourceInstance(
                                type=node["type"],
                                id=str(node["id"]),
                                name=node.get("name", ""),
                                system=related["system_id"],
                                ancestor_chain=tuple(
                                    ResourceInstance(type=p["type"], id=str(p["id"]), name=p.get("name", ""))
                                    for p in nodes[:-1]
                                ),
                            )
                        )
        return ApplyURLRequest(
            subject=Subject(id="", tenant_id=self.tenant_id),
            action_ids=tuple(action_ids),
            resources=tuple(resources),
        )

    def get_apply_data(self, application):
        request = self._application_request(application)
        return self.framework.get_apply_data(list(request.action_ids), list(request.resources), request.subject)

    def get_apply_url(self, application):
        url = self.framework.get_apply_url(self._application_request(application))
        return bool(url), "", url
