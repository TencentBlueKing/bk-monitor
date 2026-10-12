"""日志采集 Fast Update MCP 资源。"""

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource, api
from kernel_api.resource.log_collection_common import StrictMCPSerializer, normalize_task_ids

COMMON_UPDATE_FIELDS = {
    "collector_config_name",
    "description",
    "parent_index_set_ids",
}
HOST_UPDATE_FIELDS = COMMON_UPDATE_FIELDS | {
    "target_object_type",
    "target_node_type",
    "target_nodes",
    "params",
    "data_encoding",
}
HOST_DEPLOYMENT_FIELDS = {
    "target_object_type",
    "target_node_type",
    "target_nodes",
    "params",
    "data_encoding",
}
CONTAINER_UPDATE_FIELDS = COMMON_UPDATE_FIELDS | {
    "collector_scenario_id",
    "configs",
    "add_pod_label",
    "add_pod_annotation",
    "extra_labels",
    "yaml_config_enabled",
    "yaml_config",
}
CONTAINER_DEPLOYMENT_FIELDS = {
    "collector_scenario_id",
    "configs",
    "add_pod_label",
    "add_pod_annotation",
    "extra_labels",
    "yaml_config_enabled",
}
REQUEST_SCOPE_FIELDS = {"bk_biz_id", "collector_config_id"}
TARGET_NODE_FIELDS = {
    "id",
    "bk_inst_id",
    "bk_obj_id",
    "bk_host_id",
    "ip",
    "bk_cloud_id",
    "bk_supplier_id",
    "bk_biz_id",
}
PLUGIN_PARAM_FIELDS = {
    "paths",
    "exclude_files",
    "conditions",
    "multiline_pattern",
    "multiline_max_lines",
    "multiline_timeout",
    "tail_files",
    "ignore_older",
    "max_bytes",
    "scan_frequency",
    "close_inactive",
    "harvester_limit",
    "clean_inactive",
    "winlog_name",
    "winlog_level",
    "winlog_event_id",
    "winlog_source",
    "winlog_content",
    "winlog_match_op",
    "redis_hosts",
    "redis_password",
    "redis_password_file",
    "extra_labels",
    "extra_template_labels",
    "syslog_protocol",
    "syslog_port",
    "syslog_monitor_host",
    "syslog_conditions",
    "kafka_hosts",
    "kafka_username",
    "kafka_password",
    "kafka_ssl_params",
    "kafka_topics",
    "kafka_group_id",
    "kafka_initial_offset",
}
CONTAINER_CONFIG_FIELDS = {
    "namespaces",
    "namespaces_exclude",
    "container",
    "label_selector",
    "annotation_selector",
    "paths",
    "data_encoding",
    "params",
    "collector_type",
}
CONTAINER_FIELDS = {"workload_type", "workload_name", "container_name", "container_name_exclude"}
LABEL_FIELDS = {"key", "operator", "value"}
EXTRA_TEMPLATE_LABEL_FIELDS = {"key", "value"}
LABEL_SELECTOR_FIELDS = {"match_labels", "match_expressions"}
ANNOTATION_SELECTOR_FIELDS = {"match_annotations"}
CONDITION_FIELDS = {"type", "match_type", "match_content", "separator", "separator_filters"}
SEPARATOR_FILTER_FIELDS = {"fieldindex", "word", "op", "logic_op"}
SYSLOG_CONDITION_FIELDS = {"syslog_field", "syslog_content", "syslog_op", "syslog_logic_op"}


def reject_unknown_fields(value: Any, allowed_fields: set[str], path: str) -> None:
    if not isinstance(value, Mapping):
        return
    unknown_fields = set(value) - allowed_fields
    if unknown_fields:
        raise serializers.ValidationError(
            {f"{path}.{field}": ["This field is not supported by Fast Update MCP."] for field in sorted(unknown_fields)}
        )


def validate_mapping_list(values: Any, allowed_fields: set[str], path: str) -> None:
    if not isinstance(values, list):
        return
    for index, value in enumerate(values):
        reject_unknown_fields(value, allowed_fields, f"{path}[{index}]")


def validate_plugin_params(params: Any, path: str) -> None:
    reject_unknown_fields(params, PLUGIN_PARAM_FIELDS, path)
    if not isinstance(params, Mapping):
        return
    conditions = params.get("conditions")
    reject_unknown_fields(conditions, CONDITION_FIELDS, f"{path}.conditions")
    if isinstance(conditions, Mapping):
        validate_mapping_list(
            conditions.get("separator_filters"),
            SEPARATOR_FILTER_FIELDS,
            f"{path}.conditions.separator_filters",
        )
    validate_mapping_list(params.get("extra_labels"), LABEL_FIELDS, f"{path}.extra_labels")
    validate_mapping_list(
        params.get("extra_template_labels"),
        EXTRA_TEMPLATE_LABEL_FIELDS,
        f"{path}.extra_template_labels",
    )
    validate_mapping_list(
        params.get("syslog_conditions"),
        SYSLOG_CONDITION_FIELDS,
        f"{path}.syslog_conditions",
    )


