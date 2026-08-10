from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from django.conf import settings

from constants.data_source import DATA_LINK_V4_VERSION_NAME
from metadata import models
from metadata.models.data_link import DataLink
from metadata.models.data_link.utils import compose_bkdata_data_id_name
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


def _get_subset_data_link_name(context: FederationMetricContext) -> str:
    return compose_bkdata_data_id_name(
        context.data_source.data_name,
        strategy=DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
    )


def ensure_federal_subset_data_link(bk_tenant_id: str, sub_cluster_id: str) -> None:
    context = _get_metric_context(bk_tenant_id=bk_tenant_id, cluster_id=sub_cluster_id)
    routes = _build_federation_routes(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
    if not routes:
        delete_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
        return

    data_link_name = _get_subset_data_link_name(context)
    data_link = DataLink.objects.filter(data_link_name=data_link_name).first()
    if data_link is None:
        data_link = DataLink.objects.create(
            bk_tenant_id=bk_tenant_id,
            data_link_name=data_link_name,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_strategy=DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
            bk_data_id=context.data_source.bk_data_id,
            table_ids=[context.table_id],
        )
    else:
        if data_link.bk_tenant_id != bk_tenant_id:
            raise ValueError(
                f"data_link_name({data_link_name}) belongs to tenant({data_link.bk_tenant_id}), "
                f"cannot use for tenant({bk_tenant_id})"
            )
        data_link.namespace = settings.DEFAULT_VM_DATA_LINK_NAMESPACE
        data_link.data_link_strategy = DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES
        data_link.bk_data_id = context.data_source.bk_data_id
        data_link.table_ids = [context.table_id]
        data_link.save(update_fields=["namespace", "data_link_strategy", "bk_data_id", "table_ids", "last_modify_time"])

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
    data_link_name = _get_subset_data_link_name(context)
    data_link = DataLink.objects.filter(
        bk_tenant_id=bk_tenant_id,
        data_link_name=data_link_name,
        data_link_strategy=DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
    ).first()
    if data_link:
        data_link.delete_data_link()
    models.BkBaseResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id,
        data_link_name=data_link_name,
    ).delete()
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


def reconcile_federation_data_links(bk_tenant_id: str, plan: FederationReconcilePlan) -> None:
    plan = plan.normalized()
    active_records = models.BcsFederalClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        is_deleted=False,
    )
    current_proxy_cluster_ids = set(active_records.values_list("fed_cluster_id", flat=True))
    current_sub_cluster_ids = set(active_records.values_list("sub_cluster_id", flat=True))
    # Celery 任务可能因重试而乱序，active 状态始终以执行时数据库中的完整拓扑为准；
    # removed 则过滤掉已重新加入拓扑的集群，避免旧任务覆盖新状态。
    plan = FederationReconcilePlan(
        active_proxy_cluster_ids=sorted(current_proxy_cluster_ids),
        active_sub_cluster_ids=sorted(current_sub_cluster_ids),
        removed_proxy_cluster_ids=sorted(set(plan.removed_proxy_cluster_ids) - current_proxy_cluster_ids),
        removed_sub_cluster_ids=sorted(set(plan.removed_sub_cluster_ids) - current_sub_cluster_ids),
    )

    # 在修改 Proxy 策略前先校验全部子集路由，冲突或代理 RT 未就绪时整批失败并进入重试。
    for sub_cluster_id in plan.active_sub_cluster_ids:
        _build_federation_routes(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)

    failures: list[str] = []
    failed_proxy_cluster_ids: set[str] = set()

    for fed_cluster_id in plan.active_proxy_cluster_ids:
        try:
            ensure_federal_proxy_data_link(bk_tenant_id=bk_tenant_id, fed_cluster_id=fed_cluster_id)
        except Exception as error:  # pylint: disable=broad-except
            failed_proxy_cluster_ids.add(fed_cluster_id)
            failures.append(f"proxy:{fed_cluster_id}:{error}")
            logger.exception("reconcile federation proxy failed, fed_cluster_id->[%s]", fed_cluster_id)

    for sub_cluster_id in plan.active_sub_cluster_ids:
        dependency_ids = set(
            models.BcsFederalClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                sub_cluster_id=sub_cluster_id,
                is_deleted=False,
            ).values_list("fed_cluster_id", flat=True)
        )
        failed_dependencies = sorted(dependency_ids & failed_proxy_cluster_ids)
        if failed_dependencies:
            failures.append(f"subset:{sub_cluster_id}:failed_dependencies={failed_dependencies}")
            logger.warning(
                "reconcile federation subset skipped for failed dependencies, sub_cluster_id->[%s],dependencies->[%s]",
                sub_cluster_id,
                failed_dependencies,
            )
            continue
        try:
            ensure_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
        except Exception as error:  # pylint: disable=broad-except
            failures.append(f"subset:{sub_cluster_id}:{error}")
            logger.exception("reconcile federation subset failed, sub_cluster_id->[%s]", sub_cluster_id)

    for sub_cluster_id in plan.removed_sub_cluster_ids:
        try:
            delete_federal_subset_data_link(bk_tenant_id=bk_tenant_id, sub_cluster_id=sub_cluster_id)
        except Exception as error:  # pylint: disable=broad-except
            failures.append(f"delete_subset:{sub_cluster_id}:{error}")
            logger.exception("delete federation subset failed, sub_cluster_id->[%s]", sub_cluster_id)

    for fed_cluster_id in plan.removed_proxy_cluster_ids:
        try:
            restore_standard_vm_data_link(bk_tenant_id=bk_tenant_id, cluster_id=fed_cluster_id)
        except Exception as error:  # pylint: disable=broad-except
            failures.append(f"restore_proxy:{fed_cluster_id}:{error}")
            logger.exception("restore federation proxy failed, fed_cluster_id->[%s]", fed_cluster_id)

    if failures:
        raise FederationReconcileError("; ".join(failures))
