"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import tempfile
import time
import uuid
from typing import Any

from confluent_kafka import Consumer as ConfluentConsumer
from confluent_kafka import KafkaError, KafkaException
from confluent_kafka import TopicPartition as ConfluentTopicPartition
from django.conf import settings
from kafka import KafkaConsumer, TopicPartition

from constants.data_source import DATA_LINK_V4_VERSION_NAME
from core.drf_resource import api
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id
from metadata import config, models
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG
from metadata.models.data_link.data_link_configs import DataIdConfig
from metadata.models.data_link.utils import compose_bkdata_data_id_name
from metadata.models.space.constants import EtlConfigs

logger = logging.getLogger("kernel_api")

FUNC_DATASOURCE_KAFKA_SAMPLE = "admin.datasource.kafka_sample"

KAFKA_SAMPLE_TIMEOUT_SECONDS = 10


def _consume_with_confluent_kafka(mq_cluster: models.ClusterInfo, topic: str, size: int) -> list[dict[str, Any]]:
    consumer_config: dict[str, Any] = {
        "bootstrap.servers": f"{mq_cluster.domain_name}:{mq_cluster.port}",
        "group.id": f"bkmonitor-{uuid.uuid4()}",
        "session.timeout.ms": 6000,
        "auto.offset.reset": "latest",
        "security.protocol": mq_cluster.security_protocol,
        "sasl.mechanisms": mq_cluster.sasl_mechanisms,
        "sasl.username": mq_cluster.username,
        "sasl.password": mq_cluster.password,
    }

    consumer = ConfluentConsumer(consumer_config)

    metadata = consumer.list_topics(topic)
    partitions = metadata.topics[topic].partitions.keys()
    topic_partitions = [ConfluentTopicPartition(topic, partition) for partition in partitions]

    consumer.assign(topic_partitions)
    consumer.poll(0.5)

    result: list[dict[str, Any]] = []
    errors: list[Any] = []

    for tp in topic_partitions:
        low, high = consumer.get_watermark_offsets(tp)
        end_offset = high
        if not end_offset:
            continue

        if end_offset >= size:
            consumer.seek(ConfluentTopicPartition(topic, tp.partition, end_offset - size))
        else:
            consumer.seek(ConfluentTopicPartition(topic, tp.partition, 0))

        while len(result) < size:
            try:
                messages = consumer.consume(num_messages=size - len(result), timeout=1.0)
            except Exception:
                break
            if not messages:
                break

            for msg in messages:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        break
                    else:
                        errors.append(msg.error())
                else:
                    try:
                        result.append(json.loads(msg.value().decode()))
                    except Exception:
                        pass
                if msg.offset() == end_offset - 1:
                    break

    consumer.close()

    if not result and errors:
        raise KafkaException(errors)

    return result


