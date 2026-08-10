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
import re
import time

from django.conf import settings
from django.db import transaction

from alarm_backends.core.cache.key import SERVICE_LOCK_METADATA_RECONCILE_FEDERATION_DATA_LINK
from alarm_backends.core.lock.service_lock import service_lock, share_lock
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
from metadata.service.federation_data_link import (
    FederationReconcilePlan,
    get_bcs_metric_table_id,
    reconcile_federation_data_links,
    validate_federation_topology,
)
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.bcs import change_cluster_router, get_bcs_dataids

logger = logging.getLogger("metadata")

BCS_SYNC_SYNC_CONCURRENCY = 20
CMDB_IP_SEARCH_MAX_SIZE = 100
BCS_CLUSTER_ID_PATTERN = re.compile(r"^BCS-K8S-(\d+)$")


@app.task(bind=True, ignore_result=True, queue="celery_metadata_task_worker", max_retries=3)
def reconcile_federation_data_links_task(
    self,
    bk_tenant_id: str,
    active_proxy_cluster_ids: list[str],
    active_sub_cluster_ids: list[str],
    removed_proxy_cluster_ids: list[str],
    removed_sub_cluster_ids: list[str],
):
    plan = FederationReconcilePlan(
        active_proxy_cluster_ids=active_proxy_cluster_ids,
        active_sub_cluster_ids=active_sub_cluster_ids,
        removed_proxy_cluster_ids=removed_proxy_cluster_ids,
        removed_sub_cluster_ids=removed_sub_cluster_ids,
    ).normalized()
    try:
        with service_lock(
            SERVICE_LOCK_METADATA_RECONCILE_FEDERATION_DATA_LINK,
            bk_tenant_id=bk_tenant_id,
        ):
            reconcile_federation_data_links(bk_tenant_id=bk_tenant_id, plan=plan)
    except Exception as error:  # pylint: disable=broad-except
        logger.exception(
            "reconcile_federation_data_links_task failed, tenant->[%s],plan->[%s]",
            bk_tenant_id,
            plan,
        )
        raise self.retry(exc=error, countdown=min(60 * (2**self.request.retries), 600))


def schedule_federation_reconcile(bk_tenant_id: str, plan: FederationReconcilePlan) -> None:
    plan = plan.normalized()
    transaction.on_commit(
        lambda: reconcile_federation_data_links_task.delay(
            bk_tenant_id=bk_tenant_id,
            active_proxy_cluster_ids=plan.active_proxy_cluster_ids,
            active_sub_cluster_ids=plan.active_sub_cluster_ids,
            removed_proxy_cluster_ids=plan.removed_proxy_cluster_ids,
            removed_sub_cluster_ids=plan.removed_sub_cluster_ids,
        )
    )


def get_bcs_cluster_id_suffix(cluster_id: str) -> int | None:
    """提取 BCS 集群 ID 的数字后缀。"""
    match = BCS_CLUSTER_ID_PATTERN.fullmatch(cluster_id)
    if not match:
        return None
    return int(match.group(1))


def get_discover_start_cluster_id_suffix() -> int | None:
    """获取 discover 任务起始集群 ID 的数字后缀。"""
    start_cluster_id = settings.NEW_ENV_START_CLUSTER_ID
    if not start_cluster_id:
        return None

    start_cluster_id_suffix = get_bcs_cluster_id_suffix(start_cluster_id)
    if start_cluster_id_suffix is None:
        logger.warning(
            "discover_bcs_clusters: invalid NEW_ENV_START_CLUSTER_ID(%s), disable threshold filter",
            start_cluster_id,
        )
    return start_cluster_id_suffix


def is_discover_biz_blacklisted(bk_biz_id: int | str | None) -> bool:
    """判断业务是否在 BCS 集群自动发现黑名单内。"""
    if bk_biz_id is None:
        return False

    blacklisted_biz_ids = {str(biz_id).strip() for biz_id in settings.NEW_ENV_CLUSTER_BLACK_LIST}
    return str(bk_biz_id).strip() in blacklisted_biz_ids


