import time
from datetime import datetime, timedelta

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.core.cache import cache

from apps.log_search.constants import (
    INDEX_SET_NO_DATA_CHECK_INTERVAL,
    INDEX_SET_NO_DATA_CHECK_PREFIX,
    InnerTag,
    TimeEnum,
)
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet, UserIndexSetSearchHistory
from apps.utils.lock import share_lock
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


@periodic_task(run_every=crontab(minute="*/15"))
@share_lock()
def no_data_check():
    logger.info("[no_data_check] start check index set no data")
    index_set_ids = list(
        UserIndexSetSearchHistory.objects.filter(created_at__gte=datetime.now() - timedelta(days=1)).values_list(
            "index_set_id", flat=True
        )
    )
    space_uid_list = set(
        LogIndexSet.objects.filter(index_set_id__in=index_set_ids, is_active=True).values_list("space_uid", flat=True)
    )
    index_set_id_list = LogIndexSet.objects.filter(space_uid__in=space_uid_list, is_active=True).values_list(
        "index_set_id", flat=True
    )
    multi_execute_func = MultiExecuteFunc()
    for index_set_id in index_set_id_list:
        multi_execute_func.append(index_set_id, index_set_no_data_check, index_set_id, use_request=False)
        cache.set(
            # 这里设置缓存时长为索引集无数据检查时间间隔+1的原因是作为时间冗余
            INDEX_SET_NO_DATA_CHECK_PREFIX + str(index_set_id),
            time.time(),
            TimeEnum.ONE_MINUTE_SECOND.value * INDEX_SET_NO_DATA_CHECK_INTERVAL + 1,
        )
    multi_execute_func.run()
    logger.info("[no_data_check]  end check index set no data")


def index_set_no_data_check(index_set_id):
    try:
        result = SearchHandler(index_set_id=index_set_id, search_dict={"time_range": "1d", "size": 1}).search(
            search_type=None
        )
        if result["total"] == 0:
            LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
            logger.warning(f"[no data check] index_set_id => [{index_set_id}] no have data")
            return
    except Exception as e:  # pylint: disable=broad-except
        LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
        logger.warning(f"[no data check] index_set_id => [{index_set_id}] check failed: {e}")
        return
    LogIndexSet.delete_tag_by_name(index_set_id, InnerTag.NO_DATA.value)
