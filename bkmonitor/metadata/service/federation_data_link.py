from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from alarm_backends.core.cache.key import SERVICE_LOCK_METADATA_RECONCILE_FEDERATION_DATA_LINK
from alarm_backends.core.lock.service_lock import service_lock
from constants.data_source import DATA_LINK_V4_VERSION_NAME
from metadata import models
from metadata.models.data_link import DataLink
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import utils as data_link_utils
from metadata.models.data_link.constants import DataLinkNameScene, DataLinkResourceStatus
from metadata.models.space.constants import SpaceTypes
from metadata.models.vm.constants import ACCESS_DATA_LINK_FAILURE_STATUS, ACCESS_DATA_LINK_SUCCESS_STATUS
from metadata.models.vm.utils import (
    create_bkbase_data_link,
    get_vm_cluster_id_name,
    report_metadata_data_link_access_metric,
)

logger = logging.getLogger("metadata")


class FederationNamespaceConflictError(ValueError):
    """同一个子集群的 namespace 被多个代理集群同时声明。"""


class FederationTopologyEmptySnapshotError(RuntimeError):
    """本次获取到空拓扑，但数据库中仍存在有效联邦拓扑。"""


class FederationReconcileError(RuntimeError):
    """联邦链路批量收敛存在失败项。"""


@dataclass(frozen=True)
class FederationMetricContext:
    cluster: models.BCSClusterInfo
    data_source: models.DataSource
    table_id: str
    storage_cluster_name: str


@dataclass
class FederationReconcilePlan:
    active_proxy_cluster_ids: list[str] = field(default_factory=list)
    active_sub_cluster_ids: list[str] = field(default_factory=list)
    removed_proxy_cluster_ids: list[str] = field(default_factory=list)
    removed_sub_cluster_ids: list[str] = field(default_factory=list)

    def normalized(self) -> FederationReconcilePlan:
        return FederationReconcilePlan(
            active_proxy_cluster_ids=sorted(set(self.active_proxy_cluster_ids)),
            active_sub_cluster_ids=sorted(set(self.active_sub_cluster_ids)),
            removed_proxy_cluster_ids=sorted(set(self.removed_proxy_cluster_ids)),
            removed_sub_cluster_ids=sorted(set(self.removed_sub_cluster_ids)),
        )


def reset_federation_reconcile(bk_tenant_id: str, sub_cluster_ids: set[str]) -> None:
    """调用方持有租户锁；同一子链路的有效和已删除关系一起重置。"""
    if not sub_cluster_ids:
        return
    models.BcsFederalClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        sub_cluster_id__in=sub_cluster_ids,
    ).update(reconcile_status="pending", reconcile_failures=0)
    logger.info(
        "federation config changed, reset reconcile, tenant->[%s],sub_clusters->[%s]",
        bk_tenant_id,
        sorted(sub_cluster_ids),
    )


def get_federation_reconcile_plan(bk_tenant_id: str) -> FederationReconcilePlan:
    """从持久化状态生成计划，包括需要重试清理的已删除关系。"""
    records = list(models.BcsFederalClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id))
    limit = settings.BCS_FEDERATION_RECONCILE_MAX_FAILURES
    pending_sub_ids = {
        record.sub_cluster_id
        for record in records
        if record.reconcile_status != "success" and record.reconcile_failures < limit
    }
    exhausted_sub_ids = {
        record.sub_cluster_id
        for record in records
        if record.reconcile_status != "success" and record.reconcile_failures >= limit
    }
    if exhausted_sub_ids:
        logger.warning(
            "federation failure limit reached, skip reconcile, tenant->[%s],sub_clusters->[%s],limit->[%s]",
            bk_tenant_id,
            sorted(exhausted_sub_ids),
            limit,
        )
    if records and not pending_sub_ids and not exhausted_sub_ids:
        logger.info("federation successful config unchanged, skip reconcile, tenant->[%s]", bk_tenant_id)
    active_proxy_ids = {record.fed_cluster_id for record in records if not record.is_deleted}
    active_sub_ids = {record.sub_cluster_id for record in records if not record.is_deleted}
    affected = [record for record in records if record.sub_cluster_id in pending_sub_ids]
    return FederationReconcilePlan(
        active_proxy_cluster_ids=sorted({record.fed_cluster_id for record in affected if not record.is_deleted}),
        active_sub_cluster_ids=sorted(pending_sub_ids & active_sub_ids),
        removed_proxy_cluster_ids=sorted({record.fed_cluster_id for record in affected} - active_proxy_ids),
        removed_sub_cluster_ids=sorted(pending_sub_ids - active_sub_ids),
    )


