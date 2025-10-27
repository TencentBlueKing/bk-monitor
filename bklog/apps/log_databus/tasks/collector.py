"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import datetime
import time
import re
import traceback
from collections import defaultdict

import pytz
from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.conf import settings
from django.utils.translation import gettext as _
from django.db import transaction

from apps.api import BkLogApi, TransferApi
from apps.api.modules.bkdata_databus import BkDataDatabusApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import FEATURE_BKDATA_DATAID
from apps.log_databus.constants import (
    REGISTERED_SYSTEM_DEFAULT,
    RETRY_TIMES,
    STORAGE_CLUSTER_TYPE,
    WAIT_FOR_RETRY,
    CollectItsmStatus,
    ContainerCollectStatus,
    BATCH_SYNC_CLUSTER_COUNT,
)
from apps.log_databus.handlers.collector import CollectorHandler
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.models import (
    BcsStorageClusterConfig,
    CollectorConfig,
    ContainerCollectorConfig,
    StorageUsed,
)
from apps.log_measure.handlers.elastic import ElasticHandle
from apps.log_search.constants import CustomTypeEnum
from apps.log_search.models import LogIndexSet
from apps.utils.bcs import Bcs
from apps.utils.log import logger
from apps.utils.task import high_priority_task


@high_priority_task(ignore_result=True)
def shutdown_collector_warm_storage_config(cluster_id):
    """异步关闭冷热集群的采集项"""
    result_table_list = []
    for collector in CollectorConfig.objects.all():
        if not collector.table_id:
            continue
        result_table_list.append(collector.table_id)

    if not result_table_list:
        return

    cluster_infos = CollectorHandler.bulk_cluster_infos(result_table_list=result_table_list)
    for collector in CollectorConfig.objects.all():
        try:
            if not collector.table_id:
                continue
            cluster_info = cluster_infos.get(collector.table_id)
            if not cluster_info:
                continue
            if cluster_info["cluster_config"]["cluster_id"] != cluster_id:
                continue
            TransferApi.modify_result_table(
                {
                    "table_id": collector.table_id,
                    "default_storage": "elasticsearch",
                    "default_storage_config": {"warm_phase_days": 0},
                    "bk_biz_id": collector.bk_biz_id,
                }
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error("refresh collector storage config error", e)
            continue


@periodic_task(run_every=crontab(minute="0", hour="1"))
def collector_status():
    """
    检测采集项：24小时未入库自动停止
    :return:
    """

    # 筛选24小时未入库的采集项
    day_ago = datetime.datetime.now(pytz.timezone("UTC")) - datetime.timedelta(days=1)
    collector_configs = CollectorConfig.objects.filter(
        table_id=None, is_active=True, created_at__lt=day_ago, collector_plugin_id=None
    ).exclude(itsm_ticket_status=CollectItsmStatus.APPLYING)
    # 停止采集项
    for _collector in collector_configs:
        if (
            FeatureToggleObject.switch(FEATURE_BKDATA_DATAID)
            and _collector.bkdata_data_id
            and BkDataDatabusApi.get_cleans(
                params={"raw_data_id": _collector.bkdata_data_id, "bk_biz_id": _collector.bk_biz_id}
            )
        ):
            continue
        CollectorHandler.get_instance(_collector.collector_config_id).stop()


@periodic_task(run_every=crontab(minute="0"))
def sync_storage_capacity():
    """
    每小时同步业务各集群已用容量
    :return:
    """
    # 1、获取所有集群
    params = {"cluster_type": STORAGE_CLUSTER_TYPE}
    cluster_obj = TransferApi.get_cluster_info(params)

    # 2、构建集群业务映射
    from apps.log_search.models import LogIndexSet

    cluster_biz_cnt_map = defaultdict(lambda: defaultdict(int))
    for index_set in LogIndexSet.objects.all():
        cluster_biz_cnt_map[index_set.storage_cluster_id][index_set.space_uid] += 1

    # 批量收集所有需要创建或更新的 StorageUsed 对象
    storage_used_objects = []

    for _cluster in cluster_obj:
        try:
            usage, total = get_storage_usage_and_all(_cluster["cluster_config"]["cluster_id"])

            index_count = count_storage_indices(_cluster["cluster_config"]["cluster_id"])

            # 按集群归纳的 StorageUsed 对象
            cluster_storage_obj = StorageUsed(
                bk_biz_id=0,
                storage_cluster_id=_cluster["cluster_config"]["cluster_id"],
                storage_total=total,
                storage_usage=usage,
                index_count=index_count,
                biz_count=len(cluster_biz_cnt_map.get(_cluster["cluster_config"]["cluster_id"], {}).keys()),
            )
            storage_used_objects.append(cluster_storage_obj)

            # 2-1公共集群：所有业务都需要查询
            if _cluster["cluster_config"].get("registered_system") == REGISTERED_SYSTEM_DEFAULT:
                # 一次性获取该集群下所有业务的存储容量
                all_biz_storage = get_all_biz_storage_capacity(_cluster)
                for biz_id, storage_used in all_biz_storage.items():
                    biz_storage_obj = StorageUsed(
                        bk_biz_id=biz_id,
                        storage_cluster_id=_cluster["cluster_config"]["cluster_id"],
                        storage_used=storage_used,
                    )
                    storage_used_objects.append(biz_storage_obj)
            # 2-2第三方集群：只需查询指定业务
            else:
                bk_biz_id = _cluster["cluster_config"].get("custom_option", {}).get("bk_biz_id")
                if bk_biz_id:
                    storage_used = get_biz_storage_capacity(bk_biz_id, _cluster)
                    biz_storage_obj = StorageUsed(
                        bk_biz_id=bk_biz_id,
                        storage_cluster_id=_cluster["cluster_config"]["cluster_id"],
                        storage_used=storage_used,
                    )
                    storage_used_objects.append(biz_storage_obj)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"sync_storage_info error: {e}")

    # 进行批量处理
    if storage_used_objects:
        try:
            batch_upsert_storage_used(storage_used_objects)
        except Exception as e:
            logger.exception(f"批量处理storage_used记录失败: {e}")


