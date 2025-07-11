from collections import OrderedDict

from iam.utils import meta


def gen_perms_apply_data(system, subject, action_to_resources_list):
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
