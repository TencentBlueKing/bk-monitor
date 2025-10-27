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
from datetime import datetime
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.ip import exploded_ip
from core.drf_resource import api
from core.prometheus import metrics

logger = logging.getLogger("kubernetes")
logger.setLevel(logging.INFO)


def from_iso_format(start_time: str) -> datetime | None:
    """将iso8601格式的字符串转换为当前时区的时间对象 ."""
    start_time_obj = parse_datetime(start_time)
    if not start_time_obj:
        return None

    # 转换为当前时区的时间
    current_timezone = timezone.get_current_timezone()
    start_at_current_timezone = start_time_obj.astimezone(current_timezone)
    start_at_current_timezone_naive = timezone.make_naive(start_at_current_timezone)
    return start_at_current_timezone_naive


def get_model_value(model: BCSBase, field: str, datetime_fields: set | None) -> Any:
    """获得模型的值 ."""
    value = getattr(model, field)
    if datetime_fields and value and field in datetime_fields:
        if isinstance(value, str):
            value = from_iso_format(value)
        elif isinstance(value, datetime):
            current_timezone = timezone.get_current_timezone()
            value_at_current_timezone = value.astimezone(current_timezone)
            value = timezone.make_naive(value_at_current_timezone).strftime("%Y-%m-%dT%H:%M:%S")
    return value


def bulk_save_resources(
    resource: type[BCSBase],
    resource_models: Iterable[BCSBase],
    sync_unique_field: str,
    sync_fields: list,
    sync_filter: dict | None = None,
    datetime_fields: list | set | None = None,
):
    """同步指定资源 ."""
    datetime_field_set = set(datetime_fields) if datetime_fields else None

    # 本地资源
    if not sync_filter:
        history_models = resource.objects.all()
    else:
        history_models = resource.objects.filter(**sync_filter)
    old_unique_hash_set = {getattr(model, sync_unique_field) for model in history_models}
    old_data_dict = {getattr(model, sync_unique_field): model for model in history_models}

    # 远程资源
    new_unique_hash_set = set()
    insert_resource_models = []
    labels = []
    for resource_model in resource_models:
        # 生成唯一标识并加入新的集合
        unique_hash = getattr(resource_model, sync_unique_field)

        # 新增记录
        if unique_hash not in old_unique_hash_set:
            insert_resource_models.append(resource_model)
            if len(insert_resource_models) >= 100:
                try:
                    resource.objects.bulk_create(insert_resource_models)
                except Exception as exc_info:
                    logger.error(exc_info)
                insert_resource_models = []
        else:
            new_unique_hash_set.add(unique_hash)
            old_resource_model = old_data_dict[unique_hash]
            try:
                old_compare_data = [
                    get_model_value(old_resource_model, field, datetime_field_set) for field in sync_fields
                ]
                new_compare_data = [get_model_value(resource_model, field, datetime_field_set) for field in sync_fields]
            except (ValueError, OSError) as exc_info:
                # 日期格式不正确，忽略更新
                logger.exception(exc_info)
                continue

            # 补齐ID
            resource_model.id = old_data_dict[unique_hash].id
            if old_compare_data != new_compare_data:
                # 更新指定字段，防止其他的同步进程覆盖同一个字段
                resource_model.save(update_fields=sync_fields)

        labels.append(
            {
                "id": resource_model.id,
                "bcs_cluster_id": resource_model.bcs_cluster_id,
                "api_labels": getattr(resource_model, "api_labels", {}),
            }
        )

    # 新增收尾
    if insert_resource_models:
        try:
            resource.objects.bulk_create(insert_resource_models)
        except Exception as exc_info:
            logger.error(exc_info)

    # 删除记录
    delete_unique_hash_set = old_unique_hash_set - new_unique_hash_set
    if delete_unique_hash_set:
        delete_ids = [value.id for key, value in old_data_dict.items() if key in delete_unique_hash_set]
        for ids in chunks(delete_ids, 5000):
            resource.objects.filter(id__in=ids).delete()

    return labels