def _consume_with_kafka_python(
    mq_cluster: models.ClusterInfo, topic: str, datasource: models.DataSource, size: int
) -> list[dict[str, Any]]:
    logger.info("Kafka Sample RPC: using kafka-python to tail, bk_data_id->[%s]", datasource.bk_data_id)

    if mq_cluster.is_ssl_verify:
        server = mq_cluster.extranet_domain_name if mq_cluster.extranet_domain_name else mq_cluster.domain_name
        port = mq_cluster.port
        kafka_server = f"{server}:{port}"

        security_protocol = "SASL_SSL" if mq_cluster.username else "SSL"
        sasl_mechanism = mq_cluster.consul_config.get("sasl_mechanisms") or ("PLAIN" if mq_cluster.username else None)

        ssl_cafile = mq_cluster.ssl_certificate_authorities or None
        ssl_certfile = mq_cluster.ssl_certificate or None
        ssl_keyfile = mq_cluster.ssl_certificate_key or None

        temp_files: list[str] = []
        try:
            if ssl_cafile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_cafile)
                    ssl_cafile = fd.name
                    temp_files.append(ssl_cafile)

            if ssl_certfile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_certfile)
                    ssl_certfile = fd.name
                    temp_files.append(ssl_certfile)

            if ssl_keyfile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_keyfile)
                    ssl_keyfile = fd.name
                    temp_files.append(ssl_keyfile)

            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=kafka_server,
                security_protocol=security_protocol,
                sasl_mechanism=sasl_mechanism,
                sasl_plain_username=mq_cluster.username,
                sasl_plain_password=mq_cluster.password,
                request_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
                consumer_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
                ssl_cafile=ssl_cafile,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_check_hostname=not mq_cluster.ssl_insecure_skip_verify,
            )
        finally:
            import os

            for tmp_file in temp_files:
                try:
                    os.unlink(tmp_file)
                except OSError:
                    pass
    else:
        param: dict[str, Any] = {
            "bootstrap_servers": f"{mq_cluster.domain_name}:{mq_cluster.port}",
            "request_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
            "consumer_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
        }
        if mq_cluster.username:
            param["sasl_plain_username"] = mq_cluster.username
            param["sasl_plain_password"] = mq_cluster.password
            param["security_protocol"] = "SASL_PLAINTEXT"
            param["sasl_mechanism"] = "PLAIN"
        consumer = KafkaConsumer(topic, **param)

    max_retries = getattr(settings, "KAFKA_TAIL_API_RETRY_TIMES", 1)
    retry_delay = getattr(settings, "KAFKA_TAIL_API_RETRY_INTERVAL_SECONDS", 2)
    for attempt in range(max_retries):
        consumer.poll(size)
        partitions_for_topic = consumer.partitions_for_topic(topic)
        if partitions_for_topic:
            break
        logger.warning(
            "Kafka Sample RPC: Failed to get partitions for topic->[%s],attempt->[%s],retrying.", topic, attempt
        )
        time.sleep(retry_delay)
    else:
        consumer.close()
        raise CustomException(message="获取 Kafka 分区失败")

    result: list[dict[str, Any]] = []
    for partition in partitions_for_topic:
        tp = TopicPartition(topic=topic, partition=partition)
        end_offset = consumer.end_offsets([tp])[tp]
        if not end_offset:
            continue

        if end_offset >= size:
            consumer.seek(tp, end_offset - size)
        else:
            consumer.seek_to_beginning()
        for msg in consumer:
            try:
                result.append(json.loads(msg.value.decode()))
            except Exception:
                pass
            if len(result) >= size:
                break
            if msg.offset == end_offset - 1:
                break
        if len(result) >= size:
            break

    consumer.close()
    return result


def _get_route_stream_to(route: Any) -> dict[str, Any]:
    if isinstance(route, dict):
        stream_to = route.get("stream_to")
    else:
        stream_to = getattr(route, "stream_to", None)
    return stream_to if isinstance(stream_to, dict) else {}


def _get_route_topic_name(route: Any) -> str | None:
    kafka = _get_route_stream_to(route).get("kafka")
    if not isinstance(kafka, dict):
        return None
    topic_name = kafka.get("topic_name")
    return str(topic_name) if topic_name not in (None, "") else None


def _iter_gse_routes(route_info_list: Any):
    for route_group in route_info_list or []:
        if isinstance(route_group, dict):
            routes = route_group.get("route") or []
        elif isinstance(route_group, list):
            routes = route_group
        else:
            continue
        yield from routes


