from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from django.conf import settings
from iam import Resource
from iam.apply.models import (
    ActionWithoutResources,
    ActionWithResources,
    Application,
    RelatedResourceType,
    ResourceInstance,
    ResourceNode,
)
from iam.utils import meta

from apps.iam.backends.v3.meta import setup_meta
from apps.iam.exceptions import ActionNotExistError
from apps.utils.log import logger


def gen_perms_apply_data(system: str, action_to_resources_list: list[dict[str, Any]]) -> dict[str, Any]:
    """
    根据传入的参数生成无权限交互协议数据
    action_to_resources_list 应该参照以下格式:
    [
        {
            "action": Action,
            "resources_list": [[resource1, resource2], [resource1, resource2]]
        },
        ...
    ]
    单个 action 中对应的 resources_list 必须是同类型的 Resource
    """
    data = {
        "system_id": system,
        "system_name": meta.get_system_name(system),
    }

    actions = []
    for atr in action_to_resources_list:
        action_obj = atr["action"]
        resources_list = atr["resources_list"]
        action = {
            "id": action_obj.id,
            "name": meta.get_action_name(system, action_obj.id),
        }

        # 1. aggregate resources by system and type
        system_resources_list = OrderedDict({})
        for resources in resources_list:
            system_resources = OrderedDict({})

            # 1. assemble system_resources e.g. {"system1": [r1, r2], "system2": [r3]}
            for resource in resources:
                system_resources.setdefault(resource.system, []).append(resource)

            # 2. append to system_resources_list e.g.g {"system1": [[r1, r2]], "system2": [[r3]]}
            for system_id, resources in system_resources.items():
                system_resources_list.setdefault(system_id, []).append(resources)

        related_resource_types = []
        for system_id, resources_list in system_resources_list.items():
            # get resource type from last resource in resources
            a_resource = resources_list[0][-1]
            resource_types = {
                "system_id": system_id,
                "system_name": meta.get_system_name(system_id),
                "type": a_resource.type,
                "type_name": meta.get_resource_name(system_id, a_resource.type),
            }
            instances = []

            for resources in resources_list:
                for resource in resources:
                    inst_item = [
                        {
                            "type": resource.type,
                            "type_name": meta.get_resource_name(system_id, resource.type),
                            "id": resource.id,
                            "name": resource.attribute.get("name", "") if resource.attribute else "",
                        }
                    ]
                    instances.append(inst_item)

            resource_types["instances"] = instances
            related_resource_types.append(resource_types)

        action["related_resource_types"] = related_resource_types
        actions.append(action)

    data["actions"] = actions

    return data


class V3ApplicationBuilder:
    """生成 IAM V3 的无权限申请数据与申请链接。

    这里的 action 与 resource 都是 V3 SDK 类型；引擎类型的转换由 V3PermissionProvider 在边界完成。
    """

    def __init__(self, client, system_id: str, *, action_resolver: Callable[[Any], Any] | None = None) -> None:
        self.client = client
        self.system_id = system_id
        self.action_resolver = action_resolver

    def get_apply_data(self, actions: list[Any], resources: list[Resource] | None = None) -> tuple[dict, str]:
        resources = resources or []
        action_to_resources_list = []
        for action in actions:
            action = self._resolve_action(action)

            if not action.related_resource_types:
                # 如果没有关联资源，则直接置空
                resources = []

            action_to_resources_list.append({"action": action, "resources_list": [resources]})

        setup_meta(self.system_id)

        data = gen_perms_apply_data(self.system_id, action_to_resources_list)
        url = self.get_apply_url(actions, resources)
        return data, url

    def get_apply_url(self, action_ids: list[Any], resources: list[Resource] | None = None, system_id: str = "") -> str:
        """
        处理无权限 - 跳转申请列表
        """
        application = self.make_application(action_ids, resources, system_id)
        ok, message, url = self.client.get_apply_url(application)
        if not ok:
            logger.error(f"iam generate apply url fail: {message}")
            return settings.BK_IAM_SAAS_HOST
        url = f"{url}&tab_key=independent" if "?" in url else f"{url}?tab_key=independent"
        return url

    def make_application(
        self, action_ids: list[Any], resources: list[Resource] | None = None, system_id: str = ""
    ) -> Application:
        resources = resources or []
        actions = []

        for action_id in action_ids:
            # 对于没有关联资源的动作，则不传资源
            related_resources_types = []
            try:
                action = self._resolve_action(action_id)
                action_id = action.id
                related_resources_types = action.related_resource_types
            except ActionNotExistError:
                pass

            if not related_resources_types:
                actions.append(ActionWithoutResources(action_id))
            else:
                related_resources = []
                for related_resource in related_resources_types:
                    instances = []
                    for r in resources:
                        if r.system == related_resource.system_id and r.type == related_resource.id:
                            instances.append(
                                ResourceInstance(
                                    [ResourceNode(type=r.type, id=r.id, name=r.attribute.get("name", r.id))]
                                )
                            )

                    related_resources.append(
                        RelatedResourceType(
                            system_id=related_resource.system_id,
                            type=related_resource.id,
                            instances=instances,
                        )
                    )

                actions.append(ActionWithResources(action_id, related_resources))

        return Application(system_id or self.system_id, actions=actions)

    def _resolve_action(self, action_ref: Any) -> Any:
        if self.action_resolver is None:
            raise ValueError(f"action resolver is required for action={action_ref}")
        return self.action_resolver(action_ref)
