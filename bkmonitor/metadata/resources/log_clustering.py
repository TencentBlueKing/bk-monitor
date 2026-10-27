"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging
from contextlib import contextmanager
from typing import Any

import pydantic
from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from tenacity import RetryError

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource
from metadata import models
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import DataLinkResourceConfigBase
from metadata.models.data_link import utils as data_link_utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkNameScene
from metadata.models.result_table import LogV4DataLinkOption
from metadata.task.datalink import apply_log_datalink
from metadata.tools.redis_lock import DistributedLock
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")

__all__ = ["SetLogClusteringConfigResource"]

LOG_FILTER_METHODS = ["eq", "neq", "include", "exclude"]
DISTANCE_THRESHOLDS = ["0.1", "0.3", "0.5", "0.7", "0.9"]
DEFAULT_MAX_MESSAGE_BYTES = 1024 * 1024
MAX_MESSAGE_BYTES_LIMIT = 16 * 1024 * 1024
# 需覆盖一次完整日志链路下发（含 BKBase 接口重试）的耗时
CHANGE_LOCK_TIMEOUT_SECONDS = 15 * 60


class LogClusteringResourceRefSerializer(serializers.Serializer):
    kind = serializers.CharField(label="资源类型")
    name = serializers.CharField(label="资源名称")
    namespace = serializers.CharField(label="命名空间")
    tenant = serializers.CharField(label="租户ID", required=False)


class LogClusteringKafkaSerializer(serializers.Serializer):
    cluster_ref = serializers.CharField(label="BKFara Kafka 集群别名")
    input_topic = serializers.CharField(label="候选 Topic")
    output_topic = serializers.CharField(label="结果 Topic")
    consumer_group = serializers.CharField(label="Quix Worker 消费组")
    result_group = serializers.CharField(label="Databus 结果消费组")
    partitions = serializers.IntegerField(label="分区数", min_value=1)
    retention_ms = serializers.IntegerField(label="消息保留时间(ms)", min_value=1)
    recovery_window_ms = serializers.IntegerField(label="恢复窗口(ms)", min_value=1)
    source_namespace = serializers.CharField(label="来源名称")
    mapping_revision = serializers.CharField(label="映射版本")

    def validate(self, attrs):
        if attrs["recovery_window_ms"] > attrs["retention_ms"]:
            raise ValidationError({"recovery_window_ms": "recovery_window_ms must not exceed retention_ms"})
        return attrs


class LogClusteringFilterRuleSerializer(serializers.Serializer):
    key = serializers.CharField(label="字段")
    method = serializers.ChoiceField(label="匹配方式", choices=LOG_FILTER_METHODS)
    # 首尾空白属于匹配内容，不能被序列化去除
    value = serializers.ListField(
        label="匹配值", child=serializers.CharField(allow_blank=True, trim_whitespace=False), allow_empty=False
    )
    condition = serializers.ChoiceField(label="逻辑关系", choices=["", "and", "or"], allow_blank=True)


class LogClusteringInputMappingSerializer(serializers.Serializer):
    log = serializers.CharField(label="正文字段")
    timestamp = serializers.CharField(label="毫秒时间字段")


class LogClusteringBindingSerializer(serializers.Serializer):
    task_id = serializers.CharField(label="BKFara 任务ID")
    index_id = serializers.CharField(label="日志平台索引ID")
    generation = serializers.IntegerField(label="任务代际", min_value=0)
    config_revision = serializers.IntegerField(label="BKFara 输入配置版本", min_value=0)
    kafka = LogClusteringKafkaSerializer(label="Kafka 绑定")
    log_filter = LogClusteringFilterRuleSerializer(label="聚类过滤规则", many=True, default=list)
    input_mapping = LogClusteringInputMappingSerializer(label="输入字段映射")
    distance_threshold = serializers.ChoiceField(label="距离档位", choices=DISTANCE_THRESHOLDS)
    pattern_index = serializers.CharField(label="Pattern 索引")
    state_index = serializers.CharField(label="恢复状态索引")
    max_message_bytes = serializers.IntegerField(
        label="候选消息上限(字节)", min_value=1, max_value=MAX_MESSAGE_BYTES_LIMIT, default=DEFAULT_MAX_MESSAGE_BYTES
    )

    def validate_log_filter(self, value):
        for index, rule in enumerate(value):
            if (index == 0) != (rule["condition"] == ""):
                raise ValidationError("the first rule condition must be empty, the following must be and/or")
        return value


