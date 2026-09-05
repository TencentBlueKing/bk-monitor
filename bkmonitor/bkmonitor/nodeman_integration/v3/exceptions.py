class NodeManV3ResultState:
    """Machine-readable result markers shared by the V3 adapter layers."""

    UNSUPPORTED = "unsupported"
    WRITE_RESULT_UNKNOWN = "write_result_unknown"


class NodeManV3DefiniteFailure(Exception):
    """A local failure proven to happen before an inconclusive NodeMan write."""


class NodeManV3PayloadError(NodeManV3DefiniteFailure):
    """The monitor-side payload cannot be built from the current local data."""
