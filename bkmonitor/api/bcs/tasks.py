"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from itertools import islice

from celery import shared_task
from django.db import router, transaction
from django.db.models import Q
from django.utils import timezone

from alarm_backends.core.lock.service_lock import share_lock
from bkmonitor.models import (
    BCSBase,
    BCSCluster,
    BCSContainer,
    BCSIngress,
    BCSNode,
    BCSPod,
    BCSPodMonitor,
    BCSService,
    BCSServiceMonitor,
    BCSWorkload,
)
from bkmonitor.utils.ip import exploded_ip
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("kubernetes")
logger.setLevel(logging.INFO)


def bulk_save_resources(
    resource: type[BCSBase],
    resource_models: Iterable[BCSBase],
    sync_unique_field: str,
    sync_fields: list,
    sync_filter: dict | None = None,
    datetime_fields: list | set | None = None,
    delete_missing: bool = True,
    prepare_batch: Callable | None = None,
):
    """逐批提交资源和标签；只有完整耗尽远程输入后才清理缺失行。

    last_synced_at 是本行成功确认的时间，分页失败时前批可保留，不能用它判断整轮成功。
    """
    seen_ids = set()
    source = iter(resource_models)
    while batch := list(islice(source, 100)):
        if prepare_batch:
            prepare_batch(batch)
        seen_ids.update(save_resource_batch(resource, batch, sync_fields))
    if delete_missing:
        delete_missing_resources(resource, sync_filter, seen_ids)
    return seen_ids


def save_resource_batch(resource, batch, sync_fields):
    database = router.db_for_write(resource)
    manager = resource._base_manager.using(database)
    identity_fields = resource.SYNC_IDENTITY_FIELDS

    def identity(model):
        return tuple(getattr(model, field) for field in identity_fields)

    incoming = {identity(model): model for model in batch}
    if len(incoming) != len(batch):
        raise ValueError(f"duplicate {resource.__name__} identity in input")
    query = Q()
    for key in incoming:
        query |= Q(**dict(zip(identity_fields, key)))

    with transaction.atomic(using=database):
        existing = {}
        for model in manager.select_for_update().filter(query):
            key = identity(model)
            if key in existing:
                # Cluster 没有独立自然唯一约束，歧义必须失败，不能任取一行覆盖配置。
                raise ValueError(f"ambiguous {resource.__name__} identity: {key}")
            existing[key] = model

        now = timezone.now()
        inserted, updated = [], []
        for key, model in incoming.items():
            model.last_synced_at = now
            if key in existing:
                model.id = existing[key].id
                updated.append(model)
            else:
                inserted.append(model)
        if inserted:
            manager.bulk_create(inserted, batch_size=100)
        if updated:
            # 自然键稳定，归属及 hash 更新复用原行；只更新同步字段，保留告警/灰度等配置。
            manager.bulk_update(updated, list(dict.fromkeys([*sync_fields, "last_synced_at"])), batch_size=100)

        # MySQL bulk_create 不保证回填主键；按自然身份回读并验证后才能写标签。
        saved = {}
        for model in manager.select_for_update().filter(query):
            key = identity(model)
            if key in saved:
                raise ValueError(f"ambiguous {resource.__name__} identity: {key}")
            saved[key] = model
        for key, model in incoming.items():
            if key not in saved or not saved[key].id or saved[key].unique_hash != model.unique_hash:
                raise ValueError(f"failed to read back {resource.__name__} identity: {key}")
            model.id = saved[key].id
        if resource is not BCSCluster:
            resource.bulk_save_labels(batch, using=database)
    return {model.id for model in batch}


def delete_missing_resources(resource, sync_filter, seen_ids):
    manager = resource._base_manager.using(router.db_for_write(resource))
    candidates = manager.filter(**(sync_filter or {})).values_list("id", flat=True).iterator(chunk_size=5000)
    deleted_ids = []
    for resource_id in candidates:
        if resource_id not in seen_ids:
            deleted_ids.append(resource_id)
        if len(deleted_ids) >= 5000:
            manager.filter(id__in=deleted_ids).delete()
            deleted_ids = []
    if deleted_ids:
        manager.filter(id__in=deleted_ids).delete()