def query(cluster_id):
    def get(url):
        try:
            return BkLogApi.es_route({"scenario_id": "es", "storage_cluster_id": cluster_id, "url": url})
        except Exception as e:  # pylint:disable=broad-except
            logger.exception(f"request es info error {e}")
            return None

    return get


def get_storage_usage_and_all(cluster_id):
    storage_config = query(cluster_id)("_cat/allocation?bytes=b")
    usage = 0
    total = 0
    if not storage_config:
        return usage, total
    for _storage in storage_config:
        total += int(_storage.get("disk.total") or 0)
        usage += int(_storage.get("disk.used") or 0)
    return int((usage / total) * 100), total


def count_storage_indices(cluster_id):
    indices = query(cluster_id)("_cat/indices?bytes=b")
    if not indices:
        return 0

    return len(indices) if indices else 0


def _get_cluster_connection_info(cluster):
    """
    提取集群连接信息的公共逻辑
    :param cluster: 集群信息
    :return: (domain_name, port, username, password)
    """
    cluster_config = cluster["cluster_config"]
    domain_name = cluster_config["domain_name"]
    port = cluster_config["port"]
    auth_info = cluster.get("auth_info", {})
    username = auth_info.get("username")
    password = auth_info.get("password")
    return domain_name, port, username, password


def _get_indices_info(cluster, index_format):
    """
    获取索引信息的公共逻辑
    :param cluster: 集群信息
    :param index_format: 索引格式
    :return: 索引信息列表
    """
    # 获取集群连接信息
    domain_name, port, username, password = _get_cluster_connection_info(cluster)

    # 获取索引信息并过滤掉关闭状态的索引
    try:
        indices_info = ElasticHandle(domain_name, port, username, password).get_indices_cat(
            index=index_format, bytes="mb", column=["index", "store.size", "status"]
        )
        return [index_info for index_info in indices_info if index_info["status"] != "close"]
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(f"集群[{domain_name}] 索引cat信息获取失败，错误信息：{e}")
        raise


