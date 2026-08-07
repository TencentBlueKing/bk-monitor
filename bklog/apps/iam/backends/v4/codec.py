from __future__ import annotations

import re

from apps.iam.iam_engine.core.requests import ResourceInstance, to_definition_id

_IAM_PATH_SEGMENT_PATTERN = re.compile(r"(?:^|/)(?P<type>[^/,]+),(?P<id>[^/]+)(?=/|$)")
_V2_ACTION_SUFFIX = "_v2"

# BKLog 权限模型的根资源类型：仓库模型 support-files/iam/initial.json 与
# IAM V4 dev/bklog_test（2026-08-07 查询）均注册为 space。
# 正式 bk_log_search V4 模型注册后，灰度前仍需在目标环境重新核对。
BKLOG_ROOT_RESOURCE_TYPE_ID = "space"


class V4ResourceCodec:
    """将引擎资源编码成 IAM V4 鉴权和申请接口需要的格式。"""

    root_resource_type_id = ""

    def encode_action(self, action_id: str) -> str:
        return to_definition_id(action_id)

    def encode_resource_type(self, resource_type: str) -> str:
        return to_definition_id(resource_type)

    def encode_resource_for_auth(self, resource: ResourceInstance) -> dict:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        attributes = dict(resource.attributes)
        iam_path = attributes.get("_bk_iam_path_")
        if isinstance(iam_path, list | tuple | set):
            iam_path = next(iter(iam_path), "")
        if iam_path:
            attributes["_bk_iam_path_"] = self.normalize_iam_path(str(iam_path))
        elif resource_type == self.root_resource_type_id:
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

    @staticmethod
    def normalize_iam_path(iam_path: str) -> str:
        normalized = iam_path
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        return normalized

    def build_ancestors(self, resource: ResourceInstance) -> list[dict[str, str]]:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        if resource_type == self.root_resource_type_id:
            return []

        attributes = dict(resource.attributes)
        iam_path = attributes.get("_bk_iam_path_")
        if isinstance(iam_path, list | tuple | set):
            iam_path = next(iter(iam_path), "")
        if iam_path:
            matches = _IAM_PATH_SEGMENT_PATTERN.finditer(self.normalize_iam_path(str(iam_path)))
            ancestors = [
                {
                    "type": self.encode_resource_type(match.group("type")),
                    "id": match.group("id"),
                }
                for match in matches
            ]
            if ancestors:
                return ancestors

        biz_id = attributes.get("bk_biz_id")
        if self.root_resource_type_id and biz_id is not None and str(biz_id).lstrip("-").isdigit():
            return [{"type": self.root_resource_type_id, "id": str(biz_id)}]

        if resource.ancestor_chain:
            return [
                {
                    "type": self.encode_resource_type(to_definition_id(ancestor.type)),
                    "id": str(ancestor.id),
                }
                for ancestor in resource.ancestor_chain
            ]

        return []


class BklogNameCodec(V4ResourceCodec):
    """在通用 V4 编码上适配日志平台的 Action 命名。"""

    root_resource_type_id = BKLOG_ROOT_RESOURCE_TYPE_ID

    def encode_action(self, action_id: str) -> str:
        action_id = to_definition_id(action_id)
        if action_id.endswith(_V2_ACTION_SUFFIX):
            return action_id[: -len(_V2_ACTION_SUFFIX)]
        return action_id