def validate_federation_topology(fed_clusters: dict) -> None:
    """校验完整拓扑中同一子集群的 namespace 是否被多个联邦代理重复声明。"""
    namespace_owners: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for fed_cluster_id, fed_cluster_data in fed_clusters.items():
        for sub_cluster_id, namespaces in fed_cluster_data.get("sub_clusters", {}).items():
            if namespaces is None:
                continue
            for namespace in namespaces:
                if namespace:
                    namespace_owners[sub_cluster_id][namespace].add(fed_cluster_id)

    conflicts = {
        sub_cluster_id: {
            namespace: sorted(fed_cluster_ids)
            for namespace, fed_cluster_ids in namespace_map.items()
            if len(fed_cluster_ids) > 1
        }
        for sub_cluster_id, namespace_map in namespace_owners.items()
    }
    conflicts = {sub_cluster_id: values for sub_cluster_id, values in conflicts.items() if values}
    if conflicts:
        raise FederationNamespaceConflictError(f"federation topology has overlapping namespaces: {conflicts}")


def get_bcs_metric_table_id(bk_tenant_id: str, bk_data_id: int) -> str | None:
    """获取 BCS 内置指标的默认结果表，避免自动分表后按 data_id ``get`` 出现多条记录。"""
    group_table_id = (
        models.TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_data_id=bk_data_id,
        )
        .values_list("table_id", flat=True)
        .first()
    )
    if group_table_id:
        return group_table_id

    table_ids = models.DataSourceResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=bk_data_id,
    ).order_by("table_id")
    return (
        table_ids.filter(table_id__endswith=".__default__").values_list("table_id", flat=True).first()
        or table_ids.values_list("table_id", flat=True).first()
    )


def _get_metric_context(bk_tenant_id: str, cluster_id: str) -> FederationMetricContext:
    cluster = models.BCSClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    if not cluster.K8sMetricDataID:
        raise ValueError(f"cluster({cluster_id}) K8sMetricDataID is empty")

    data_source = models.DataSource.objects.get(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=cluster.K8sMetricDataID,
    )
    table_id = get_bcs_metric_table_id(bk_tenant_id=bk_tenant_id, bk_data_id=cluster.K8sMetricDataID)
    if not table_id:
        raise ValueError(f"cluster({cluster_id}) metric result table is not ready")

    storage_cluster_name = ""
    access_vm_record = (
        models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id=table_id)
        .order_by("-id")
        .first()
    )
    if access_vm_record:
        vm_cluster = models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_id=access_vm_record.vm_cluster_id,
            cluster_type=models.ClusterInfo.TYPE_VM,
        ).first()
        if vm_cluster:
            storage_cluster_name = vm_cluster.cluster_name

    if not storage_cluster_name:
        vm_cluster = get_vm_cluster_id_name(
            bk_tenant_id=bk_tenant_id,
            space_type=SpaceTypes.BKCC.value,
            space_id=str(cluster.bk_biz_id),
        )
        storage_cluster_name = vm_cluster["cluster_name"]

    return FederationMetricContext(
        cluster=cluster,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name=storage_cluster_name,
    )


def _report_reconcile_metric(context: FederationMetricContext, strategy: str, status: int) -> None:
    report_metadata_data_link_access_metric(
        version=DATA_LINK_V4_VERSION_NAME,
        data_id=context.data_source.bk_data_id,
        biz_id=context.cluster.bk_biz_id,
        status=status,
        strategy=strategy,
    )


