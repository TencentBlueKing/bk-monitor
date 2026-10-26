import logging
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST = "RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST"


def get_relation_query_v1beta3_biz_ids() -> set[int]:
    raw_biz_ids: Any = getattr(settings, RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST, [])
    if raw_biz_ids is None:
        return set()
    if isinstance(raw_biz_ids, str):
        values = raw_biz_ids.split(",")
    elif isinstance(raw_biz_ids, list | tuple | set):
        values = raw_biz_ids
    else:
        values = [raw_biz_ids]

    biz_ids = set()
    for value in values:
        value = str(value).strip()
        if not value:
            continue
        try:
            biz_ids.add(int(value))
        except ValueError:
            logger.warning("invalid %s item ignored: %s", RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST, value)
    return biz_ids


def is_relation_query_v1beta3_enabled(bk_biz_id: int | str | None) -> bool:
    try:
        return int(bk_biz_id) in get_relation_query_v1beta3_biz_ids()
    except (TypeError, ValueError):
        return False
