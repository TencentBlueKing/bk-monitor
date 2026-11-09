import logging
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

RELATION_V1BETA3_BIZ_ID_WHITE_LIST = "RELATION_V1BETA3_BIZ_ID_WHITE_LIST"
# 名单含该值时全部业务都使用 v1beta3，新增业务无需逐个加入；没有业务 ID 的请求仍使用原 URL。
RELATION_V1BETA3_ALL_BIZ = "*"


def _relation_v1beta3_values() -> list[str]:
    raw_biz_ids: Any = getattr(settings, RELATION_V1BETA3_BIZ_ID_WHITE_LIST, [])
    if raw_biz_ids is None:
        return []
    if isinstance(raw_biz_ids, str):
        values = raw_biz_ids.split(",")
    elif isinstance(raw_biz_ids, list | tuple | set):
        values = raw_biz_ids
    else:
        values = [raw_biz_ids]
    return [str(value).strip() for value in values]


def get_relation_v1beta3_biz_ids() -> set[int]:
    biz_ids = set()
    for value in _relation_v1beta3_values():
        if not value or value == RELATION_V1BETA3_ALL_BIZ:
            continue
        try:
            biz_ids.add(int(value))
        except ValueError:
            logger.warning("invalid %s item ignored: %s", RELATION_V1BETA3_BIZ_ID_WHITE_LIST, value)
    return biz_ids


def is_relation_v1beta3_enabled(bk_biz_id: int | str | None) -> bool:
    try:
        biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return False
    return RELATION_V1BETA3_ALL_BIZ in _relation_v1beta3_values() or biz_id in get_relation_v1beta3_biz_ids()
