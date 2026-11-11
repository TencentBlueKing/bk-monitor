"""告警策略只读 Admin RPC。"""

from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from bkm_space.api import SpaceApi
from bkmonitor.models import StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, serialize_model, paginate_queryset

FIELDS = [
    "id",
    "name",
    "bk_biz_id",
    "source",
    "scenario",
    "type",
    "is_enabled",
    "is_invalid",
    "invalid_type",
    "create_user",
    "create_time",
    "update_user",
    "update_time",
]


class StrategyParams(serializers.Serializer):
    bk_tenant_id = serializers.CharField(required=False, allow_blank=True)
    strategy_id = serializers.IntegerField(min_value=1, required=False)
    bk_biz_id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False, allow_blank=True)
    source = serializers.CharField(required=False, allow_blank=True)
    scenario = serializers.CharField(required=False, allow_blank=True)
    is_enabled = serializers.BooleanField(required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class StrategyListParams(StrategyParams):
    strategy_id = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    bk_biz_id = serializers.ListField(child=serializers.IntegerField(), required=False)
    name = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    source = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    scenario = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    is_enabled = serializers.ListField(child=serializers.BooleanField(), required=False)


def validate(params, operation="list"):
    allowed = (
        set(INPUT_PROPERTIES)
        if operation == "list"
        else {"bk_tenant_id", "strategy_id", "page", "page_size"}
        if operation == "redis_keys"
        else {"bk_tenant_id", "strategy_id"}
    )
    unexpected = set(params) - allowed
    if unexpected:
        raise CustomException(message="不支持的请求参数：" + ", ".join(sorted(unexpected)))
    if operation == "list":
        params = {
            key: value if isinstance(value, list) else [value] for key, value in params.items() if key in LIST_FILTERS
        } | {key: value for key, value in params.items() if key not in LIST_FILTERS}
    serializer = (StrategyListParams if operation == "list" else StrategyParams)(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def strategy_queryset(params):
    tenant = params.get("bk_tenant_id")
    query = StrategyModel.objects.all()
    if settings.ENABLE_MULTI_TENANT_MODE and tenant and tenant != "__all__":
        biz_ids = [space.bk_biz_id for space in SpaceApi.list_spaces(bk_tenant_id=tenant)]
        query = query.filter(bk_biz_id__in=biz_ids)
    return query


def scoped_strategy(params, strategy_id):
    record = strategy_queryset(params).filter(id=strategy_id).first()
    if record is None:
        raise CustomException(message="当前租户下未找到告警策略", data={"code": "STRATEGY_NOT_FOUND"})
    return record


def list_strategies(params):
    p = validate(params)
    query = strategy_queryset(p)
    for name in ("strategy_id", "bk_biz_id", "source", "scenario", "is_enabled"):
        values = [value for value in p.get(name, []) if value != ""]
        if values:
            field = "id" if name == "strategy_id" else name
            query = query.filter(**{field + "__in": values})
    names = [name for name in p.get("name", []) if name]
    if names:
        condition = Q()
        for name in names:
            condition |= Q(name__icontains=name)
        query = query.filter(condition)
    rows, total = paginate_queryset(query.order_by("-id"), page=p["page"], page_size=p["page_size"])
    return response(
        "alarm_strategy.list",
        p,
        {
            "items": [serialize_model(row, FIELDS) for row in rows],
            "total": total,
            "page": p["page"],
            "page_size": p["page_size"],
        },
    )


def detail(params):
    p = validate(params, "detail")
    if not p.get("strategy_id"):
        raise CustomException(message="strategy_id 为必填项")
    record = scoped_strategy(p, p["strategy_id"])
    config = Strategy.from_models([record])[0].to_dict(convert_dashboard=False, generate_priority_group_key=False)
    return response("alarm_strategy.detail", p, {"strategy": {**serialize_model(record, FIELDS), "config": config}})


def redis_keys(params):
    from kernel_api.rpc.functions.admin import alarm_redis_service as service

    p = validate(params, "redis_keys")
    record = scoped_strategy(p, p.get("strategy_id"))
    from bkmonitor.models import ItemModel

    refs = [{"template_id": "STRATEGY_CONFIG_CACHE", "strategy_id": record.id, "key_params": {}}]
    for name in ("SERVICE_LOCK_DETECT", "SERVICE_LOCK_PREPARATION"):
        if hasattr(service.keys, name):
            refs.append({"template_id": name, "strategy_id": record.id, "key_params": {}})
    for item_id in ItemModel.objects.filter(strategy_id=record.id).values_list("id", flat=True):
        for name in ("DATA_LIST_KEY", "NO_DATA_LIST_KEY", "ANOMALY_LIST_KEY", "LAST_CHECKPOINTS_CACHE_KEY"):
            refs.append({"template_id": name, "strategy_id": record.id, "key_params": {"item_id": item_id}})
    start = (p["page"] - 1) * p["page_size"]
    items = []
    for ref in refs[start : start + p["page_size"]]:
        try:
            client, source, redis_key = service.target({**p, **ref})
            status = service.key_status(client, redis_key, source)
        except Exception as error:
            status = {
                "key": None,
                "exists": None,
                "type": None,
                "ttl": None,
                "length": None,
                "source": None,
                "error": str(error),
            }
        items.append({**ref, **status})
    return response(
        "alarm_strategy.redis_keys",
        p,
        {"items": items, "total": len(refs), "page": p["page"], "page_size": p["page_size"]},
        "inspect",
    )


def response(operation, params, data, safety="read"):
    return build_response(
        operation=operation,
        func_name="admin." + operation,
        bk_tenant_id=params.get("bk_tenant_id"),
        data=data,
        safety_level=safety,
    )


INPUT_PROPERTIES = {
    "bk_tenant_id": {"type": "string"},
    "strategy_id": {"type": "integer", "minimum": 1},
    "bk_biz_id": {"type": "integer"},
    "name": {"type": "string"},
    "source": {"type": "string"},
    "scenario": {"type": "string"},
    "is_enabled": {"type": "boolean"},
    "page": {"type": "integer", "minimum": 1, "default": 1},
    "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
}
LIST_FILTERS = ("strategy_id", "bk_biz_id", "name", "source", "scenario", "is_enabled")
LIST_INPUT_PROPERTIES = {
    name: {"anyOf": [schema, {"type": "array", "items": schema}]} if name in LIST_FILTERS else schema
    for name, schema in INPUT_PROPERTIES.items()
}

for operation, handler, summary in [
    ("list", list_strategies, "分页查询告警策略"),
    ("detail", detail, "查询告警策略配置"),
    ("redis_keys", redis_keys, "分页查询策略关联 Redis Key 状态"),
]:
    fields = (
        list(INPUT_PROPERTIES)
        if operation == "list"
        else ["bk_tenant_id", "strategy_id", "page", "page_size"]
        if operation == "redis_keys"
        else ["bk_tenant_id", "strategy_id"]
    )
    KernelRPCRegistry.register_function(
        func_name="admin.alarm_strategy." + operation,
        handler=handler,
        summary=summary,
        description=summary
        + "；省略租户时查询当前环境全部租户。"
        + (
            "过滤字段支持单值或列表，字段内 OR、字段间 AND，空列表不筛选；name 按任一名称模糊匹配。"
            if operation == "list"
            else ""
        ),
        params_schema={
            "type": "object",
            "properties": {
                name: (LIST_INPUT_PROPERTIES if operation == "list" else INPUT_PROPERTIES)[name] for name in fields
            },
            "required": [] if operation == "list" else ["strategy_id"],
            "additionalProperties": False,
        },
        example_params={"strategy_id": [1, 2], "bk_biz_id": [2, 3], "scenario": ["os", "host_process"]}
        if operation == "list"
        else {"strategy_id": 1},
    )
