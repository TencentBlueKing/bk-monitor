"""日志采集 Fast Create MCP 资源。"""

from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource, api

ENVIRONMENT_LINUX = "linux"
ENVIRONMENT_WINDOWS = "windows"
ENVIRONMENT_CONTAINER = "container"

COMMON_CREATE_FIELDS = {
    "bk_biz_id",
    "environment",
    "collector_config_name",
    "collector_config_name_en",
    "collector_scenario_id",
    "category_id",
    "description",
    "parent_index_set_ids",
    "confirm",
}
HOST_CREATE_FIELDS = {
    "target_object_type",
    "target_node_type",
    "target_nodes",
    "params",
    "data_encoding",
}
CONTAINER_CREATE_FIELDS = {
    "bcs_cluster_id",
    "configs",
    "add_pod_label",
    "add_pod_annotation",
    "extra_labels",
    "yaml_config_enabled",
    "yaml_config",
}
HOST_REQUIRED_FIELDS = {
    "target_object_type",
    "target_node_type",
    "target_nodes",
    "params",
}
CONTAINER_REQUIRED_FIELDS = {
    "bcs_cluster_id",
    "configs",
}
SCENARIOS_BY_ENVIRONMENT = {
    ENVIRONMENT_LINUX: {"row", "section"},
    ENVIRONMENT_WINDOWS: {"wineventlog"},
    ENVIRONMENT_CONTAINER: {"row", "section"},
}

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
    "extra_labels",
    "extra_template_labels",
}
WINDOWS_PLUGIN_PARAM_FIELDS = {
    "winlog_name",
    "winlog_level",
    "winlog_event_id",
    "winlog_source",
    "winlog_content",
    "winlog_match_op",
    "extra_labels",
    "extra_template_labels",
}
WINDOWS_ONLY_PLUGIN_PARAM_FIELDS = {
    "winlog_name",
    "winlog_level",
    "winlog_event_id",
    "winlog_source",
    "winlog_content",
    "winlog_match_op",
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


def reject_unknown_fields(value: Any, allowed_fields: set[str], path: str) -> None:
    if not isinstance(value, Mapping):
        return
    unknown_fields = set(value) - allowed_fields
    if unknown_fields:
        raise serializers.ValidationError(
            {f"{path}.{field}": ["This field is not supported by Fast Create MCP."] for field in sorted(unknown_fields)}
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


def validate_nested_create_fields(attrs: Mapping) -> None:
    validate_mapping_list(attrs.get("target_nodes"), TARGET_NODE_FIELDS, "target_nodes")
    validate_plugin_params(attrs.get("params"), "params")
    validate_mapping_list(attrs.get("extra_labels"), LABEL_FIELDS, "extra_labels")
    for index, config in enumerate(attrs.get("configs") or []):
        config_path = f"configs[{index}]"
        reject_unknown_fields(config, CONTAINER_CONFIG_FIELDS, config_path)
        if not isinstance(config, Mapping):
            continue
        missing_fields = {"params", "collector_type"} - set(config)
        if missing_fields:
            raise serializers.ValidationError(
                {f"{config_path}.{field}": ["This field is required."] for field in sorted(missing_fields)}
            )
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


def normalize_task_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list | tuple | set):
        values = value
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


class StrictFastCreateSerializer(serializers.Serializer):
    """拒绝未声明字段，避免 MCP 覆盖存储、数据链路或索引集默认选择。"""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data.keys()) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["This field is not supported by Fast Create MCP."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)


