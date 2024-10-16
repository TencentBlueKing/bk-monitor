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
import json
import logging
import time
import traceback

from confluent_kafka import TopicCollection
from confluent_kafka.admin import AdminClient
from django.conf import settings
from django.db.models import F
from django.utils.translation import ugettext as _

from alarm_backends.core.lock.service_lock import share_lock
from metadata import models
from metadata.config import (
    KAFKA_SASL_MECHANISM,
    KAFKA_SASL_PROTOCOL,
    PERIODIC_TASK_DEFAULT_TTL,
)
from metadata.models.constants import EsSourceType
from metadata.task.tasks import manage_es_storage
from metadata.utils import consul_tools

logger = logging.getLogger("metadata")


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshConsulInfluxdbTableInfo")
def refresh_consul_influxdb_tableinfo():
    """
    刷新storage信息给unify-query使用
    """
    try:
        logger.info("start to refresh metadata influxdb table info")
        models.ResultTable.refresh_consul_influxdb_tableinfo()
    except Exception as e:
        logger.error("refresh influxdb table info failed for ->{}".format(e))


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshConsulStorage")
def refresh_consul_storage():
    """
    刷新storage信息给unify-query使用
    """
    try:
        logger.info("start to refresh metadata es storage info")
        models.ClusterInfo.refresh_consul_storage_config()
    except Exception as e:
        logger.error("refresh es storage failed for ->{}".format(e))


@share_lock(identify="metadata_refreshConsulESInfo")
def refresh_consul_es_info():
    """
    刷新es相关的consul信息，供unify-query使用
    """
    try:
        logger.info("start to refresh metadata es table info")
        models.ESStorage.refresh_consul_table_config()
    except Exception as e:
        logger.error("refresh es table failed for ->{}".format(e))


@share_lock(ttl=1800, identify="metadata_refreshInfluxdbRoute")
def refresh_influxdb_route():
    """
    实际定时任务需要操作的内容
    注意：会发现此处有很多单独的异常捕获内容，主要是为了防止其中一个系统的异常，会波及其他系统
    :return:
    """

    # 更新influxdb路由信息至consul当中
    # 顺序应该是 主机 -> 集群 -> 结果表
    try:
        for host_info in models.InfluxDBHostInfo.objects.all():
            host_info.refresh_consul_cluster_config()
            logger.debug("host->[%s] refresh consul config success." % host_info.host_name)

        models.InfluxDBClusterInfo.refresh_consul_cluster_config()
        logger.debug("influxdb cluster refresh consul config success.")

        index = models.InfluxDBStorage.objects.count()
        for result_table in models.InfluxDBStorage.objects.all():
            index -= 1
            result_table.refresh_consul_cluster_config(is_publish=(index == 0))
            logger.debug("result_table->[%s] refresh consul config success." % result_table.table_id)

        # 更新 vm router
        models.AccessVMRecord.refresh_vm_router()

    except Exception:
        # 上述的内容对外统一是依赖consul，所以使用一个exception进行捕获
        logger.error("failed to refresh influxdb router info for->[{}]".format(traceback.format_exc()))

    # 任务完成前，更新一下version
    consul_tools.refresh_router_version()
    logger.info("influxdb router config refresh success.")

    # 更新TS结果表外部的依赖信息
    for result_table in models.InfluxDBStorage.objects.all():
        try:
            # 确认数据库已经创建
            result_table.sync_db()
            # 确保存在可用的清理策略
            result_table.ensure_rp()
            logger.debug("tsdb result_table->[{}] sync_db success.".format(result_table.table_id))
        except Exception:
            logger.error(
                "result_table->[{}] failed to sync database for->[{}]".format(
                    result_table.table_id, traceback.format_exc()
                )
            )
    # 刷新tag路由
    try:
        logger.info("start to refresh metadata tag")
        models.InfluxDBTagInfo.refresh_consul_tag_config()
    except Exception as e:
        logger.error("refresh tag failed for ->{}".format(e))


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_cleanInfluxdbTag")
def clean_influxdb_tag():
    models.InfluxDBTagInfo.clean_consul_config()
    models.InfluxDBTagInfo.clean_redis_tag_config()


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_cleanInfluxdbStorage")
def clean_influxdb_storage():
    models.InfluxDBStorage.clean_consul_config()
    models.InfluxDBStorage.clean_redis_cluster_config()


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_cleanInfluxdbCluster")
def clean_influxdb_cluster():
    models.InfluxDBClusterInfo.clean_consul_config()
    models.InfluxDBClusterInfo.clean_redis_cluster_config()


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_cleanInfluxdbHost")
def clean_influxdb_host():
    models.InfluxDBHostInfo.clean_consul_config()
    models.InfluxDBHostInfo.clean_redis_host_config()


