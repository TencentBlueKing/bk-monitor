"""Completeness checks for consumers of relation query results."""

from django.utils.translation import gettext as _

from core.errors.api import BKAPIError


class IncompleteRelationError(BKAPIError):
    def __init__(self):
        super().__init__(
            system_name="unify-query",
            result={"message": _("关联查询结果不完整，请稍后重试")},
        )


def is_incomplete_relation(item: dict) -> bool:
    # Older relation responses omit both fields and remain complete by default.
    return bool(item.get("partial") or item.get("truncated"))


def ensure_complete_relation(response: dict) -> None:
    if any(is_incomplete_relation(item) for item in response.get("data", [])):
        raise IncompleteRelationError()
