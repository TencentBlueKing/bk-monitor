"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
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
from metadata.models.data_link.constants import DataLinkKind, DataLinkNameScene, DataLinkResourceStatus
from metadata.models.result_table import LogV4DataLinkOption
from metadata.task.datalink import apply_log_datalink

logger = logging.getLogger("metadata")

__all__ = ["SetLogClusteringConfigResource", "OperateLogClusteringResource", "GetLogClusteringStatusResource"]

CLUSTERING_ENABLE_ACTIONS = {"disable": False, "enable": True}
# metadata 内部动作：切换 Databus 是否引用聚类 Sink 后完整下发日志链路
SINK_REFERENCE_ACTIONS = {"detach": False, "attach": True}

RESULT_MODES = ["update_original", "append"]


class LogClusteringResourceRefSerializer(serializers.Serializer):
    kind = serializers.CharField(label="资源类型")
    name = serializers.CharField(label="资源名称")
    namespace = serializers.CharField(label="命名空间")
    tenant = serializers.CharField(label="租户ID", required=False)


def get_log_clustering_datalink(bk_tenant_id: str, table_id: str, check_storage: bool = True) -> models.DataLink:
    """按监控结果表定位日志 V4 链路，check_storage 时校验其有 ES 存储可作为 raw_sink"""
    bkbase_rt = models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id=table_id).first()
    if bkbase_rt is None:
        raise ValidationError(f"table_id({table_id}) has no bkbase datalink")
    datalink = models.DataLink.objects.filter(
        bk_tenant_id=bk_tenant_id, data_link_name=bkbase_rt.data_link_name
    ).first()
    if datalink is None or datalink.data_link_strategy != models.DataLink.BK_LOG:
        raise ValidationError(f"table_id({table_id}) is not a bk_log datalink")
    if not check_storage:
        return datalink

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
    return datalink


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


def get_log_clustering_raw_sink(datalink: models.DataLink) -> dict[str, str] | None:
    """聚类 Sink 的 raw_sink：本链路唯一的 ES 存储绑定，与完整生成配置时认领的绑定一致；无法唯一确定时返回 None"""
    bindings = list(
        models.ESStorageBindingConfig.objects.filter(
            bk_tenant_id=datalink.bk_tenant_id,
            namespace=datalink.namespace,
            data_link_name=datalink.data_link_name,
        )[:2]
    )
    return bindings[0].reference if len(bindings) == 1 else None


def is_databus_referencing_sink(databus_config: dict[str, Any] | None, sink: models.LogClusteringSinkConfig) -> bool:
    return any(
        ref.get("kind") == sink.kind and ref.get("name") == sink.name for ref in get_databus_sink_refs(databus_config)
    )


def apply_log_clustering_sink_only(
    datalink: models.DataLink, sink: models.LogClusteringSinkConfig, raw_sink: dict[str, str]
) -> None:
    from metadata.models.data_link.log_clustering import prepare_clustering_stores

    configs = prepare_clustering_stores(sink) + [sink.compose_config(raw_sink=raw_sink)]
    if sink.result.get("mode", "update_original") == "update_original":
        from metadata.models.data_link.utils import generate_result_table_field_list
        from metadata.models.result_table import LogV4DataLinkOption

        option = models.ResultTableOption.objects.get(
            table_id=sink.table_id,
            bk_tenant_id=sink.bk_tenant_id,
            name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        )
        keys = LogV4DataLinkOption(**json.loads(option.value)).es_storage_config.unique_field_list
        source = models.ResultTableConfig.objects.get(
            table_id=sink.table_id,
            bk_tenant_id=sink.bk_tenant_id,
            namespace=datalink.namespace,
            data_link_name=datalink.data_link_name,
        )
        configs.insert(
            0,
            source.compose_config(
                fields=generate_result_table_field_list(
                    sink.table_id,
                    sink.bk_tenant_id,
                    unique_field_list=keys,
                )
            ),
        )
    configs = datalink.merge_existing_component_configs(configs)
    try:
        datalink.apply_data_link_with_retry(configs)
    except RetryError as e:
        raise e.__cause__ if e.__cause__ else e


