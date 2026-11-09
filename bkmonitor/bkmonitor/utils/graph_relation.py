import logging
from typing import Any

from django.conf import settings


logger = logging.getLogger(__name__)

RELATION_V1BETA3_BIZ_ID_WHITE_LIST = "RELATION_V1BETA3_BIZ_ID_WHITE_LIST"
# 名单含 -1 时全部业务都使用 v1beta3，与其他业务灰度名单的全量约定一致；未解析到业务（0）的请求仍使用原 URL。
RELATION_V1BETA3_ALL_BIZ = -1


def get_relation_v1beta3_biz_ids() -> set[int]:
    raw_biz_ids: Any = getattr(settings, RELATION_V1BETA3_BIZ_ID_WHITE_LIST, [])
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
            logger.warning("invalid %s item ignored: %s", RELATION_V1BETA3_BIZ_ID_WHITE_LIST, value)
    return biz_ids


def is_relation_v1beta3_enabled(bk_biz_id: int | str | None) -> bool:
    try:
        biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return False
    biz_ids = get_relation_v1beta3_biz_ids()
    return biz_id in biz_ids or (RELATION_V1BETA3_ALL_BIZ in biz_ids and biz_id != 0)
