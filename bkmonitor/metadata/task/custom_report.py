"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
import traceback
from datetime import timedelta

import billiard as multiprocessing
from django import db
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from alarm_backends.core.lock.service_lock import share_lock
from bkmonitor.models import QueryConfigModel
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.time_tools import datetime_str_to_datetime
from bkmonitor.utils.version import compare_versions, get_max_version
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.models.constants import EVENT_GROUP_SLEEP_THRESHOLD, EventGroupStatus
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils import es_tools

logger = logging.getLogger("metadata")

RECOMMENDED_VERSION = {"bk-collector": "0.16.1061"}


def update_event_by_cluster(cluster_id_with_table_ids: dict | None = None, data_ids: list | None = None):
    """
    按照ES集群更新event维度等信息
    :param cluster_id_with_table_ids: ES集群id与table_id_list的字典
    {
        3:["table_id_1", "table_id2"],
        4:["table_id_3", "table_id4"],
    }
    :param data_ids: 按照data_id进行更新
    """
    s_time = time.time()
    if data_ids is not None:
        for event_group in models.EventGroup.objects.filter(bk_data_id__in=data_ids).iterator():
            event_group.update_event_dimensions_from_es()
        e_time = time.time()
        logger.info("check_event_update:update data_ids[%s], cost:%s s", data_ids, e_time - s_time)

    if cluster_id_with_table_ids is None:
        return

    for cluster_id, table_ids in cluster_id_with_table_ids.items():
        try:
            client = es_tools.get_client(cluster_id)
        except Exception:
            logger.error("check_event_update:get es_client->[%s] failed for->[%s]", cluster_id, traceback.format_exc())
            continue

        for event_group in models.EventGroup.objects.filter(
            is_enable=True, is_delete=False, table_id__in=table_ids
        ).iterator():
            try:
                logger.info("check_event_update:update_event[%s]", event_group.event_group_name)
                event_group.update_event_dimensions_from_es(client)
            except Exception:
                logger.error(
                    "check_event_update:event_group->[%s] try to update from es->[%s] failed for->[%s]",
                    event_group.event_group_name,
                    cluster_id,
                    traceback.format_exc(),
                )
            else:
                logger.info(
                    "check_event_update:event_group->[%s] is update from es->[%s] success.",
                    event_group.event_group_name,
                    cluster_id,
                )
    e_time = time.time()
    logger.info(
        "check_event_update:update cluster[%s], cost:%s s", list(cluster_id_with_table_ids.keys()), e_time - s_time
    )


@share_lock(identify="metadata_refreshEventGroup")
def check_event_update():
    """
    同步自定义事件维度及事件，每三分钟将会从ES同步一次
    """
    logger.info("check_event_update:start")
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_event_update", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()
    table_ids = set(
        models.EventGroup.objects.filter(is_enable=True, is_delete=False).values_list("table_id", flat=True)
    )
    storage_cluster_table_ids = {}
    for storage in (
        models.ESStorage.objects.filter(table_id__in=table_ids).values("storage_cluster_id", "table_id").iterator()
    ):
        storage_cluster_table_ids.setdefault(storage["storage_cluster_id"], []).append(storage["table_id"])

    if not storage_cluster_table_ids:
        return
    # 将ES集群按照并行进程数量分组处理
    max_worker = getattr(settings, "MAX_TASK_PROCESS_NUM", 1)
    items = list(storage_cluster_table_ids.items())
    length = len(items)
    # 每一组最大任务数量
    chunk_size = length // max_worker + 1 if length % max_worker != 0 else int(length / max_worker)
    # 按数量分组，最多分为max_worker组
    chunks = [items[i : i + chunk_size] for i in range(0, length, chunk_size)]

    processes = []
    # 使用django-ORM时启用多进程会导致子进程使用同一个数据库连接，会产生无效连接，在启用多进程之前需要关闭连接，在子进程中重新创建连接
    db.connections.close_all()
    for items in chunks:
        param_dict = dict(items)
        # multiprocessing模块在celery中会导致worker假死，使用billiard模块启用多进程
        t = multiprocessing.Process(target=update_event_by_cluster, args=(param_dict,))
        processes.append(t)
        t.start()

    for t in processes:
        t.join()
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_event_update", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="check_event_update", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("check_event_update:finished, cost->[%s] seconds", cost_time)


def refresh_custom_report_2_node_man(bk_biz_id=None):
    # 判定节点管理是否上传支持v2新配置模版的bk-collector版本0.16.1061
    default_version = "0.0.0"
    plugin_infos = api.node_man.plugin_info(name="bk-collector")
    version_str_list = [p.get("version", default_version) for p in plugin_infos if p.get("is_ready", True)]
    max_version = get_max_version(default_version, version_str_list)

    if compare_versions(max_version, RECOMMENDED_VERSION["bk-collector"]) > 0:
        if bk_biz_id is not None:
            bk_tenant_ids = [bk_biz_id_to_bk_tenant_id(bk_biz_id)]
        else:
            bk_tenant_ids = [tenant["id"] for tenant in api.bk_login.list_tenant()]

        for bk_tenant_id in bk_tenant_ids:
            try:
                models.CustomReportSubscription.refresh_collector_custom_conf(
                    bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id
                )
            except Exception as e:
                logger.exception(
                    f"refresh custom report config to collector error, bk_tenant_id({bk_tenant_id}), bk_biz_id({bk_biz_id}), error({e})"
                )
    else:
        logger.info(
            f"当前节点管理已上传的bk-collector版本（{max_version}）低于支持新配置模版版本"
            f"（{RECOMMENDED_VERSION['bk-collector']}），暂不下发bk-collector配置文件"
        )


