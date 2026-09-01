from django.utils.translation import gettext_lazy as _

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3DefiniteFailure, NodeManV3ResultState
from core.errors.collecting import CollectingError


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


def validate_config_matrix(
    action: str,
    configs: list[dict],
    *,
    current_version: str | None = None,
    target_version: str | None = None,
) -> None:
    if action in {"install", "upgrade"}:
        if not configs or any(not config.get("is_main") for config in configs):
            raise ValueError(f"{action} only accepts main config")
        if target_version and any(config.get("plugin_version") != target_version for config in configs):
            raise ValueError(f"{action} config version must match target version")
        return

    if action == "apply":
        if not configs:
            raise ValueError("apply requires a non-empty config list")
        if any(config.get("is_main") for config in configs):
            raise ValueError("apply only accepts subconfig")
        if not current_version or any(config.get("plugin_version") != current_version for config in configs):
            raise ValueError("apply config version must match current process version")
        return

    raise ValueError(f"unsupported NodeMan V3 config action: {action}")