def refresh_datasource():
    # 更新datasource的外部依赖 及 配置信息
    # NOTE: 过滤有结果表的数据源并且状态是启动
    # 过滤到有结果表的数据源
    ds_rt_map = {
        ds_rt["table_id"]: ds_rt["bk_data_id"]
        for ds_rt in models.DataSourceResultTable.objects.values("bk_data_id", "table_id")
    }
    # 过滤启用的结果表
    enabled_rts = models.ResultTable.objects.filter(
        table_id__in=ds_rt_map.keys(), is_deleted=False, is_enable=True
    ).values_list("table_id", flat=True)
    # 过滤到对应的数据源 ID
    ds_with_rt = {data_id for rt, data_id in ds_rt_map.items() if rt in enabled_rts}
    for datasource in models.DataSource.objects.filter(is_enable=True, bk_data_id__in=ds_with_rt).order_by(
        "-last_modify_time"
    ):
        try:
            # 更新前，需要从DB读取一次最新的数据，避免脏数据读写
            datasource.clean_cache()
            # 2. 更新ETL及datasource的配置
            datasource.refresh_outer_config()
            logger.debug("data_id->[%s] refresh all outer success" % datasource.bk_data_id)
        except Exception:
            logger.error(
                "data_id->[{}] failed to refresh outer config for->[{}]".format(
                    datasource.bk_data_id, traceback.format_exc()
                )
            )


@share_lock(identify="metadata_refreshKafkaStorage")
def refresh_kafka_storage():
    # 确认所有kafka存储都有对应的topic
    for kafka_storage in models.KafkaStorage.objects.all():
        try:
            kafka_storage.ensure_topic()
            logger.debug("kafka storage for result_table->[{}] is ensure create.".format(kafka_storage.table_id))
        except Exception:
            logger.error(
                "kafka->[{}] failed to make sure topic exists for->[{}]".format(
                    kafka_storage.table_id, traceback.format_exc()
                )
            )


def refresh_kafka_topic_info():
    cluster_map = {}
    for kafka_topic_info in models.KafkaTopicInfo.objects.all():
        try:
            bk_data_id = kafka_topic_info.bk_data_id
            datasource = models.DataSource.objects.get(bk_data_id=bk_data_id)
            try:
                client = cluster_map[datasource.mq_cluster_id]
            except KeyError:
                cluster = models.ClusterInfo.objects.get(cluster_id=datasource.mq_cluster_id)
                conf = {
                    "bootstrap.servers": f"{cluster.domain_name}:{cluster.port}",
                }
                # NOTE: 当有用户名和密码时，指定对应的sasl_mechanism和security_protocol
                if cluster.username and cluster.password:
                    conf["sasl.mechanisms"] = KAFKA_SASL_MECHANISM
                    conf["security.protocol"] = KAFKA_SASL_PROTOCOL
                    conf["sasl.username"] = cluster.username
                    conf["sasl.password"] = cluster.password

                client = AdminClient(conf)
                cluster_map[datasource.mq_cluster_id] = client
            topics = client.describe_topics(TopicCollection([kafka_topic_info.topic]))
            topic_detail = topics.get(kafka_topic_info.topic)
            if not topic_detail:
                continue
            try:
                len_partition = len(topic_detail.result().partitions)
            except AttributeError:
                continue
            if not len_partition:
                raise ValueError(_("分区数量获取失败，请确认"))

            # NOTE: 当 metadata 中 topic 对应的 partition 小于 kafka 中实际的 partition 时，直接跳过
            if kafka_topic_info.partition >= len_partition:
                continue

            kafka_topic_info.partition = len_partition
            # 仅更新变动的字段
            kafka_topic_info.save(update_fields=["partition"])

            # 重新获取一次数据，然后刷新consul
            datasource.clean_cache()
            datasource.refresh_consul_config()
        except Exception as e:
            logger.exception("partition of topic->[%s] failed to confirm for->[%s]", kafka_topic_info.topic, e)
            continue
        logger.info(
            "kafka topic info for partition of topic->[%s] with partition->[%s]has been refreshed.",
            kafka_topic_info.topic,
            kafka_topic_info.partition,
        )


