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
                # 与 V3 的 gen_perms_apply_data 对齐：前端权限弹窗按 type_name 展示资源类型名，
                # 缺失会渲染成 "undefined：<实例名>"。schema 里的 name 是 gettext_lazy 代理
                # （__proxy__ / Promise，非 str 子类），此处按当前请求语言求值成 str，
                # 确保外层与各实例节点复用同一份结果、payload 内只保留纯 str。
                # schema 未注册该资源类型时（schema 注入不完整）以类型 id 兜底，
                # 与 permission.py 的 V3 envelope 同口径，避免整条申请数据降级为空。
                rt_def = p.schema.resource_types.get(rt)
                type_name = str(rt_def.name) if rt_def else p.codec.encode_resource_type(rt)
                related.append(
                    {
                        "system_id": p.system_id,
                        "id": p.codec.encode_resource_type(rt),
                        "type_name": type_name,
                        "instances": [
                            [
                                {
                                    "type": p.codec.encode_resource_type(rt),
                                    "type_name": type_name,
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
