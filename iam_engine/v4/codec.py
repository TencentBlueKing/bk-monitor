"""Shared V4 resource IDs: preserve product identities as strings."""


class SpaceResourceCodec:
    """Resource-ID mixin for product NameCodecs; no product imports or I/O.

    Positive, zero and negative space IDs retain their original spelling.
    Other resource IDs also retain their spelling; only integer inputs are
    normalized to strings. Prefixes from earlier codecs are distinct IAM IDs,
    not aliases: decoding must not silently map them to numeric space IDs.
    """

    def encode_resource_id(self, resource_type: str, resource_id: object) -> str:
        return str(resource_id)

    def decode_resource_id(self, resource_type: str, resource_id: object) -> str:
        return str(resource_id)