@share_lock(identify="metadata_refreshESStorage", ttl=7200)
def refresh_es_storage():
    logger.info("refresh_es_storage:start to refresh es_storage")
    start_time = time.time()  # 记录开始时间

    # 1. 获取设置中的黑名单和白名单
    es_blacklist = getattr(settings, "ES_CLUSTER_BLACKLIST", [])
    # es_cluster_wl = getattr(settings, "ES_SERIAL_CLUSTER_LIST", [])

    # # 处理白名单中的集群，串行处理
    # if es_cluster_wl:
    #     es_storage_data = models.ESStorage.objects.filter(
    #         storage_cluster_id__in=es_cluster_wl, need_create_index=True
    #     )
    #     manage_es_storage.delay(es_storage_data)

    # 2.筛选出需要创建索引且不在黑名单中的集群
    # Note：由于白名单中的集群涉及的索引数量过大，现不再采用串行处理方式，改为根据ES集群ID分组进行索引轮转任务
    es_storages = models.ESStorage.objects.filter(source_type=EsSourceType.LOG.value, need_create_index=True).exclude(
        storage_cluster_id__in=es_blacklist
    )

    # 3. 过滤掉无效的表，进一步减少轮转的索引数据量
    table_id_list = models.ResultTable.objects.filter(
        table_id__in=es_storages.values_list("table_id", flat=True), is_enable=True, is_deleted=False
    ).values_list("table_id", flat=True)

    es_storages = es_storages.filter(table_id__in=table_id_list)

    # 4. 设置每个任务处理的记录数
    start, step = 0, 100

    # 5. 按 storage_cluster_id 分组下发轮转任务，提高并发性能，降低ES集群的压力
    es_storages_by_cluster = es_storages.values('storage_cluster_id').distinct()

    for cluster in es_storages_by_cluster:
        cluster_id = cluster['storage_cluster_id']
        cluster_storages = es_storages.filter(storage_cluster_id=cluster_id)
        count = cluster_storages.count()
        logger.info("refresh_es_storage:refresh cluster_id->[%s] es_storages count->[%s]", cluster_id, count)
        # 5.1 为每个集群创建批量任务
        for s in range(start, count, step):
            manage_es_storage.delay(cluster_storages[s : s + step])

    end_time = time.time()  # 记录结束时间
    logger.info("refresh_es_storage:es_storage cron task started successfully,use %.2f seconds.", end_time - start_time)


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshBCSInfo")
def refresh_bcs_info():
    """
    刷新bcs_info到consul
    """
    try:
        logger.info("start to refresh resources")
        models.PodMonitorInfo.refresh_all_to_consul()
    except Exception as e:
        logger.error("refresh bcs info into consul failed for ->{}".format(e))
    # 清理到期的回溯索引
    models.EsSnapshotRestore.clean_expired_restore()


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshEsRestore")
def refresh_es_restore():
    # 刷新回溯状态
    not_done_restores = models.EsSnapshotRestore.objects.exclude(total_doc_count=F("complete_doc_count")).exclude(
        is_deleted=True
    )
    for not_done_restore in not_done_restores:
        try:
            not_done_restore.get_complete_doc_count()
        except Exception:
            logger.info(
                "es_restore->[{}] failed to cron task for->[{}]".format(
                    not_done_restore.restore_id, traceback.format_exc()
                )
            )
            continue


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refreshInfluxDBProxyStorage")
def refresh_influxdb_proxy_storage():
    """刷新 influxdb proxy 和实际存储的关系"""
    logger.info("start to push influxdb proxy and storage to consul and redis")
    models.InfluxDBProxyStorage.push()
    logger.info("push influxdb proxy and storage to consul and redis successfully")


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_cleanInfluxDBProxyStorage")
def clean_influxdb_proxy_storage():
    logger.info("start to clean influxdb proxy and storage data")
    models.InfluxDBProxyStorage.clean()
    logger.info("clean influxdb proxy and storage data successfully")


