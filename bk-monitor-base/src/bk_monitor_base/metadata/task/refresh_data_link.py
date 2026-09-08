import logging

from bk_monitor_base.metadata import models
from bk_monitor_base.metadata.task.tasks import bulk_refresh_data_link_status
from bk_monitor_base.metadata.utils.lock import share_lock

logger = logging.getLogger("metadata")


@share_lock(identify="metadata_refreshDataLink", ttl=1800)
def refresh_data_link_status():
    """
    刷新链路状态（各组件状态+整体状态）
    """
    logger.info("refresh_data_link_status: cron task started,start to refresh data_link status")
    bkbase_rt_records = models.BkBaseResultTable.objects.all()

    table_id_list = models.ResultTable.objects.filter(
        table_id__in=bkbase_rt_records.values_list("monitor_table_id", flat=True), is_enable=True, is_deleted=False
    ).values_list("table_id", flat=True)

    bkbase_rt_records = models.BkBaseResultTable.objects.filter(monitor_table_id__in=table_id_list)
    logger.info("refresh_data_link_status: now try to bulk_refresh_data_link_status,len->[%s] ", len(bkbase_rt_records))
    bulk_refresh_data_link_status.delay(list(bkbase_rt_records))  # task_id
