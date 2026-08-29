from django.conf import settings

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import get_collector_detail, list_collectors
from apps.log_admin_resource.handlers.collector_evidence import (
    FUNCTIONS as COLLECTOR_EVIDENCE_FUNCTIONS,
    HANDLERS as COLLECTOR_EVIDENCE_HANDLERS,
)
from apps.log_admin_resource.handlers.collector_storage import (
    apply_collector_storage,
    get_collector_storage_snapshot,
    preview_collector_storage,
)
from apps.log_admin_resource.handlers.bkdata_inspection import (
    batch_get_bkdata_result_table_snapshots,
    get_bkdata_clean_snapshot,
    get_bkdata_flow_snapshot,
    get_bkdata_raw_snapshot,
)
from apps.log_admin_resource.handlers.async_export import (
    FUNCTIONS as ASYNC_EXPORT_FUNCTIONS,
    HANDLERS as ASYNC_EXPORT_HANDLERS,
)
from apps.log_admin_resource.handlers.clustering_config import (
    get_clustering_config_detail,
    list_clustering_configs,
)
from apps.log_admin_resource.handlers.clustering_pipeline import (
    force_fail_clustering_pipeline_node,
    get_clustering_access_pipeline,
    retry_clustering_pipeline_node,
    skip_clustering_pipeline_node,
)
from apps.log_admin_resource.handlers.index_set import get_index_set_detail, list_index_sets
from apps.log_admin_resource.handlers.index_set_route import (
    FUNCTIONS as INDEX_SET_ROUTE_FUNCTIONS,
    HANDLERS as INDEX_SET_ROUTE_HANDLERS,
)
from apps.log_admin_resource.handlers.log_extract import (
    FUNCTIONS as LOG_EXTRACT_FUNCTIONS,
    HANDLERS as LOG_EXTRACT_HANDLERS,
)
from apps.log_admin_resource.handlers.model_query import (
    FUNCTIONS as MODEL_QUERY_FUNCTIONS,
    HANDLERS as MODEL_QUERY_HANDLERS,
)
from apps.log_admin_resource.handlers.platform_source import (
    FUNCTIONS as PLATFORM_SOURCE_FUNCTIONS,
    HANDLERS as PLATFORM_SOURCE_HANDLERS,
)
from apps.log_admin_resource.handlers.storage_cluster import list_storage_clusters
from apps.log_admin_resource.schema import validate_params


PROTOCOL = "bklog.admin_resource.v1"


def _object_schema(*required, properties=None, additional_properties=True):
    schema = {
        "type": "object",
        "properties": properties or {key: {} for key in required},
        "additionalProperties": additional_properties,
    }
    if required:
        schema["required"] = list(required)
    return schema


def _pagination_response_schema():
    return _object_schema(
        "items",
        "page",
        "page_size",
        "total",
        properties={
            "items": {"type": "array", "items": {"type": "object"}},
            "page": {"type": "integer"},
            "page_size": {"type": "integer"},
            "total": {"type": "integer"},
        },
    )


def _probe_response_schema():
    error_schema = _object_schema(
        "code",
        "message",
        "upstream_code",
        "upstream_message",
        "request_id",
        "retryable",
        properties={
            "code": {"type": "string"},
            "message": {"type": "string"},
            "upstream_code": {"type": ["string", "null"]},
            "upstream_message": {"type": ["string", "null"]},
            "request_id": {"type": ["string", "null"]},
            "retryable": {"type": "boolean"},
        },
    )
    return _object_schema(
        "probe_status",
        "exists",
        "empty",
        "observed_at",
        "duration_ms",
        "data",
        "error",
        "warnings",
        properties={
            "probe_status": {"type": "string", "enum": ["success", "failed", "skipped"]},
            "exists": {"type": ["boolean", "null"]},
            "empty": {"type": ["boolean", "null"]},
            "observed_at": {"type": "string", "format": "date-time"},
            "duration_ms": {"type": "number", "minimum": 0},
            "data": {},
            "error": {"anyOf": [error_schema, {"type": "null"}]},
            "warnings": {"type": "array", "items": {"type": "object"}},
        },
    )


def _snapshot_response_schema(*resource_keys, probe_keys):
    properties = {key: {} for key in resource_keys}
    properties.update({key: _probe_response_schema() for key in probe_keys})
    return _object_schema(*resource_keys, *probe_keys, properties=properties)


