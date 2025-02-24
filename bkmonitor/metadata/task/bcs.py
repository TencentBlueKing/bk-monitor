# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import collections
import itertools
import logging
import time

from django.conf import settings

from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.service.scheduler.app import app
from core.drf_resource import api
from core.prometheus import metrics
from metadata import models
from metadata.config import PERIODIC_TASK_DEFAULT_TTL
from metadata.models.bcs.resource import (
    BCSClusterInfo,
    PodMonitorInfo,
    ServiceMonitorInfo,
)
from metadata.task.tasks import bulk_create_fed_data_link
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.bcs import change_cluster_router, get_bcs_dataids

logger = logging.getLogger("metadata")

BCS_SYNC_SYNC_CONCURRENCY = 20
CMDB_IP_SEARCH_MAX_SIZE = 100


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshBCSMonitorInfo")
def refresh_bcs_monitor_info():
    """
    刷新BCS集群监控信息
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_bcs_monitor_info", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()
    fed_clusters = {}
    try:
        fed_clusters = api.bcs.get_federation_clusters()
        fed_cluster_id_list = list(fed_clusters.keys())
    except Exception as e:  # pylint: disable=broad-except
        fed_cluster_id_list = []
        logger.error("get federation clusters failed: {}".format(e))

    bcs_clusters = list(
        BCSClusterInfo.objects.filter(
            status__in=[models.BCSClusterInfo.CLUSTER_STATUS_RUNNING, models.BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING],
        )
    )

    # 对 bcs_clusters 进行排序，确保 fed_cluster_id_list 中的集群优先
    bcs_clusters = sorted(bcs_clusters, key=lambda x: x.cluster_id not in fed_cluster_id_list)

    # 拉取所有cluster，遍历刷新monitorinfo信息
    for cluster in bcs_clusters:
        try:
            is_fed_cluster = cluster.cluster_id in fed_cluster_id_list
            # 刷新集群内置公共dataid resource
            cluster.refresh_common_resource(is_fed_cluster=is_fed_cluster)
            logger.debug("refresh bcs common resource in cluster:{} done".format(cluster.cluster_id))

            # 查找新的monitor info并记录到数据库，删除已不存在的
            ServiceMonitorInfo.refresh_resource(cluster.cluster_id, cluster.CustomMetricDataID)
            logger.debug("refresh bcs service monitor resource in cluster:{} done".format(cluster.cluster_id))
            PodMonitorInfo.refresh_resource(cluster.cluster_id, cluster.CustomMetricDataID)
            logger.debug("refresh bcs pod monitor resource in cluster:{} done".format(cluster.cluster_id))

            # 刷新配置了自定义dataid的dataid resource
            ServiceMonitorInfo.refresh_custom_resource(cluster_id=cluster.cluster_id)
            logger.debug("refresh bcs service monitor custom resource in cluster:{} done".format(cluster.cluster_id))
            PodMonitorInfo.refresh_custom_resource(cluster_id=cluster.cluster_id)
            logger.debug("refresh bcs pod monitor custom resource in cluster:{} done".format(cluster.cluster_id))
            if is_fed_cluster:
                # 更新联邦集群记录
                try:
                    sync_federation_clusters(fed_clusters)
                except Exception as e:  # pylint: disable=broad-except
                    logger.error("sync_federation_clusters failed, error:{}".format(e))

        except Exception:  # noqa
            logger.exception("refresh bcs monitor info failed, cluster_id(%s)", cluster.cluster_id)

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_bcs_monitor_info", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，并上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="refresh_bcs_monitor_info", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("refresh_bcs_monitor_info: task finished, cost time->[%s] seconds", cost_time)


@app.task(ignore_result=True, queue="celery_cron")
def refresh_dataid_resource(cluster_id, data_id):
    ServiceMonitorInfo.refresh_resource(cluster_id, data_id)
    PodMonitorInfo.refresh_resource(cluster_id, data_id)


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshBCSMetricsInfo")
def refresh_bcs_metrics_label():
    """
    刷新BCS集群监控指标label
    """

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_bcs_metrics_label", status=TASK_STARTED, process_target=None
    ).inc()
    start_time = time.time()
    logger.debug("start refresh bcs metrics label")
    # 获取所有bcs相关dataid
    data_ids, data_id_cluster_map = get_bcs_dataids()
    logger.debug("get bcs dataids->{}".format(data_ids))

    # 基于dataid过滤出自定义指标group_id
    time_series_group_ids = [
        item["time_series_group_id"]
        for item in models.TimeSeriesGroup.objects.filter(bk_data_id__in=data_ids, is_delete=False).values(
            "time_series_group_id"
        )
    ]
    logger.debug("get bcs time_series_group_ids->{}".format(time_series_group_ids))

    # 基于group_id拿到对应的指标项
    bcs_metrics = [
        item
        for item in models.TimeSeriesMetric.objects.filter(group_id__in=time_series_group_ids).values(
            "field_name", "field_id", "label"
        )
    ]
    logger.debug("get bcs metrics->{}".format(bcs_metrics))
    # 遍历指标组
    label_result = {}
    label_prefix_map = settings.BCS_METRICS_LABEL_PREFIX.copy()
    default_label = ""
    if "*" in label_prefix_map.keys():
        default_label = label_prefix_map["*"]
    for metric in bcs_metrics:
        # 基于group的dataid，对数据补充集群id字段
        field_name = metric["field_name"]
        source_label = metric["label"]
        target_label = ""
        # 通过遍历匹配，获取到需要处理label的指标信息
        for prefix in label_prefix_map.keys():
            if field_name.startswith(prefix):
                target_label = label_prefix_map[prefix]
                break
        if target_label == "":
            target_label = default_label
        # 记录需要更新label的field_id，后面批量更新
        if source_label != target_label:
            if target_label not in label_result.keys():
                label_result[target_label] = [metric["field_id"]]
            else:
                label_result[target_label].append(metric["field_id"])
    logger.debug("will replace bcs label info->{}".format(label_result))
    # 每个label批量更新一下
    for label_name, field_ids in label_result.items():
        models.TimeSeriesMetric.objects.filter(field_id__in=field_ids).update(label=label_name)

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_bcs_metrics_label", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="refresh_bcs_metrics_label", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.debug("refresh bcs metrics label done,use->[%s] seconds", cost_time)


@share_lock(ttl=3600, identify="metadata_discoverBCSClusters")
def discover_bcs_clusters():
    """
    周期刷新bcs集群列表，将未注册进metadata的集群注册进来
    """
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="discover_bcs_clusters", status=TASK_STARTED, process_target=None
    ).inc()

    # BCS 接口仅返回非 DELETED 状态的集群信息
    start_time = time.time()
    logger.info("discover_bcs_clusters: start to discover bcs clusters")
    try:
        bcs_clusters = api.kubernetes.fetch_k8s_cluster_list()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("discover_bcs_clusters: get bcs clusters failed, error:{}".format(e))
        return
    cluster_list = []
    # 获取所有联邦集群 ID
    fed_clusters = {}
    try:
        fed_clusters = api.bcs.get_federation_clusters()
        fed_cluster_id_list = list(fed_clusters.keys())  # 联邦的代理集群列表
    except Exception as e:  # pylint: disable=broad-except
        fed_cluster_id_list = []
        logger.warning("discover_bcs_clusters: get federation clusters failed, error:{}".format(e))

    # 联邦集群顺序调整到前面，因为创建链路时依赖联邦关系记录
    bcs_clusters = sorted(bcs_clusters, key=lambda x: x["cluster_id"] not in fed_cluster_id_list)

    # bcs 集群中的正常状态
    for bcs_cluster in bcs_clusters:
        logger.info("discover_bcs_clusters: get bcs cluster:{},start to register".format(bcs_cluster["cluster_id"]))
        project_id = bcs_cluster["project_id"]
        bk_biz_id = bcs_cluster["bk_biz_id"]
        cluster_id = bcs_cluster["cluster_id"]
        cluster_raw_status = bcs_cluster["status"]
        cluster_list.append(cluster_id)

        # todo 同一个集群在切换业务时不能重复接入
        cluster = BCSClusterInfo.objects.filter(cluster_id=cluster_id).first()
        if cluster:
            # 更新集群信息，兼容集群迁移场景
            # 场景1:集群迁移业务，项目ID不变，只会变业务ID
            # 场景2:集群迁移项目，项目ID和业务ID都可能变化
            update_fields = []
            is_fed_cluster = cluster_id in fed_cluster_id_list
            # NOTE: 现阶段完全以 BCS 的集群状态为准，
            if cluster_raw_status != cluster.status:
                cluster.status = cluster_raw_status
                update_fields.append("status")
            # 如果 BCS Token 变了需要刷新
            if cluster.api_key_content != settings.BCS_API_GATEWAY_TOKEN:
                cluster.api_key_content = settings.BCS_API_GATEWAY_TOKEN
                update_fields.append("api_key_content")

            if int(bk_biz_id) != cluster.bk_biz_id:
                # 记录旧业务ID，更新新业务ID
                old_bk_biz_id = cluster.bk_biz_id
                cluster.bk_biz_id = int(bk_biz_id)
                update_fields.append("bk_biz_id")

                # 若业务ID变更，其RT对应的业务ID也应一并变更
                logger.info(
                    "discover_bcs_clusters: cluster_id:{},project_id:{} change bk_biz_id to {}".format(
                        cluster_id, project_id, int(bk_biz_id)
                    )
                )

                # 变更对应的路由元信息
                change_cluster_router(
                    cluster=cluster,
                    old_bk_biz_id=old_bk_biz_id,
                    new_bk_biz_id=int(bk_biz_id),
                    is_fed_cluster=is_fed_cluster,
                )

            # 如果project_id改动，需要更新集群信息
            if project_id != cluster.project_id:
                cluster.project_id = project_id
                update_fields.append("project_id")

            if update_fields:
                update_fields.append("last_modify_time")
                cluster.save(update_fields=update_fields)

            if cluster.bk_cloud_id is None:
                # 更新云区域ID
                update_bcs_cluster_cloud_id_config(bk_biz_id, cluster_id)

            # 若集群变为联邦集群的子集群且此前未创建过联邦集群的汇聚链路，需要额外进行联邦汇聚链路创建操作
            # check_create_fed_vm_data_link(cluster)

            logger.debug("cluster_id:{},project_id:{} already exists,skip create it".format(cluster_id, project_id))
            continue

        cluster = BCSClusterInfo.register_cluster(
            bk_biz_id=bk_biz_id,
            cluster_id=cluster_id,
            project_id=project_id,
            creator="admin",
            is_fed_cluster=is_fed_cluster,
        )
        if is_fed_cluster:
            # 创建联邦集群记录
            try:
                sync_federation_clusters(fed_clusters)
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("discover_bcs_clusters: sync_federation_clusters failed, error:{}".format(e))
        logger.info(
            "discover_bcs_clusters: cluster_id:{},project_id:{},bk_biz_id:{} registered".format(
                cluster.cluster_id, cluster.project_id, cluster.bk_biz_id
            )
        )

        try:
            logger.info(
                "cluster_id:{},project_id:{},bk_biz_id:{} start to init resource".format(
                    cluster.cluster_id, cluster.project_id, cluster.bk_biz_id
                )
            )
            cluster.init_resource(is_fed_cluster=is_fed_cluster)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "cluster_id:{},project_id:{},bk_biz_id:{} init resource failed, error:{}".format(
                    cluster.cluster_id, cluster.project_id, cluster.bk_biz_id, e
                )
            )
            continue

        # 更新云区域ID
        update_bcs_cluster_cloud_id_config(bk_biz_id, cluster_id)

        logger.info(
            "cluster_id:{},project_id:{},bk_biz_id:{} init resource finished".format(
                cluster.cluster_id, cluster.project_id, cluster.bk_biz_id
            )
        )

    # 如果是不存在的集群列表则更新当前状态为删除，加上>0的判断防止误删
    if cluster_list:
        BCSClusterInfo.objects.exclude(cluster_id__in=cluster_list).update(
            status=BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED
        )

    # 统计耗时，并上报指标
    cost_time = time.time() - start_time
    logger.info("discover_bcs_clusters finished, cost time->[%s]", cost_time)
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="discover_bcs_clusters", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="refresh_bcs_monitor_info", process_target=None).observe(
        cost_time
    )
    metrics.report_all()


def update_bcs_cluster_cloud_id_config(bk_biz_id=None, cluster_id=None):
    """补齐云区域ID ."""
    # 获得缺失云区域的集群配置
    filter_kwargs = {}
    if bk_biz_id:
        filter_kwargs["bk_biz_id"] = bk_biz_id
    if cluster_id:
        filter_kwargs["cluster_id"] = cluster_id
    filter_kwargs.update(
        {
            "status__in": [BCSClusterInfo.CLUSTER_STATUS_RUNNING, BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING],
            "bk_cloud_id__isnull": True,
        }
    )
    clusters = BCSClusterInfo.objects.filter(**filter_kwargs).values("bk_biz_id", "cluster_id")
    for start in range(0, len(clusters), BCS_SYNC_SYNC_CONCURRENCY):
        cluster_chunk = clusters[start : start + BCS_SYNC_SYNC_CONCURRENCY]
        # 从BCS获取集群的节点IP
        params = {cluster["cluster_id"]: cluster["bk_biz_id"] for cluster in cluster_chunk}
        bulk_request_params = [{"bcs_cluster_id": bcs_cluster_id} for bcs_cluster_id in params.keys()]
        try:
            api_nodes = api.kubernetes.fetch_k8s_node_list_by_cluster.bulk_request(
                bulk_request_params, ignore_exceptions=True
            )
        except Exception as exc_info:  # noqa
            logger.exception(exc_info)
            continue
        node_ip_map = {}
        for node in itertools.chain.from_iterable(item for item in api_nodes if item):
            bcs_cluster_id = node["bcs_cluster_id"]
            bk_biz_id = params.get(bcs_cluster_id)
            if not bk_biz_id:
                continue
            node_ip = node["node_ip"]
            if not node_ip:
                continue
            node_ip_map.setdefault(bk_biz_id, {}).setdefault(bcs_cluster_id, []).append(node_ip)

        # 从cmdb根据ip获得主机信息，包括云区域
        cmdb_params = []
        for bk_biz_id, cluster_info in node_ip_map.items():
            for node_ips in cluster_info.values():
                # 防止ip过多，超过接口限制
                node_ips = node_ips[:CMDB_IP_SEARCH_MAX_SIZE]
                cmdb_params.append(
                    {
                        "bk_biz_id": bk_biz_id,
                        "ips": [
                            {
                                "ip": ip,
                            }
                            for ip in node_ips
                        ],
                    }
                )
        if not cmdb_params:
            continue
        try:
            host_infos = api.cmdb.get_host_by_ip.bulk_request(cmdb_params)
        except Exception as exc_info:  # noqa
            logger.exception(exc_info)
            continue
        bk_cloud_map = {}
        for item in itertools.chain.from_iterable(host_info_chunk for host_info_chunk in host_infos if host_info_chunk):
            ip_map = {}
            if item.bk_host_innerip:
                ip_map[item.bk_host_innerip] = item.bk_cloud_id
            if item.bk_host_innerip_v6:
                ip_map[item.bk_host_innerip_v6] = item.bk_cloud_id
            bk_cloud_map.setdefault(item.bk_biz_id, {}).update(ip_map)

        # 计算每个集群云区域的top1
        update_params = {}
        for bk_biz_id, cluster_info in node_ip_map.items():
            for bcs_cluster_id, node_ips in cluster_info.items():
                # 获取node ip对应的云区域ID
                bk_cloud_ids = []
                for node_ip in node_ips:
                    bk_cloud_id = bk_cloud_map.get(bk_biz_id, {}).get(node_ip)
                    if bk_cloud_id is None:
                        continue
                    bk_cloud_ids.append(bk_cloud_id)
                if not bk_cloud_ids:
                    continue
                # 计算每个集群云区域的计数
                counter = collections.Counter(bk_cloud_ids)
                # 获取计数最大的一个云区域，当做集群的云区域
                most_common_bk_cloud_id = counter.most_common(1)[0][0]
                update_params.setdefault(most_common_bk_cloud_id, []).append(bcs_cluster_id)

        # 更新云区域
        for bk_cloud_id, bcs_cluster_ids in update_params.items():
            BCSClusterInfo.objects.filter(cluster_id__in=bcs_cluster_ids).update(bk_cloud_id=bk_cloud_id)


def sync_federation_clusters(fed_clusters):
    """
    同步联邦集群信息，创建或更新对应数据记录
    :param fed_clusters: BCS API返回的联邦集群拓扑结构信息
    """

    logger.info("sync_federation_clusters:sync_federation_clusters started.")
    need_process_clusters = []  # 记录需要创建联邦汇聚链路的集群列表，统一进行异步操作
    try:
        # 获取传入数据中的所有联邦集群 ID
        fed_cluster_ids = set(fed_clusters.keys())

        # 获取数据库中现有的联邦集群 ID (排除软删除的记录)
        existing_fed_clusters = set(
            models.BcsFederalClusterInfo.objects.filter(is_deleted=False).values_list('fed_cluster_id', flat=True)
        )

        # 删除不再归属的联邦集群记录
        clusters_to_delete = existing_fed_clusters - fed_cluster_ids
        if clusters_to_delete:
            logger.info("sync_federation_clusters:Deleting federation cluster info for->[%s]", clusters_to_delete)
            models.BcsFederalClusterInfo.objects.filter(fed_cluster_id__in=clusters_to_delete).update(is_deleted=True)

        # 遍历最新的联邦集群关系
        for fed_cluster_id, fed_cluster_data in fed_clusters.items():
            logger.info("sync_federation_clusters:Syncing federation cluster ->[%s]", fed_cluster_id)

            host_cluster_id = fed_cluster_data['host_cluster_id']
            sub_clusters = fed_cluster_data['sub_clusters']

            # 获取代理集群的对应 RT 信息
            cluster = models.BCSClusterInfo.objects.get(cluster_id=fed_cluster_id)
            fed_builtin_k8s_metric_data_id = cluster.K8sMetricDataID
            fed_builtin_k8s_event_data_id = cluster.K8sEventDataID

            fed_builtin_metric_table_id = models.DataSourceResultTable.objects.get(
                bk_data_id=fed_builtin_k8s_metric_data_id
            ).table_id
            fed_builtin_event_table_id = models.DataSourceResultTable.objects.get(
                bk_data_id=fed_builtin_k8s_event_data_id
            ).table_id

            # 遍历每个子集群，处理命名空间归属
            for sub_cluster_id, namespaces in sub_clusters.items():
                logger.info(
                    "sync_federation_clusters:Syncing sub-cluster -> [%s],namespaces->[%s]", sub_cluster_id, namespaces
                )
                if namespaces is None:
                    logger.info(
                        "sync_federation_clusters:Skipping sub-cluster->[%s] as namespaces is None", sub_cluster_id
                    )
                    continue

                # 获取现有的命名空间记录（当前数据库中已存在的子集群记录，排除软删除的记录）
                existing_records = models.BcsFederalClusterInfo.objects.filter(
                    fed_cluster_id=fed_cluster_id, sub_cluster_id=sub_cluster_id, is_deleted=False
                )

                # 获取现有的命名空间列表
                if existing_records.exists():
                    current_namespaces = existing_records.first().fed_namespaces
                else:
                    current_namespaces = []

                # 直接覆盖更新命名空间列表
                updated_namespaces = list(set(namespaces))

                # 如果数据库中的记录与更新的数据一致，跳过更新
                if set(updated_namespaces) == set(current_namespaces):
                    logger.info(
                        "sync_federation_clusters:Sub-cluster->[%s] in federation->[%s] is already up-to-date,skipping",
                        sub_cluster_id,
                        fed_cluster_id,
                    )
                    continue

                # 如果命名空间有变更，更新记录
                logger.info(
                    "sync_federation_clusters:Updating namespaces for sub-cluster->[%s],in federation->[%s]",
                    sub_cluster_id,
                    fed_cluster_id,
                )

                models.BcsFederalClusterInfo.objects.update_or_create(
                    fed_cluster_id=fed_cluster_id,
                    host_cluster_id=host_cluster_id,
                    sub_cluster_id=sub_cluster_id,
                    defaults={
                        'fed_namespaces': updated_namespaces,
                        'fed_builtin_metric_table_id': fed_builtin_metric_table_id,
                        'fed_builtin_event_table_id': fed_builtin_event_table_id,
                    },
                )

                # 记录
                need_process_clusters.append(sub_cluster_id)
                logger.info(
                    "sync_federation_clusters:Updated federation cluster info for sub-cluster->[%s] in fed->[%s] "
                    "successfully，will create fed data_link later",
                    sub_cluster_id,
                    fed_cluster_id,
                )

        # 查找哪些子集群的联邦集群信息不再存在于传入的 fed_clusters 中
        all_sub_clusters_in_fed_clusters = {
            (fed_cluster_id, sub_cluster_id)
            for fed_cluster_id, fed_cluster_data in fed_clusters.items()
            for sub_cluster_id in fed_cluster_data['sub_clusters'].keys()
        }

        # 获取数据库中所有子集群的记录（排除软删除的记录）
        existing_sub_clusters = models.BcsFederalClusterInfo.objects.filter(is_deleted=False).values_list(
            'fed_cluster_id', 'sub_cluster_id'
        )

        # 找出不再归属任何联邦集群的子集群记录
        sub_clusters_to_delete = set(existing_sub_clusters) - all_sub_clusters_in_fed_clusters

        if sub_clusters_to_delete:
            logger.info(
                "sync_federation_clusters:Deleting sub-clusters that are no longer part of any federation->[%s]",
                sub_clusters_to_delete,
            )
            # 使用动态条件生成过滤器来删除记录
            for sub_cluster_id in sub_clusters_to_delete:
                models.BcsFederalClusterInfo.objects.filter(
                    fed_cluster_id=sub_cluster_id[0], sub_cluster_id=sub_cluster_id[1]
                ).update(is_deleted=True)

        logger.info(
            "sync_federation_clusters:Start Creating federation data links for sub-clusters->[%s] " "asynchronously",
            need_process_clusters,
        )
        # bulk_create_fed_data_link(need_process_clusters)
        bulk_create_fed_data_link.delay(set(need_process_clusters))  # 异步创建联邦汇聚链路

        logger.info("sync_federation_clusters:sync_federation_clusters finished successfully.")

    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e)
        logger.warning("sync_federation_clusters:sync_federation_clusters failed, error->[%s]", e)
