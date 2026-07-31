import json
import logging
import random
import string

from pydantic import ValidationError

from alarm_backends.service.scheduler.app import app
from bkmonitor.utils.tenant import get_tenant_default_biz_id
from constants.common import DEFAULT_TENANT_ID
from metadata.models import AccessVMRecord, DataSource, DataSourceResultTable, ResultTable, ResultTableOption
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import (
    DataIdConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
)
from metadata.models.data_link.utils import compose_bkdata_data_id_name, compose_transfer_consumer_group
from metadata.models.result_table import GraphRelationV4DataLinkOption, LogV4DataLinkOption
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage, SurrealDBStorage

logger = logging.getLogger(__name__)


def _resolve_graph_relation_vm_cluster(rt: ResultTable) -> ClusterInfo:
    vm_record = AccessVMRecord.objects.filter(
        bk_tenant_id=rt.bk_tenant_id,
        result_table_id=rt.table_id,
    ).last()
    if vm_record:
        cluster = ClusterInfo.objects.filter(
            bk_tenant_id=rt.bk_tenant_id,
            cluster_id=vm_record.vm_cluster_id,
            cluster_type=ClusterInfo.TYPE_VM,
        ).first()
        if cluster:
            return cluster

    from metadata.models import Space
    from metadata.models.vm.utils import get_vm_cluster_id_name

    space_data = {}
    try:
        space_data = Space.objects.get_space_info_by_biz_id(int(rt.get_target_bk_biz_id()))
    except Exception as error:  # pylint: disable=broad-except
        logger.warning(
            "resolve_graph_relation_vm_cluster: get space failed, tenant(%s) table(%s), error=%s",
            rt.bk_tenant_id,
            rt.table_id,
            error,
        )
    vm_cluster = get_vm_cluster_id_name(
        bk_tenant_id=rt.bk_tenant_id,
        space_type=space_data.get("space_type", ""),
        space_id=space_data.get("space_id", ""),
    )
    return ClusterInfo.objects.get(
        bk_tenant_id=rt.bk_tenant_id,
        cluster_id=vm_cluster["cluster_id"],
        cluster_type=ClusterInfo.TYPE_VM,
    )


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def apply_graph_relation_v4_datalink(bk_tenant_id: str, table_id: str) -> None:
    """根据 ResultTableOption 创建或更新统一 Graph Relation V4 DataLink。

    VM 与 SurrealDB 共用一条 DataLink，具体写入目标由
    ``graph_relation_v4_data_link`` Option 决定。该任务只负责准备接入参数和
    回填监控侧元数据，组件的完整期望状态及分支清理由 Graph V4 compose/apply 负责。

    Args:
        bk_tenant_id: 结果表所属租户。
        table_id: 需要接入 Graph V4 链路的监控结果表。
    """
    # 1. 读取并校验写入目标，同时定位当前 RT 唯一的数据源。
    rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    option_record = ResultTableOption.objects.get(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
    )
    option = GraphRelationV4DataLinkOption.from_option_value(option_record.get_value())
    dsrt = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
    if dsrt is None:
        raise ValueError(f"apply_graph_relation_v4_datalink: tenant({bk_tenant_id}) {table_id} datasource not found")
    data_source = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=dsrt.bk_data_id)
    target_bk_biz_id = rt.get_target_bk_biz_id()

    # 2. 沿用普通 VM 接入的数据源注册规则。非 BKData 数据源需要保留
    # Transfer consumer group，但它只传给 VM DataBus 承接原消费位点；
    # SurrealDB DataBus 使用独立消费组，避免双写时与 VM 竞争 Kafka 分区。
    consumer_group = None
    data_source_created_from = data_source.created_from
    data_id_name = compose_bkdata_data_id_name(data_source.data_name)
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        consumer_group = compose_transfer_consumer_group(data_source)
        data_source.register_to_bkbase(
            bk_biz_id=target_bk_biz_id,
            namespace="bkmonitor",
            bkbase_data_name=data_id_name,
        )
    elif not DataIdConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        namespace="bkmonitor",
        name=data_id_name,
    ).exists():
        data_source.register_to_bkbase(
            bk_biz_id=target_bk_biz_id,
            namespace="bkmonitor",
            bkbase_data_name=data_id_name,
        )

    # 3. 只解析 Option 实际启用分支的依赖：
    # SurrealDB-only 不要求 AccessVMRecord/VM 集群，VM-only 不要求 SurrealDBStorage。
    vm_cluster = _resolve_graph_relation_vm_cluster(rt) if option.should_write_vm else None
    surrealdb_storage = None
    if option.should_write_surrealdb:
        surrealdb_storage = SurrealDBStorage.objects.filter(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
        ).first()
        if surrealdb_storage is None:
            raise ValueError(
                f"apply_graph_relation_v4_datalink: tenant({bk_tenant_id}) {table_id} surrealdb storage not found"
            )

    # 4. 优先复用该 RT 已有的普通 VM 或 Graph DataLink，避免双写时额外创建
    # 一条并行 VM 链路。旧配置生成的 Graph DataLink 也可以直接认领；
    # ResultTableOption 会让复用后的链路在本次 apply 中进入 V4 compose。
    configured_rt = None
    candidates = BkBaseResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id,
        monitor_table_id=table_id,
    ).order_by("-last_modify_time", "-create_time")
    for candidate in candidates:
        strategy = (
            DataLink.objects.filter(
                bk_tenant_id=bk_tenant_id,
                data_link_name=candidate.data_link_name,
            )
            .values_list("data_link_strategy", flat=True)
            .first()
        )
        if strategy in {DataLink.BK_STANDARD_V2_TIME_SERIES, DataLink.GRAPH_RELATION_TIME_SERIES}:
            configured_rt = candidate
            break

    data_link_name = configured_rt.data_link_name if configured_rt else data_id_name
    datalink = DataLink.objects.filter(
        bk_tenant_id=bk_tenant_id,
        data_link_name=data_link_name,
    ).first()
    if datalink is None:
        datalink = DataLink.objects.create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            namespace="bkmonitor",
            data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
            bk_data_id=data_source.bk_data_id,
            table_ids=[table_id],
        )
    else:
        datalink.namespace = "bkmonitor"
        datalink.data_link_strategy = DataLink.GRAPH_RELATION_TIME_SERIES
        datalink.bk_data_id = data_source.bk_data_id
        datalink.table_ids = [table_id]
        datalink.save(update_fields=["namespace", "data_link_strategy", "bk_data_id", "table_ids", "last_modify_time"])

    # 5. Graph V4 复用原 graph_relation_time_series strategy；ResultTableOption
    # 决定 compose 走普通组件路径。包含 VM 时 VM 是查询主存储，SurrealDB-only
    # 才将 SurrealDB 记录为主存储。
    storage_type = ClusterInfo.TYPE_VM if option.should_write_vm else ClusterInfo.TYPE_SURREALDB
    datalink.apply_data_link(
        bk_biz_id=target_bk_biz_id,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name=vm_cluster.cluster_name if vm_cluster else "",
        storage_type=storage_type,
        consumer_group=consumer_group,
    )
    primary_cluster = vm_cluster if vm_cluster else surrealdb_storage.storage_cluster
    datalink.sync_metadata(table_id=table_id, storage_cluster_id=primary_cluster.cluster_id)

    # 6. AccessVMRecord 同时承载 VM 分支的历史接入身份：VM 单写/双写时回填；
    # SurrealDB-only 不新建也不删除已有记录，以便后续切回 VM 时继续复用原
    # VM 集群和结果表名称。当前实际主存储仍以 BkBaseResultTable.storage_type
    # 及 ResultTableOption 为准，不由 AccessVMRecord 是否存在决定。
    if option.should_write_vm and vm_cluster:
        bkbase_rt = BkBaseResultTable.objects.get(
            bk_tenant_id=bk_tenant_id,
            data_link_name=datalink.data_link_name,
        )
        vm_record = AccessVMRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            result_table_id=table_id,
        ).last()
        vm_record_values = {
            "bk_base_data_id": data_source.bk_data_id,
            "bk_base_data_name": bkbase_rt.bkbase_data_name or data_id_name,
            "vm_cluster_id": vm_cluster.cluster_id,
            "vm_result_table_id": bkbase_rt.bkbase_table_id,
        }
        if vm_record:
            for field, value in vm_record_values.items():
                setattr(vm_record, field, value)
            vm_record.save(update_fields=list(vm_record_values))
        else:
            AccessVMRecord.objects.create(
                bk_tenant_id=bk_tenant_id,
                result_table_id=table_id,
                **vm_record_values,
            )

    # 7. 非 BKData 数据源已经切换到 BKBase DataBus 消费，清理旧 Transfer
    # Consul 配置，保持与普通 VM V4 接入流程一致。
    if data_source_created_from != DataIdCreatedFromSystem.BKDATA.value:
        data_source.delete_consul_config()


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
