"""Pure rules for bounding CHECK_RESULT sorted-set members."""


class InvalidRetentionConfig(ValueError):
    """Raised when an explicitly configured retention window is unsafe to use."""


def rank_trim_stop(point_remains: int) -> int:
    """Return the inclusive ZREMRANGEBYRANK stop rank that leaves exactly N members."""
    if isinstance(point_remains, bool) or not isinstance(point_remains, int) or point_remains <= 0:
        raise InvalidRetentionConfig(f"point_remains must be a positive integer, got {point_remains!r}")
    return -(point_remains + 1)
