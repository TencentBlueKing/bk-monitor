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
from typing import Any

from dateutil import parser
from django.conf import settings
from django.utils import timezone

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

logger = logging.getLogger("metadata")


def parse_time(time_str):
    """
    解析时间字符串，兼容微秒等格式
    @param time_str: 时间字符串
    @return: DateTIme 对象
    """
    try:
        return parser.parse(time_str)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("parse_time:parse->[%s],error->[%s]", time_str, e)
        return None


def sync_kafka_metadata(bk_tenant_id: str, kafka_info: dict[str, Any], ds: models.DataSource, bk_data_id: int):
    """
    同步 Kafka 元数据信息
    @param bk_tenant_id: 租户ID
    @param kafka_info: Kafka 集群信息
    @param ds: 数据源信息
    @param bk_data_id: 数据源 ID
    """
    kafka_cluster = None
    try:
        kafka_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, domain_name=kafka_info["host"])
    except models.ClusterInfo.DoesNotExist:
        logger.info(
            "sync_kafka_metadata: data different,kafka_cluster does not exist,try to create,data->[%s],"
            "bk_data_id->[%s]",
            kafka_info,
            bk_data_id,
        )
        if kafka_info["auth"]:  # TODO：当Kafka带鉴权时，需要后续介入补充
            logger.warning(
                "sync_kafka_metadata: kafka auth is not empty,please add auth info later,data->[%s],bk_data_id->[%s]",
                kafka_info,
                bk_data_id,
            )
        # 如果 Kafka 集群信息不存在，创建新集群
        if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
            logger.info(
                "sync_kafka_metadata: try to write to db,switch on,data->[%s],bk_data_id->[%s]", kafka_info, bk_data_id
            )
            kafka_cluster = models.ClusterInfo.objects.create(
                bk_tenant_id=bk_tenant_id,
                cluster_name=kafka_info["host"],
                domain_name=kafka_info["host"],
                cluster_type=models.ClusterInfo.TYPE_KAFKA,
                port=kafka_info["port"],
                is_default_cluster=False,
            )

    if not kafka_cluster:
        logger.error(
            "sync_kafka_metadata: kafka_cluster does not exist,data->[%s],bk_data_id->[%s]", kafka_info, bk_data_id
        )
        return

    # 更新 KafkaTopicInfo 信息，按需更新
    try:
        kafka_topic_ins = models.KafkaTopicInfo.objects.get(bk_data_id=bk_data_id)
        if kafka_topic_ins.topic != kafka_info["topic"] or kafka_topic_ins.partition != kafka_info["partitions"]:
            logger.info(
                "sync_kafka_metadata: data different,kafka_topic_info is different from old,try to update,"
                "bk_data_id->[%s],"
                "old_topic->[%s],new_topic->[%s],old_partitions->[%s],new_partitions->[%s]",
                bk_data_id,
                kafka_topic_ins.topic,
                kafka_info["topic"],
                kafka_topic_ins.partition,
                kafka_info["partitions"],
            )
            if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
                logger.info(
                    "sync_kafka_metadata: try to write to db,switch on,data->[%s],bk_data_id->[%s]",
                    kafka_info,
                    bk_data_id,
                )
                kafka_topic_ins.topic = kafka_info["topic"]
                kafka_topic_ins.partition = kafka_info["partitions"]
                kafka_topic_ins.save()
    except models.KafkaTopicInfo.DoesNotExist:
        # 如果 KafkaTopicInfo 不存在，创建新 KafkaTopicInfo
        kafka_topic_ins = models.KafkaTopicInfo.objects.create(
            bk_data_id=bk_data_id, topic=kafka_info["topic"], partition=kafka_info["partitions"]
        )

    # 更新 DataSource 信息，按需更新
    if ds.mq_cluster_id != kafka_cluster.cluster_id or ds.mq_config_id != kafka_topic_ins.pk:
        logger.info(
            "sync_kafka_metadata: data different,mq_cluster_info is different from old,try to update,bk_data_id->["
            "%s],old_mq_cluster_id->[%s],new_mq_cluster_id->[%s],old_mq_config_id->[%s],new_mq_config_id->[%s]",
            bk_data_id,
            ds.mq_cluster_id,
            kafka_cluster.cluster_id,
            ds.mq_config_id,
            kafka_topic_ins.pk,
        )
        if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
            logger.info("sync_kafka_metadata: try to write to db,switch on,data->[%s]", kafka_info)
            ds.mq_cluster_id = kafka_cluster.cluster_id
            ds.mq_config_id = kafka_topic_ins.pk
            ds.save()


