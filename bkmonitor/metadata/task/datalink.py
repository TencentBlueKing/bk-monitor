import json
import logging
import random
import string

from pydantic import ValidationError

from alarm_backends.service.scheduler.app import app
from bkmonitor.utils.tenant import get_tenant_default_biz_id
from constants.common import DEFAULT_TENANT_ID
from metadata.models import DataSource, DataSourceResultTable, ResultTable, ResultTableOption
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig, ESStorageBindingConfig
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.models.result_table import LogV4DataLinkOption
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage

logger = logging.getLogger(__name__)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def apply_log_datalink(bk_tenant_id: str, table_id: str):
    """创建/更新日志V4数据链路

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表ID
    """

    logger.info("apply_log_datalink: tenant(%s) %s start", bk_tenant_id, table_id)

    # 获取结果表和数据源信息
    rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    dsrt = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
    if not dsrt:
        raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} related datasource not found")
    ds: DataSource = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=dsrt.bk_data_id)
    data_source_created_from = ds.created_from

    # 判断使用V4链路还是transfer链路
    enabled_v4_datalink_option = ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK
    ).first()
    enabled_v4_datalink = enabled_v4_datalink_option and enabled_v4_datalink_option.get_value()
    if not enabled_v4_datalink:
        # 使用transfer链路
        if ds.created_from != DataIdCreatedFromSystem.BKGSE.value:
            # 禁止从V4链路切换回transfer
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} cannot switch back to transfer")
        return

    # 如果这次是从transfer链路切换到V4链路，则需要设置consumer_group，避免数据链路切换时消费组不一致
    consumer_group = (
        compose_transfer_consumer_group(ds)
        if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value
        else None
    )

    # 如果datasource是gse创建的，需要在bkbase上注册
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.info(
            "apply_log_datalink: tenant(%s) %s datasource created_from change to bkdata, register to bkbase",
            bk_tenant_id,
            table_id,
        )
        ds.register_to_bkbase(bk_biz_id=rt.bk_biz_id, namespace="bklog")

    # 读取option中的日志链路配置
    datalink_option = ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_V4_LOG_DATA_LINK
    ).first()
    if not datalink_option:
        raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option not found")

    # 校验配置
    try:
        datalink_config = LogV4DataLinkOption(**datalink_option.get_value())
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(
            "apply_log_v4_datalink: tenant(%s) %s datalink option json parse error, %s",
            bk_tenant_id,
            table_id,
            str(e),
        )
        raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option is not json")
    except ValidationError as e:
        logger.error(
            "apply_log_v4_datalink: tenant(%s) %s datalink option is invalid, %s", bk_tenant_id, table_id, str(e)
        )
        raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option is invalid")

    # 存储集群查询
    es_storage: ESStorage | None = None
    doris_storage: DorisStorage | None = None
    if datalink_config.es_storage_config:
        es_storage = ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        if not es_storage:
            logger.error("apply_log_v4_datalink: tenant(%s) %s es storage not found", bk_tenant_id, table_id)
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} es storage not found")

    if datalink_config.doris_storage_config:
        doris_storage = DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        if not doris_storage:
            logger.error("apply_log_v4_datalink: tenant(%s) %s doris storage not found", bk_tenant_id, table_id)
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} doris storage not found")

    # 创建/更新V4链路配置
    bkbase_rt = BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id=table_id).first()
    if not bkbase_rt:
        if rt.bk_biz_id < 0:
            bk_biz_id_str = f"space_{-rt.bk_biz_id}"
        else:
            bk_biz_id_str = str(rt.bk_biz_id)
        # 生成链路名称，格式为bklog_{bk_biz_id}_{16位随机字符串}
        random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
        data_link_name = f"bklog_{bk_biz_id_str}_{random_str}"

        # 如果链路名称已存在，则生成新的链路名称
        while DataLink.objects.filter(data_link_name=data_link_name).exists():
            random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
            data_link_name = f"bklog_{bk_biz_id_str}_{random_str}"

        # 创建链路
        logger.info(
            "apply_log_datalink: tenant(%s) bkbase_rt not found, create datalink name->[%s]",
            bk_tenant_id,
            data_link_name,
        )
        datalink = DataLink.objects.create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            namespace="bklog",
            data_link_strategy=DataLink.BK_LOG,
            bk_data_id=ds.bk_data_id,
            table_ids=[table_id],
        )
    else:
        # 获取链路
        logger.info(
            "apply_log_datalink: tenant(%s) bkbase_rt found, update datalink name->[%s]",
            bk_tenant_id,
            bkbase_rt.data_link_name,
        )
        datalink, _ = DataLink.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=bkbase_rt.data_link_name,
            namespace="bklog",
            data_link_strategy=DataLink.BK_LOG,
            defaults={"bk_data_id": ds.bk_data_id, "table_ids": [table_id]},
        )

        # 更新BkBaseResultTable状态
        bkbase_rt.status = DataLinkResourceStatus.CREATING.value
        bkbase_rt.save()

    datalink.apply_data_link(bk_biz_id=rt.bk_biz_id, data_source=ds, table_id=table_id, consumer_group=consumer_group)

    # 回填 BkBaseResultTable 的 bkbase_rt_name / bkbase_table_id / bkbase_data_name 等。
    # 当 ES / Doris 两种存储同时存在时，按 ResultTable.default_storage 选择记录的存储类型；
    # 否则回退到任一存在的 storage（兼容只配置单一存储的链路）。
    # storage_cluster_id 直接传入 sync_metadata，由其反查 ClusterInfo 得到 storage_type。
    sync_storage_cluster_id: int | None = None
    if rt.default_storage == ClusterInfo.TYPE_DORIS and doris_storage is not None:
        sync_storage_cluster_id = doris_storage.storage_cluster_id
    elif rt.default_storage == ClusterInfo.TYPE_ES and es_storage is not None:
        sync_storage_cluster_id = es_storage.storage_cluster_id
    elif es_storage is not None:
        sync_storage_cluster_id = es_storage.storage_cluster_id
    elif doris_storage is not None:
        sync_storage_cluster_id = doris_storage.storage_cluster_id
    if sync_storage_cluster_id is not None:
        datalink.sync_metadata(table_id=table_id, storage_cluster_id=sync_storage_cluster_id)
    else:
        logger.warning(
            "apply_log_v4_datalink: tenant(%s) %s no storage cluster found, skip sync_metadata",
            bk_tenant_id,
            table_id,
        )

    # 清理多余的存储链路
    es_binding_config = ESStorageBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=datalink.data_link_name
    ).first()
    if not datalink_config.es_storage_config and es_binding_config:
        logger.info(
            "apply_log_v4_datalink: tenant(%s) %s es storage binding config delete, data_link_name->[%s]",
            bk_tenant_id,
            table_id,
            datalink.data_link_name,
        )
        es_binding_config.delete_config()
    doris_binding_config = DorisStorageBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=datalink.data_link_name
    ).first()
    if not datalink_config.doris_storage_config and doris_binding_config:
        logger.info(
            "apply_log_v4_datalink: tenant(%s) %s doris storage binding config delete, data_link_name->[%s]",
            bk_tenant_id,
            table_id,
            datalink.data_link_name,
        )
        doris_binding_config.delete_config()

    # 补充dorisstorage的表记录
    if doris_storage and not doris_storage.bkbase_table_id and doris_binding_config:
        doris_storage.bkbase_table_id = (
            f"{doris_binding_config.datalink_biz_ids.data_biz_id}_{doris_binding_config.bkbase_result_table_name}"
        )
        doris_storage.save()

    # 清理transfer链路配置
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.info(
            "apply_log_v4_datalink: tenant(%s) %s datasource created_from change to bkdata, clean consul config for datasource->[%s]",
            bk_tenant_id,
            table_id,
            ds.bk_data_id,
        )
        ds.delete_consul_config()

    logger.info("apply_log_datalink: tenant(%s) %s end", bk_tenant_id, table_id)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def apply_event_group_datalink(bk_tenant_id: str, table_id: str):
    """创建/更新事件组V4数据链路

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表ID
    """

    logger.info("apply_event_group_datalink: tenant(%s) %s start", bk_tenant_id, table_id)

    # 获取结果表和数据源信息
    rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    dsrt = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
    if not dsrt:
        raise ValueError(f"apply_event_group_datalink: tenant({bk_tenant_id}) {table_id} related datasource not found")
    ds: DataSource = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=dsrt.bk_data_id)
    data_source_created_from = ds.created_from

    # 判断使用V4链路还是transfer链路，如果存在事件组V4数据链路配置或默认启用事件组V4数据链路，则使用V4链路
    enabled_v4_datalink_option = ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK
    ).first()
    enabled_v4_datalink = enabled_v4_datalink_option and enabled_v4_datalink_option.get_value()

    if not enabled_v4_datalink:
        if data_source_created_from != DataIdCreatedFromSystem.BKGSE.value:
            # 禁止从V4链路切换回transfer
            raise ValueError(
                f"apply_event_group_datalink: tenant({bk_tenant_id}) {table_id} cannot switch back to transfer"
            )
        return

    consumer_group = (
        compose_transfer_consumer_group(ds)
        if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value
        else None
    )

    # 如果datasource是gse创建的，需要在bkbase上注册
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.info(
            "apply_event_group_datalink: tenant(%s) %s datasource created_from change to bkdata, register to bkbase",
            bk_tenant_id,
            table_id,
        )
        ds.register_to_bkbase(bk_biz_id=rt.bk_biz_id, namespace="bklog")

    # 获取数据链路
    bkbase_rt = BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id=table_id).first()
    if not bkbase_rt:
        data_link_name = f"bkmonitor_custom_event_{ds.bk_data_id}"
        logger.info(
            "apply_event_group_datalink: tenant(%s) bkbase_rt not found, create datalink name->[%s]",
            bk_tenant_id,
            data_link_name,
        )
        datalink = DataLink.objects.create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            namespace="bklog",
            data_link_strategy=DataLink.BK_STANDARD_V2_EVENT,
            bk_data_id=ds.bk_data_id,
            table_ids=[table_id],
        )
    else:
        logger.info(
            "apply_event_group_datalink: tenant(%s) bkbase_rt found, update datalink name->[%s]",
            bk_tenant_id,
            bkbase_rt.data_link_name,
        )
        datalink, _ = DataLink.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=bkbase_rt.data_link_name,
            namespace="bklog",
            data_link_strategy=DataLink.BK_STANDARD_V2_EVENT,
            defaults={"bk_data_id": ds.bk_data_id, "table_ids": [table_id]},
        )

        # 更新BkBaseResultTable状态
        bkbase_rt.status = DataLinkResourceStatus.CREATING.value
        bkbase_rt.save()

    # 创建/更新链路配置
    datalink.apply_data_link(bk_biz_id=rt.bk_biz_id, data_source=ds, table_id=table_id, consumer_group=consumer_group)

    # 回填 BkBaseResultTable 的 bkbase_rt_name / bkbase_table_id / bkbase_data_name 等。
    # 事件组 V4 链路使用 ES 存储，按 table_id 关联到 ESStorage 拿到 storage_cluster_id。
    es_storage = ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
    if es_storage is not None:
        datalink.sync_metadata(table_id=table_id, storage_cluster_id=es_storage.storage_cluster_id)
    else:
        logger.warning(
            "apply_event_group_datalink: tenant(%s) %s no ESStorage found, skip sync_metadata",
            bk_tenant_id,
            table_id,
        )

    # 清理transfer链路配置
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        logger.info(
            "apply_event_group_datalink: tenant(%s) %s datasource created_from change to bkdata, clean consul config for datasource->[%s]",
            bk_tenant_id,
            table_id,
            ds.bk_data_id,
        )
        ds.delete_consul_config()

    logger.info("apply_event_group_datalink: tenant(%s) %s end", bk_tenant_id, table_id)


