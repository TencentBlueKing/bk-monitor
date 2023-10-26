# -*- coding: utf-8 -*-
import json
import time
from typing import List

from alarm_backends.core.cache.base import CacheManager
from calendars.models import CalendarModel
from calendars.resources.item import ItemDetailResource


class CalendarCacheManager(CacheManager):

    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".calendar.{calendar_id}"

    @classmethod
    def mget(cls, calendar_ids: List[int]) -> List[List]:
        if not calendar_ids:
            return []
        results = cls.cache.mget(
            [cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id) for calendar_id in calendar_ids]
        )
        return [json.loads(result or "[]") for result in results]

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
        calendar_ids = CalendarModel.objects.values_list("id", flat=True)
        pipeline = cls.cache.pipeline()
        success_count = 0
        failed_count = 0
        for calendar_id in calendar_ids:
            try:
                items = ItemDetailResource()(calendar_ids=[calendar_id], time=now_ts)
                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id), json.dumps(items), cls.CACHE_TIMEOUT
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                cls.logger.warning("[calendar] id(%s) query error: %s", calendar_id, e)
        pipeline.execute()
        cls.logger.info("[calendar] refresh finished: success(%s), failed(%s)", success_count, failed_count)


def main():
    CalendarCacheManager.refresh()
