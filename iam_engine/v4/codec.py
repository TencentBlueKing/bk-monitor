"""Shared V4 space IDs: preserve numeric IDs and reversibly encode negatives."""

import re


NEGATIVE_SPACE_RESOURCE_ID_PREFIX = "neg_"
_NEGATIVE_INTEGER_PATTERN = re.compile(r"^-(?P<absolute_id>\d+)$")
_ENCODED_NEGATIVE_INTEGER_PATTERN = re.compile(rf"^{re.escape(NEGATIVE_SPACE_RESOURCE_ID_PREFIX)}(?P<absolute_id>\d+)$")


class SpaceResourceCodec:
    """Resource-ID mixin for product NameCodecs; no product imports or I/O.

    Local space IDs are integers. Positive IDs stay unchanged; negative IDs use
    neg_<absolute id> on the V4 wire. Other resource types stay unchanged.
    Products supply their existing encode_resource_type implementation.
    """

    def encode_resource_id(self, resource_type: str, resource_id: object) -> str:
        normalized_type = self.encode_resource_type(resource_type)
        normalized_id = str(resource_id)
        if normalized_type != "space":
            return normalized_id
        match = _NEGATIVE_INTEGER_PATTERN.fullmatch(normalized_id)
        if match is None:
            return normalized_id
        return f"{NEGATIVE_SPACE_RESOURCE_ID_PREFIX}{match.group('absolute_id')}"

    def decode_resource_id(self, resource_type: str, resource_id: object) -> str:
        normalized_type = self.encode_resource_type(resource_type)
        normalized_id = str(resource_id)
        if normalized_type != "space":
            return normalized_id
        match = _ENCODED_NEGATIVE_INTEGER_PATTERN.fullmatch(normalized_id)
        if match is None:
            return normalized_id
        return f"-{match.group('absolute_id')}"
