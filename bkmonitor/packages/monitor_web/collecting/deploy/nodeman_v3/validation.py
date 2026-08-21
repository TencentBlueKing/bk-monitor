class NodeManV3CapabilityBlocked(RuntimeError):
    """A required external NodeMan V3 capability is not yet contractually available."""


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
