from django.utils.translation import gettext_lazy as _

from core.errors.collecting import CollectingError


class NodeManV3ResultState:
    """Machine-readable result markers shared by the V3 adapter layers."""

    UNSUPPORTED = "unsupported"
    WRITE_RESULT_UNKNOWN = "write_result_unknown"


class NodeManV3DefiniteFailure(Exception):
    """A local failure proven to happen before an inconclusive NodeMan write."""


class NodeManV3PayloadError(NodeManV3DefiniteFailure):
    """The monitor-side payload cannot be built from the current local data."""


class NodeManV3CapabilityBlocked(CollectingError, NodeManV3DefiniteFailure):
    """A required NodeMan V3 capability is absent from the external protocol."""

    code = 3311014
    name = _("NodeMan V3 接口协议不支持")
    message_tpl = _("NodeMan V3 接口协议不支持：{msg}")
    result_state = NodeManV3ResultState.UNSUPPORTED

    def __init__(self, message: str):
        super().__init__(
            {"msg": message},
            data={"result_state": self.result_state},
            extra={"nodeman_v3_result_state": self.result_state},
        )
