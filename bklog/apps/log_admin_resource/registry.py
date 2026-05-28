from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector import get_collector_detail, list_collectors
from apps.log_admin_resource.handlers.index_set import get_index_set_detail, list_index_sets


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