def validate_nested_update_fields(attrs: Mapping) -> None:
    validate_mapping_list(attrs.get("target_nodes"), TARGET_NODE_FIELDS, "target_nodes")
    validate_plugin_params(attrs.get("params"), "params")
    validate_mapping_list(attrs.get("extra_labels"), LABEL_FIELDS, "extra_labels")
    for index, config in enumerate(attrs.get("configs") or []):
        config_path = f"configs[{index}]"
        reject_unknown_fields(config, CONTAINER_CONFIG_FIELDS, config_path)
        if not isinstance(config, Mapping):
            continue
        reject_unknown_fields(config.get("container"), CONTAINER_FIELDS, f"{config_path}.container")
        label_selector = config.get("label_selector")
        reject_unknown_fields(label_selector, LABEL_SELECTOR_FIELDS, f"{config_path}.label_selector")
        if isinstance(label_selector, Mapping):
            validate_mapping_list(
                label_selector.get("match_labels"),
                LABEL_FIELDS,
                f"{config_path}.label_selector.match_labels",
            )
            validate_mapping_list(
                label_selector.get("match_expressions"),
                LABEL_FIELDS,
                f"{config_path}.label_selector.match_expressions",
            )
        annotation_selector = config.get("annotation_selector")
        reject_unknown_fields(
            annotation_selector,
            ANNOTATION_SELECTOR_FIELDS,
            f"{config_path}.annotation_selector",
        )
        if isinstance(annotation_selector, Mapping):
            validate_mapping_list(
                annotation_selector.get("match_annotations"),
                LABEL_FIELDS,
                f"{config_path}.annotation_selector.match_annotations",
            )
        validate_plugin_params(config.get("params"), f"{config_path}.params")


class FastUpdateLogCollectorResource(Resource):
    """只更新采集配置，不修改清洗、字段和存储配置。"""

    class RequestSerializer(StrictMCPSerializer):
        unsupported_api_name = "Fast Update MCP"
        unsupported_field_message = "This field is not supported by {api_name}."

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, min_value=1, label="采集项ID")
        collector_config_name = serializers.CharField(required=False, max_length=50, label="采集项名称")
        description = serializers.CharField(
            required=False, allow_blank=True, allow_null=True, max_length=100, label="描述"
        )
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        target_object_type = serializers.CharField(required=False, label="目标类型")
        target_node_type = serializers.CharField(required=False, label="节点类型")
        target_nodes = serializers.ListField(child=serializers.DictField(), required=False, label="目标节点")
        params = serializers.DictField(required=False, label="主机采集参数")
        data_encoding = serializers.CharField(required=False, label="日志字符集")
        collector_scenario_id = serializers.CharField(required=False, label="容器日志类型")
        configs = serializers.ListField(
            child=serializers.DictField(), required=False, allow_empty=False, label="完整容器日志配置"
        )
        add_pod_label = serializers.BooleanField(required=False, label="是否添加 Pod 标签")
        add_pod_annotation = serializers.BooleanField(required=False, label="是否添加 Pod 注解")
        extra_labels = serializers.ListField(child=serializers.DictField(), required=False, label="额外标签")
        yaml_config_enabled = serializers.BooleanField(required=False, label="是否使用 YAML 配置")
        yaml_config = serializers.CharField(required=False, allow_blank=True, label="YAML 配置内容")

        def validate(self, attrs):
            attrs = super().validate(attrs)
            if not set(attrs) - REQUEST_SCOPE_FIELDS:
                raise serializers.ValidationError("At least one collection field must be provided.")
            validate_nested_update_fields(attrs)
            return attrs

    def perform_request(self, validated_request_data):
        request_data = validated_request_data.copy()
        bk_biz_id = request_data.pop("bk_biz_id")
        collector_config_id = request_data.pop("collector_config_id")

        collector = api.log_search.log_collector_update_context(
            collector_config_id=collector_config_id,
            enforce_permission=True,
        )
        if str(collector.get("bk_biz_id")) != str(bk_biz_id):
            raise PermissionDenied("Collector config does not belong to the requested business.")

        environment = str(collector.get("environment") or "").lower()
        if environment == "container":
            allowed_fields = CONTAINER_UPDATE_FIELDS
            deployment_requested = bool(CONTAINER_DEPLOYMENT_FIELDS.intersection(request_data))
            if "yaml_config" in request_data:
                yaml_config_enabled = request_data.get(
                    "yaml_config_enabled", collector.get("yaml_config_enabled", False)
                )
                deployment_requested = deployment_requested or yaml_config_enabled
        else:
            if environment not in {"linux", "windows"}:
                environment = "windows" if collector.get("collector_scenario_id") == "wineventlog" else "linux"
            allowed_fields = HOST_UPDATE_FIELDS
            deployment_requested = bool(HOST_DEPLOYMENT_FIELDS.intersection(request_data))

        invalid_fields = set(request_data) - allowed_fields
        if invalid_fields:
            raise serializers.ValidationError(
                {
                    field: [f"This field cannot be updated for a {environment} collector."]
                    for field in sorted(invalid_fields)
                }
            )
        if environment in {"linux", "windows"} and len(request_data.get("description") or "") > 64:
            raise serializers.ValidationError(
                {"description": "Host collector description cannot exceed 64 characters."}
            )
        if environment == "container" and "description" in request_data and request_data["description"] is None:
            raise serializers.ValidationError({"description": "Container collector description cannot be null."})

        update_result = (
            api.log_search.fast_update_log_collector(
                collector_config_id=collector_config_id,
                update_clean_config=False,
                enforce_permission=True,
                **request_data,
            )
            or {}
        )

        if deployment_requested and ("subscription_id" not in update_result or "task_id_list" not in update_result):
            latest_collector = api.log_search.data_bus_collectors(collector_config_id=collector_config_id)
        else:
            latest_collector = {}

        subscription_id = update_result.get(
            "subscription_id",
            latest_collector.get("subscription_id", collector.get("subscription_id")),
        )
        task_id_list = (
            update_result.get("task_id_list", latest_collector.get("task_id_list")) if deployment_requested else []
        )
        return {
            "collector_config_id": collector_config_id,
            "environment": environment,
            "subscription_id": subscription_id,
            "task_ids": normalize_task_ids(task_id_list),
            "updated_fields": sorted(request_data),
            "clean_config_updated": False,
        }