def get_biz_storage_capacity(bk_biz_id, cluster):
    """
    获取指定业务的存储容量
    :param bk_biz_id: 业务ID
    :param cluster: 集群信息
    :return: 存储容量（GB）
    """
    index_format = f"{bk_biz_id}_bklog_*"
    active_indices = _get_indices_info(cluster, index_format)

    # 累加存储容量
    total_size = 0
    for _info in active_indices:
        total_size += int(_info["store.size"])
    return round(total_size / 1024, 2)


def get_all_biz_storage_capacity(cluster):
    """
    获取集群下所有业务的存储容量
    :param cluster: 集群信息
    :return: 字典格式 {biz_id: storage_size}
    """
    index_format = "*_bklog_*"
    active_indices = _get_indices_info(cluster, index_format)

    # 按业务ID分组累加存储容量
    biz_storage_map = defaultdict(int)
    for index_info in active_indices:
        index_name = index_info["index"]

        # 尝试解析biz_id，如果解析失败说明不是有效的bklog索引
        biz_id = parse_index_to_biz_id(index_name)
        if biz_id is None:
            continue
        # 处理存储大小转换
        store_size = int(index_info["store.size"])
        # 累加存储容量
        biz_storage_map[biz_id] += store_size

    # 转换为GB并保留两位小数
    result = {}
    for biz_id, total_size in biz_storage_map.items():
        result[biz_id] = round(total_size / 1024, 2)

    return result


def parse_index_to_biz_id(index_name):
    """
    解析索引名称获取biz_id
    :param index_name: 完整的索引名称
    :return: biz_id 或 None
    """
    # 定义所有支持的索引格式模式
    patterns = [
        r"^v2_(\d+)_bklog_.*$",  # v2_x_bklog_* 格式
        r"^v2_space_(\d+)_bklog_.*$",  # v2_space_x_bklog_* 格式
    ]

    # 尝试每个模式
    for pattern in patterns:
        match = re.match(pattern, index_name)
        if match:
            if "v2_space_" in pattern:
                # 对于空间ID，取负数才是真正的业务ID
                space_id = int(match.group(1))
                biz_id = -space_id
            else:
                biz_id = int(match.group(1))
            return biz_id
    return None


@high_priority_task(ignore_result=True)
def create_container_release(bcs_cluster_id: str, container_config_id: int, config_name: str, config_params: dict):
    for __ in range(RETRY_TIMES):
        try:
            container_config: ContainerCollectorConfig = ContainerCollectorConfig.objects.get(pk=container_config_id)
            container_config.status = ContainerCollectStatus.RUNNING.value
            container_config.status_detail = _("配置下发中")
            container_config.save(update_fields=["status", "status_detail"])
            break
        except ContainerCollectorConfig.objects.DoesNotExist:
            # db的事务可能还未结束，这里需要重试
            time.sleep(WAIT_FOR_RETRY)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[create_container_release] get container config failed: {e}")
            raise e
    else:
        logger.error(f"[create_container_release] retry container_config[{container_config_id}] {RETRY_TIMES} times")
        return

    try:
        labels = None
        if settings.CONTAINER_COLLECTOR_CR_LABEL_BKENV:
            labels = {"bk_env": settings.CONTAINER_COLLECTOR_CR_LABEL_BKENV}
        Bcs(bcs_cluster_id).save_bklog_config(bklog_config_name=config_name, bklog_config=config_params, labels=labels)
        container_config.status = ContainerCollectStatus.SUCCESS.value
        container_config.status_detail = _("配置下发成功")
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("[create_container_release] save bklog config failed: %s", e)
        container_config.status = ContainerCollectStatus.FAILED.value
        container_config.status_detail = _("配置下发失败: {reason}").format(reason=e)
    container_config.save(update_fields=["status", "status_detail"])