def format_log_clustering_identity(bk_tenant_id: str, component: DataLinkResourceConfigBase) -> dict[str, str]:
    return {"tenant": bk_tenant_id, "namespace": component.namespace, "name": component.name}


def get_databus_sink_refs(databus_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not databus_config:
        return []
    return databus_config.get("spec", {}).get("sinks", [])


class SetLogClusteringConfigResource(Resource):
    """
    保存日志聚类绑定并下发 LogClusteringSink

    Databus 尚未引用聚类 Sink 时（首次接入、关闭后重新保存）按日志链路完整下发；
    已引用时只下发聚类 Sink，过滤规则等绑定变更不重复下发 Databus；raw_sink 无法唯一确定时仍按日志链路完整下发。
    下发失败时调用方重试同一请求即可。
    过滤更新由 BKBase 内部完成交接，调用方无需先执行排空动作；本接口不代表 Runtime 已采用新配置。
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(label="监控结果表ID")
        # 由调用方按 BKBase LogClusteringSink 协议组装，metadata 原样保存和下发。
        binding = serializers.DictField(label="聚类绑定配置")
        kafka_resource = LogClusteringResourceRefSerializer(label="聚类 Kafka 资源引用")
        runtime_cluster = LogClusteringResourceRefSerializer(label="专用 Databus 集群")
        recovery_resource = LogClusteringResourceRefSerializer(label="结果关联存储资源")
        result_mode = serializers.ChoiceField(choices=RESULT_MODES, required=False)

        def validate(self, attrs):
            if not attrs["binding"].get("index_id"):
                raise ValidationError({"binding": "index_id is required"})
            references = [
                ("kafka_resource", attrs["kafka_resource"], "Kafka"),
                ("runtime_cluster", attrs["runtime_cluster"], "DatabusCluster"),
                ("recovery_resource", attrs["recovery_resource"], "ElasticSearch"),
            ]
            for field, ref, kind in references:
                if ref["kind"] != kind:
                    raise ValidationError({field: f"kind must be {kind}"})
                if ref.get("tenant", attrs["bk_tenant_id"]) != attrs["bk_tenant_id"]:
                    raise ValidationError({field: "cross-tenant resource reference is not allowed"})
                if settings.ENABLE_MULTI_TENANT_MODE:
                    ref.setdefault("tenant", attrs["bk_tenant_id"])
            return attrs

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]
        config_fields = {
            "binding": validated_request_data["binding"],
            "kafka_resource": validated_request_data["kafka_resource"],
            "runtime_cluster": validated_request_data["runtime_cluster"],
            "recovery_resource": validated_request_data["recovery_resource"],
        }

        datalink = get_log_clustering_datalink(bk_tenant_id, table_id)
        databus = get_log_clustering_databus(datalink)
        dsrt = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
        if dsrt is None:
            raise ValidationError(f"table_id({table_id}) related datasource not found")

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            lock_log_clustering_datalink(datalink)
            sink = get_log_clustering_sink(datalink, for_update=True)
            is_new_sink = sink is None
            if is_new_sink:
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
            requested_mode = validated_request_data.get("result_mode")
            if not sink.result or (requested_mode and requested_mode != sink.result.get("mode")):
                sink.result = {"mode": requested_mode or "update_original"}
            for field, value in config_fields.items():
                setattr(sink, field, value)
            sink.attached = True
            sink.save()

        # 本地绑定先提交；下发失败时调用方重试同一请求，按远端 Databus 实际引用情况重新下发
        remote_databus = datalink.get_existing_component_config(
            DataLinkKind.DATABUS.value, databus.name, databus.namespace
        )
        raw_sink = get_log_clustering_raw_sink(datalink)
        if (
            raw_sink
            and is_databus_referencing_sink(remote_databus, sink)
            and all(
                (remote_databus["spec"].get("preferCluster") or {}).get(key, bk_tenant_id)
                == sink.runtime_cluster.get(key, bk_tenant_id)
                for key in ("kind", "namespace", "name", "tenant")
            )
        ):
            apply_log_clustering_sink_only(datalink, sink, raw_sink)
            applied_scope = "sink_only"
        else:
            apply_log_datalink(bk_tenant_id=bk_tenant_id, table_id=table_id)
            applied_scope = "datalink"

        logger.info(
            "SetLogClusteringConfigResource: table_id->[%s] sink->[%s] applied_scope->[%s]",
            table_id,
            sink.name,
            applied_scope,
        )
        return {
            "attached": sink.attached,
            "applied_scope": applied_scope,
            "sink": format_log_clustering_identity(bk_tenant_id, sink),
            "databus": format_log_clustering_identity(bk_tenant_id, databus),
        }


class OperateLogClusteringResource(Resource):
    """
    执行日志聚类控制动作

    disable/enable 通过原资源 apply 修改 spec.clustering.enabled；
    detach/attach 是 metadata 内部动作：切换 Databus 是否引用聚类 Sink 后完整下发日志链路，
    detach 即恢复原存储绑定，调用方应先确认 disable 收尾完成。动作只表示请求已提交，
    实际收尾、解绑结果需通过状态接口回读。模型更新、Worker 维护不调用这些业务动作。
    动作失败时调用方重试同一动作即可。
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(label="监控结果表ID")
        action = serializers.ChoiceField(
            label="动作", choices=list(CLUSTERING_ENABLE_ACTIONS) + list(SINK_REFERENCE_ACTIONS)
        )

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]
        action = validated_request_data["action"]

        datalink = get_log_clustering_datalink(bk_tenant_id, table_id)

        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            lock_log_clustering_datalink(datalink)
            sink = get_log_clustering_sink(datalink, for_update=True)
            if sink is None:
                raise ValidationError(f"table_id({table_id}) has no log clustering config")
            if action in SINK_REFERENCE_ACTIONS:
                sink.attached = SINK_REFERENCE_ACTIONS[action]
                sink.save()

        if action in SINK_REFERENCE_ACTIONS:
            apply_log_datalink(bk_tenant_id=bk_tenant_id, table_id=table_id)
        else:
            remote_sink = datalink.get_existing_component_config(sink.kind, sink.name, sink.namespace)
            if remote_sink is None:
                raise ValidationError(f"log clustering sink({sink.name}) does not exist in BKBase")
            # 保留完整远端配置，只更新开关；不把 status 等运行态写回，也不重下发 Databus。
            config = {key: copy.deepcopy(remote_sink[key]) for key in ("kind", "metadata", "spec")}
            config["spec"]["clustering"]["enabled"] = CLUSTERING_ENABLE_ACTIONS[action]
            try:
                datalink.apply_data_link_with_retry([config])
            except RetryError as e:
                raise e.__cause__ if e.__cause__ else e

        logger.info("OperateLogClusteringResource: table_id->[%s] sink->[%s] action->[%s]", table_id, sink.name, action)
        return {
            "action": action,
            "attached": sink.attached,
        }