def rebuild_built_in_metric_datalink(bk_data_id: int, kafka_cluster_id: int):
    """重建内置指标数据链路

    1. 1100006 - bkunifylogbeat_common_metrics
    2. 1100007 - bkunifylogbeat_task_metrics
    3. 1100013 - bkm_statistics
    4. 1100011 - custom_report_aggate_dataid

    Args:
        bk_tenant_id: 租户ID
        bk_data_id: 数据源ID
    """

    bk_tenant_id = DEFAULT_TENANT_ID

    logger.info("rebuild_built_in_metric_datalink: tenant(%s) bk_data_id->[%s] start", bk_tenant_id, bk_data_id)

    # 获取数据源
    ds = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
    if not ds:
        raise ValueError(
            f"rebuild_built_in_metric_datalink: tenant({bk_tenant_id}) bk_data_id->[%s] not found", bk_data_id
        )

    table_ids = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).values_list(
        "table_id", flat=True
    )
    if not table_ids:
        raise ValueError(
            f"rebuild_built_in_metric_datalink: tenant({bk_tenant_id}) bk_data_id->[%s] not found", bk_data_id
        )
    if len(table_ids) != 1:
        raise ValueError(
            f"rebuild_built_in_metric_datalink: tenant({bk_tenant_id}) bk_data_id->[%s] has multiple table_ids",
            bk_data_id,
        )
    rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_ids[0])

    # 修改数据源配置
    ds.is_enable = True
    ds.mq_cluster_id = kafka_cluster_id
    ds.created_from = DataIdCreatedFromSystem.BKDATA.value
    ds.save()

    # gse路由注册与bkbase注册
    ds.refresh_gse_config_to_gse()
    ds.register_to_bkbase(bk_biz_id=get_tenant_default_biz_id(bk_tenant_id), namespace="bkmonitor")

    # 链路重建
    rt.is_enable = True
    rt.save()
    rt.apply_datalink(force_update=True, delay=False)