@high_priority_task(ignore_result=True)
def delete_container_release(
    bcs_cluster_id: str, container_config_id: int, config_name: str, delete_config: bool = False
):
    try:
        # 删除配置，如果没抛异常，则必定成功
        Bcs(bcs_cluster_id).delete_bklog_config(config_name)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("[delete_container_release] delete bklog config failed: %s", e)

    try:
        container_config = ContainerCollectorConfig.objects.get(pk=container_config_id)
    except ContainerCollectorConfig.DoesNotExist:
        # 采集配置可能已经被删掉，这种情况下直接返回就行，不用更新采集状态
        return

    if delete_config:
        # 停用后直接删掉
        container_config.delete()
    else:
        # 无论成败与否，都设置为已停用
        container_config.status = ContainerCollectStatus.TERMINATED.value
        container_config.save(update_fields=["status"])


@periodic_task(run_every=crontab(minute="0"))
def create_custom_log_group():
    """
    将存量的 Otlp Log 创建 Log Group
    """

    otlp_logs = CollectorConfig.objects.filter(custom_type=CustomTypeEnum.OTLP_LOG.value, log_group_id__isnull=True)
    for log in otlp_logs:
        try:
            CollectorHandler.create_custom_log_group(log)
            log.refresh_from_db(fields=["log_group_id"])
            logger.info(
                "[CreateCustomLogGroupSuccess] Collector => %s; LogGroupID => %s",
                log.collector_config_id,
                log.log_group_id,
            )
        except Exception as err:
            msg = traceback.format_exc()
            logger.error(
                "[CreateCustomLogGroupFailed] Collector => %s; Error => %s ; Detail => %s",
                log.collector_config_id,
                str(err),
                msg,
            )


@high_priority_task(ignore_result=True)
def switch_bcs_collector_storage(bk_biz_id, bcs_cluster_id, storage_cluster_id, bk_app_code):
    collectors = CollectorConfig.objects.filter(
        bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id, bk_app_code=bk_app_code
    )
    # 新增bcs采集存储集群全局配置更新
    BcsStorageClusterConfig.objects.update_or_create(
        bcs_cluster_id=bcs_cluster_id, bk_biz_id=bk_biz_id, defaults={"storage_cluster_id": storage_cluster_id}
    )

    # 存量bcs采集存储集群更新
    from apps.log_databus.handlers.etl import EtlHandler

    for collector in collectors:
        try:
            collect_config = CollectorHandler.get_instance(collector.collector_config_id).retrieve()
            if collect_config["storage_cluster_id"] == storage_cluster_id:
                logger.info(
                    f"switch collector->[{collector.collector_config_id}] old storage cluster is the same: {storage_cluster_id}, skip it."
                )
                continue
            etl_params = {
                "table_id": collector.collector_config_name_en,
                "storage_cluster_id": storage_cluster_id,
                "retention": collect_config["retention"],
                "allocation_min_days": collect_config["allocation_min_days"],
                "storage_replies": collect_config["storage_replies"],
                "etl_params": collect_config["etl_params"],
                "etl_config": collect_config["etl_config"],
                "fields": [field for field in collect_config["fields"] if not field["is_built_in"]],
            }
            etl_handler = EtlHandler.get_instance(collector.collector_config_id)
            etl_handler.update_or_create(**etl_params)
            logger.info(
                "switch collector->[{}] storage cluster success: {} -> {}".format(
                    collector.collector_config_id, collect_config["storage_cluster_id"], storage_cluster_id
                )
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"switch collector->[{collector.collector_config_id}] storage cluster error: {e}")


