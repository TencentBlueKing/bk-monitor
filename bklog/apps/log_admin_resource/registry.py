from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import get_collector_detail, list_collectors
from apps.log_admin_resource.handlers.collector_storage import (
    apply_collector_storage,
    get_collector_storage_snapshot,
    preview_collector_storage,
)
from apps.log_admin_resource.handlers.index_set import get_index_set_detail, list_index_sets
from apps.log_admin_resource.handlers.storage_cluster import list_storage_clusters


PROTOCOL = "bklog.admin_resource.v1"


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
    },
    "bklog.index_set.detail": {
        "func_name": "bklog.index_set.detail",
        "description": "Get bklog index set detail for admin resource views.",
        "safety_level": "read",
    },
}

HANDLERS = {
    "bklog.collector.list": list_collectors,
    "bklog.collector.detail": get_collector_detail,
    "bklog.collector.storage.preview": preview_collector_storage,
    "bklog.collector.storage.snapshot": get_collector_storage_snapshot,
    "bklog.collector.storage.apply": apply_collector_storage,
    "bklog.storage_cluster.list": list_storage_clusters,
    "bklog.index_set.list": list_index_sets,
    "bklog.index_set.detail": get_index_set_detail,
}


class AdminResourceRegistry:
    @classmethod
    def call(cls, func_name, params):
        if func_name == "__meta__":
            return cls.meta(params)
        if func_name in HANDLERS:
            return HANDLERS[func_name](params or {})
        raise ValidationError(f"unknown func_name: {func_name}")

    @classmethod
    def meta(cls, params):
        params = params or {}
        action = params.get("action", "list")
        if action == "list":
            return {"functions": sorted(FUNCTIONS.keys())}
        if action == "detail":
            target_func_name = params.get("target_func_name")
            if target_func_name not in FUNCTIONS:
                raise ValidationError(f"unknown target_func_name: {target_func_name}")
            return FUNCTIONS[target_func_name]
        raise ValidationError(f"unknown meta action: {action}")


def wrap_result(func_name, result):
    return {"func_name": func_name, "protocol": PROTOCOL, "result": result}