def ensure_federal_proxy_data_link(bk_tenant_id: str, fed_cluster_id: str) -> None:
    context = _get_metric_context(bk_tenant_id=bk_tenant_id, cluster_id=fed_cluster_id)
    logger.info(
        "ensure_federal_proxy_data_link: tenant->[%s],fed_cluster_id->[%s],data_id->[%s],table_id->[%s]",
        bk_tenant_id,
        fed_cluster_id,
        context.data_source.bk_data_id,
        context.table_id,
    )
    try:
        create_bkbase_data_link(
            bk_biz_id=context.cluster.bk_biz_id,
            monitor_table_id=context.table_id,
            data_source=context.data_source,
            storage_cluster_name=context.storage_cluster_name,
            data_link_strategy=DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
            bcs_cluster_id=fed_cluster_id,
            cleanup_absent_components=True,
        )
    except Exception:
        _report_reconcile_metric(context, DataLink.BCS_FEDERAL_PROXY_TIME_SERIES, ACCESS_DATA_LINK_FAILURE_STATUS)
        raise
    _report_reconcile_metric(context, DataLink.BCS_FEDERAL_PROXY_TIME_SERIES, ACCESS_DATA_LINK_SUCCESS_STATUS)


def _build_federation_routes(bk_tenant_id: str, sub_cluster_id: str) -> list[dict]:
    records = list(
        models.BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            sub_cluster_id=sub_cluster_id,
            is_deleted=False,
        ).order_by("fed_cluster_id")
    )
    namespace_owners: dict[str, list[str]] = defaultdict(list)
    routes: list[dict] = []
    for record in records:
        namespaces = sorted({namespace for namespace in (record.fed_namespaces or []) if namespace})
        for namespace in namespaces:
            namespace_owners[namespace].append(record.fed_cluster_id)
        if not namespaces:
            continue
        if not record.fed_builtin_metric_table_id:
            raise FederationReconcileError(
                f"federation proxy metric table is not ready: tenant={bk_tenant_id},"
                f"fed_cluster_id={record.fed_cluster_id},sub_cluster_id={sub_cluster_id}"
            )
        routes.append(
            {
                "fed_cluster_id": record.fed_cluster_id,
                "namespaces": namespaces,
                "target_metric_table_id": record.fed_builtin_metric_table_id,
            }
        )

    conflicts = {
        namespace: sorted(set(fed_cluster_ids))
        for namespace, fed_cluster_ids in namespace_owners.items()
        if len(set(fed_cluster_ids)) > 1
    }
    if conflicts:
        raise FederationNamespaceConflictError(
            f"sub_cluster_id={sub_cluster_id} has overlapping federation namespaces: {conflicts}"
        )
    return routes


def _get_subset_data_link(context: FederationMetricContext) -> DataLink | None:
    """按联邦子链路的业务关系定位，兼容存量名字以及尚未完成 sync_metadata 的链路。"""
    tenant = context.data_source.bk_tenant_id
    # 名称不再能由 DataId 推导；先收集 RT 映射，同时兼容只写入主记录的未完成申请。
    related_names = set(
        models.BkBaseResultTable.objects.filter(
            bk_tenant_id=tenant,
            monitor_table_id=context.table_id,
        ).values_list("data_link_name", flat=True)
    )
    candidates = [
        link
        for link in DataLink.objects.filter(
            Q(bk_data_id=context.data_source.bk_data_id) | Q(data_link_name__in=related_names),
            bk_tenant_id=tenant,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_strategy=DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
        )
        if link.pk in related_names or context.table_id in link.table_ids or not link.table_ids
    ]
    # 迁移后已回填来源和 RT 的链路优先；旧名称的空主记录可能仍保留 RT 映射。
    explicit_candidates = [
        link
        for link in candidates
        if link.bk_data_id == context.data_source.bk_data_id and context.table_id in link.table_ids
    ]
    if explicit_candidates:
        candidates = explicit_candidates
    if len(candidates) > 1:
        raise FederationReconcileError(f"ambiguous federation subset links: tenant={tenant}, table={context.table_id}")
    return candidates[0] if candidates else None


