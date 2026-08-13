from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from apps.iam.backends.v4.codec import V4ResourceCodec
from apps.iam.iam_engine.core.requests import ActionDefinition, ResourceInstance, to_definition_id

ActionResources = tuple[ActionDefinition, Sequence[ResourceInstance]]


def build_apply_data(
    *,
    system_id: str,
    system_name: Any,
    codec: V4ResourceCodec,
    action_resources: Sequence[ActionResources],
) -> dict[str, Any]:
    """按 IAM 无权限交互协议组装 V4 的申请展示数据。

    结构与 V3 的 ``gen_perms_apply_data`` 保持一致：前端 ``auth-dialog.vue`` 与
    ``auth-container-page.vue`` 直接读 ``actions[].name`` 和 ``related_resource_types[].instances``，
    双栈必须给出同一种形状，UNION 模式下 V4 生成失败回落 V3 时前端才不会看到两种结构。

    id 用 V4 编码（剥掉 ``_v2`` 后缀），与 ``apply_url`` 指向的申请单对齐；展示名取本地定义，
    与 V3 同源——V3 那张 SDK meta 表也是 ``setup_meta`` 从 ``_all_actions`` / ``_all_resources`` 灌进去的。
    """
    return {
        "system_id": system_id,
        "system_name": system_name,
        "actions": [
            {
                "id": codec.encode_action(to_definition_id(action)),
                "name": _display_name(action),
                "related_resource_types": _build_related_resource_types(
                    system_id=system_id,
                    system_name=system_name,
                    codec=codec,
                    action=action,
                    resources=resources,
                ),
            }
            for action, resources in action_resources
        ],
    }


def _build_related_resource_types(
    *,
    system_id: str,
    system_name: Any,
    codec: V4ResourceCodec,
    action: ActionDefinition,
    resources: Sequence[ResourceInstance],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for resource_type in getattr(action, "related_resource_types", ()) or ():
        encoded_type = codec.encode_resource_type(to_definition_id(resource_type))
        type_name = _display_name(resource_type)
        instances = [
            # 与 V3 一致：每个资源单独成一条实例链，不展开祖先——祖先只有 id 没有名称，展开只会渲染出空行。
            [
                {
                    "type": encoded_type,
                    "type_name": type_name,
                    "id": codec.encode_resource_id(encoded_type, resource.id),
                    "name": resource.name,
                }
            ]
            for resource in resources
            if codec.encode_resource_type(to_definition_id(resource.type)) == encoded_type
        ]
        if not instances:
            continue
        groups.append(
            {
                "system_id": system_id,
                "system_name": system_name,
                "type": encoded_type,
                "type_name": type_name,
                "instances": instances,
            }
        )
    return groups


def _display_name(definition: Any) -> Any:
    """展示名可能是 ``gettext_lazy`` 代理，保持惰性交给渲染层求值；缺少 name 时退回 id。"""
    return getattr(definition, "name", "") or to_definition_id(definition)
