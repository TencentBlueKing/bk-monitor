"""V4 application payloads with the existing UI envelope, never a V3 fallback."""

from bkmonitor.iam.action import canonicalize_action_id
from iam_engine.core.requests import to_definition_id
from iam_engine.v4.exceptions import V4ClientError


class V4ApplicationBuilder:
    def __init__(self, provider):
        self.provider = provider

    def get_apply_data(self, actions, resources):
        p = self.provider
        resolved = [p._resolve(r, tenant_id=p.tenant_id) for r in resources]
        data, permissions = [], []
        for action in actions:
            aid = canonicalize_action_id(to_definition_id(action))
            definition = p.schema.actions[aid]
            rt = definition.resource_type
            matched = [r for r in resolved if canonicalize_action_id(to_definition_id(r.type)) == rt]
            related = []
            if rt and matched:
                related.append(
                    {
                        "system_id": p.system_id,
                        "id": p.codec.encode_resource_type(rt),
                        "instances": [
                            [
                                {
                                    "type": p.codec.encode_resource_type(rt),
                                    "id": p.codec.encode_resource_id(rt, str(r.id)),
                                    "name": r.name or r.id,
                                }
                            ]
                            for r in matched
                        ],
                    }
                )
            data.append({"id": p.codec.encode_action(aid), "name": definition.name, "related_resource_types": related})
            permissions.append(
                {
                    "action_id": p.codec.encode_action(aid),
                    "resources": [p.codec.encode_resource_for_apply(r) for r in matched],
                }
            )
        try:
            url = p.client.generate_perm_apply_url(permissions=permissions)
        except V4ClientError:
            url = ""
        return {"system": p.system_id, "actions": data}, url