def ensure_federal_subset_data_link(bk_tenant_id: str, sub_cluster_id: str) -> None:
    context = _get_metric_context(bk_tenant_id=bk_tenant_id, cluster_id=sub_cluster_id)
    routes = _build_federation_routes(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
    if not routes:
        delete_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
        return

    # 首次名称分配和 RT 映射在本地一起提交，后续 apply 失败时按此关系继续重试。
    with transaction.atomic(using=DATABASE_CONNECTION_NAME):
        models.ResultTable.objects.select_for_update().get(bk_tenant_id=bk_tenant_id, table_id=context.table_id)
        data_link = _get_subset_data_link(context)
        if data_link is None:
            data_link = data_link_utils.create_resource_with_random_name(
                DataLink,
                DataLinkNameScene.FEDERAL_SUBSET,
                context.data_source.bk_data_id,
                name_field="data_link_name",
                bk_tenant_id=bk_tenant_id,
                namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                data_link_strategy=DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
                bk_data_id=context.data_source.bk_data_id,
                table_ids=[context.table_id],
            )
        else:
            data_link.bk_data_id = context.data_source.bk_data_id
            data_link.table_ids = [context.table_id]
            data_link.save(update_fields=["bk_data_id", "table_ids", "last_modify_time"])
        models.BkBaseResultTable.objects.get_or_create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link.pk,
            defaults={"monitor_table_id": context.table_id, "storage_type": models.ClusterInfo.TYPE_VM},
        )

    logger.info(
        "ensure_federal_subset_data_link: tenant->[%s],sub_cluster_id->[%s],routes->[%s]",
        bk_tenant_id,
        sub_cluster_id,
        routes,
    )
    try:
        data_link.apply_data_link(
            bk_biz_id=context.cluster.bk_biz_id,
            data_source=context.data_source,
            table_id=context.table_id,
            storage_cluster_name=context.storage_cluster_name,
            federation_routes=routes,
        )
        data_link.sync_metadata(
            table_id=context.table_id,
            storage_cluster_name=context.storage_cluster_name,
        )
    except Exception:
        _report_reconcile_metric(context, DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES, ACCESS_DATA_LINK_FAILURE_STATUS)
        raise
    _report_reconcile_metric(context, DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES, ACCESS_DATA_LINK_SUCCESS_STATUS)


def delete_federal_subset_data_link(bk_tenant_id: str, sub_cluster_id: str) -> None:
    context = _get_metric_context(bk_tenant_id=bk_tenant_id, cluster_id=sub_cluster_id)
    # 创建和删除使用同一套关联查询；仅清理 Databus，保留链路、路由组件及共享 RT/Binding。
    with transaction.atomic(using=DATABASE_CONNECTION_NAME):
        models.ResultTable.objects.select_for_update().get(bk_tenant_id=bk_tenant_id, table_id=context.table_id)
        data_link = _get_subset_data_link(context)
        if data_link is None:
            return
        data_link_name = data_link.pk
        data_link.delete_data_link()
        models.BkBaseResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
        ).update(status=DataLinkResourceStatus.TERMINATING.value)
    logger.info(
        "delete_federal_subset_data_link: tenant->[%s],sub_cluster_id->[%s],data_link_name->[%s]",
        bk_tenant_id,
        sub_cluster_id,
        data_link_name,
    )


def restore_standard_vm_data_link(bk_tenant_id: str, cluster_id: str) -> None:
    context = _get_metric_context(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
    create_bkbase_data_link(
        bk_biz_id=context.cluster.bk_biz_id,
        monitor_table_id=context.table_id,
        data_source=context.data_source,
        storage_cluster_name=context.storage_cluster_name,
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
        bcs_cluster_id=cluster_id,
        cleanup_absent_components=True,
    )
    logger.info(
        "restore_standard_vm_data_link: tenant->[%s],cluster_id->[%s],table_id->[%s]",
        bk_tenant_id,
        cluster_id,
        context.table_id,
    )


def reconcile_federation_data_links(
    bk_tenant_id: str,
    plan: FederationReconcilePlan,
    *,
    force: bool = False,
) -> None:
    # 计划参数兼容已排队的消息；拿锁后始终以数据库中的最新配置和状态为准。
    with service_lock(SERVICE_LOCK_METADATA_RECONCILE_FEDERATION_DATA_LINK, bk_tenant_id=bk_tenant_id):
        if force:
            sub_ids = set(
                models.BcsFederalClusterInfo.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                ).values_list("sub_cluster_id", flat=True)
            )
            reset_federation_reconcile(bk_tenant_id, sub_ids)
        _reconcile_federation_data_links(bk_tenant_id)