@share_lock(identify="sync_bcs_cluster_to_db")
def sync_bcs_cluster_to_db() -> list[BCSCluster]:
    """先提交各租户基础名录，再独立统计节点；失败租户不参与清理。"""
    cluster_models, failures, deleted_cluster_ids = [], [], set()
    sync_fields = [
        "bk_tenant_id",
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "project_name",
        "environment",
        "status",
        "created_at",
        "updated_at",
        "unique_hash",
        "space_uid",
    ]
    database = router.db_for_write(BCSCluster)
    manager = BCSCluster._base_manager.using(database)
    for tenant in api.bk_login.list_tenant():
        tenant_id = tenant["id"]
        try:
            models = BCSCluster.load_list_from_api({"bk_tenant_id": tenant_id})
            # 在写入前验证整份名录，跨批重复和既有歧义均不能触发尾删。
            cluster_ids = [model.bcs_cluster_id for model in models]
            if len(cluster_ids) != len(set(cluster_ids)):
                raise ValueError("duplicate cluster identity in tenant inventory")
            tenant_filter = {"bk_tenant_id": tenant_id}
            previous_ids = set(manager.filter(**tenant_filter).values_list("bcs_cluster_id", flat=True))
            bulk_save_resources(BCSCluster, models, "unique_hash", sync_fields, tenant_filter)
            deleted_cluster_ids.update(previous_ids - set(cluster_ids))
            cluster_models.extend(models)
        except Exception as exc_info:
            failures.append(exc_info)
            logger.exception("sync_bcs_cluster_to_db tenant(%s) failed", tenant_id)

    # 只清理成功名录明确删除的集群，含最后一个集群和 Ingress。
    still_existing = set(
        manager.filter(bcs_cluster_id__in=deleted_cluster_ids).values_list("bcs_cluster_id", flat=True)
    )
    deleted_cluster_ids -= still_existing
    if deleted_cluster_ids:
        for resource in [
            BCSNode,
            BCSPod,
            BCSContainer,
            BCSWorkload,
            BCSService,
            BCSIngress,
            BCSServiceMonitor,
            BCSPodMonitor,
        ]:
            resource._base_manager.using(router.db_for_write(resource)).filter(
                bcs_cluster_id__in=deleted_cluster_ids
            ).delete()

    # 基础名录已经全部推进后才请求计数；失败保留原值，继续后序集群。
    for cluster in cluster_models:
        try:
            counts = api.kubernetes.fetch_k8s_node_count_by_cluster(
                {"bk_tenant_id": cluster.bk_tenant_id, "bcs_cluster_id": cluster.bcs_cluster_id}
            )
            manager.filter(id=cluster.id).update(node_count=counts["node_count"])
            cluster.node_count = counts["node_count"]
        except Exception as exc_info:
            failures.append(exc_info)
            logger.exception("sync_bcs_cluster_to_db cluster(%s) node count failed", cluster.bcs_cluster_id)
    if failures:
        raise RuntimeError(f"BCS inventory/count failed for {len(failures)} objects") from failures[0]
    return cluster_models


def run_sub_task(task_name: str, wrapper: Callable, bcs_cluster_id: str):
    """执行子任务 ."""
    start = time.time()
    identify = f"{task_name}_{bcs_cluster_id}"
    exception = None
    executed = False

    def execute(cluster_id):
        nonlocal executed
        executed = True
        return wrapper(cluster_id)

    try:
        logger.info("^[Cron Task](%s %s) start", task_name, bcs_cluster_id)
        share_lock(identify=identify)(execute)(bcs_cluster_id)
        if not executed:
            logger.info("[Cron Task](%s %s) skipped: lock held", task_name, bcs_cluster_id)
    except Exception as exc_info:  # noqa
        exception = exc_info
        logger.exception("![Cron Task](%s %s) error: %s", task_name, bcs_cluster_id, exc_info)
        raise
    finally:
        time_cost = time.time() - start
        logger.info("$[Cron Task](%s %s) cost: %s", task_name, bcs_cluster_id, time_cost)
        queue_name = "celery_cron"
        metrics.CRON_BCS_SUB_TASK_EXECUTE_TIME.labels(
            task_name=task_name,
            sync_bcs_cluster_id=bcs_cluster_id,
            queue=queue_name,
        ).observe(time_cost)
        metrics.CRON_BCS_SUB_TASK_EXECUTE_COUNT.labels(
            task_name=task_name,
            sync_bcs_cluster_id=bcs_cluster_id,
            exception=exception,
            status=metrics.StatusEnum.from_exc(exception) if exception or executed else metrics.StatusEnum.DEFERRED,
            queue=queue_name,
        ).inc()
        metrics.report_all()