def sync_es_metadata(bk_tenant_id: str, es_info: list[dict[str, Any]], table_id: str):
    """
    同步 ES 元数据信息
    ES信息为一个列表,包含所有历史ES集群信息记录，会按照时间进行倒排序
    @param bk_tenant_id: 租户ID
    @param es_info: ES 元数据信息
    @param table_id: 结果表ID
    """
    es_cluster = None
    logger.info("sync_es_metadata: start,table_id->[%s],es_info->[%s]", table_id, es_info)
    try:
        es_storage = models.ESStorage.objects.get(table_id=table_id)
    except models.ESStorage.DoesNotExist:
        logger.error("sync_es_metadata: es_storage_ins does not exist,table_id->[%s]", table_id)
        return

    # 对es_info进行排序，按照时间进行倒排序
    es_info_sorted: list[dict[str, Any]] = sorted(
        es_info, key=lambda x: parse_time(x["update_time"]) or "", reverse=True
    )

    # 先同步当前ES信息
    current_es_info = es_info_sorted[0]
    try:
        es_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, domain_name=current_es_info["host"])
    except models.ClusterInfo.DoesNotExist:
        # 如果 ES 集群信息不存在，创建新集群（理论上不应出现这种情况）
        logger.error(
            "sync_es_metadata: data different,es cluster does not exist,please check,table_id->[%s],es_info->[%s]",
            table_id,
            es_info,
        )
        if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
            logger.info("sync_es_metadata: try to write to db,switch on,data->[%s],table_id->[%s]", es_info, table_id)
            models.ClusterInfo.objects.create(
                bk_tenant_id=bk_tenant_id,
                domain_name=current_es_info["host"],
                port=current_es_info["port"],
                cluster_type=models.ClusterInfo.TYPE_ES,
                is_default_cluster=False,
                cluster_name=current_es_info["host"],
            )

    if not es_cluster:
        logger.error("sync_es_metadata: es_cluster does not exist,table_id->[%s]", table_id)
        return

    # 更新 ESStorage 信息，按需更新
    if es_storage.storage_cluster_id != es_cluster.cluster_id:
        logger.info(
            "sync_es_metadata: data different,es_storage info is different from old ,try to update,"
            "table_id->[%s],old_es_cluster_id->[%s],new_es_cluster_id->[%s]",
            table_id,
            es_storage.storage_cluster_id,
            es_cluster.cluster_id,
        )
        if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
            logger.info("sync_es_metadata: try to write to db,switch on,data->[%s],table_id->[%s]", es_info, table_id)
            es_storage.storage_cluster_id = es_cluster.cluster_id
            es_storage.save()

    if not settings.ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE:
        logger.info("sync_es_metadata: not enable sync history es cluster record from bkbase,skip,table_id->[%s]")
        return

    logger.info(
        "sync_es_metadata: start to sync history es cluster record,table_id->[%s],es_info->[%s]", table_id, es_info
    )

    # 解析所有集群信息，收集cluster_id和启用/停用时间
    clusters = []
    valid_cluster_ids = []
    for idx, info in enumerate(es_info_sorted):
        host = info["host"]
        try:
            cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, domain_name=host)
            enable_time = info["update_time"]
            # 停用时间：上一条更晚记录的启用时间（若存在）
            disable_time = parse_time(es_info_sorted[idx - 1]["update_time"]) if idx > 0 else None
            clusters.append(
                {
                    "cluster": cluster,
                    "enable_time": enable_time,
                    "disable_time": disable_time,
                    "is_current": idx == 0,  # 仅第一个为当前集群
                }
            )
            valid_cluster_ids.append(cluster.cluster_id)
        except models.ClusterInfo.DoesNotExist:
            logger.error(f"sync_es_metadata: cluster not exists, host={host}")
            continue

    # 标记不在当前有效列表中的记录为已删除
    models.StorageClusterRecord.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).exclude(
        cluster_id__in=valid_cluster_ids
    ).update(is_deleted=True, disable_time=timezone.now(), delete_time=timezone.now())

    # 先重置所有记录的is_current状态
    models.StorageClusterRecord.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).update(is_current=False)

    # 遍历处理每个集群记录
    for cluster_data in clusters:
        try:
            cluster = cluster_data["cluster"]
            enable_time = parse_time(cluster_data["enable_time"])
            disable_time = parse_time(cluster_data["disable_time"])
            is_current = cluster_data["is_current"]

            # 查找或创建记录
            record, created = models.StorageClusterRecord.objects.get_or_create(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                cluster_id=cluster.cluster_id,
                defaults={
                    "creator": "system",  # 根据实际需求调整创建者
                    "disable_time": disable_time,
                    "enable_time": enable_time,
                    "is_current": is_current,
                    "is_deleted": False,
                },
            )

            # 更新现有记录（若存在且需要修改）
            if not created:
                update_fields = []
                if record.disable_time != disable_time:
                    record.disable_time = disable_time
                    update_fields.append("disable_time")
                if record.is_current != is_current:
                    record.is_current = is_current
                    update_fields.append("is_current")
                if record.is_deleted:
                    record.is_deleted = False
                    update_fields.append("is_deleted")
                if update_fields:
                    record.save(update_fields=update_fields)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("sync_es_metadata: failed to sync es metadata,table_id->[%s],error->[%s]", table_id, e)
            continue

    # 确保最新的记录is_current=True（防止并发问题）
    if clusters:
        latest_cluster = clusters[0]
        models.StorageClusterRecord.objects.filter(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            cluster_id=latest_cluster["cluster"].cluster_id,
            enable_time=parse_time(latest_cluster["enable_time"]),
        ).update(is_current=True)

    # 推送路由
    logger.info("sync_es_metadata: push router to redis,table_id->[%s]", table_id)
    space_client = SpaceTableIDRedis()
    space_client.push_es_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)

    logger.info("sync_es_metadata: sync es metadata successfully, table_id->[%s]", table_id)