def _required_id_schema(key):
    return {
        "type": "object",
        "properties": {key: {"type": "integer", "minimum": 1}},
        "required": [key],
        "additionalProperties": False,
    }


def _bkdata_id_schema(key, include_sample_limit=False):
    properties = {
        "bk_biz_id": {"type": "integer", "not": {"const": 0}},
        key: {"type": "integer", "minimum": 1},
    }
    if include_sample_limit:
        properties["sample_limit"] = {"type": "integer", "minimum": 1, "maximum": 20}
    return {
        "type": "object",
        "properties": properties,
        "required": ["bk_biz_id", key],
        "additionalProperties": False,
    }


def _pipeline_action_params_schema(action):
    properties = {
        "config_id": {"type": "integer", "minimum": 1},
        "task_id": {"type": "string", "minLength": 1, "maxLength": 256},
        "node_id": {"type": "string", "minLength": 1, "maxLength": 256},
        "expected_version": {"type": "string", "minLength": 1, "maxLength": 64},
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
    }
    required = ["config_id", "task_id", "node_id", "expected_version", "reason"]
    if action == "skip":
        properties["acknowledge_external_effects"] = {"type": "boolean", "const": True}
        required.append("acknowledge_external_effects")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _pipeline_action_response_schema(action):
    return _object_schema(
        "action",
        "config_id",
        "task_id",
        "node_id",
        "reason",
        "result",
        "message",
        "before",
        "pipeline",
        properties={
            "action": {"type": "string", "const": action},
            "config_id": {"type": "integer"},
            "task_id": {"type": "string"},
            "node_id": {"type": "string"},
            "reason": {"type": "string"},
            "result": {"type": "boolean", "const": True},
            "message": {"type": "string"},
            "before": {"type": "object"},
            "pipeline": {"type": "object"},
        },
    )


