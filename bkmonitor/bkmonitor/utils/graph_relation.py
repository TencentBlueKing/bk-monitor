import json
import logging
from typing import Any

from django.conf import settings
from django.db import DatabaseError
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)

RELATION_V1BETA3_BIZ_ID_WHITE_LIST = "RELATION_V1BETA3_BIZ_ID_WHITE_LIST"


RELATION_SCHEMA_READY_KEY = "bkmonitorv3:entity:v1beta3:schema_ready"
RELATION_SCHEMA_VERSION_HEADER = "X-Bk-Relation-Schema-Version"


def parse_relation_v1beta3_biz_ids(raw_biz_ids: Any) -> set[int]:
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


def get_relation_v1beta3_biz_ids() -> set[int]:
    # Routing and publication must observe the same committed list. Dynamic
    # settings cache values per process, which is unsafe during rollback.
    if getattr(settings, "USE_DYNAMIC_SETTINGS", False):
        from bkmonitor.models import GlobalConfig

        row = (
            GlobalConfig.objects.filter(key=RELATION_V1BETA3_BIZ_ID_WHITE_LIST).values_list("value", flat=True).first()
        )
        return parse_relation_v1beta3_biz_ids(row)
    return parse_relation_v1beta3_biz_ids(getattr(settings, RELATION_V1BETA3_BIZ_ID_WHITE_LIST, []))


def get_relation_schema_version(bk_biz_id: int | str | None) -> str:
    """Admit a business only after a full definition publication for this list."""
    try:
        biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return ""
    from metadata.utils.redis_tools import RedisTools

    try:
        enabled_biz_ids = get_relation_v1beta3_biz_ids()
        if biz_id not in enabled_biz_ids:
            return ""
        raw = RedisTools().client.get(RELATION_SCHEMA_READY_KEY)
        if not raw:
            return ""
        ready = json.loads(raw)
        if not isinstance(ready, dict) or ready.get("biz_ids") != sorted(enabled_biz_ids):
            return ""
        version = ready.get("version")
        return version if isinstance(version, str) else ""
    except (DatabaseError, RedisError, json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("failed to check relation rollout readiness for biz_id=%s", biz_id)
        return ""