class FastCreateLogCollectorResource(Resource):
    """使用 BKLOG Fast Create 创建 Linux、Windows 或容器日志采集项。"""

    class RequestSerializer(StrictFastCreateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        environment = serializers.ChoiceField(
            required=True,
            choices=[ENVIRONMENT_LINUX, ENVIRONMENT_WINDOWS, ENVIRONMENT_CONTAINER],
            label="采集环境",
        )
        collector_config_name = serializers.CharField(required=True, max_length=50, label="采集项名称")
        collector_config_name_en = serializers.RegexField(
            required=True,
            min_length=5,
            max_length=50,
            regex=r"^[A-Za-z0-9_]+$",
            label="采集项英文名",
        )
        collector_scenario_id = serializers.ChoiceField(
            required=True,
            choices=["row", "section", "wineventlog"],
            label="日志类型",
        )
        category_id = serializers.CharField(required=False, max_length=64, label="分类ID")
        description = serializers.CharField(
            required=False,
            allow_blank=True,
            allow_null=True,
            max_length=100,
            label="描述",
        )
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        target_object_type = serializers.CharField(required=False, label="主机目标类型")
        target_node_type = serializers.CharField(required=False, label="主机节点类型")
        target_nodes = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            label="主机目标节点",
        )
        params = serializers.DictField(required=False, label="主机采集参数")
        data_encoding = serializers.CharField(required=False, label="日志字符集")
        bcs_cluster_id = serializers.CharField(required=False, allow_blank=False, label="BCS集群ID")
        configs = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            allow_empty=False,
            label="容器日志配置",
        )
        add_pod_label = serializers.BooleanField(required=False, label="是否添加Pod标签")
        add_pod_annotation = serializers.BooleanField(required=False, label="是否添加Pod注解")
        extra_labels = serializers.ListField(
            child=serializers.DictField(),
            required=False,
            label="额外标签",
        )
        yaml_config_enabled = serializers.BooleanField(required=False, label="是否使用YAML配置")
        yaml_config = serializers.CharField(required=False, allow_blank=True, label="YAML配置内容")
        confirm = serializers.BooleanField(required=True, label="确认执行创建")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("写操作必须由用户确认，请设置 confirm=true")
            return value

        def validate(self, attrs):
            attrs = super().validate(attrs)
            environment = attrs["environment"]
            environment_fields = CONTAINER_CREATE_FIELDS if environment == ENVIRONMENT_CONTAINER else HOST_CREATE_FIELDS
            invalid_fields = (set(attrs) - COMMON_CREATE_FIELDS) - environment_fields
            if invalid_fields:
                raise serializers.ValidationError(
                    {
                        field: [f"This field cannot be used for a {environment} collector."]
                        for field in sorted(invalid_fields)
                    }
                )

            required_fields = (
                CONTAINER_REQUIRED_FIELDS if environment == ENVIRONMENT_CONTAINER else HOST_REQUIRED_FIELDS
            )
            missing_fields = required_fields - set(attrs)
            if missing_fields:
                raise serializers.ValidationError(
                    {field: [f"This field is required for a {environment} collector."] for field in missing_fields}
                )

            scenario = attrs["collector_scenario_id"]
            if scenario not in SCENARIOS_BY_ENVIRONMENT[environment]:
                raise serializers.ValidationError(
                    {"collector_scenario_id": [f"{scenario} cannot be used for a {environment} collector."]}
                )

            if environment != ENVIRONMENT_CONTAINER and len(attrs.get("description") or "") > 64:
                raise serializers.ValidationError(
                    {"description": ["Host collector description cannot exceed 64 characters."]}
                )

            validate_nested_create_fields(attrs)
            if environment == ENVIRONMENT_WINDOWS:
                params = attrs.get("params") or {}
                invalid_params = set(params) - WINDOWS_PLUGIN_PARAM_FIELDS
                if invalid_params:
                    raise serializers.ValidationError(
                        {
                            f"params.{field}": ["This field cannot be used for a windows collector."]
                            for field in sorted(invalid_params)
                        }
                    )
                if not params.get("winlog_name"):
                    raise serializers.ValidationError({"params.winlog_name": ["This field is required."]})
            else:
                params_list = (
                    [attrs.get("params") or {}]
                    if environment == ENVIRONMENT_LINUX
                    else [config.get("params") or {} for config in attrs.get("configs") or []]
                )
                for index, params in enumerate(params_list):
                    invalid_params = set(params).intersection(WINDOWS_ONLY_PLUGIN_PARAM_FIELDS)
                    if invalid_params:
                        path = "params" if environment == ENVIRONMENT_LINUX else f"configs[{index}].params"
                        raise serializers.ValidationError(
                            {
                                f"{path}.{field}": [f"This field cannot be used for a {environment} collector."]
                                for field in sorted(invalid_params)
                            }
                        )

            return attrs

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        create_result = (
            api.log_search.fast_create_log_collector(
                enforce_permission=True,
                **request_data,
            )
            or {}
        )
        collector_config_id = create_result.get("collector_config_id")
        if not collector_config_id:
            raise serializers.ValidationError("Fast Create did not return collector_config_id.")

        result_fields = {"bk_data_id", "subscription_id", "task_id_list", "index_set_id"}
        missing_result_fields = result_fields - set(create_result)
        collector = {}
        if missing_result_fields:
            collector = api.log_search.data_bus_collectors(
                collector_config_id=collector_config_id,
                enforce_permission=True,
            )
            if str(collector.get("bk_biz_id")) != str(request_data["bk_biz_id"]):
                raise PermissionDenied("Created collector does not belong to the requested business.")

        def result_value(field: str):
            return create_result[field] if field in create_result else collector.get(field)

        return {
            "collector_config_id": collector_config_id,
            "bk_data_id": result_value("bk_data_id"),
            "subscription_id": result_value("subscription_id"),
            "task_id_list": normalize_task_ids(result_value("task_id_list")),
            "index_set_id": result_value("index_set_id"),
        }
