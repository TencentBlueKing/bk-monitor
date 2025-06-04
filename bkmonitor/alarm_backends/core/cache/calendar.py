import json
import time

from alarm_backends.core.cache.base import CacheManager
from calendars.models import CalendarModel
from calendars.resources.item import ItemDetailResource
from constants.common import DEFAULT_TENANT_ID


class CalendarCacheManager(CacheManager):
    # 缓存key
    CACHE_KEY_TEMPLATE = CacheManager.CACHE_KEY_PREFIX + ".calendar.{calendar_id}"

    @classmethod
    def mget(cls, bk_tenant_id: str, calendar_ids: list[int]) -> list[list]:
        if not calendar_ids:
            return []
        results = cls.cache.mget(
            [cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id) for calendar_id in calendar_ids]
        )
        calendars = [json.loads(result or "[]") for result in results]

        # 补充默认租户ID
        for calendar_items in calendars:
            for calendar_item in calendar_items:
                if "bk_tenant_id" not in calendar_item:
                    calendar_item["bk_tenant_id"] = DEFAULT_TENANT_ID

        # 如果指定了租户ID，则只返回指定租户的日历
        calendars = [
            [calendar_item for calendar_item in calendar_items if calendar_item["bk_tenant_id"] == bk_tenant_id]
            for calendar_items in calendars
        ]

        return calendars

    @classmethod
    def get(cls, bk_tenant_id: str, calendar_id: int) -> list:
        key = cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar_id)
        result = cls.cache.get(key)
        if not result:
            return []
        calendar: list = json.loads(result)
        return [calendar_item for calendar_item in calendar if calendar_item["bk_tenant_id"] == bk_tenant_id]

    @classmethod
    def refresh(cls):
        now_ts = int(time.time())
        calendars = CalendarModel.objects.all().only("id", "bk_tenant_id")
        pipeline = cls.cache.pipeline()
        success_count = 0
        failed_count = 0
        for calendar in calendars:
            try:
                items = ItemDetailResource()(
                    bk_tenant_id=calendar.bk_tenant_id, calendar_ids=[calendar.pk], time=now_ts
                )
                # 补充租户ID
                for item in items:
                    item["bk_tenant_id"] = calendar.bk_tenant_id

                # 写入缓存
                pipeline.set(
                    cls.CACHE_KEY_TEMPLATE.format(calendar_id=calendar.pk), json.dumps(items), cls.CACHE_TIMEOUT
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                cls.logger.warning("[calendar] id(%s) query error: %s", calendar.pk, e)
        pipeline.execute()
        cls.logger.info("[calendar] refresh finished: success(%s), failed(%s)", success_count, failed_count)


def main():
    CalendarCacheManager.refresh()