def _query_gse_route_topic(datasource: models.DataSource) -> str | None:
    route_params = {
        "condition": {"channel_id": datasource.bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
        "operation": {"operator_name": getattr(settings, "COMMON_USERNAME", "system")},
    }

    route_info_list = api.gse.query_route(**route_params)
    for route in _iter_gse_routes(route_info_list):
        topic = _get_route_topic_name(route)
        if topic:
            return topic

    return None


def _consume_with_gse_config(mq_cluster: models.ClusterInfo, topic: str | None, size: int) -> list[dict[str, Any]]:
    if not topic:
        return []

    consumer_config = {
        "bootstrap_servers": f"{mq_cluster.domain_name}:{mq_cluster.port}",
        "request_timeout_ms": 1000,
        "consumer_timeout_ms": 1000,
    }

    consumer = KafkaConsumer(topic, **consumer_config)
    consumer.poll(size)
    partitions_for_topic = consumer.partitions_for_topic(topic)
    if not partitions_for_topic:
        consumer.close()
        raise CustomException(message="获取 Kafka 分区失败")
    result: list[dict[str, Any]] = []
    for partition in partitions_for_topic:
        tp = TopicPartition(topic=topic, partition=partition)
        end_offset = consumer.end_offsets([tp])[tp]
        if not end_offset:
            continue

        if end_offset >= size:
            consumer.seek(tp, end_offset - size)
        else:
            consumer.seek_to_beginning()
        for msg in consumer:
            try:
                result.append(json.loads(msg.value.decode()))
            except Exception:
                pass
            if len(result) >= size:
                break
            if msg.offset == end_offset - 1:
                break
        if len(result) >= size:
            break

    consumer.close()
    return result


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_KAFKA_SAMPLE,
    summary="Admin Kafka 采样数据",
    description="从 Kafka 拉取指定 DataSource 的最近 N 条数据样本，消费后立即断开。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_data_id": "必填，数据源 ID",
        "size": "可选，拉取条数，默认 10，最大 50",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010, "size": 10},
)
def kafka_sample(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    bk_data_id = params.get("bk_data_id")
    if bk_data_id in (None, ""):
        raise CustomException(message="bk_data_id 为必填项")
    try:
        bk_data_id = int(bk_data_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_data_id 必须是整数") from error

    size = params.get("size", 10)
    if size in (None, ""):
        size = 10
    try:
        size = int(size)
    except (TypeError, ValueError) as error:
        raise CustomException(message="size 必须是整数") from error
    if size < 1:
        raise CustomException(message="size 必须大于等于 1")
    size = min(size, 50)

    try:
        datasource = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
    except models.DataSource.DoesNotExist as error:
        raise CustomException(message=f"未找到 DataSource: bk_data_id={bk_data_id}") from error

    mq_cluster = datasource.mq_cluster
    topic = datasource.mq_config.topic
    try:
        route_topic = _query_gse_route_topic(datasource)
    except Exception as error:
        route_topic = None
        logger.warning(
            "Kafka Sample RPC: query GSE route failed, bk_data_id->[%s], error->[%s]",
            datasource.bk_data_id,
            error,
        )
    if route_topic:
        topic = route_topic

    result_table = None
    dsrt = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).first()
    if dsrt:
        try:
            result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=dsrt.table_id)
        except models.ResultTable.DoesNotExist:
            result_table = None

    if mq_cluster.is_auth:
        items = _consume_with_confluent_kafka(mq_cluster, topic, size)
    elif datasource.datalink_version == DATA_LINK_V4_VERSION_NAME:
        if result_table and datasource.etl_config == EtlConfigs.BK_STANDARD_V2_EVENT.value:
            data_id_config_name = compose_bkdata_data_id_name(datasource.data_name)
            try:
                data_id_config = DataIdConfig.objects.get(
                    bk_tenant_id=bk_tenant_id,
                    namespace=BKBASE_NAMESPACE_BK_LOG,
                    name=data_id_config_name,
                )
            except DataIdConfig.DoesNotExist:
                logger.warning(
                    "Kafka Sample RPC: DataIdConfig not found, bk_tenant_id->[%s], namespace->[%s], name->[%s]",
                    bk_tenant_id,
                    BKBASE_NAMESPACE_BK_LOG,
                    data_id_config_name,
                )
                items = []
            else:
                res = api.bkdata.tail_kafka_data(
                    bk_tenant_id=bk_tenant_id,
                    namespace=BKBASE_NAMESPACE_BK_LOG,
                    name=data_id_config.name,
                    limit=size,
                )
                items = [json.loads(data) for data in res]
        elif result_table and datasource.etl_config != "bk_flat_batch":
            from metadata.models.vm import AccessVMRecord

            try:
                vm_record = AccessVMRecord.objects.get(bk_tenant_id=bk_tenant_id, result_table_id=result_table.table_id)
            except AccessVMRecord.DoesNotExist:
                logger.warning("Kafka Sample RPC: AccessVMRecord not found for table_id->[%s]", result_table.table_id)
                items = []
            else:
                from metadata.models.data_link.utils import get_bkbase_raw_data_name_for_v3_datalink

                data_id_name = vm_record.bk_base_data_name
                namespace = params.get("namespace", "bkmonitor")
                if not data_id_name:
                    data_id_name = get_bkbase_raw_data_name_for_v3_datalink(
                        bk_tenant_id=bk_tenant_id, bkbase_data_id=vm_record.bk_base_data_id
                    )
                logger.info(
                    "Kafka Sample RPC: using bkdata kafka tail api, bk_data_id->[%s], namespace->[%s], name->[%s]",
                    bk_data_id,
                    namespace,
                    data_id_name,
                )
                res = api.bkdata.tail_kafka_data(
                    bk_tenant_id=bk_tenant_id, namespace=namespace, name=data_id_name, limit=size
                )
                items = [json.loads(data) for data in res]
        else:
            items = _consume_with_gse_config(mq_cluster, topic, size)
    else:
        items = _consume_with_kafka_python(mq_cluster, topic, datasource, size)

    result = items[:size]

    return build_response(
        operation="datasource.kafka_sample",
        func_name=FUNC_DATASOURCE_KAFKA_SAMPLE,
        bk_tenant_id=bk_tenant_id,
        data={
            "bk_data_id": bk_data_id,
            "topic": topic,
            "items": result,
            "count": len(result),
        },
    )
