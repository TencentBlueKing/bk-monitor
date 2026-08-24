"""Pure rules for bounding CHECK_RESULT sorted-set members."""

from collections.abc import Mapping

DEFAULT_RETENTION_POINTS = 12
RETENTION_BUFFER_POINTS = 2
RANK_TRIM_DATA_TYPES = frozenset({"time_series", "log"})


class InvalidRetentionConfig(ValueError):
    """Raised when an explicitly configured retention window is unsafe to use."""


def _positive_window(config: Mapping, field: str, label: str) -> int | None:
    if field not in config:
        return None

    value = config[field]
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise InvalidRetentionConfig(f"{label} must be a positive integer, got {value!r}")

    try:
        window = int(value)
    except (TypeError, ValueError) as error:
        raise InvalidRetentionConfig(f"{label} must be a positive integer, got {value!r}") from error
    if window <= 0:
        raise InvalidRetentionConfig(f"{label} must be a positive integer, got {value!r}")
    return window


def _window_config(detect: Mapping, field: str, label: str) -> Mapping | None:
    if field not in detect:
        return None
    config = detect[field]
    if not isinstance(config, Mapping):
        raise InvalidRetentionConfig(f"{label} must be a mapping, got {config!r}")
    return config


def calculate_item_retention(strategy: Mapping, item: Mapping, *, aiops_only: bool = False) -> int:
    """Return the minimum safe member count for one non-event strategy item."""
    detects_by_level = {
        str(detect["level"]): detect
        for detect in strategy.get("detects") or []
        if isinstance(detect, Mapping) and detect.get("level") is not None
    }
    item_levels = {
        str(algorithm["level"])
        for algorithm in item.get("algorithms") or []
        if isinstance(algorithm, Mapping) and algorithm.get("level") is not None
    }

    candidates: list[int] = []
    for level in item_levels:
        detect = detects_by_level.get(level)
        if detect is None:
            candidates.append(DEFAULT_RETENTION_POINTS)
            continue

        recovery_config = _window_config(detect, "recovery_config", f"level({level}) recovery_config")
        recovery_window = (
            _positive_window(recovery_config, "check_window", f"level({level}) recovery check_window")
            if recovery_config is not None
            else None
        )
        if aiops_only:
            trigger_window = 5
        else:
            trigger_config = _window_config(detect, "trigger_config", f"level({level}) trigger_config")
            trigger_window = (
                _positive_window(trigger_config, "check_window", f"level({level}) trigger check_window")
                if trigger_config is not None
                else None
            )

        if trigger_window is None or recovery_window is None:
            candidates.append(DEFAULT_RETENTION_POINTS)
            continue
        candidates.append(trigger_window + recovery_window + RETENTION_BUFFER_POINTS)

    no_data_config = item.get("no_data_config", {})
    if not isinstance(no_data_config, Mapping):
        raise InvalidRetentionConfig(f"no_data_config must be a mapping, got {no_data_config!r}")
    if no_data_config.get("is_enabled"):
        continuous = _positive_window(no_data_config, "continuous", "no_data continuous")
        candidates.append(continuous + RETENTION_BUFFER_POINTS if continuous is not None else DEFAULT_RETENTION_POINTS)

    return max(candidates, default=DEFAULT_RETENTION_POINTS)


def is_item_rank_trim_eligible(item: Mapping) -> bool:
    """Only item types covered by the single-member-per-period contract are eligible."""
    data_types = {
        query_config.get("data_type_label")
        for query_config in item.get("query_configs") or []
        if isinstance(query_config, Mapping)
    }
    return bool(data_types) and data_types <= RANK_TRIM_DATA_TYPES


def rank_trim_stop(point_remains: int) -> int:
    """Return the inclusive ZREMRANGEBYRANK stop rank that leaves exactly N members."""
    if isinstance(point_remains, bool) or not isinstance(point_remains, int) or point_remains <= 0:
        raise InvalidRetentionConfig(f"point_remains must be a positive integer, got {point_remains!r}")
    return -(point_remains + 1)
