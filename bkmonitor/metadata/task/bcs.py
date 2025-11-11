"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
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
    fed_cluster_id_list = []
    try:
        for tenant in api.bk_login.list_tenant():
            fed_clusters.update(api.bcs.get_federation_clusters(bk_tenant_id=tenant["id"]))
            fed_cluster_id_list.extend(list(fed_clusters.keys()))
    except Exception as e:  # pylint: disable=broad-except
        fed_cluster_id_list = []
        logger.error(f"get federation clusters failed: {e}")

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
            logger.debug(f"refresh bcs common resource in cluster:{cluster.cluster_id} done")

            # 查找新的monitor info并记录到数据库，删除已不存在的
            ServiceMonitorInfo.refresh_resource(cluster.cluster_id, cluster.CustomMetricDataID)
            logger.debug(f"refresh bcs service monitor resource in cluster:{cluster.cluster_id} done")
            PodMonitorInfo.refresh_resource(cluster.cluster_id, cluster.CustomMetricDataID)
            logger.debug(f"refresh bcs pod monitor resource in cluster:{cluster.cluster_id} done")

            # 刷新配置了自定义dataid的dataid resource
            ServiceMonitorInfo.refresh_custom_resource(cluster_id=cluster.cluster_id)
            logger.debug(f"refresh bcs service monitor custom resource in cluster:{cluster.cluster_id} done")
            PodMonitorInfo.refresh_custom_resource(cluster_id=cluster.cluster_id)
            logger.debug(f"refresh bcs pod monitor custom resource in cluster:{cluster.cluster_id} done")
            if is_fed_cluster:
                # 更新联邦集群记录
                try:
                    sync_federation_clusters(fed_clusters)
                except Exception as e:  # pylint: disable=broad-except
                    logger.error(f"sync_federation_clusters failed, error:{e}")

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
    logger.info("start refresh bcs metrics label")
    # 获取所有bcs相关dataid
    data_ids, data_id_cluster_map = get_bcs_dataids()
    logger.info(f"get bcs dataids->{data_ids}")

    # 基于dataid过滤出自定义指标group_id
    time_series_group_ids = [
        item["time_series_group_id"]
        for item in models.TimeSeriesGroup.objects.filter(bk_data_id__in=data_ids, is_delete=False).values(
            "time_series_group_id"
        )
    ]

    # 基于group_id拿到对应的指标项
    bcs_metrics = [
        item
        for item in models.TimeSeriesMetric.objects.filter(label="").values(
            "field_name", "field_id", "label", "group_id"
        )
    ]

    kubernetes_field_ids = []
    non_kubernetes_field_ids = []

    # 遍历指标组
    for metric in bcs_metrics:
        # 若非容器指标，则打上custom标签
        if metric["group_id"] not in time_series_group_ids:
            non_kubernetes_field_ids.append(metric["field_id"])
        else:
            kubernetes_field_ids.append(metric["field_id"])

    # 更新指标label
    if kubernetes_field_ids:
        models.TimeSeriesMetric.objects.filter(field_id__in=kubernetes_field_ids).update(label="kubernetes")

    if non_kubernetes_field_ids:
        models.TimeSeriesMetric.objects.filter(field_id__in=non_kubernetes_field_ids).update(label="custom")

    cost_time = time.time() - start_time

    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="refresh_bcs_metrics_label", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    # 统计耗时，上报指标
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="refresh_bcs_metrics_label", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("refresh bcs metrics label done,use->[%s] seconds", cost_time)