def sync_cluster_resources(resource, bcs_cluster_id, sync_fields, datetime_fields, prepare_batch=None):
    clusters = BCSCluster.objects.all()
    if bcs_cluster_id:
        clusters = clusters.filter(bcs_cluster_id=bcs_cluster_id)
    failures = []
    synced_cluster_ids = []
    for cluster in clusters.values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id"):
        cluster_id = cluster["bcs_cluster_id"]
        try:
            models = resource.load_list_from_api({cluster_id: (cluster["bk_tenant_id"], cluster["bk_biz_id"])})
            bulk_save_resources(
                resource,
                models,
                "unique_hash",
                sync_fields,
                {"bcs_cluster_id": cluster_id},
                datetime_fields,
                prepare_batch=prepare_batch,
            )
            synced_cluster_ids.append(cluster_id)
        except Exception as exc_info:
            failures.append(exc_info)
            logger.exception("sync %s cluster(%s) failed", resource.__name__, cluster_id)
    if failures:
        raise RuntimeError(f"{resource.__name__} sync failed for {len(failures)} clusters") from failures[0]
    # 调用方需要结果时再读库；定时任务忽略返回值，不重新聚合整个资源模型列表。
    return resource._base_manager.using(router.db_for_write(resource)).filter(bcs_cluster_id__in=synced_cluster_ids)


def populate_node_host_ids(nodes):
    biz_hosts = defaultdict(list)
    for node in nodes:
        if node.ip:
            biz_hosts[node.bk_biz_id].append({"ip": node.ip, "bk_cloud_id": node.cloud_id})
    host_ids = {}
    for bk_biz_id, host_ips in biz_hosts.items():
        for host in api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=host_ips):
            for ip in (host.bk_host_innerip, host.bk_host_innerip_v6):
                if ip:
                    host_ids[(exploded_ip(ip), str(host.bk_cloud_id))] = host.bk_host_id
    for node in nodes:
        node.bk_host_id = host_ids.get((exploded_ip(node.ip), str(node.cloud_id))) if node.ip else None


@share_lock(identify="sync_bcs_ingress_to_db")
def sync_bcs_ingress_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_ingress_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_ingress_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_ingress_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_ingress, bcs_cluster_id)


def sync_bcs_ingress(bcs_cluster_id):
    """同步bcs ingress元数据到数据库 ."""
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "class_name",
        "service_list",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(BCSIngress, bcs_cluster_id, sync_fields, datetime_fields)


@share_lock(identify="sync_bcs_workload_to_db")
def sync_bcs_workload_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_workload_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_workload_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_workload_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_workload, bcs_cluster_id)


def sync_bcs_workload(bcs_cluster_id):
    """同步bcs workload元数据到数据库 ."""
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "type",
        "pod_name_list",
        "images",
        "pod_count",
        "container_count",
        "resource_requests_cpu",
        "resource_requests_memory",
        "resource_limits_cpu",
        "resource_limits_memory",
        "status",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(BCSWorkload, bcs_cluster_id, sync_fields, datetime_fields)


@share_lock(identify="sync_bcs_service_to_db")
def sync_bcs_service_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_service_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_service_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_service_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_service, bcs_cluster_id)


def sync_bcs_service(bcs_cluster_id):
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "type",
        "cluster_ip",
        "external_ip",
        "ports",
        "pod_name_list",
        "endpoint_count",
        "pod_count",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(BCSService, bcs_cluster_id, sync_fields, datetime_fields)


@share_lock(identify="sync_bcs_pod_to_db")
def sync_bcs_pod_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_pod_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_pod_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_pod_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_pod, bcs_cluster_id)


def sync_bcs_pod(bcs_cluster_id):
    sync_unique_field = "unique_hash"
    # 同步更新的字段
    pod_sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "node_name",
        "node_ip",
        "workload_type",
        "workload_name",
        "total_container_count",
        "ready_container_count",
        "pod_ip",
        "images",
        "restarts",
        "resource_requests_cpu",
        "resource_requests_memory",
        "resource_limits_cpu",
        "resource_limits_memory",
        "status",
        "created_at",
        "unique_hash",
    ]

    container_sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "pod_name",
        "workload_type",
        "workload_name",
        "node_ip",
        "node_name",
        "image",
        "resource_requests_cpu",
        "resource_requests_memory",
        "resource_limits_cpu",
        "resource_limits_memory",
        "status",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    try:
        cluster = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
    except BCSCluster.DoesNotExist:
        return

    bk_biz_id = cluster.bk_biz_id
    bk_tenant_id = cluster.bk_tenant_id
    pods = iter(api.kubernetes.fetch_k8s_pod_list_by_cluster(bk_tenant_id=bk_tenant_id, bcs_cluster_id=bcs_cluster_id))
    sync_filter = {"bcs_cluster_id": bcs_cluster_id}
    pod_ids, container_ids = set(), set()
    while batch := list(islice(pods, 100)):
        pod_ids.update(
            bulk_save_resources(
                BCSPod,
                (BCSPod.from_api_item(pod, bk_biz_id) for pod in batch),
                sync_unique_field,
                pod_sync_fields,
                sync_filter,
                datetime_fields,
                delete_missing=False,
            )
        )
        container_ids.update(
            bulk_save_resources(
                BCSContainer,
                (container for pod in batch for container in BCSContainer.from_pod(pod, bk_biz_id)),
                sync_unique_field,
                container_sync_fields,
                sync_filter,
                datetime_fields,
                delete_missing=False,
            )
        )
    # 同一 Pod 流完整结束后才清理两类资源，中途错误保留所有未见旧行。
    delete_missing_resources(BCSPod, sync_filter, pod_ids)
    delete_missing_resources(BCSContainer, sync_filter, container_ids)