def get_log_clustering_datalink(bk_tenant_id: str, table_id: str) -> models.DataLink:
    """按监控结果表定位日志 V4 链路，并校验其满足聚类首版的单 ES 存储条件"""
    bkbase_rt = models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id=table_id).first()
    if bkbase_rt is None:
        raise ValidationError(f"table_id({table_id}) has no bkbase datalink")
    datalink = models.DataLink.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=bkbase_rt.data_link_name
    ).first()
    if datalink is None or datalink.data_link_strategy != models.DataLink.BK_LOG:
        raise ValidationError(f"table_id({table_id}) is not a bk_log datalink")

    # 与 compose_log_configs 生成存储绑定的条件保持一致：存储记录存在且 V4 Option 声明了对应存储配置
    option = models.ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table_id, name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    ).first()
    if option is None:
        raise ValidationError(f"table_id({table_id}) has no log v4 datalink option")
    try:
        datalink_option = LogV4DataLinkOption(**json.loads(option.value))
    except (pydantic.ValidationError, TypeError, ValueError) as e:
        raise ValidationError(f"table_id({table_id}) log v4 datalink option is invalid: {e}")
    if not (
        datalink_option.es_storage_config
        and models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).exists()
    ):
        raise ValidationError(f"table_id({table_id}) has no elasticsearch storage")
    if (
        datalink_option.doris_storage_config
        and models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).exists()
    ):
        raise ValidationError(f"table_id({table_id}) with doris storage is not supported")
    return datalink


def get_log_clustering_pattern_cluster(bk_tenant_id: str, pattern_resource: dict[str, Any]) -> models.ClusterInfo:
    """patternResource 对应的 metadata ES 集群；metadata 注册到 BKBase 的 ES 资源名即集群名"""
    pattern_cluster = models.ClusterInfo.objects.filter(
        bk_tenant_id=pattern_resource.get("tenant") or bk_tenant_id,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name=pattern_resource.get("name"),
    ).first()
    if pattern_cluster is None:
        raise ValidationError(f"pattern_resource({pattern_resource}) is not a metadata elasticsearch cluster")
    return pattern_cluster


def get_log_clustering_databus(datalink: models.DataLink) -> models.DataBusConfig:
    databus_list = list(
        models.DataBusConfig.objects.filter(
            bk_tenant_id=datalink.bk_tenant_id,
            namespace=datalink.namespace,
            data_link_name=datalink.data_link_name,
        )
    )
    if len(databus_list) != 1:
        raise ValidationError(
            f"data_link_name({datalink.data_link_name}) requires exactly one databus, got {len(databus_list)}"
        )
    return databus_list[0]


def get_log_clustering_sink(
    datalink: models.DataLink, for_update: bool = False
) -> models.LogClusteringSinkConfig | None:
    queryset = models.LogClusteringSinkConfig.objects.filter(
        bk_tenant_id=datalink.bk_tenant_id,
        namespace=datalink.namespace,
        data_link_name=datalink.data_link_name,
    )
    if for_update:
        queryset = queryset.select_for_update()
    return queryset.first()


def lock_log_clustering_datalink(datalink: models.DataLink) -> None:
    """同一链路上的聚类配置落库串行执行，避免并发首次接入分配出多个聚类 Sink"""
    models.DataLink.objects.select_for_update().get(pk=datalink.pk)


@contextmanager
def serialize_log_clustering_change(datalink: models.DataLink):
    """
    同一链路上的聚类配置变更从落库到远端下发全程互斥，避免较慢的旧请求在新请求之后下发而覆盖远端配置
    远端下发不能放进数据库事务：日志链路下发要求本地组件身份先提交，失败回滚会丢失已分配的资源名
    """
    lock = DistributedLock(
        redis_client=RedisTools.metadata_redis_client,
        lock_name=f"metadata:log_clustering:{datalink.bk_tenant_id}:{datalink.data_link_name}",
        timeout=CHANGE_LOCK_TIMEOUT_SECONDS,
    )
    if not lock.acquire():
        raise ValidationError(
            f"data_link_name({datalink.data_link_name}) has another log clustering change in progress, retry later"
        )
    try:
        yield
    finally:
        lock.release()


def check_log_clustering_operation(
    sink: models.LogClusteringSinkConfig | None, operation_id: str, request_digest: str, expected_revision: int
) -> bool:
    """校验操作幂等与并发版本，返回本次请求是否为已处理操作的重放"""
    if sink is not None and sink.last_operation_id == operation_id:
        if sink.last_request_digest != request_digest:
            raise ValidationError(f"operation_id({operation_id}) has been used by a different request")
        return True

    current_revision = sink.revision if sink is not None else 0
    if expected_revision != current_revision:
        raise ValidationError(
            f"expected_revision({expected_revision}) is stale, current revision is {current_revision}"
        )
    return False


def compute_request_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def is_databus_referencing_sink(databus_config: dict[str, Any] | None, sink: models.LogClusteringSinkConfig) -> bool:
    if not databus_config:
        return False
    return any(
        ref.get("kind") == sink.kind and ref.get("name") == sink.name
        for ref in databus_config.get("spec", {}).get("sinks", [])
    )


def apply_log_clustering_sink_only(datalink: models.DataLink, sink: models.LogClusteringSinkConfig) -> None:
    configs = datalink.merge_existing_component_configs([sink.compose_config()])
    try:
        datalink.apply_data_link_with_retry(configs)
    except RetryError as e:
        raise e.__cause__ if e.__cause__ else e