# 用于定时任务的包装函数，加锁防止任务重叠
refresh_all_custom_report_2_node_man = share_lock()(refresh_custom_report_2_node_man)


@share_lock()
def refresh_custom_log_config(log_group_id=None):
    """
    Refresh Custom Log Config to Bk Collector
    """

    # Filter All Enabled Log Report Group
    log_groups = models.LogGroup.objects.filter(is_enable=True)
    if log_group_id:
        log_groups = log_groups.filter(log_group_id=log_group_id)

    # Deploy Configs
    for log_group in log_groups:
        try:
            models.LogSubscriptionConfig.refresh(log_group)
        except Exception as err:
            logger.exception(
                "[RefreshCustomLogConfigFailed] Err => %s; LogGroup => %s", str(err), log_group.log_group_id
            )


def check_custom_event_group_sleep():
    """
    检查自定义事件组是否应该进行休眠
    如果自定义事件超过半年没有被使用，则进行休眠，清理索引
    """
    logger.info("check_custom_event_group_sleep:start")
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_custom_event_group_sleep", status=TASK_STARTED, process_target=None
    ).inc()

    start_time = time.time()
    event_groups = models.EventGroup.objects.filter(
        Q(last_check_report_time__isnull=True)
        | Q(last_check_report_time__lt=timezone.now() - timedelta(days=EVENT_GROUP_SLEEP_THRESHOLD)),
        status=EventGroupStatus.NORMAL.value,
    ).exclude(
        Q(event_group_name__startswith="bcs_BCS-K8S-", event_group_name__endswith="_k8s_event")
        | Q(event_group_name__startswith="Log_log_")
    )

    # 获取已配置测试
    custom_event_query_configs = QueryConfigModel.objects.filter(
        data_source_label=DataSourceLabel.CUSTOM, data_type_label=DataTypeLabel.EVENT
    )
    table_ids_with_strategy = set()
    for query_config in custom_event_query_configs:
        if not query_config.config.get("result_table_id"):
            continue
        table_ids_with_strategy.add(query_config.config.get("result_table_id"))

    need_clean_es_storages: list[models.ESStorage] = []
    for event_group in event_groups:
        if event_group.table_id in table_ids_with_strategy:
            continue

        try:
            es = models.ESStorage.objects.get(table_id=event_group.table_id)
        except models.ESStorage.DoesNotExist:
            logger.info(
                f"bk_biz_id({event_group.bk_biz_id}) EventGroup {event_group.event_group_name} "
                f"has no ESStorage, set status to SLEEP"
            )
            event_group.status = EventGroupStatus.SLEEP.value
            event_group.save(update_fields=["status"])
            continue

        indices, index_version = es.get_index_stats()
        if not indices:
            logger.info(
                f"bk_biz_id({event_group.bk_biz_id}) EventGroup {event_group.event_group_name} "
                f"does not have any index, set status to SLEEP"
            )
            event_group.status = EventGroupStatus.SLEEP.value
            event_group.save(update_fields=["status"])
            continue

        last_check_report_time = None
        for index, stats in indices.items():
            if index_version == "v2":
                index_re = es.index_re_v2
            else:
                index_re = es.index_re_v1

            re_result = index_re.match(index)
            current_datetime_str = re_result.group("datetime")
            current_datetime_object = datetime_str_to_datetime(current_datetime_str, es.date_format, es.time_zone)
            if stats["primaries"]["docs"]["count"] > 0 and current_datetime_object >= timezone.now() - timedelta(
                days=EVENT_GROUP_SLEEP_THRESHOLD
            ):
                if last_check_report_time is None or current_datetime_object > last_check_report_time:
                    last_check_report_time = current_datetime_object

        if last_check_report_time is None:
            logger.info(
                f"bk_biz_id({event_group.bk_biz_id}) EventGroup {event_group.event_group_name} "
                f"has no data for a long time, set status to SLEEP and delete index"
            )
            need_clean_es_storages.append(es)
        else:
            logger.info(
                f"bk_biz_id({event_group.bk_biz_id}) EventGroup {event_group.event_group_name} has data, "
                f"set last_check_report_time {last_check_report_time}"
            )
            event_group.last_check_report_time = last_check_report_time
            event_group.save(update_fields=["last_check_report_time"])

    if not settings.ENABLE_CUSTOM_EVENT_SLEEP:
        logger.info("ENABLE_CUSTOM_EVENT_SLEEP is False, skip cleaning ESStorage")
        return

    # 删除需要清理的ESStorage的索引
    for es in need_clean_es_storages:
        client = es.get_client()
        for index, detail in client.indices.get(f"{es.index_name}*").items():
            aliases = list(detail.get("aliases", {}).keys())
            params = {"actions": [{"remove": {"index": index, "alias": alias}} for alias in aliases]}
            client.indices.update_aliases(body=params)
            client.indices.delete(index)
            logger.info(f"Delete alias for ESStorage {es.table_id} {index} {aliases}")
        client.close()
        models.EventGroup.objects.filter(table_id=es.table_id).update(status=EventGroupStatus.SLEEP.value)

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="check_custom_event_group_sleep", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(
        task_name="check_custom_event_group_sleep", process_target=None
    ).observe(cost_time)
    metrics.report_all()
    logger.info(f"check_custom_event_group_sleep:end, cost_time->[{cost_time}] seconds")


def report_custom_metrics():
    """
    上报自定义指标
    """
    logger.info("report_custom_metrics:start")
    metrics.report_all()
    logger.info("report_custom_metrics:end")
