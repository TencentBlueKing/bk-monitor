from __future__ import annotations

import re

from apps.iam.iam_engine.core.requests import ResourceInstance, to_definition_id

_BIZ_PATH_PATTERN = re.compile(r"(?:^|/)(?:biz|space),(-?\d+)(?:/|$)")
_V2_ACTION_SUFFIX = "_v2"


class BklogNameCodec:
    """在 Provider 边界将 BKLog 业务命名转换为 IAM V4 格式。"""

    def encode_action(self, action_id: str) -> str:
        action_id = to_definition_id(action_id)
        if action_id.endswith(_V2_ACTION_SUFFIX):
            return action_id[: -len(_V2_ACTION_SUFFIX)]
        return action_id

    def encode_resource_type(self, resource_type: str) -> str:
        resource_type = to_definition_id(resource_type)
        if resource_type == "biz":
            return "space"
        return resource_type

    def encode_resource_for_auth(self, resource: ResourceInstance) -> dict:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        attributes = dict(resource.attributes)
        iam_path = attributes.get("_bk_iam_path_")
        if isinstance(iam_path, list | tuple | set):
            iam_path = next(iter(iam_path), "")
        if iam_path:
            attributes["_bk_iam_path_"] = self.normalize_iam_path(str(iam_path))
        elif resource_type == "space":
            attributes.pop("_bk_iam_path_", None)
        return {
            "id": str(resource.id),
            "attributes": attributes,
        }

    def encode_resource_for_apply(self, resource: ResourceInstance) -> dict:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        ancestors = self.build_ancestors(resource)
        payload = {"type": resource_type, "id": str(resource.id)}
        if ancestors:
            payload["ancestors"] = ancestors
        return payload

    def normalize_iam_path(self, iam_path: str) -> str:
        normalized = iam_path.replace("/biz,", "/space,").replace(",biz,", ",space,")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        return normalized

    def build_ancestors(self, resource: ResourceInstance) -> list[dict[str, str]]:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        if resource_type == "space":
            return []

        attributes = dict(resource.attributes)
        iam_path = attributes.get("_bk_iam_path_")
        if isinstance(iam_path, list | tuple | set):
            iam_path = next(iter(iam_path), "")
        if iam_path:
            match = _BIZ_PATH_PATTERN.search(self.normalize_iam_path(str(iam_path)))
            if match:
                return [{"type": "space", "id": match.group(1)}]

        biz_id = attributes.get("bk_biz_id")
        if biz_id is not None and str(biz_id).lstrip("-").isdigit():
            return [{"type": "space", "id": str(biz_id)}]

        for ancestor in resource.ancestor_chain:
            ancestor_type = self.encode_resource_type(to_definition_id(ancestor.type))
            if ancestor_type == "space":
                return [{"type": "space", "id": str(ancestor.id)}]

        return []
