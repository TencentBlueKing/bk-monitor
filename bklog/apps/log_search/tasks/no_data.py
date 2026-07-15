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
    index_set_ids = set(
        UserIndexSetSearchHistory.objects.filter(created_at__gte=datetime.now() - timedelta(days=1)).values_list(
            "index_set_id", flat=True
        )
    )
    space_uid_list = set(
        LogIndexSet.objects.filter(index_set_id__in=index_set_ids, is_active=True).values_list("space_uid", flat=True)
    )
    index_set_list = list(
        LogIndexSet.objects.filter(space_uid__in=space_uid_list, is_active=True).values(
            "index_set_id", "space_uid", "is_group"
        )
    )
    index_set_check_execute_func = MultiExecuteFunc()
    for index_set in index_set_list:
        if not index_set["is_group"]:
            index_set_check_execute_func.append(
                result_key=index_set["index_set_id"],
                func=index_set_no_data_check,
                params={
                    "bk_biz_id": space_uid_to_bk_biz_id(index_set["space_uid"]),
                    "index_set_id": index_set["index_set_id"],
                },
                use_request=False,
                multi_func_params=True,
            )
        cache.set(
            # 这里设置缓存时长为索引集无数据检查时间间隔+1的原因是作为时间冗余
            INDEX_SET_NO_DATA_CHECK_PREFIX + str(index_set["index_set_id"]),
            time.time(),
            TimeEnum.ONE_MINUTE_SECOND.value * INDEX_SET_NO_DATA_CHECK_INTERVAL + 1,
        )
    checked_results = index_set_check_execute_func.run()

    group_check_execute_func = MultiExecuteFunc()
    for index_set in index_set_list:
        if index_set["is_group"]:
            group_check_execute_func.append(
                result_key=index_set["index_set_id"],
                func=index_set_no_data_check,
                params={
                    "index_set_id": index_set["index_set_id"],
                    "bk_biz_id": space_uid_to_bk_biz_id(index_set["space_uid"]),
                    "checked_results": checked_results,
                },
                use_request=False,
                multi_func_params=True,
            )
    group_check_execute_func.run()
    logger.info("[no_data_check]  end check index set no data")


def _index_set_has_data(index_set_id, bk_biz_id, current_time):
    """
    检查单个索引集近一天是否有数据，异常按无数据处理，保持原有 no_data_check 行为。
    """
    params = {
        "bk_biz_id": bk_biz_id,
        "index_set_ids": [index_set_id],
        "start_time": int(current_time.shift(days=-1).timestamp()),
        "end_time": int(current_time.timestamp()),
    }
    try:
        total_count = UnifyQueryFieldHandler(params).get_total_count()
        return bool(total_count)
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(f"[no data check] index_set_id => [{index_set_id}] check failed: {e}")
        return False


def index_set_no_data_check(index_set_id, bk_biz_id, checked_results=None):
    current_time = arrow.now()
    index_set = LogIndexSet.objects.filter(index_set_id=index_set_id).first()

    if index_set and index_set.is_group:
        # 索引组只有在所有子索引集都无数据时，才标记为无数据。
        child_index_set_ids = index_set.get_child_index_set_ids()
        for child_index_set_id in child_index_set_ids:
            has_data = checked_results.get(child_index_set_id) if checked_results is not None else None
            if has_data is None:
                # 查到后写回本轮结果池供后续复用（索引组并发检查时，这里可能还会有少量重复查询）
                has_data = _index_set_has_data(child_index_set_id, bk_biz_id, current_time)
                if checked_results is not None:
                    checked_results[child_index_set_id] = has_data
            # 任一子索引集有数据，说明该索引组仍可检索到数据，需要清理无数据标签。
            if has_data:
                LogIndexSet.delete_tag_by_name(index_set_id, InnerTag.NO_DATA.value)
                return True

        LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
        logger.warning(
            f"[no data check] index_set_id => [{index_set_id}] and child index sets => "
            f"[{child_index_set_ids}] no have data"
        )
        return False

    # 普通索引集保持原有判定逻辑：自身近一天无数据则打无数据标签。
    has_data = _index_set_has_data(index_set_id, bk_biz_id, current_time)
    if not has_data:
        LogIndexSet.set_tag(index_set_id, InnerTag.NO_DATA.value)
        logger.warning(f"[no data check] index_set_id => [{index_set_id}] no have data")
        return False

    LogIndexSet.delete_tag_by_name(index_set_id, InnerTag.NO_DATA.value)
    return True