def format_log_clustering_identity(bk_tenant_id: str, component: DataLinkResourceConfigBase) -> dict[str, str]:
    return {"tenant": bk_tenant_id, "namespace": component.namespace, "name": component.name}


class SetLogClusteringConfigResource(Resource):
    """
    保存日志聚类绑定并下发 LogClusteringSink

    Databus 尚未引用聚类 Sink 时（首次接入、关闭后重新保存）按日志链路完整下发；
    已引用时只下发聚类 Sink，过滤规则等绑定变更不重复下发 Databus。
    调用方需要先完成 BKBase 侧的 drain/finish，本接口不等待排空，也不代表 Runtime 已采用新配置。
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(label="监控结果表ID")
        operation_id = serializers.CharField(label="操作ID", max_length=64)
        expected_revision = serializers.IntegerField(label="期望的当前配置版本", min_value=0)
        binding = LogClusteringBindingSerializer(label="聚类绑定配置")
        kafka_resource = LogClusteringResourceRefSerializer(label="聚类 Kafka 资源引用")
        pattern_resource = LogClusteringResourceRefSerializer(label="Pattern 存储资源引用")

        def validate(self, attrs):
            if attrs["kafka_resource"]["kind"] != "Kafka":
                raise ValidationError({"kafka_resource": "kind must be Kafka"})
            if attrs["pattern_resource"]["kind"] != DataLinkKind.ELASTICSEARCH.value:
                raise ValidationError({"pattern_resource": f"kind must be {DataLinkKind.ELASTICSEARCH.value}"})
            if settings.ENABLE_MULTI_TENANT_MODE:
                for field in ("kafka_resource", "pattern_resource"):
                    attrs[field].setdefault("tenant", attrs["bk_tenant_id"])
            return attrs

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]
        operation_id = validated_request_data["operation_id"]
        config_fields = {
            "binding": validated_request_data["binding"],
            "kafka_resource": validated_request_data["kafka_resource"],
            "pattern_resource": validated_request_data["pattern_resource"],
        }
        request_digest = compute_request_digest({"table_id": table_id, **config_fields})

        datalink = get_log_clustering_datalink(bk_tenant_id, table_id)
        databus = get_log_clustering_databus(datalink)
        get_log_clustering_pattern_cluster(bk_tenant_id, config_fields["pattern_resource"])
        dsrt = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
        if dsrt is None:
            raise ValidationError(f"table_id({table_id}) related datasource not found")

        with serialize_log_clustering_change(datalink):
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                lock_log_clustering_datalink(datalink)
                sink = get_log_clustering_sink(datalink, for_update=True)
                is_replay = check_log_clustering_operation(
                    sink, operation_id, request_digest, validated_request_data["expected_revision"]
                )
                if not is_replay:
                    if sink is None:
                        sink = data_link_utils.create_resource_with_random_name(
                            models.LogClusteringSinkConfig,
                            DataLinkNameScene.LOG_CLUSTERING_SINK,
                            dsrt.bk_data_id,
                            bk_tenant_id=bk_tenant_id,
                            namespace=datalink.namespace,
                            data_link_name=datalink.data_link_name,
                            bk_biz_id=databus.bk_biz_id,
                            table_id=table_id,
                        )
                    for field, value in config_fields.items():
                        setattr(sink, field, value)
                    sink.attached = True
                    sink.revision += 1
                    sink.last_operation_id = operation_id
                    sink.last_request_digest = request_digest
                    sink.save()
            revision = sink.revision

            # 本地绑定先提交；下发失败时调用方用同一 operation_id 重试，按远端 Databus 实际引用情况重新下发
            remote_databus = datalink.get_existing_component_config(
                DataLinkKind.DATABUS.value, databus.name, databus.namespace
            )
            if is_databus_referencing_sink(remote_databus, sink):
                apply_log_clustering_sink_only(datalink, sink)
                applied_scope = "sink_only"
            else:
                apply_log_datalink(bk_tenant_id=bk_tenant_id, table_id=table_id)
                applied_scope = "datalink"
            # 完整下发时 compose 会回写 rawSink
            sink.refresh_from_db(fields=["raw_sink"])

        logger.info(
            "SetLogClusteringConfigResource: table_id->[%s] sink->[%s] revision->[%s] applied_scope->[%s] "
            "operation_id->[%s] replay->[%s]",
            table_id,
            sink.name,
            revision,
            applied_scope,
            operation_id,
            is_replay,
        )
        return {
            "revision": revision,
            "attached": sink.attached,
            "applied_scope": applied_scope,
            "sink": format_log_clustering_identity(bk_tenant_id, sink),
            "databus": format_log_clustering_identity(bk_tenant_id, databus),
            "raw_sink": sink.raw_sink,
        }