@share_lock(ttl=PERIODIC_TASK_DEFAULT_TTL, identify="metadata_refresh_unify_query_additional_config")
def refresh_unify_query_additional_config():
    logger.info("start to refresh config for unify_query")
    models.InfluxDBStorage.refresh_additional_info_for_unify_query()
    logger.info("end to refresh config for unify_query")


@share_lock(identify="metadata_clean_datasource_from_consul")
def clean_datasource_from_consul():
    """比较数据库和consul中不一致的数据源，然后删除数据

    1. 没有使用的 transfer 集群，递归删除
        - NOTE: 这里的 transfer 集群通过使用的 data id 路径分割获取
    2. 在使用的 transfer 集群，如果 data id 不存在，则删除
    """
    logger.info("start to delete datasource from consul")
    # 获取使用的 transfer 集群
    data_info = models.DataSource.objects.filter(is_enable=True).values("bk_data_id", "transfer_cluster_id")
    # 组装 transfer 消费的数据源 ID
    transfer_id_and_data_ids = {}
    for d in data_info:
        # NOTE: 转换为字符串，便于后续和 consul 中数据进行对比
        transfer_id_and_data_ids.setdefault(d["transfer_cluster_id"], set()).add(str(d["bk_data_id"]))

    from metadata import config

    hash_consul = consul_tools.HashConsul()
    # 比对 transfer 集群，不存在的 transfer 集群直接删除
    transfer_key_tmpl = f"{config.CONSUL_PATH}/v1/"
    transfer_consul_data = hash_consul.list(transfer_key_tmpl)
    # d format: {'LockIndex': 0, 'Key': 'xxx/metadata/v1/default/data_id/1001'}
    # default 为 transfer 集群
    transfer_cluster_ids = set()
    for d in transfer_consul_data[1]:
        try:
            transfer_cluster_id = d["Key"].split(transfer_key_tmpl)[-1].split("/")[0]
        except Exception as e:
            logger.error("parse consul data id error, data: %s error: %s", d, e)
            continue
        transfer_cluster_ids.add(transfer_cluster_id)
    diff_transfers = transfer_cluster_ids - set(transfer_id_and_data_ids.keys())
    # 如果存在没有使用的 transfer 集群，则递归删除
    # NOTE: 因为风险有些高，先记录下数据，然后再开启删除
    # for transfer_id in diff_transfers:
    #     hash_consul.delete(f"{transfer_key_tmpl}{transfer_id}", recurse=True)

    logger.info("deleted transfer cluster: %s", json.dumps(diff_transfers))

    # 获取 consul 中的数据源 ID
    key_tmpl = f"{config.CONSUL_PATH}/v1/{{transfer_cluster_id}}/data_id/"
    for transfer_id, data_ids in transfer_id_and_data_ids.items():
        consul_key = key_tmpl.format(transfer_cluster_id=transfer_id)
        consul_data = hash_consul.list(consul_key)
        # 组装数据源 ID
        consul_data_ids = set()
        # d format: {'LockIndex': 0, 'Key': 'xxx/metadata/v1/default/data_id/1001'}
        for d in consul_data[1]:
            try:
                consul_data_id = d["Key"].rsplit("/", 1)[-1]
            except Exception as e:
                logger.error("parse consul data id error, data: %s error: %s", d, e)
                continue
            consul_data_ids.add(consul_data_id)

        # 比对数据，然后删除数据库中不存在的数据源ID
        diff_data_ids = consul_data_ids - data_ids
        if not diff_data_ids:
            continue

        logger.info("need delete data id: %s", json.dumps(diff_data_ids))

        # 删除数据
        # NOTE: 因为风险有些高，先记录下数据，然后再开启删除
        # for d in diff_data_ids:
        #     deleted_key = config.CONSUL_DATA_ID_PATH_FORMAT.format(transfer_cluster_id=transfer_id, data_id=d)
        #     try:
        #         hash_consul.delete(deleted_key)
        #     except Exception as e:
        #         logger.error("delete consul key error, key: %s, error: %s", deleted_key, e)
        #         continue

    logger.info("delete datasource from consul successfully")