FUNCTIONS = {
    "bklog.collector.list": {
        "func_name": "bklog.collector.list",
        "description": "List bklog collector configs for admin resource views.",
        "safety_level": "read",
    },
    "bklog.collector.detail": {
        "func_name": "bklog.collector.detail",
        "description": "Get bklog collector config detail for admin resource views.",
        "safety_level": "read",
    },
    "bklog.collector.storage.preview": {
        "func_name": "bklog.collector.storage.preview",
        "description": "Preview bklog collector storage config changes.",
        "safety_level": "read",
    },
    "bklog.collector.storage.snapshot": {
        "func_name": "bklog.collector.storage.snapshot",
        "description": "Get current bklog collector storage config snapshots.",
        "safety_level": "read",
        "params_schema": {
            "type": "object",
            "properties": {
                "collector_config_ids": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1},
                    "minItems": 1,
                    "maxItems": 30,
                }
            },
            "required": ["collector_config_ids"],
            "additionalProperties": False,
        },
    },
    "bklog.collector.storage.apply": {
        "func_name": "bklog.collector.storage.apply",
        "description": "Apply bklog collector storage config changes.",
        "safety_level": "write",
    },
    "bklog.storage_cluster.list": {
        "func_name": "bklog.storage_cluster.list",
        "description": "List bklog ES storage clusters for admin resource views.",
        "safety_level": "read",
    },
    "bklog.index_set.list": {
        "func_name": "bklog.index_set.list",
        "description": "List bklog index sets for admin resource views.",
        "safety_level": "read",
        "params_schema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                "space_uid": {"type": "string"},
                "index_set_id": {"type": "integer", "minimum": 1},
                "index_set_name": {"type": "string"},
                "collector_config_id": {"type": "integer", "minimum": 1},
                "scenario_id": {"type": "string"},
                "result_table_id": {"type": "string"},
                "is_active": {"type": "boolean"},
                "is_group": {"type": "boolean"},
                "has_clustering_config": {"type": "boolean"},
                "signature_enable": {"type": "boolean"},
                "access_finished_stored": {"type": "boolean"},
                "ordering": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "response_schema": _pagination_response_schema(),
        "examples": [{"params": {"page": 1, "page_size": 20, "has_clustering_config": True}}],
    },
    "bklog.index_set.detail": {
        "func_name": "bklog.index_set.detail",
        "description": "Get bklog index set detail for admin resource views.",
        "safety_level": "read",
        "params_schema": _required_id_schema("index_set_id"),
        "response_schema": _object_schema(
            "index_set", "indexes", "collectors", "clustering_relations", "raw", "warnings"
        ),
        "examples": [{"params": {"index_set_id": 16462}}],
    },
    "bklog.clustering_config.list": {
        "func_name": "bklog.clustering_config.list",
        "description": "List clustering configurations and their Flow/RT references.",
        "safety_level": "read",
        "params_schema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                "config_id": {"type": "integer", "minimum": 1},
                "index_set_id": {"type": "integer", "minimum": 1},
                "related_index_set_id": {"type": "integer", "minimum": 1},
                "bk_biz_id": {"type": "integer", "not": {"const": 0}},
                "collector_config_id": {"type": "integer", "minimum": 1},
                "signature_enable": {"type": "boolean"},
                "access_finished_stored": {"type": "boolean"},
                "flow_id": {"type": "integer", "minimum": 1},
                "result_table_id": {"type": "string"},
                "ordering": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "response_schema": _pagination_response_schema(),
        "examples": [{"params": {"page": 1, "page_size": 20, "index_set_id": 16462}}],
    },
    "bklog.clustering_config.detail": {
        "func_name": "bklog.clustering_config.detail",
        "description": "Get every persisted clustering configuration parameter by exact config ID.",
        "safety_level": "read",
        "params_schema": {
            "type": "object",
            "properties": {
                "config_id": {"type": "integer", "minimum": 1},
                "include_flow_configs": {"type": "boolean", "default": False},
            },
            "required": ["config_id"],
            "additionalProperties": False,
        },
        "response_schema": _object_schema(
            "config",
            "summary",
            "flow_references",
            "generated_flow_configs",
            "result_table_references",
            "access_tasks",
        ),
        "examples": [
            {"params": {"config_id": 1}},
            {"params": {"config_id": 1, "include_flow_configs": True}},
        ],
    },
    "bklog.clustering_config.access_pipeline": {
        "func_name": "bklog.clustering_config.access_pipeline",
        "description": "Inspect the fixed serial clustering access pipeline and persistent task steps.",
        "safety_level": "inspect",
        "params_schema": {
            "type": "object",
            "properties": {
                "config_id": {"type": "integer", "minimum": 1},
                "task_id": {"type": "string", "minLength": 1},
            },
            "required": ["config_id"],
            "additionalProperties": False,
        },
        "response_schema": _object_schema(
            "config_id",
            "selected_task_id",
            "task_selection",
            "task_records",
            "pipeline",
            properties={
                "config_id": {"type": "integer"},
                "selected_task_id": {"type": ["string", "null"]},
                "task_selection": {"type": "string", "enum": ["latest", "explicit"]},
                "task_records": {"type": "array", "items": {"type": "object"}},
                "pipeline": _probe_response_schema(),
            },
        ),
        "examples": [{"params": {"config_id": 1}}, {"params": {"config_id": 1, "task_id": "pipeline-id"}}],
    },
    "bklog.clustering_config.pipeline.retry": {
        "func_name": "bklog.clustering_config.pipeline.retry",
        "description": "Retry the current failed node of a clustering access pipeline after strict state checks.",
        "safety_level": "write",
        "params_schema": _pipeline_action_params_schema("retry"),
        "response_schema": _pipeline_action_response_schema("retry"),
        "examples": [
            {
                "params": {
                    "config_id": 1,
                    "task_id": "pipeline-id",
                    "node_id": "node-id",
                    "expected_version": "status-version",
                    "reason": "已修复节点依赖，重试当前步骤",
                }
            }
        ],
    },
    "bklog.clustering_config.pipeline.skip": {
        "func_name": "bklog.clustering_config.pipeline.skip",
        "description": "Skip the current failed node only after the caller confirms its external effects are complete.",
        "safety_level": "destructive",
        "params_schema": _pipeline_action_params_schema("skip"),
        "response_schema": _pipeline_action_response_schema("skip"),
        "examples": [
            {
                "params": {
                    "config_id": 1,
                    "task_id": "pipeline-id",
                    "node_id": "node-id",
                    "expected_version": "status-version",
                    "reason": "外部副作用已人工完成，跳过原节点",
                    "acknowledge_external_effects": True,
                }
            }
        ],
    },
    "bklog.clustering_config.pipeline.force_fail": {
        "func_name": "bklog.clustering_config.pipeline.force_fail",
        "description": "Force the current running node to failed state after strict current-node and version checks.",
        "safety_level": "destructive",
        "params_schema": _pipeline_action_params_schema("force_fail"),
        "response_schema": _pipeline_action_response_schema("force_fail"),
        "examples": [
            {
                "params": {
                    "config_id": 1,
                    "task_id": "pipeline-id",
                    "node_id": "node-id",
                    "expected_version": "status-version",
                    "reason": "节点长时间未刷新，先强制失败后人工判断重试或跳过",
                }
            }
        ],
    },
    "bklog.bkdata.raw.snapshot": {
        "func_name": "bklog.bkdata.raw.snapshot",
        "description": "Inspect RawData deployment and latest full raw samples.",
        "safety_level": "inspect",
        "data_classification": "sensitive_logs",
        "params_schema": _bkdata_id_schema("raw_data_id", include_sample_limit=True),
        "response_schema": _snapshot_response_schema("raw_data_id", "bk_biz_id", probe_keys=("deploy", "tail")),
        "examples": [{"params": {"bk_biz_id": 5000140, "raw_data_id": 12345, "sample_limit": 10}}],
    },
    "bklog.bkdata.clean.snapshot": {
        "func_name": "bklog.bkdata.clean.snapshot",
        "description": "Inspect a clean definition and its distribution tasks.",
        "safety_level": "inspect",
        "params_schema": {
            "type": "object",
            "properties": {
                "bk_biz_id": {"type": "integer", "not": {"const": 0}},
                "processing_id": {"type": "string", "minLength": 1},
                "result_table_id": {"type": "string", "minLength": 1},
            },
            "required": ["bk_biz_id", "processing_id"],
            "additionalProperties": False,
        },
        "response_schema": _snapshot_response_schema(
            "processing_id", "result_table_id", "bk_biz_id", probe_keys=("detail", "tasks")
        ),
        "examples": [
            {
                "params": {
                    "bk_biz_id": 5000140,
                    "processing_id": "5000140_bklog_host_collect_demo",
                }
            }
        ],
    },
    "bklog.bkdata.flow.snapshot": {
        "func_name": "bklog.bkdata.flow.snapshot",
        "description": "Inspect an explicitly selected DataFlow, its deployment, and its actual graph.",
        "safety_level": "inspect",
        "params_schema": _bkdata_id_schema("flow_id"),
        "response_schema": _snapshot_response_schema(
            "flow_id", "bk_biz_id", probe_keys=("detail", "latest_deploy", "graph")
        ),
        "examples": [{"params": {"bk_biz_id": 5000140, "flow_id": 66341}}],
    },
    "bklog.bkdata.result_table.snapshot_batch": {
        "func_name": "bklog.bkdata.result_table.snapshot_batch",
        "description": "Inspect up to 20 result tables and their latest full samples with bounded concurrency.",
        "safety_level": "inspect",
        "data_classification": "sensitive_logs",
        "params_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "properties": {
                            "result_table_id": {"type": "string", "minLength": 1},
                            "bk_biz_id": {"type": "integer", "not": {"const": 0}},
                        },
                        "required": ["result_table_id"],
                        "additionalProperties": False,
                    },
                },
                "sample_limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
        "response_schema": _object_schema(
            "items",
            "item_count",
            "sample_limit",
            "max_concurrency",
            "duration_ms",
            properties={
                "items": {
                    "type": "array",
                    "items": _object_schema(
                        "result_table_id",
                        "bk_biz_id",
                        "detail",
                        "tail",
                        properties={
                            "result_table_id": {"type": "string"},
                            "bk_biz_id": {"type": "integer"},
                            "detail": _probe_response_schema(),
                            "tail": _probe_response_schema(),
                        },
                    ),
                },
                "item_count": {"type": "integer", "minimum": 0, "maximum": 20},
                "sample_limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "max_concurrency": {"type": "integer", "const": 5},
                "duration_ms": {"type": "number", "minimum": 0},
            },
        ),
        "examples": [
            {
                "params": {
                    "items": [{"result_table_id": "5000140_bklog_16462_clustering", "bk_biz_id": 5000140}],
                    "sample_limit": 10,
                }
            }
        ],
    },
}
FUNCTIONS.update(PLATFORM_SOURCE_FUNCTIONS)
FUNCTIONS.update(COLLECTOR_EVIDENCE_FUNCTIONS)
FUNCTIONS.update(INDEX_SET_ROUTE_FUNCTIONS)
FUNCTIONS.update(ASYNC_EXPORT_FUNCTIONS)
FUNCTIONS.update(LOG_EXTRACT_FUNCTIONS)
FUNCTIONS.update(MODEL_QUERY_FUNCTIONS)

