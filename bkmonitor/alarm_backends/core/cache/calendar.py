# -*- coding: utf-8 -*-
import json
import time
from typing import List, Optional

from alarm_backends.core.cache.base import CacheManager
from calendars.models import CalendarModel
from calendars.resources.item import ItemDetailResource
from constants.common import DEFAULT_TENANT_ID


class CalendarCacheManager(CacheManager):
    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".calendar.{calendar_id}"

    @classmethod
    def mget(cls, calendar_ids: List[int], bk_tenant_id: Optional[str] = None) -> List[List]:
        if not calendar_ids:
            return []
        results = cls.cache.mget(
            [cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id) for calendar_id in calendar_ids]
        )
        calendars = [json.loads(result or "{}") for result in results]

        # 补充默认租户ID
        for calendar in calendars:
            if "bk_tenant_id" not in calendar:
                calendar["bk_tenant_id"] = DEFAULT_TENANT_ID

        # 如果指定了租户ID，则只返回指定租户的日历
        if bk_tenant_id:
            calendars = [calendar for calendar in calendars if calendar["bk_tenant_id"] == bk_tenant_id]

        return calendars

    @classmethod
    def get(cls, calendar_id: int) -> List:
        key = cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id)
        result = cls.cache.get(key)
        if not result:
            return []
        return json.loads(result)

    @classmethod
    def refresh(cls):
        now_ts = int(time.time())
        calendars = CalendarModel.objects.all().only("id", "bk_tenant_id")
        pipeline = cls.cache.pipeline()
        success_count = 0
        failed_count = 0
        for calendar in calendars:
            try:
                items = ItemDetailResource()(calendar_ids=[calendar.id], time=now_ts)
                # 补充租户ID
                for item in items:
                    item["bk_tenant_id"] = calendar.bk_tenant_id

                # 写入缓存
                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar.id), json.dumps(items), cls.CACHE_TIMEOUT
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                cls.logger.warning("[calendar] id(%s) query error: %s", calendar.id, e)
        pipeline.execute()
        cls.logger.info("[calendar] refresh finished: success(%s), failed(%s)", success_count, failed_count)


def main():
    CalendarCacheManager.refresh()