def get_log_clustering_query_targets(sink: models.LogClusteringSinkConfig) -> dict:
    """返回聚类结果和 Pattern 在 metadata 登记的实际存储，调用方据此注册查询路由。"""

    def resolve(table_id):
        storage = models.ESStorage.objects.get(bk_tenant_id=sink.bk_tenant_id, table_id=table_id)
        cluster = models.ClusterInfo.objects.get(bk_tenant_id=sink.bk_tenant_id, cluster_id=storage.storage_cluster_id)
        return {
            "table_id": table_id,
            "storage_type": cluster.cluster_type,
            "source_type": storage.source_type,
            "cluster_id": cluster.cluster_id,
            "query_index": storage.index_name,
            "need_add_time": storage.need_create_index,
        }

    def store_table_id(store):
        ref = store["result_table"]
        return models.ResultTableConfig.objects.get(
            bk_tenant_id=sink.bk_tenant_id, namespace=ref["namespace"], name=ref["name"]
        ).table_id

    if not sink.pattern_store:
        raise ValidationError("pattern store is not prepared")
    result = sink.result or {}
    clustered_table_id = store_table_id(result) if result.get("mode") == "append" else sink.table_id
    return {"clustered": resolve(clustered_table_id), "pattern": resolve(store_table_id(sink.pattern_store))}