HANDLERS = {
    "bklog.collector.list": list_collectors,
    "bklog.collector.detail": get_collector_detail,
    "bklog.collector.storage.preview": preview_collector_storage,
    "bklog.collector.storage.snapshot": get_collector_storage_snapshot,
    "bklog.collector.storage.apply": apply_collector_storage,
    "bklog.storage_cluster.list": list_storage_clusters,
    "bklog.index_set.list": list_index_sets,
    "bklog.index_set.detail": get_index_set_detail,
    "bklog.clustering_config.list": list_clustering_configs,
    "bklog.clustering_config.detail": get_clustering_config_detail,
    "bklog.clustering_config.access_pipeline": get_clustering_access_pipeline,
    "bklog.clustering_config.pipeline.retry": retry_clustering_pipeline_node,
    "bklog.clustering_config.pipeline.skip": skip_clustering_pipeline_node,
    "bklog.clustering_config.pipeline.force_fail": force_fail_clustering_pipeline_node,
    "bklog.bkdata.raw.snapshot": get_bkdata_raw_snapshot,
    "bklog.bkdata.clean.snapshot": get_bkdata_clean_snapshot,
    "bklog.bkdata.flow.snapshot": get_bkdata_flow_snapshot,
    "bklog.bkdata.result_table.snapshot_batch": batch_get_bkdata_result_table_snapshots,
}
HANDLERS.update(PLATFORM_SOURCE_HANDLERS)
HANDLERS.update(COLLECTOR_EVIDENCE_HANDLERS)
HANDLERS.update(INDEX_SET_ROUTE_HANDLERS)
HANDLERS.update(ASYNC_EXPORT_HANDLERS)
HANDLERS.update(LOG_EXTRACT_HANDLERS)
HANDLERS.update(MODEL_QUERY_HANDLERS)