@high_priority_task(ignore_result=True)
def update_collector_storage_config(storage_cluster_id):
    """
    非冷热修改为冷热数据时,更新采集项存储配置
    :param storage_cluster_id: 存储集群ID
    """
    index_set_ids = LogIndexSet.objects.filter(storage_cluster_id=storage_cluster_id).values_list(
        "index_set_id", flat=True
    )
    collectors = CollectorConfig.objects.filter(index_set_id__in=index_set_ids, is_active=True)
    for collector in collectors:
        try:
            handler = CollectorHandler.get_instance(collector.collector_config_id)
            collect_config = handler.retrieve()
            clean_stash = handler.get_clean_stash()
            etl_params = clean_stash["etl_params"] if clean_stash else collect_config["etl_params"]
            etl_fields = (
                clean_stash["etl_fields"]
                if clean_stash
                else [field for field in collect_config["fields"] if not field["is_built_in"]]
            )

            etl_params = {
                "table_id": collector.collector_config_name_en,
                "storage_cluster_id": storage_cluster_id,
                "retention": collect_config["retention"],
                "allocation_min_days": collect_config["retention"],
                "storage_replies": collect_config["storage_replies"],
                "es_shards": collect_config["storage_shards_nums"],
                "etl_params": etl_params,
                "etl_config": collect_config["etl_config"],
                "fields": etl_fields,
            }
            etl_handler = EtlHandler.get_instance(collector.collector_config_id)
            etl_handler.update_or_create(**etl_params)
            logger.info(
                "[update_collector_storage_config] executed successfully, collector_config_id->%s",
                collector.collector_config_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "[update_collector_storage_config] executed failed, collector_config_id->%s, reason: %s",
                collector.collector_config_id,
                e,
            )


@high_priority_task(ignore_result=True)
def modify_result_table(params):
    """
    更新结果表
    """
    try:
        TransferApi.modify_result_table(params)
        logger.info(
            "[modify_result_table] executed successfully, table_id->%s",
            params["table_id"],
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.exception(
            "[modify_result_table] executed failed, table_id->%s, reason: %s",
            params["table_id"],
            e,
        )


def batch_upsert_storage_used(storage_used_objects):
    """
    批量处理 StorageUsed 对象的创建和更新
    """
    if not storage_used_objects:
        raise ValueError("没有StorageUsed需要处理")

    total_count = len(storage_used_objects)

    # 查询现有数据
    existing_objects = StorageUsed.objects.filter(
        bk_biz_id__in=set([obj.bk_biz_id for obj in storage_used_objects]),
        storage_cluster_id__in=set([obj.storage_cluster_id for obj in storage_used_objects]),
    )
    existing_map = {(obj.bk_biz_id, obj.storage_cluster_id): obj for obj in existing_objects}

    # 分类处理：需要创建的和需要更新的
    to_create = []
    to_update = []

    for obj in storage_used_objects:
        key = (obj.bk_biz_id, obj.storage_cluster_id)
        if key in existing_map:
            # 更新现有对象
            existing_obj = existing_map[key]
            existing_obj.storage_used = obj.storage_used
            existing_obj.storage_total = obj.storage_total
            existing_obj.storage_usage = obj.storage_usage
            existing_obj.index_count = obj.index_count
            existing_obj.biz_count = obj.biz_count
            to_update.append(existing_obj)
        else:
            # 创建新对象
            to_create.append(obj)

    # 使用事务进行批量操作
    with transaction.atomic():
        # 批量创建
        if to_create:
            StorageUsed.objects.bulk_create(to_create, batch_size=BATCH_SYNC_CLUSTER_COUNT)

        # 批量更新
        if to_update:
            StorageUsed.objects.bulk_update(
                to_update,
                ["storage_used", "storage_total", "storage_usage", "index_count", "biz_count"],
                batch_size=BATCH_SYNC_CLUSTER_COUNT,
            )
    logger.info(f"批量处理完成，共处理 {total_count} 条记录（创建: {len(to_create)}, 更新: {len(to_update)}）")
