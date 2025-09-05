"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import tempfile
from kafka import KafkaConsumer
from kafka.structs import TopicPartition
from django.conf import settings

from metadata.models import DataSource, ClusterInfo
from metadata import config


def get_consumer(mq_ins):
    if mq_ins.is_ssl_verify:  # SSL验证是否强验证
        server = mq_ins.extranet_domain_name if mq_ins.extranet_domain_name else mq_ins.domain_name
        port = mq_ins.port
        kafka_server = server + ":" + str(port)

        security_protocol = "SASL_SSL" if mq_ins.username else "SSL"
        sasl_mechanism = mq_ins.consul_config.get("sasl_mechanisms") or ("PLAIN" if mq_ins.username else None)

        # SSL认证证书相关，需要保存到临时文件以获取Consumer
        ssl_cafile = mq_ins.ssl_certificate_authorities
        ssl_certfile = mq_ins.ssl_certificate
        ssl_keyfile = mq_ins.ssl_certificate_key

        if ssl_cafile:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                fd.write(ssl_cafile)
                ssl_cafile = fd.name

        if ssl_certfile:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                fd.write(ssl_certfile)
                ssl_certfile = fd.name

        if ssl_keyfile:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                fd.write(ssl_keyfile)
                ssl_keyfile = fd.name

        # 创建Consumer消费实例
        consumer = KafkaConsumer(
            bootstrap_servers=kafka_server,
            security_protocol=security_protocol,
            sasl_mechanism=sasl_mechanism,
            sasl_plain_username=mq_ins.username,
            sasl_plain_password=mq_ins.password,
            request_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
            consumer_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
            ssl_cafile=ssl_cafile,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
            ssl_check_hostname=not mq_ins.ssl_insecure_skip_verify,
        )
    else:
        param = {
            "bootstrap_servers": f"{mq_ins.domain_name}:{mq_ins.port}",
            "request_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
            "consumer_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
        }
        if mq_ins.username:
            param["sasl_plain_username"] = mq_ins.username
            param["sasl_plain_password"] = mq_ins.password
            param["security_protocol"] = "SASL_PLAINTEXT"
            param["sasl_mechanism"] = "PLAIN"
        consumer = KafkaConsumer(**param)
    return consumer


def get_topic_message_counts(cluster, topics):
    print(f"bootstrap_servers: {bootstrap_servers}")
    consumer = get_consumer(cluster)
    consumer.topics()

    # 获取所有Topic列表
    topic_counts = {}

    for topic in topics:
        # 获取Topic的分区列表
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            continue

        # 为每个分区创建TopicPartition对象
        topic_partitions = [TopicPartition(topic, p) for p in partitions]
        # 查询所有分区的end_offsets（即当前最大消息偏移量）
        end_offsets = consumer.end_offsets(topic_partitions)

        # 累加所有分区的消息量
        total = sum(end_offsets[tp] for tp in topic_partitions)
        topic_counts[topic] = total

    consumer.close()
    return topic_counts


def get_kafka_info(cluster_id=None):
    # 获取data id对应的 kafka 信息，基于kafka信息分组。
    data_sources = DataSource.objects.filter(is_enable=True)
    kafka_clusters = ClusterInfo.objects.filter(cluster_type=ClusterInfo.TYPE_KAFKA)
    if cluster_id:
        kafka_clusters = kafka_clusters.filter(cluster_id=cluster_id)
    kafka_info = {}
    topic_info = {}
    # 获取所有kafka集群信息
    for cluster in kafka_clusters:
        kafka_info[cluster.cluster_id] = cluster

    # 根据data id配置的集群，按集群分组data id
    for ds in data_sources:
        topic_info.setdefault(ds.mq_cluster_id, []).append(
            f"{config.KAFKA_TOPIC_PREFIX}{ds.bk_data_id}0",
        )

    for mq_cluster_id, topics in topic_info.items():
        cluster = kafka_info.get(mq_cluster_id)
        if not cluster:
            continue
        ret = get_topic_message_counts(cluster, topics)
        print(ret)


if __name__ == "__main__":
    # 示例调用
    bootstrap_servers = "kafka-broker1:9092,kafka-broker2:9092"
    counts = get_topic_message_counts(bootstrap_servers, topics=["0bkmonitor_10010"])
    print(counts)  # 输出如 {'topic1': 15000, 'topic2': 3000}
