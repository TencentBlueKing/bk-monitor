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

from metadata import models

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
    kafka_cluster: models.ClusterInfo | None = None

    kafka_clusters: list[models.ClusterInfo] = list(
        models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, domain_name=kafka_info["host"])
    )
    # 如果存在多个集群，优先选择ds当前已经关联的集群
    for cluster in kafka_clusters:
        if cluster.cluster_id == ds.mq_cluster_id:
            kafka_cluster = cluster
            break
    else:
        if len(kafka_clusters) > 0:
            kafka_cluster = kafka_clusters[0]

    if not kafka_cluster:
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
        else:
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
    if kafka_cluster and (ds.mq_cluster_id != kafka_cluster.cluster_id or ds.mq_config_id != kafka_topic_ins.pk):
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
    es_cluster: models.ClusterInfo | None = None
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
    es_clusters = models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, domain_name=current_es_info["host"])
    for cluster in es_clusters:
        if cluster.cluster_id == es_storage.storage_cluster_id:
            es_cluster = cluster
            break
    else:
        if len(es_clusters) > 0:
            es_cluster = es_clusters[0]

    if not es_cluster:
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
        else:
            logger.error("sync_es_metadata: es_cluster does not exist,table_id->[%s],es_info->[%s]", table_id, es_info)
            return

    # 更新 ESStorage 信息，按需更新
    if es_cluster and es_storage.storage_cluster_id != es_cluster.cluster_id:
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
        access_vm_record: models.AccessVMRecord | None = models.AccessVMRecord.objects.filter(
            bk_tenant_id=bk_tenant_id, vm_result_table_id=vm_result_table_id
        ).first()
        if not access_vm_record:  # 若不存在对应的VMRT接入记录,记录日志并跳过
            logger.warning(
                "sync_vm_metadata: access_vm_record does not exist,vm_result_table_id->[%s]", vm_result_table_id
            )
            continue

        vm_cluster: models.ClusterInfo | None = None
        vm_clusters: list[models.ClusterInfo] = list(
            models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, domain_name=detail["insert_host"])
        )

        for cluster in vm_clusters:
            if cluster.cluster_id == access_vm_record.vm_cluster_id:
                vm_cluster = cluster
                break
        else:
            if len(vm_clusters) > 0:
                vm_cluster = vm_clusters[0]

        if not vm_cluster:
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
            else:
                logger.error(
                    "sync_vm_metadata: vm_cluster does not exist,vm_result_table_id->[%s],detail->[%s]",
                    vm_result_table_id,
                    detail,
                )
                return

        if vm_cluster and access_vm_record.vm_cluster_id != vm_cluster.cluster_id:
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