def _reconcile_federation_data_links(bk_tenant_id: str) -> None:
    plan = get_federation_reconcile_plan(bk_tenant_id)
    if plan == FederationReconcilePlan():
        logger.info("federation reconcile skipped: success or failure limit reached, tenant->[%s]", bk_tenant_id)
        return

    records = list(models.BcsFederalClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id))
    grouped = defaultdict(list)
    active_proxy_ids = set()
    for record in records:
        grouped[record.sub_cluster_id].append(record)
        if not record.is_deleted:
            active_proxy_ids.add(record.fed_cluster_id)

    proxy_errors = {}
    for proxy_id in plan.active_proxy_cluster_ids:
        try:
            ensure_federal_proxy_data_link(bk_tenant_id=bk_tenant_id, fed_cluster_id=proxy_id)
        except Exception as error:
            proxy_errors[proxy_id] = str(error)
            logger.exception("reconcile federation proxy failed, fed_cluster_id->[%s]", proxy_id)

    subset_errors = {}
    for sub_id in plan.active_sub_cluster_ids + plan.removed_sub_cluster_ids:
        sub_records = grouped[sub_id]
        dependencies = {record.fed_cluster_id for record in sub_records if not record.is_deleted}
        errors = []
        logger.info(
            "federation reconcile attempt, tenant->[%s],sub_cluster->[%s],failures->[%s/%s]",
            bk_tenant_id,
            sub_id,
            max(record.reconcile_failures for record in sub_records),
            settings.BCS_FEDERATION_RECONCILE_MAX_FAILURES,
        )
        failed_dependencies = dependencies & proxy_errors.keys()
        if failed_dependencies:
            errors.append(f"failed_dependencies={sorted(failed_dependencies)}")
        else:
            try:
                if sub_id in plan.active_sub_cluster_ids:
                    ensure_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_id)
                else:
                    delete_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_id)
            except Exception as error:
                errors.append(str(error))
                logger.exception("reconcile federation subset failed, sub_cluster_id->[%s]", sub_id)
        subset_errors[sub_id] = errors

    restore_errors = {}
    for proxy_id in plan.removed_proxy_cluster_ids:
        try:
            restore_standard_vm_data_link(bk_tenant_id=bk_tenant_id, cluster_id=proxy_id)
        except Exception as error:
            restore_errors[proxy_id] = str(error)
            logger.exception("restore federation proxy failed, fed_cluster_id->[%s]", proxy_id)

    failures = []
    for sub_id, errors in subset_errors.items():
        sub_records = grouped[sub_id]
        removed_proxies = {record.fed_cluster_id for record in sub_records} - active_proxy_ids
        for proxy_id in sorted(removed_proxies & restore_errors.keys()):
            errors.append(f"restore_proxy:{proxy_id}:{restore_errors[proxy_id]}")

        count = max(record.reconcile_failures for record in sub_records)
        if errors:
            count += 1
            status = "failed"
            failures.append(f"subset:{sub_id}:{errors}")
            logger.error(
                "federation reconcile failed, tenant->[%s],sub_cluster->[%s],failures->[%s/%s],stopped->[%s]",
                bk_tenant_id,
                sub_id,
                count,
                settings.BCS_FEDERATION_RECONCILE_MAX_FAILURES,
                count >= settings.BCS_FEDERATION_RECONCILE_MAX_FAILURES,
            )
        else:
            count = 0
            status = "success"
            logger.info("federation reconcile success, tenant->[%s],sub_cluster->[%s]", bk_tenant_id, sub_id)
        models.BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            sub_cluster_id=sub_id,
        ).update(reconcile_status=status, reconcile_failures=count)

    if failures:
        raise FederationReconcileError("; ".join(failures))