class AdminResourceRegistry:
    @classmethod
    def call(cls, func_name, params, app_code=None):
        cls._validate_app_access(app_code=app_code, func_name=func_name)
        if func_name == "__meta__":
            return cls.meta(params, app_code=app_code)
        if func_name in HANDLERS:
            function = FUNCTIONS[func_name]
            if function.get("validate_params"):
                validate_params(params or {}, function.get("params_schema") or _object_schema())
            return HANDLERS[func_name](params or {})
        raise ValidationError(f"unknown func_name: {func_name}")

    @classmethod
    def meta(cls, params, app_code=None):
        params = params or {}
        action = params.get("action", "list")
        visible_functions = cls._visible_functions(app_code)
        if action == "list":
            names = sorted(visible_functions)
            return {
                "protocol": PROTOCOL,
                "functions": names,
                "capabilities": [cls._capability_summary(visible_functions[name]) for name in names],
            }
        if action == "detail":
            target_func_name = params.get("target_func_name")
            if target_func_name not in visible_functions:
                raise ValidationError(f"unknown target_func_name: {target_func_name}")
            return cls._public_metadata(visible_functions[target_func_name])
        raise ValidationError(f"unknown meta action: {action}")

    @staticmethod
    def _public_metadata(function):
        return {key: value for key, value in function.items() if not key.startswith("_") and key != "validate_params"}

    @staticmethod
    def _capability_summary(function):
        return {key: function[key] for key in ("func_name", "description", "safety_level") if key in function}

    @classmethod
    def _visible_functions(cls, app_code):
        if app_code in settings.RESOURCE_CALL_APP_CODE_WHITE_LIST:
            return FUNCTIONS
        return {
            name: function
            for name, function in FUNCTIONS.items()
            if function.get("safety_level") in {"read", "inspect"}
        }

    @classmethod
    def _validate_app_access(cls, app_code, func_name):
        if not app_code:
            raise BklogPermissionError("resource call requires a trusted APIGW app identity")
        if func_name == "__meta__" or func_name not in FUNCTIONS:
            return
        safety_level = FUNCTIONS[func_name].get("safety_level")
        if safety_level in {"write", "destructive"} and app_code not in settings.RESOURCE_CALL_APP_CODE_WHITE_LIST:
            raise BklogPermissionError("resource call app is outside the management allowlist")


def wrap_result(func_name, result):
    return {"func_name": func_name, "protocol": PROTOCOL, "result": result}
