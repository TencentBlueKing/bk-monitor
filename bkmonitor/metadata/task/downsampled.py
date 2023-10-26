import logging

from alarm_backends.core.lock.service_lock import share_lock
from metadata import models
from metadata.models.constants import BkDataTaskStatus

logger = logging.getLogger(__name__)


@share_lock(identify="metadata_refreshInfluxdbDownsampled")
def refresh_influxdb_downsampled():
    """同步所有influxdb的降精度配置"""

    # 同步数据
    models.DownsampledDatabase.clean_consul_config()
    for db in models.DownsampledDatabase.objects.all():
        db.sync_database_config()

        models.DownsampledRetentionPolicies.sync_all(db.database)
        models.DownsampledContinuousQueries.sync_all(db.database)


@share_lock(identify="metadata_accessAndCalcForDownsample")
def access_and_calc_for_downsample():
    # TODO: 现阶段白名单空间，后续全量开放时，注意空间的适配
    status_list = [
        BkDataTaskStatus.STARTING.value,
        BkDataTaskStatus.ACCESSING.value,
        BkDataTaskStatus.CREATING.value,
        BkDataTaskStatus.RUNNING.value,
        BkDataTaskStatus.STOPPING.value,
    ]
    for ds in models.DownsampleByDateFlow.objects.all():
        # 检查状态，判断是否处于
        if ds.status in status_list:
            ds.check_and_update_status()
            continue
        ds.access_and_calc_by_dataflow()
        ds.check_and_update_status()