@share_lock(identify="sync_bcs_cluster_to_db")
def sync_bcs_cluster_to_db() -> list[BCSCluster]:
    """同步cluster数据到数据库 ."""
    # 获得全部集群信息，不包含资源使用量
    cluster_models = []

    # 查询所有租户下的集群信息
    for tenant in api.bk_login.list_tenant():
        cluster_models.extend(BCSCluster.load_list_from_api({"bk_tenant_id": tenant["id"]}))

    # 同步cluster信息
    sync_unique_field = "unique_hash"
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
        "node_count",
        "unique_hash",
        "space_uid",
    ]
    sync_filter = None
    datetime_fields = ["created_at", "updated_at"]
    bulk_save_resources(BCSCluster, cluster_models, sync_unique_field, sync_fields, sync_filter, datetime_fields)

    # 集群被删除后，需要删除相关的数据
    bcs_cluster_id_list = list(BCSCluster.objects.values_list("bcs_cluster_id", flat=True))
    if bcs_cluster_id_list:
        bcs_cluster_id_set = set(bcs_cluster_id_list)
        for model_cls in [BCSNode, BCSPod, BCSContainer, BCSWorkload, BCSService, BCSServiceMonitor, BCSPodMonitor]:
            history_bcs_cluster_id_set = {
                model["bcs_cluster_id"] for model in model_cls.objects.all().values("bcs_cluster_id").distinct()
            }
            invalid_bcs_cluster_id_list = list(history_bcs_cluster_id_set - bcs_cluster_id_set)
            if invalid_bcs_cluster_id_list:
                model_cls.objects.filter(bcs_cluster_id__in=invalid_bcs_cluster_id_list).delete()

    return cluster_models


