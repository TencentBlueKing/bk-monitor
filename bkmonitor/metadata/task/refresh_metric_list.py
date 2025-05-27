import logging
import time
from monitor.models import ApplicationConfig
from celery import shared_task

import settings
from metadata.resources import SyncBkBaseRtMetaByBizIdResource

logger = logging.getLogger("metadata")


@shared_task
def update_metric_list_by_biz(bk_biz_id: int):
    """
    后台运行， 只需要刷新bkdata的数据
    """
    # 对特殊情况直接返回
    if not settings.ENABLE_BKDATA_METRIC_CACHE or bk_biz_id <= 0:
        return
    try:
        start = time.time()
        logger.info(f"update metric list(BKDATA) by biz({bk_biz_id})")
        # 调用meta的接口
        SyncBkBaseRtMetaByBizIdResource().request({"bk_biz_id": bk_biz_id})
        logger.info(f"update metric list(BKDATA) succeed in {time.time() - start}")
    except BaseException as e:
        logger.exception("Failed to update metric list(%s) for (%s)", "BKDATA", e)

    ApplicationConfig.objects.filter(cc_biz_id=bk_biz_id, key=f"{bk_biz_id}_update_metric_cache").delete()
