import time
from datetime import datetime, timedelta

import arrow
from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.core.cache import cache

from apps.log_search.constants import (
    INDEX_SET_NO_DATA_CHECK_INTERVAL,
    INDEX_SET_NO_DATA_CHECK_PREFIX,
    InnerTag,
    TimeEnum,
)
from apps.log_search.models import LogIndexSet, UserIndexSetSearchHistory
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.utils.lock import share_lock
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc
from bkm_space.utils import space_uid_to_bk_biz_id


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
    index_set_list = LogIndexSet.objects.filter(space_uid__in=space_uid_list, is_active=True).values(
        "index_set_id", "space_uid"
    )
    multi_execute_func = MultiExecuteFunc()
    for index_set in index_set_list:
        params = {
            "bk_biz_id": space_uid_to_bk_biz_id(index_set["space_uid"]),
            "index_set_id": index_set["index_set_id"],
        }
        multi_execute_func.append(
            result_key=index_set["index_set_id"],
            func=index_set_no_data_check,
            params=params,
            use_request=False,
            multi_func_params=True,
        )
        cache.set(
            # 这里设置缓存时长为索引集无数据检查时间间隔+1的原因是作为时间冗余
            INDEX_SET_NO_DATA_CHECK_PREFIX + str(index_set["index_set_id"]),
            time.time(),
            TimeEnum.ONE_MINUTE_SECOND.value * INDEX_SET_NO_DATA_CHECK_INTERVAL + 1,
        )
    multi_execute_func.run()
    logger.info("[no_data_check]  end check index set no data")


def index_set_no_data_check(index_set_id, bk_biz_id):
    current_time = arrow.now()
    params = {
        "bk_biz_id": bk_biz_id,
        "index_set_ids": [index_set_id],
        "start_time": int(current_time.shift(days=-1).timestamp()),
        "end_time": int(current_time.timestamp()),
    }
    try:
        total_count = UnifyQueryFieldHandler(params).get_total_count()
        if not total_count:
            LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
            logger.warning(f"[no data check] index_set_id => [{index_set_id}] no have data")
            return
    except Exception as e:  # pylint: disable=broad-except
        LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
        logger.warning(f"[no data check] index_set_id => [{index_set_id}] check failed: {e}")
        return
    LogIndexSet.delete_tag_by_name(index_set_id, InnerTag.NO_DATA.value)