def run_sub_task(task_name: str, wrapper: Callable, bcs_cluster_id: str):
    """执行子任务 ."""
    start = time.time()
    identify = f"{task_name}_{bcs_cluster_id}"
    exception = None
    try:
        logger.info("^[Cron Task](%s %s) start", task_name, bcs_cluster_id)
        share_lock(identify=identify)(wrapper)(bcs_cluster_id)
    except Exception as exc_info:  # noqa
        exception = exc_info
        logger.exception("![Cron Task](%s %s) error: %s", task_name, bcs_cluster_id, exc_info)
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
            status=metrics.StatusEnum.from_exc(exception),
            queue=queue_name,
        ).inc()
        metrics.report_all()


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
    sync_unique_field = "unique_hash"
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

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    if not clusters:
        return None
    ingress_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            ingress_models = BCSIngress.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_ingress error[{bcs_cluster_id}]: {exc_info}")
            continue
        bcs_cluster_id_list = list({model.bcs_cluster_id for model in ingress_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {"bcs_cluster_id__in": bcs_cluster_id_list}
        bulk_save_resources(BCSIngress, ingress_models, sync_unique_field, sync_fields, sync_filter, datetime_fields)
        # 同步标签
        patch_exists_resource_id(ingress_models)
        BCSIngress.bulk_save_labels(ingress_models)
    return ingress_models


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
    sync_unique_field = "unique_hash"
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

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    if not clusters:
        return None
    workload_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            workload_models = BCSWorkload.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_workload error[{bcs_cluster_id}]: {exc_info}")
            continue
        bcs_cluster_id_list = list({model.bcs_cluster_id for model in workload_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {
            "bcs_cluster_id__in": bcs_cluster_id_list,
        }
        bulk_save_resources(BCSWorkload, workload_models, sync_unique_field, sync_fields, sync_filter, datetime_fields)
        # 同步标签
        patch_exists_resource_id(workload_models)
        BCSWorkload.bulk_save_labels(workload_models)
    return workload_models


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
    sync_unique_field = "unique_hash"
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

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    if not clusters:
        return None
    service_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            service_models = BCSService.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_service error[{bcs_cluster_id}]: {exc_info}")
            continue
        bcs_cluster_id_list = list({model.bcs_cluster_id for model in service_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {
            "bcs_cluster_id__in": bcs_cluster_id_list,
        }
        bulk_save_resources(BCSService, service_models, sync_unique_field, sync_fields, sync_filter, datetime_fields)
        # 同步标签
        patch_exists_resource_id(service_models)
        BCSService.bulk_save_labels(service_models)
    return service_models


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
    try:
        pod_models = BCSPod.load_list_from_api(
            {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id}
        )
    except Exception as exc_info:
        logger.exception(f"sync_bcs_pod error[{bcs_cluster_id}]: {exc_info}")
        return

    # 同步pod
    sync_filter = {"bcs_cluster_id": bcs_cluster_id}
    labels = bulk_save_resources(BCSPod, pod_models, sync_unique_field, pod_sync_fields, sync_filter, datetime_fields)
    BCSPod.bulk_save_labels(labels)

    try:
        container_models = BCSContainer.load_list_from_api(
            {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id}
        )
    except Exception as exc_info:
        logger.exception(f"sync_bcs_pod error[{bcs_cluster_id}]: {exc_info}")
        return

    # 同步container
    labels = bulk_save_resources(
        BCSContainer, container_models, sync_unique_field, container_sync_fields, sync_filter, datetime_fields
    )
    BCSContainer.bulk_save_labels(labels)


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
    sync_unique_field = "unique_hash"
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
        "status",
        "created_at",
        "unique_hash",
    ]
    datetime_fields = ["created_at"]

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    node_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            node_models = BCSNode.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_node error[{bcs_cluster_id}]: {exc_info}")
            continue

        # 查询主机对应的主机ID
        biz_hosts = defaultdict(list)
        for node in node_models:
            biz_hosts[node.bk_biz_id].append({"ip": node.ip, "bk_cloud_id": node.cloud_id})

        ip_cloud_id_to_host_id = {}
        for bk_biz_id, host_ips in biz_hosts.items():
            for host in api.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=host_ips):
                if host.bk_host_innerip:
                    ip_cloud_id_to_host_id[(host.bk_host_innerip, str(host.bk_cloud_id))] = host.bk_host_id
                if host.bk_host_innerip_v6:
                    ip_cloud_id_to_host_id[(host.bk_host_innerip_v6, str(host.bk_cloud_id))] = host.bk_host_id

        # 更新主机ID
        for node in node_models:
            node.bk_host_id = ip_cloud_id_to_host_id.get((exploded_ip(node.ip), node.cloud_id))

        bcs_cluster_id_list = list({model.bcs_cluster_id for model in node_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {
            "bcs_cluster_id__in": bcs_cluster_id_list,
        }
        bulk_save_resources(BCSNode, node_models, sync_unique_field, sync_fields, sync_filter, datetime_fields)
        # 同步标签
        patch_exists_resource_id(node_models)
        BCSNode.bulk_save_labels(node_models)
    return node_models


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
    sync_unique_field = "unique_hash"
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

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    if not clusters:
        return None
    service_monitor_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            service_monitor_models = BCSServiceMonitor.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_service_monitor error[{bcs_cluster_id}]: {exc_info}")
            continue
        bcs_cluster_id_list = list({model.bcs_cluster_id for model in service_monitor_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {
            "bcs_cluster_id__in": bcs_cluster_id_list,
        }
        bulk_save_resources(
            BCSServiceMonitor, service_monitor_models, sync_unique_field, sync_fields, sync_filter, datetime_fields
        )
        # 同步标签
        patch_exists_resource_id(service_monitor_models)
        BCSServiceMonitor.bulk_save_labels(service_monitor_models)

    return service_monitor_models


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
    sync_unique_field = "unique_hash"
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

    if bcs_cluster_id:
        clusters = BCSCluster.objects.filter(bcs_cluster_id=bcs_cluster_id).values(
            "bk_tenant_id", "bk_biz_id", "bcs_cluster_id"
        )
    else:
        clusters = BCSCluster.objects.all().values("bk_tenant_id", "bk_biz_id", "bcs_cluster_id")
    if not clusters:
        return None
    pod_monitor_models = None

    for cluster_chunk in chunks(clusters, settings.BCS_SYNC_SYNC_CONCURRENCY):
        params = {
            cluster["bcs_cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        try:
            pod_monitor_models = BCSPodMonitor.load_list_from_api(params)
        except Exception as exc_info:
            logger.exception(f"sync_bcs_pod_monitor error[{bcs_cluster_id}]: {exc_info}")
            continue
        bcs_cluster_id_list = list({model.bcs_cluster_id for model in pod_monitor_models})
        if not bcs_cluster_id_list:
            continue

        sync_filter = {
            "bcs_cluster_id__in": bcs_cluster_id_list,
        }
        bulk_save_resources(
            BCSPodMonitor, pod_monitor_models, sync_unique_field, sync_fields, sync_filter, datetime_fields
        )
        # 同步标签
        patch_exists_resource_id(pod_monitor_models)
        BCSPodMonitor.bulk_save_labels(pod_monitor_models)

    return pod_monitor_models


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


def patch_exists_resource_id(resource_models):
    if not resource_models:
        return
    bcs_cluster_id_list = [resource_model.bcs_cluster_id for resource_model in resource_models]
    models = (
        resource_models[0].__class__.objects.filter(bcs_cluster_id__in=bcs_cluster_id_list).values("id", "unique_hash")
    )
    exists_hash_data = {model["unique_hash"]: model["id"] for model in models}
    for resource_model in resource_models:
        unique_hash = resource_model.get_unique_hash()
        if not resource_model.id and unique_hash in exists_hash_data:
            resource_model.id = exists_hash_data.get(unique_hash)