@share_lock(ttl=3600, identify="metadata_discoverBCSClusters")
def discover_bcs_clusters():
    """
    BCS集群同步周期任务,调用BCS侧API全量拉取集群信息（包含联邦集群）,并进行同步逻辑
    """

    def _init_bcs_cluster_resource(cluster: BCSClusterInfo, is_fed_cluster: bool) -> tuple[bool, Exception | None]:
        """
        初始化 BCS 集群资源
        """
        try:
            init_result = cluster.init_resource(is_fed_cluster=is_fed_cluster)
            return init_result, None
        except Exception as e:  # pylint: disable=broad-except
            return False, e

    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="discover_bcs_clusters", status=TASK_STARTED, process_target=None
    ).inc()

    # BCS 接口仅返回非 DELETED 状态的集群信息
    start_time = time.time()
    logger.info("discover_bcs_clusters: start to discover bcs clusters")
    cluster_list: list[str] = []
    for tenant in api.bk_login.list_tenant():
        bk_tenant_id = tenant["id"]
        try:
            bcs_clusters = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=bk_tenant_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"discover_bcs_clusters: get bcs clusters failed, error:{e}")
            return
        # 获取所有联邦集群 ID
        fed_clusters = {}
        try:
            fed_clusters = api.bcs.get_federation_clusters(bk_tenant_id=bk_tenant_id)
            fed_cluster_id_list = list(fed_clusters.keys())  # 联邦的代理集群列表
        except Exception as e:  # pylint: disable=broad-except
            fed_cluster_id_list = []
            logger.warning(f"discover_bcs_clusters: get federation clusters failed, error:{e}")

        # 联邦集群顺序调整到前面，因为创建链路时依赖联邦关系记录
        bcs_clusters = sorted(bcs_clusters, key=lambda x: x["cluster_id"] not in fed_cluster_id_list)

        # bcs 集群中的正常状态
        for bcs_cluster in bcs_clusters:
            logger.info("discover_bcs_clusters: get bcs cluster:{},start to register".format(bcs_cluster["cluster_id"]))
            project_id = bcs_cluster["project_id"]
            bk_biz_id = int(bcs_cluster["bk_biz_id"])

            # 对 业务ID 进行二次校验
            try:
                bk_biz_id_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    f"discover_bcs_clusters: cluster_id:{bcs_cluster['cluster_id']} bk_biz_id:{bk_biz_id} get bk_tenant_id failed, error:{e}"
                )
                continue

            if bk_biz_id_tenant_id != bk_tenant_id:
                logger.error(
                    f"discover_bcs_clusters: cluster_id:{bcs_cluster['cluster_id']} bk_biz_id:{bk_biz_id} not belong to bk_tenant_id:{bk_tenant_id}"
                )
                continue

            cluster_id = bcs_cluster["cluster_id"]
            cluster_raw_status = bcs_cluster["status"]
            cluster_list.append(cluster_id)
            is_fed_cluster = cluster_id in fed_cluster_id_list

            # todo 同一个集群在切换业务时不能重复接入
            cluster = BCSClusterInfo.objects.filter(cluster_id=cluster_id).first()
            if cluster:
                # 更新集群信息，兼容集群迁移场景
                # 场景1:集群迁移业务，项目ID不变，只会变业务ID
                # 场景2:集群迁移项目，项目ID和业务ID都可能变化
                update_fields: set[str] = set()

                # 如果集群状态为初始化失败，则重试
                if cluster.status == BCSClusterInfo.CLUSTER_STATUS_INIT_FAILED:
                    init_result, err = _init_bcs_cluster_resource(cluster, is_fed_cluster=is_fed_cluster)
                    if init_result:
                        logger.info(
                            f"cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} retry init resource success"
                        )
                        update_fields.add("status")
                        cluster.status = BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING
                    else:
                        logger.error(
                            f"cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} retry init resource failed, error:{err}"
                        )

                # NOTE: 现阶段完全以 BCS 的集群状态为准，如果集群初始化状态为失败，则不更新
                if cluster_raw_status != cluster.status and cluster.status != BCSClusterInfo.CLUSTER_STATUS_INIT_FAILED:
                    cluster.status = cluster_raw_status
                    update_fields.add("status")

                # 如果 BCS Token 变了需要刷新
                if cluster.api_key_content != settings.BCS_API_GATEWAY_TOKEN:
                    cluster.api_key_content = settings.BCS_API_GATEWAY_TOKEN
                    update_fields.add("api_key_content")

                if int(bk_biz_id) != cluster.bk_biz_id:
                    # 记录旧业务ID，更新新业务ID
                    old_bk_biz_id = cluster.bk_biz_id
                    cluster.bk_biz_id = int(bk_biz_id)
                    update_fields.add("bk_biz_id")

                    # 若业务ID变更，其RT对应的业务ID也应一并变更
                    logger.info(
                        f"discover_bcs_clusters: cluster_id:{cluster_id},project_id:{project_id} change bk_biz_id to {int(bk_biz_id)}"
                    )

                    # 变更对应的路由元信息
                    change_cluster_router(
                        cluster=cluster,
                        old_bk_biz_id=old_bk_biz_id,
                        new_bk_biz_id=bk_biz_id,
                        is_fed_cluster=is_fed_cluster,
                    )

                # 如果project_id改动，需要更新集群信息
                if project_id != cluster.project_id:
                    cluster.project_id = project_id
                    update_fields.add("project_id")

                if update_fields:
                    update_fields.add("last_modify_time")
                    cluster.save(update_fields=list(update_fields))

                if cluster.bk_cloud_id is None:
                    # 更新云区域ID
                    update_bcs_cluster_cloud_id_config(bk_biz_id, cluster_id)

                if is_fed_cluster:
                    # 创建联邦集群记录
                    try:
                        sync_federation_clusters(fed_clusters)
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(f"discover_bcs_clusters: sync_federation_clusters failed, error:{e}")

                logger.info(f"cluster_id:{cluster_id},project_id:{project_id} already exists,skip create it")
                continue

            cluster = BCSClusterInfo.register_cluster(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                cluster_id=cluster_id,
                project_id=project_id,
                creator="admin",
                is_fed_cluster=is_fed_cluster,
            )
            logger.info(
                f"discover_bcs_clusters: cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} registered"
            )

            # 初始化集群资源
            init_result, err = _init_bcs_cluster_resource(cluster, is_fed_cluster=is_fed_cluster)
            if init_result:
                logger.info(
                    f"cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} init resource success"
                )
            else:
                cluster.status = BCSClusterInfo.CLUSTER_STATUS_INIT_FAILED
                cluster.save(update_fields=["status"])
                logger.error(
                    f"cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} init resource failed, error:{err}"
                )
                continue

            # 更新云区域ID
            update_bcs_cluster_cloud_id_config(bk_biz_id, cluster_id)

            logger.info(
                f"cluster_id:{cluster.cluster_id},project_id:{cluster.project_id},bk_biz_id:{cluster.bk_biz_id} init resource finished"
            )

    # 如果是不存在的集群列表则更新当前状态为删除，加上>0的判断防止误删
    if cluster_list:
        logger.info(
            "discover_bcs_clusters: enable always running fake clusters->[%s]",
            settings.ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST,
        )
        cluster_list.extend(settings.ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST)

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
    clusters = BCSClusterInfo.objects.filter(**filter_kwargs).values("bk_tenant_id", "bk_biz_id", "cluster_id")
    for start in range(0, len(clusters), BCS_SYNC_SYNC_CONCURRENCY):
        cluster_chunk = clusters[start : start + BCS_SYNC_SYNC_CONCURRENCY]
        # 从BCS获取集群的节点IP
        params: dict[str, tuple[str, int]] = {
            cluster["cluster_id"]: (cluster["bk_tenant_id"], cluster["bk_biz_id"]) for cluster in cluster_chunk
        }
        bulk_request_params = [
            {"bcs_cluster_id": bcs_cluster_id, "bk_tenant_id": bk_tenant_id}
            for bcs_cluster_id, (bk_tenant_id, _) in params.items()
        ]
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
            if not params.get(bcs_cluster_id):
                continue
            bk_biz_id = params[bcs_cluster_id][1]
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
            models.BcsFederalClusterInfo.objects.filter(is_deleted=False).values_list("fed_cluster_id", flat=True)
        )

        # 删除不再归属的联邦集群记录
        clusters_to_delete = existing_fed_clusters - fed_cluster_ids
        if clusters_to_delete:
            logger.info("sync_federation_clusters:Deleting federation cluster info for->[%s]", clusters_to_delete)
            models.BcsFederalClusterInfo.objects.filter(fed_cluster_id__in=clusters_to_delete).update(is_deleted=True)

        # 遍历最新的联邦集群关系
        for fed_cluster_id, fed_cluster_data in fed_clusters.items():
            logger.info("sync_federation_clusters:Syncing federation cluster ->[%s]", fed_cluster_id)

            host_cluster_id = fed_cluster_data["host_cluster_id"]
            sub_clusters = fed_cluster_data["sub_clusters"]

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
                        "fed_namespaces": updated_namespaces,
                        "fed_builtin_metric_table_id": fed_builtin_metric_table_id,
                        "fed_builtin_event_table_id": fed_builtin_event_table_id,
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
            for sub_cluster_id in fed_cluster_data["sub_clusters"].keys()
        }

        # 获取数据库中所有子集群的记录（排除软删除的记录）
        existing_sub_clusters = models.BcsFederalClusterInfo.objects.filter(is_deleted=False).values_list(
            "fed_cluster_id", "sub_cluster_id"
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
            "sync_federation_clusters:Start Creating federation data links for sub-clusters->[%s] asynchronously",
            need_process_clusters,
        )
        # bulk_create_fed_data_link(need_process_clusters)
        bulk_create_fed_data_link.delay(set(need_process_clusters))  # 异步创建联邦汇聚链路

        logger.info("sync_federation_clusters:sync_federation_clusters finished successfully.")

    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e)
        logger.warning("sync_federation_clusters:sync_federation_clusters failed, error->[%s]", e)
