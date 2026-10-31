"""Serialize existing V3 resource paths for permission applications only."""


def application_resource_path(resource, *, leaf_name, resource_systems=None):
    """Return ancestors followed by the leaf, using the SDK path convention.

    Both legacy /type,id/ and cross-system /system,type,id/ paths are supported.
    Ancestor names follow the V3 SDK's permission-prompt convention; this does
    not resolve resources or change the attributes used by authorization.
    """
    nodes = []
    path = (resource.attribute or {}).get("_bk_iam_path_")
    if path:
        for part in path[1:-1].split("/"):
            parts = part.split(",")
            if len(parts) == 2:
                resource_type, resource_id = parts
                system = (resource_systems or {}).get(resource_type, resource.system)
            elif len(parts) == 3:
                system, resource_type, resource_id = parts
            else:
                raise ValueError(f"Invalid _bk_iam_path_: {path}")
            nodes.append(
                {"system": system, "type": resource_type, "id": resource_id, "name": f"{resource_type},{resource_id}"}
            )
    nodes.append({"system": resource.system, "type": resource.type, "id": resource.id, "name": leaf_name})
    return nodes