class GetLogClusteringStatusResource(Resource):
    """
    查询日志聚类链路状态

    按 BKBase 回读的聚类 Sink 与 Databus 汇总链路是否就绪、是否已恢复原存储绑定；
    query_targets 返回聚类结果和 Pattern 在 metadata 登记的存储，由调用方注册查询路由。
    远端查询失败不影响其他字段返回，错误记录在 errors 中。
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(label="监控结果表ID")
        include_query_targets = serializers.BooleanField(default=False)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]

        datalink = get_log_clustering_datalink(bk_tenant_id, table_id, check_storage=False)
        sink = get_log_clustering_sink(datalink)
        if sink is None:
            return {"configured": False}
        databus = get_log_clustering_databus(datalink)

        errors: list[dict[str, Any]] = []

        def fetch(source: str, func):
            try:
                return func()
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "GetLogClusteringStatusResource: table_id->[%s] fetch %s failed, error->[%s]", table_id, source, e
                )
                errors.append({"source": source, "message": str(e)})
                return None

        sink_resource = (
            fetch("sink_resource", lambda: datalink.get_existing_component_config(sink.kind, sink.name, sink.namespace))
            or {}
        )
        databus_resource = (
            fetch(
                "databus_resource",
                lambda: datalink.get_existing_component_config(databus.kind, databus.name, databus.namespace),
            )
            or {}
        )
        sink_phase = (sink_resource.get("status") or {}).get("phase")
        databus_ok = (databus_resource.get("status") or {}).get("phase") == DataLinkResourceStatus.OK.value
        sink_referenced = is_databus_referencing_sink(databus_resource, sink)
        raw_sink = get_log_clustering_raw_sink(datalink)
        raw_sink_referenced = bool(raw_sink) and any(
            ref.get("kind") == raw_sink["kind"] and ref.get("name") == raw_sink["name"]
            for ref in get_databus_sink_refs(databus_resource)
        )

        result = {
            "configured": True,
            "attached": sink.attached,
            "sink": format_log_clustering_identity(bk_tenant_id, sink),
            "databus": format_log_clustering_identity(bk_tenant_id, databus),
            "enabled": ((sink_resource.get("spec") or {}).get("clustering") or {}).get("enabled"),
            "sink_phase": sink_phase,
            # Databus 已引用聚类 Sink，且两者均为 Ok
            "ready": sink_referenced and databus_ok and sink_phase == DataLinkResourceStatus.OK.value,
            # Databus 已恢复引用原存储绑定，不再引用聚类 Sink
            "detached": raw_sink_referenced and not sink_referenced and databus_ok,
            "clustering_status": parse_clustering_status(sink_resource),
            "errors": errors,
        }
        if validated_request_data["include_query_targets"]:
            result["query_targets"] = fetch("query_targets", lambda: get_log_clustering_query_targets(sink))
        return result


def parse_clustering_status(sink_resource: dict[str, Any]) -> dict[str, Any] | None:
    """旧版 BKBase 在 status.message 中返回 JSON 进度，仅停用收尾使用；普通文本返回 None。"""
    message = (sink_resource.get("status") or {}).get("message")
    try:
        progress = json.loads(message) if message else None
    except (ValueError, TypeError):
        return None
    return progress if isinstance(progress, dict) else None