def is_discover_biz_whitelisted(bk_biz_id: int | str | None) -> bool:
    """判断业务是否在 BCS 集群自动发现白名单内。

    白名单是起始集群阈值（``NEW_ENV_START_CLUSTER_ID``）的例外：命中白名单的业务，
    即使集群 ID 后缀不大于阈值，也会被 discover 任务接管。白名单为空表示无例外。

    Args:
        bk_biz_id: 集群所属业务 ID。

    Returns:
        True 表示业务命中白名单（豁免阈值过滤）；False 表示未命中。
    """
    if bk_biz_id is None:
        return False

    whitelisted_biz_ids = {str(biz_id).strip() for biz_id in settings.NEW_ENV_CLUSTER_WHITE_LIST}
    return str(bk_biz_id).strip() in whitelisted_biz_ids


def is_discover_managed_cluster(cluster_id: str, start_cluster_id_suffix: int | None, bk_biz_id: int | str) -> bool:
    """
    判断当前集群是否由 discover 任务接管新增和删除。

    规则（按顺序短路）：
    - ``bk_biz_id`` 命中 ``NEW_ENV_CLUSTER_BLACK_LIST``：不接管（黑名单优先级最高）；
    - ``bk_biz_id`` 命中 ``NEW_ENV_CLUSTER_WHITE_LIST``：接管（作为起始集群阈值的例外，
      即使 ``cluster_id`` 后缀不大于阈值也接管）；
    - 未配置 ``NEW_ENV_START_CLUSTER_ID``（``start_cluster_id_suffix`` 为 ``None``）：全部接管，保持历史行为；
    - 已配置：仅当 ``cluster_id`` 的数字后缀**严格大于**该阈值时才接管，阈值本身不接管；
    - ``cluster_id`` 无法解析出数字后缀：保守地视为不接管，避免异常数据被误纳入删除链。

    Args:
        cluster_id: BCS 集群 ID，形如 ``BCS-K8S-00001``。
        start_cluster_id_suffix: ``NEW_ENV_START_CLUSTER_ID`` 的数字后缀，``None`` 表示阈值未生效。
        bk_biz_id: 集群所属业务 ID，用于应用业务黑/白名单过滤。

    Returns:
        True 表示该集群由 discover 任务接管；False 表示不接管。
    """
    if is_discover_biz_blacklisted(bk_biz_id):
        return False

    # 白名单作为起始集群阈值的例外：命中即接管，绕过 cluster_id 后缀阈值过滤。
    if is_discover_biz_whitelisted(bk_biz_id):
        return True

    if start_cluster_id_suffix is None:
        return True

    cluster_id_suffix = get_bcs_cluster_id_suffix(cluster_id)
    if cluster_id_suffix is None:
        return False

    return cluster_id_suffix > start_cluster_id_suffix


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
    fed_clusters_by_tenant: dict[str, dict] = {}
    for tenant in api.bk_login.list_tenant():
        bk_tenant_id = tenant["id"]
        try:
            fed_clusters_by_tenant[bk_tenant_id] = api.bcs.get_federation_clusters(bk_tenant_id=bk_tenant_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("get federation clusters failed, tenant->[%s],error->[%s]", bk_tenant_id, e)
    fed_cluster_ids_by_tenant = {
        bk_tenant_id: set(tenant_fed_clusters) for bk_tenant_id, tenant_fed_clusters in fed_clusters_by_tenant.items()
    }

    bcs_clusters = list(
        BCSClusterInfo.objects.filter(
            status__in=[models.BCSClusterInfo.CLUSTER_STATUS_RUNNING, models.BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING],
        )
    )

    # 对 bcs_clusters 进行排序，确保各租户自己的联邦代理集群优先。
    bcs_clusters = sorted(
        bcs_clusters,
        key=lambda cluster: cluster.cluster_id not in fed_cluster_ids_by_tenant.get(cluster.bk_tenant_id, set()),
    )

    # discover 任务起始集群 ID 阈值，用于与 discover_bcs_clusters 的接管范围保持一致
    start_cluster_id_suffix = get_discover_start_cluster_id_suffix()

    # 拉取所有cluster，遍历刷新monitorinfo信息
    for cluster in bcs_clusters:
        # 跳过不由 discover 接管的集群（黑名单业务、白名单外且集群后缀不大于阈值等），
        # 避免刷新本任务范围外集群的监控信息。
        if not is_discover_managed_cluster(cluster.cluster_id, start_cluster_id_suffix, bk_biz_id=cluster.bk_biz_id):
            logger.info(
                "refresh_bcs_monitor_info: cluster_id:%s,bk_biz_id:%s is not managed by discover filters, skip refresh",
                cluster.cluster_id,
                cluster.bk_biz_id,
            )
            continue

        try:
            is_fed_cluster = cluster.cluster_id in fed_cluster_ids_by_tenant.get(cluster.bk_tenant_id, set())
            # 刷新集群内置公共dataid resource
            # NOTE: 没有必要每次都刷新dataid，可以交给discover_bcs_clusters任务刷新
            if not settings.DISABLE_BCS_CLUSTER_REFRESH_COMMON_RESOURCE:
                cluster.refresh_common_resource(is_fed_cluster=is_fed_cluster)
                logger.info(f"refresh bcs common resource in cluster:{cluster.cluster_id} done")

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
        except Exception:  # noqa
            logger.exception("refresh bcs monitor info failed, cluster_id(%s)", cluster.cluster_id)

    for bk_tenant_id, fed_clusters in fed_clusters_by_tenant.items():
        try:
            plan = sync_federation_clusters(fed_clusters=fed_clusters, bk_tenant_id=bk_tenant_id)
            schedule_federation_reconcile(bk_tenant_id=bk_tenant_id, plan=plan)
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(
                "refresh_bcs_monitor_info: sync federation failed, tenant->[%s],error->[%s]",
                bk_tenant_id,
                error,
            )

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
    start_cluster_id_suffix = get_discover_start_cluster_id_suffix()
    all_discovered_cluster_ids: set[str] = set()
    managed_discovered_cluster_ids: set[str] = set()
    for tenant in api.bk_login.list_tenant():
        bk_tenant_id = tenant["id"]
        try:
            bcs_clusters = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=bk_tenant_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"discover_bcs_clusters: get bcs clusters failed, error:{e}")
            return
        # 获取所有联邦集群 ID
        fed_clusters = {}
        fed_topology_available = True
        try:
            fed_clusters = api.bcs.get_federation_clusters(bk_tenant_id=bk_tenant_id)
            fed_cluster_id_list = list(fed_clusters.keys())  # 联邦的代理集群列表
        except Exception as e:  # pylint: disable=broad-except
            fed_topology_available = False
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
            all_discovered_cluster_ids.add(cluster_id)
            is_fed_cluster = cluster_id in fed_cluster_id_list
            is_managed_cluster = is_discover_managed_cluster(cluster_id, start_cluster_id_suffix, bk_biz_id=bk_biz_id)
            if is_managed_cluster:
                managed_discovered_cluster_ids.add(cluster_id)

            # todo 同一个集群在切换业务时不能重复接入
            cluster = BCSClusterInfo.objects.filter(cluster_id=cluster_id).first()
            if cluster:
                if not is_managed_cluster:
                    logger.info(
                        "discover_bcs_clusters: cluster_id:%s,bk_biz_id:%s is not managed by discover filters, skip update",
                        cluster_id,
                        bk_biz_id,
                    )
                    continue

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

                logger.info(f"cluster_id:{cluster_id},project_id:{project_id} already exists,skip create it")
                continue

            if not is_managed_cluster:
                logger.info(
                    "discover_bcs_clusters: cluster_id:%s,bk_biz_id:%s is not managed by discover filters, "
                    "start_cluster_id:%s,biz_black_list:%s,biz_white_list:%s, skip register",
                    cluster_id,
                    bk_biz_id,
                    settings.NEW_ENV_START_CLUSTER_ID,
                    settings.NEW_ENV_CLUSTER_BLACK_LIST,
                    settings.NEW_ENV_CLUSTER_WHITE_LIST,
                )
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

        if fed_topology_available:
            try:
                plan = sync_federation_clusters(fed_clusters=fed_clusters, bk_tenant_id=bk_tenant_id)
                schedule_federation_reconcile(bk_tenant_id=bk_tenant_id, plan=plan)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "discover_bcs_clusters: sync federation failed, tenant->[%s],error->[%s]",
                    bk_tenant_id,
                    error,
                )

    # 如果是不存在的集群列表则更新当前状态为删除，加上>0的判断防止误删
    if all_discovered_cluster_ids:
        logger.info(
            "discover_bcs_clusters: enable always running fake clusters->[%s]",
            settings.ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST,
        )
        # ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST 本身语义就是"不应被标记为删除"，
        # 无论是否在 discover 阈值管理范围内，都统一加入 protected 集合，避免被误删。
        protected_cluster_ids = managed_discovered_cluster_ids | set(settings.ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST)
        managed_existing_cluster_ids = [
            cluster_id
            for cluster_id, bk_biz_id in BCSClusterInfo.objects.values_list("cluster_id", "bk_biz_id")
            if is_discover_managed_cluster(cluster_id, start_cluster_id_suffix, bk_biz_id=bk_biz_id)
        ]

        if managed_existing_cluster_ids:
            BCSClusterInfo.objects.filter(cluster_id__in=managed_existing_cluster_ids).exclude(
                cluster_id__in=protected_cluster_ids
            ).update(status=BCSClusterInfo.CLUSTER_RAW_STATUS_DELETED)

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


