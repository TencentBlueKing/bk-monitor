"""V3 product application data; same tuple capability as BKLog."""

import logging

from iam.apply.models import (
    ActionWithoutResources,
    ActionWithResources,
    Application,
    RelatedResourceType,
    ResourceInstance,
    ResourceNode,
)
from iam.utils import gen_perms_apply_data
from bkmonitor.iam.action import canonicalize_action_id
from iam_engine.core.requests import to_definition_id

logger = logging.getLogger(__name__)


class V3ApplicationBuilder:
    def __init__(self, provider):
        self.provider = provider

    def get_apply_data(self, actions, resources):
        p = self.provider
        client = p.client
        from iam import meta

        meta.setup_system(p.system_id, p._cfg.system.name)
        for resource_type in p.schema.resource_types.values():
            system_id = resource_type.extensions.get("v3", {}).get("system_id") or p.system_id
            meta.setup_resource(system_id, p.codec.encode_resource_type(resource_type.id), resource_type.name)
        for action in p.schema.actions.values():
            meta.setup_action(p.system_id, p.codec.encode_action(action.id), action.name)
        resolved = [p._resolve(r, tenant_id=p.tenant_id) for r in resources]
        sdk_actions, action_resources = [], []
        for action in actions:
            aid = canonicalize_action_id(to_definition_id(action))
            encoded = p.codec.encode_action(aid)
            definition = p.schema.actions[aid]
            rt = definition.resource_type
            matched = [r for r in resolved if canonicalize_action_id(to_definition_id(r.type)) == rt]
            sdk_resources = []
            for resource in matched:
                sdk_resource = p.codec.encode_resource(resource, client)
                sdk_resource.attribute["name"] = resource.name or resource.id
                sdk_resources.append(sdk_resource)
            action_resources.append(
                {"action": client.make_action(encoded), "resources_list": [sdk_resources] if sdk_resources else [[]]}
            )
            if not rt:
                sdk_actions.append(ActionWithoutResources(encoded))
                continue
            resource_type = p.schema.resource_types[rt]
            system_id = resource_type.extensions.get("v3", {}).get("system_id") or p.system_id
            instances = [
                ResourceInstance(
                    [
                        ResourceNode(
                            type=p.codec.encode_resource_type(rt),
                            id=p.codec.encode_resource_id(rt, str(r.id)),
                            name=r.name or r.id,
                        )
                    ]
                )
                for r in matched
            ]
            sdk_actions.append(
                ActionWithResources(
                    encoded,
                    [
                        RelatedResourceType(
                            system_id=system_id,
                            type=p.codec.encode_resource_type(rt),
                            instances=instances,
                        )
                    ],
                )
            )
        data = gen_perms_apply_data(
            system=p.system_id, subject=client.make_subject(p.username), action_to_resources_list=action_resources
        )
        application = Application(p.system_id, actions=sdk_actions)
        ok, message, url = client.get_apply_url(application)
        if not ok:
            logger.error("iam generate apply url fail: %s", message)
            return data, p._cfg.fallback_apply_url
        return data, url