@share_lock(identify="sync_bcs_node_to_db")
def sync_bcs_node_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_node_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_node_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_node_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_node, bcs_cluster_id)


def sync_bcs_node(bcs_cluster_id):
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "taints",
        "roles",
        "ip",
        "endpoint_count",
        "pod_count",
        "cloud_id",
        "bk_host_id",
        "status",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(
        BCSNode, bcs_cluster_id, sync_fields, datetime_fields, prepare_batch=populate_node_host_ids
    )


@share_lock(identify="sync_bcs_service_monitor_to_db")
def sync_bcs_service_monitor_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_service_monitor_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_service_monitor_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_service_monitor_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_service_monitor, bcs_cluster_id)


def sync_bcs_service_monitor(bcs_cluster_id):
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "metric_path",
        "metric_port",
        "metric_interval",
        "status",
        "created_at",
        "unique_hash",
        "monitor_status",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(BCSServiceMonitor, bcs_cluster_id, sync_fields, datetime_fields)


@share_lock(identify="sync_bcs_pod_monitor_to_db")
def sync_bcs_pod_monitor_to_db():
    clusters = BCSCluster.objects.all().values("bk_biz_id", "bcs_cluster_id")
    for cluster in clusters:
        bcs_cluster_id = cluster["bcs_cluster_id"]
        sync_bcs_pod_monitor_to_db_sub_task.apply_async(args=(bcs_cluster_id,))


@shared_task(ignore_result=True, queue="celery_cron")
def sync_bcs_pod_monitor_to_db_sub_task(bcs_cluster_id):
    task_name = "sync_bcs_pod_monitor_to_db_sub_task"
    run_sub_task(task_name, sync_bcs_pod_monitor, bcs_cluster_id)


def sync_bcs_pod_monitor(bcs_cluster_id):
    # 同步更新的字段
    sync_fields = [
        "bk_biz_id",
        "bcs_cluster_id",
        "name",
        "namespace",
        "metric_path",
        "metric_port",
        "metric_interval",
        "status",
        "created_at",
        "unique_hash",
        "monitor_status",
    ]
    datetime_fields = ["created_at"]

    return sync_cluster_resources(BCSPodMonitor, bcs_cluster_id, sync_fields, datetime_fields)


@share_lock(ttl=3600, identify="bcs_sync_bcs_cluster_resource")
def sync_bcs_cluster_resource():
    """同步cluster的资源使用率 ."""
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSCluster.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_workload_resource")
def sync_bcs_workload_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSWorkload.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_service_resource")
def sync_bcs_service_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSService.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_pod_resource")
def sync_bcs_pod_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSPod.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_container_resource")
def sync_bcs_container_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSContainer.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_node_resource")
def sync_bcs_node_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSNode.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_service_monitor_resource")
def sync_bcs_service_monitor_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSServiceMonitor.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bcs_pod_monitor_resource")
def sync_bcs_pod_monitor_resource():
    cluster_models = BCSCluster.objects.all()
    for cluster_model in cluster_models:
        bcs_cluster_id = cluster_model.bcs_cluster_id
        bk_biz_id = cluster_model.bk_biz_id
        try:
            BCSPodMonitor.sync_resource_usage(bk_biz_id, bcs_cluster_id)
        except Exception as exc_info:
            logger.exception(exc_info)


@share_lock(ttl=3600, identify="bcs_sync_bkmonitor_operator_info")
def sync_bkmonitor_operator_info():
    clusters = BCSCluster.objects.all()
    for c in clusters:
        try:
            c.sync_operator_info()
        except Exception as exc_info:
            logger.exception(exc_info)