def sync_vm_metadata(bk_tenant_id: str, vm_info: dict[str, dict[str, Any]]):
    """
    同步 VM 元数据信息
    vm: {rt1:{},rt2:{},rt3:{}}
    @param bk_tenant_id: 租户ID
    @param vm_info: VM 元数据信息
    """
    # 从Redis中拉取到的数据结构发生了变化
    for vm_result_table_id, detail in vm_info.items():
        logger.info(
            "sync_vm_metadata: start to sync vm record,vm_result_table_id->[%s],detail->[%s]",
            vm_result_table_id,
            detail,
        )
        access_vm_records = models.AccessVMRecord.objects.filter(
            bk_tenant_id=bk_tenant_id, vm_result_table_id=vm_result_table_id
        )
        if not access_vm_records:  # 若不存在对应的VMRT接入记录,记录日志并跳过
            logger.warning(
                "sync_vm_metadata: access_vm_record does not exist,vm_result_table_id->[%s]", vm_result_table_id
            )
            continue

        vm_cluster = None
        try:
            vm_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, domain_name=detail["insert_host"])
        except models.ClusterInfo.DoesNotExist:
            # 如果 VM 集群信息不存在，创建新集群
            logger.info(
                "sync_vm_metadata: data different,vm cluster does not exist,try to create it,detail->[%s]", detail
            )
            # 激活元数据一致性写入模式的情况下才进行写入
            if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
                logger.info(
                    "sync_vm_metadata: try to write to db,switch on,detail->[%s],vm_result_table_id->[%s]",
                    detail,
                    vm_result_table_id,
                )
                vm_cluster = models.ClusterInfo.objects.create(
                    bk_tenant_id=bk_tenant_id,
                    cluster_name=detail["name"],
                    domain_name=detail["insert_host"],
                    port=detail["insert_port"],
                    cluster_type=models.ClusterInfo.TYPE_VM,
                    is_default_cluster=False,
                )

        if not vm_cluster:  # 若对应的VM集群仍不存在,跳过并记录日志
            logger.error(
                "sync_vm_metadata: vm_cluster does not exist,vm_result_table_id->[%s],detail->[%s]",
                vm_result_table_id,
                detail,
            )
            continue

        for access_vm_record in access_vm_records:
            if access_vm_record.vm_cluster_id != vm_cluster.cluster_id:
                logger.info(
                    "sync_vm_metadata: data different,vm storage info is different from old,try to update,"
                    "access_vm_record->[%s],old_vm_cluster_id->[%s],new_vm_cluster_id->[%s]",
                    access_vm_record,
                    access_vm_record.vm_cluster_id,
                    vm_cluster.cluster_id,
                )
                # 激活元数据一致性写入模式的情况下才进行写入
                if settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB:
                    logger.info(
                        "sync_vm_metadata: try to write to db,switch on,detail->[%s],vm_result_table_id->[%s]",
                        detail,
                        vm_result_table_id,
                    )
                    access_vm_record.vm_cluster_id = vm_cluster.cluster_id
                    access_vm_record.save()
