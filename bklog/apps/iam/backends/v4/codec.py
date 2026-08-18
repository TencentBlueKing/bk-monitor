from __future__ import annotations

import re

from apps.iam.iam_engine.core.requests import ResourceInstance, to_definition_id

_IAM_PATH_SEGMENT_PATTERN = re.compile(r"(?:^|/)(?P<type>[^/,]+),(?P<id>[^/]+)(?=/|$)")

# bk_log_search 的 IAM V4 模型按「干净命名」重新注册，不保留 V3 时期的 _v2 后缀
# （V3 用 _v2 区分两代 action，见 apps/iam/backends/v3/client.py；V4 无此历史包袱）。
# 因此 V4 侧统一剥掉后缀，与 BKLOG_ROOT_RESOURCE_TYPE_ID = "space" 是配套前提，
# 二者需在目标环境一并核对。
_V2_ACTION_SUFFIX = "_v2"

# BKLog 权限模型的根资源类型：仓库模型 support-files/iam/initial.json 与
# IAM V4 dev/bklog_test（2026-08-07 查询）均注册为 space。
# 正式 bk_log_search V4 模型注册后，灰度前仍需在目标环境重新核对。
BKLOG_ROOT_RESOURCE_TYPE_ID = "space"

# IAM V4 要求资源 ID 以字母或数字开头，而 BKCI 等非 CMDB 空间的 bk_biz_id 是负数。
# 本地 bk_biz_id 是整数，因此 ``neg_<absolute id>`` 不会与合法的原始空间 ID 冲突；
# 正数保持原值，避免迁移既有 IAM V4 授权。
NEGATIVE_SPACE_RESOURCE_ID_PREFIX = "neg_"
_NEGATIVE_INTEGER_PATTERN = re.compile(r"^-(?P<absolute_id>\d+)$")
_ENCODED_NEGATIVE_INTEGER_PATTERN = re.compile(rf"^{re.escape(NEGATIVE_SPACE_RESOURCE_ID_PREFIX)}(?P<absolute_id>\d+)$")


class V4ResourceCodec:
    """将引擎资源编码成 IAM V4 鉴权和申请接口需要的格式。"""

    root_resource_type_id = ""
    root_view_action_id = ""

    def encode_action(self, action_id: str) -> str:
        return to_definition_id(action_id)

    def encode_resource_type(self, resource_type: str) -> str:
        return to_definition_id(resource_type)

    def encode_resource_id(self, resource_type: str, resource_id: object) -> str:
        del resource_type
        return str(resource_id)

    def decode_resource_id(self, resource_type: str, resource_id: object) -> str:
        del resource_type
        return str(resource_id)

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
            "id": self.encode_resource_id(resource_type, resource.id),
            "attributes": attributes,
        }

    def encode_resource_for_apply(self, resource: ResourceInstance) -> dict:
        resource_type = self.encode_resource_type(to_definition_id(resource.type))
        ancestors = self.build_ancestors(resource)
        payload = {"type": resource_type, "id": self.encode_resource_id(resource_type, resource.id)}
        if ancestors:
            payload["ancestors"] = ancestors
        return payload

    def normalize_iam_path(self, iam_path: str) -> str:
        normalized = iam_path
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        return _IAM_PATH_SEGMENT_PATTERN.sub(self._encode_iam_path_segment, normalized)

    def decode_iam_path(self, iam_path: str) -> str:
        normalized = iam_path
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        if not normalized.endswith("/"):
            normalized = f"{normalized}/"
        return _IAM_PATH_SEGMENT_PATTERN.sub(self._decode_iam_path_segment, normalized)

    def _encode_iam_path_segment(self, match: re.Match) -> str:
        prefix = "/" if match.group(0).startswith("/") else ""
        resource_type = self.encode_resource_type(match.group("type"))
        resource_id = self.encode_resource_id(resource_type, match.group("id"))
        return f"{prefix}{resource_type},{resource_id}"

    def _decode_iam_path_segment(self, match: re.Match) -> str:
        prefix = "/" if match.group(0).startswith("/") else ""
        resource_type = self.encode_resource_type(match.group("type"))
        resource_id = self.decode_resource_id(resource_type, match.group("id"))
        return f"{prefix}{resource_type},{resource_id}"

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
            return [
                {
                    "type": self.root_resource_type_id,
                    "id": self.encode_resource_id(self.root_resource_type_id, biz_id),
                }
            ]

        if resource.ancestor_chain:
            return [
                {
                    "type": self.encode_resource_type(to_definition_id(ancestor.type)),
                    "id": self.encode_resource_id(to_definition_id(ancestor.type), ancestor.id),
                }
                for ancestor in resource.ancestor_chain
            ]

        return []


class BklogNameCodec(V4ResourceCodec):
    """在通用 V4 编码上适配日志平台的 Action 命名。"""

    root_resource_type_id = BKLOG_ROOT_RESOURCE_TYPE_ID
    root_view_action_id = "view_business_v2"

    def encode_action(self, action_id: str) -> str:
        action_id = to_definition_id(action_id)
        if action_id.endswith(_V2_ACTION_SUFFIX):
            return action_id[: -len(_V2_ACTION_SUFFIX)]
        return action_id

    def encode_resource_id(self, resource_type: str, resource_id: object) -> str:
        normalized_type = self.encode_resource_type(resource_type)
        normalized_id = str(resource_id)
        if normalized_type != self.root_resource_type_id:
            return normalized_id
        match = _NEGATIVE_INTEGER_PATTERN.fullmatch(normalized_id)
        if match is None:
            return normalized_id
        return f"{NEGATIVE_SPACE_RESOURCE_ID_PREFIX}{match.group('absolute_id')}"

    def decode_resource_id(self, resource_type: str, resource_id: object) -> str:
        normalized_type = self.encode_resource_type(resource_type)
        normalized_id = str(resource_id)
        if normalized_type != self.root_resource_type_id:
            return normalized_id
        match = _ENCODED_NEGATIVE_INTEGER_PATTERN.fullmatch(normalized_id)
        if match is None:
            return normalized_id
        return f"-{match.group('absolute_id')}"