def sync_federation_clusters(fed_clusters: dict, bk_tenant_id: str = "system") -> FederationReconcilePlan:
    """按租户同步完整联邦拓扑，并返回需要执行的完整链路收敛计划。"""

    validate_federation_topology(fed_clusters)
    logger.info(
        "sync_federation_clusters: started, tenant->[%s],fed_cluster_ids->[%s]",
        bk_tenant_id,
        sorted(fed_clusters),
    )
    existing_active_records = list(
        models.BcsFederalClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    )
    existing_proxy_cluster_ids = {record.fed_cluster_id for record in existing_active_records}
    existing_sub_cluster_ids = {record.sub_cluster_id for record in existing_active_records}

    desired_pairs: set[tuple[str, str]] = set()
    with transaction.atomic():
        for fed_cluster_id, fed_cluster_data in fed_clusters.items():
            cluster = models.BCSClusterInfo.objects.get(
                bk_tenant_id=bk_tenant_id,
                cluster_id=fed_cluster_id,
            )
            metric_table_id = get_bcs_metric_table_id(
                bk_tenant_id=bk_tenant_id,
                bk_data_id=cluster.K8sMetricDataID,
            )
            event_table_id = (
                models.DataSourceResultTable.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_data_id=cluster.K8sEventDataID,
                )
                .order_by("table_id")
                .values_list("table_id", flat=True)
                .first()
            )

            host_cluster_id = fed_cluster_data["host_cluster_id"]
            for sub_cluster_id, namespaces in fed_cluster_data.get("sub_clusters", {}).items():
                desired_pairs.add((fed_cluster_id, sub_cluster_id))
                if namespaces is None:
                    logger.info(
                        "sync_federation_clusters: skip None namespaces, tenant->[%s],fed->[%s],sub->[%s]",
                        bk_tenant_id,
                        fed_cluster_id,
                        sub_cluster_id,
                    )
                    continue
                models.BcsFederalClusterInfo.objects.update_or_create(
                    bk_tenant_id=bk_tenant_id,
                    fed_cluster_id=fed_cluster_id,
                    sub_cluster_id=sub_cluster_id,
                    defaults={
                        "host_cluster_id": host_cluster_id,
                        "fed_namespaces": sorted(set(namespaces)),
                        "fed_builtin_metric_table_id": metric_table_id,
                        "fed_builtin_event_table_id": event_table_id,
                        "is_deleted": False,
                    },
                )

        active_queryset = models.BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_deleted=False,
        )
        for fed_cluster_id, sub_cluster_id in active_queryset.values_list("fed_cluster_id", "sub_cluster_id"):
            if (fed_cluster_id, sub_cluster_id) not in desired_pairs:
                models.BcsFederalClusterInfo.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    fed_cluster_id=fed_cluster_id,
                    sub_cluster_id=sub_cluster_id,
                ).update(is_deleted=True)

    current_active_records = list(
        models.BcsFederalClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, is_deleted=False)
    )
    active_proxy_cluster_ids = {record.fed_cluster_id for record in current_active_records}
    active_sub_cluster_ids = {record.sub_cluster_id for record in current_active_records}
    plan = FederationReconcilePlan(
        active_proxy_cluster_ids=sorted(active_proxy_cluster_ids),
        active_sub_cluster_ids=sorted(active_sub_cluster_ids),
        removed_proxy_cluster_ids=sorted(existing_proxy_cluster_ids - active_proxy_cluster_ids),
        removed_sub_cluster_ids=sorted(existing_sub_cluster_ids - active_sub_cluster_ids),
    )
    logger.info("sync_federation_clusters: finished, tenant->[%s],plan->[%s]", bk_tenant_id, plan)
    return plan
