"""Decide which relation definitions are visible to the v1beta3 query service."""

from bkmonitor.utils.graph_relation import get_relation_v1beta3_biz_ids
from metadata.models import Space
from metadata.models.entity_relation import NAMESPACE_ALL


def should_publish_relation_definition(namespace: str, enabled_biz_ids: set[int] | None = None) -> bool:
    """Keep shared definitions available and publish business definitions only for enabled businesses."""
    if not namespace or namespace == NAMESPACE_ALL:
        return True

    space_type, separator, space_id = namespace.partition("__")
    if not separator or not space_type or not space_id:
        return False

    if space_type == "bkcc":
        try:
            bk_biz_id = int(space_id)
        except ValueError:
            return False
    else:
        bk_biz_id = Space.objects.get_biz_id_by_space(space_type, space_id)

    biz_ids = enabled_biz_ids if enabled_biz_ids is not None else get_relation_v1beta3_biz_ids()
    return bk_biz_id in biz_ids
