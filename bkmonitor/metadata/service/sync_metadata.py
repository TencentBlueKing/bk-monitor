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

import logging

from metadata import models

logger = logging.getLogger("metadata")


def sync_kafka_metadata(kafka_info, ds, bk_data_id):
    """
    同步 Kafka 元数据信息
    @param kafka_info: Kafka 集群信息
    @param ds: 数据源信息
    @param bk_data_id: 数据源 ID
    """
    try:
        kafka_cluster = models.ClusterInfo.objects.get(domain_name=kafka_info['host'])
    except models.ClusterInfo.DoesNotExist:
        logger.info("sync_kafka_metadata: kafka_cluster does not exist,try to create,data->[%s]", kafka_info)
        if kafka_info['auth']:  # TODO：当Kafka带鉴权时，需要后续介入补充
            logger.warning(
                "sync_kafka_metadata: kafka auth is not empty,please add auth info later,data->[%s]", kafka_info
            )
        # 如果 Kafka 集群信息不存在，创建新集群
        kafka_cluster = models.ClusterInfo.objects.create(
            cluster_name=kafka_info['host'],
            domain_name=kafka_info['host'],
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            port=kafka_info['port'],
            is_default_cluster=False,
        )

    # 更新 KafkaTopicInfo 信息，按需更新
    try:
        kafka_topic_ins = models.KafkaTopicInfo.objects.get(bk_data_id=bk_data_id)
        if kafka_topic_ins.topic != kafka_info['topic'] or kafka_topic_ins.partition != kafka_info['partitions']:
            logger.info(
                "sync_kafka_metadata: kafka_topic_info is different from old,try to update,bk_data_id->[%s]", bk_data_id
            )
            kafka_topic_ins.topic = kafka_info['topic']
            kafka_topic_ins.partition = kafka_info['partitions']
            kafka_topic_ins.save()
    except models.KafkaTopicInfo.DoesNotExist:
        # 如果 KafkaTopicInfo 不存在，创建新 KafkaTopicInfo
        kafka_topic_ins = models.KafkaTopicInfo.objects.create(
            bk_data_id=bk_data_id, topic=kafka_info['topic'], partition=kafka_info['partitions']
        )

    # 更新 DataSource 信息，按需更新
    if ds.mq_cluster_id != kafka_cluster.cluster_id or ds.mq_config_id != kafka_topic_ins.id:
        logger.info(
            "sync_kafka_metadata: mq_cluster_info is different from old,try to update,bk_data_id->[%s]", bk_data_id
        )
        ds.mq_cluster_id = kafka_cluster.cluster_id
        ds.mq_config_id = kafka_topic_ins.id
        ds.save()


def sync_es_metadata(es_info, table_id):
    """
    同步 ES 元数据信息
    @param es_info: ES 元数据信息
    @param table_id: 结果表ID
    """
    try:
        es_storage = models.ESStorage.objects.get(table_id=table_id)
    except models.ESStorage.DoesNotExist:
        logger.error("sync_es_metadata: es_storage_ins does not exist,table_id->[%s]", table_id)
        return

    try:
        es_cluster = models.ClusterInfo.objects.get(domain_name=es_info['host'])
    except models.ClusterInfo.DoesNotExist:
        # 如果 ES 集群信息不存在，创建新集群（理论上不应出现这种情况）
        logger.error(
            "sync_es_metadata: es cluster does not exist,please check,table_id->[%s],es_info->[%s]", table_id, es_info
        )
        return

    # 更新 ESStorage 信息，按需更新
    if es_storage.storage_cluster_id != es_cluster.cluster_id:
        logger.info("sync_es_metadata: es_storage info is different from old ,try to update,table_id->[%s]", table_id)
        es_storage.storage_cluster_id = es_cluster.cluster_id
        es_storage.save()


def sync_vm_metadata(vm_info, table_id):
    """
    同步 VM 元数据信息
    @param vm_info: VM 元数据信息
    @param table_id: 结果表ID
    """
    try:
        access_vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
    except models.AccessVMRecord.DoesNotExist:
        logger.error("sync_vm_metadata: access_vm_record does not exist,table_id->[%s]", table_id)
        return

    try:
        vm_cluster = models.ClusterInfo.objects.get(domain_name=vm_info['select_host'])
    except models.ClusterInfo.DoesNotExist:
        # 如果 VM 集群信息不存在，创建新集群
        logger.info("sync_vm_metadata: vm cluster does not exist,try to create it,vm_info->[%s]", vm_info)
        vm_cluster = models.ClusterInfo.objects.create(
            cluster_name=vm_info['name'],
            domain_name=vm_info['select_host'],
            port=vm_info['select_port'],
            cluster_type=models.ClusterInfo.TYPE_VM,
            is_default_cluster=False,
        )

    # 更新 AccessVMRecord 信息，按需更新
    if access_vm_record.vm_cluster_id != vm_cluster.cluster_id:
        logger.info("sync_vm_metadata: vm storage info is different from old,try to update,table_id->[%s]", table_id)
        access_vm_record.vm_cluster_id = vm_cluster.cluster_id
        access_vm_record.save()
