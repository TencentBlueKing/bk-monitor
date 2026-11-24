"""按请求租户、显式业务和日志 IAM 实例权限查询采集项及索引集。"""

from itertools import islice

from apps.exceptions import ValidationError
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum
from apps.log_admin_resource.handlers.iam_decision import _evaluate_one
from apps.log_admin_resource.handlers.inspection import request_tenant_spaces, require_request_tenant_id
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet

NAME = "bklog.user_query"
OPERATIONS = ("bklog.collector.list", "bklog.collector.detail", "bklog.index_set.list", "bklog.index_set.detail")
COLLECTOR_FIELDS = (
    "collector_config_id",
    "bk_biz_id",
    "collector_config_name",
    "collector_scenario_id",
    "bk_data_id",
    "table_id",
    "target_object_type",
    "is_active",
)
INDEX_FIELDS = ("index_set_id", "index_set_name", "space_uid", "scenario_id", "is_active")


def visible_rows(permission, action, resource, rows, key, title, biz):
    # 仅传业务内候选 ID 给 IAM，先取可见集合，再计算 total 及分页。
    visible = []
    ids = rows.order_by(key).values_list(key, title).iterator(chunk_size=200)
    while batch := list(islice(ids, 200)):
        resources = [
            [
                resource.create_simple_instance(
                    str(i), {"id": str(i), "name": name, "bk_biz_id": str(biz), "_bk_iam_path_": f"/space,{biz}/"}
                )
            ]
            for i, name in batch
        ]
        request = permission.make_engine_batch_request([action], resources)
        decision = permission.mode_router.batch_is_allowed(request)
        if any(item.decision.degraded for item in decision.items):
            raise ValidationError("日志 IAM 暂不可用")
        allowed = decision.as_allowed_dict()
        visible.extend(i for i, _ in batch if allowed[str(i)][action.id])
    return rows.filter(**{key + "__in": visible})


def read_user_query(params):
    tenant = require_request_tenant_id()
    name = params["operation"]
    query = params.get("query", {})
    spaces = request_tenant_spaces()
    if params.get("bk_biz_id") is None and not params.get("space_uid"):
        raise ValidationError("必须指定 bk_biz_id 或 space_uid")
    for field in ("bk_biz_id", "space_uid"):
        if params.get(field) is not None:
            spaces = spaces.filter(**{field: params[field]})
    space = spaces.exclude(bk_biz_id=0).first()
    denied = {"allowed": False, "result": None}
    if not space:
        return denied
    permission = Permission(username=params["username"], bk_tenant_id=tenant)
    decision = _evaluate_one(
        permission,
        {"action_id": ActionEnum.VIEW_BUSINESS.id, "resource_type": "space", "resource_id": str(space.bk_biz_id)},
        index=0,
    )
    if decision["status"] != "ok" or "iam_provider_degraded" in decision["warnings"]:
        raise ValidationError("日志 IAM 暂不可用")
    if not decision["allowed"]:
        return denied
    if name not in OPERATIONS:
        raise ValidationError("未知的用户态查询")
    collector = name.startswith("bklog.collector.")
    if collector:
        rows = CollectorConfig.objects.filter(bk_biz_id=space.bk_biz_id)
        key, title, fields = "collector_config_id", "collector_config_name", COLLECTOR_FIELDS
        action, resource = ActionEnum.VIEW_COLLECTION, ResourceEnum.COLLECTION
    else:
        rows = LogIndexSet.objects.filter(space_uid=space.space_uid)
        key, title, fields = "index_set_id", "index_set_name", INDEX_FIELDS
        action, resource = ActionEnum.SEARCH_LOG, ResourceEnum.INDICES
    detail = name.endswith(".detail")
    if detail or key in query:
        rows = rows.filter(**{key: query[key]})
    if query.get("keyword"):
        rows = rows.filter(**{title + "__icontains": query["keyword"]})
    rows = visible_rows(permission, action, resource, rows, key, title, space.bk_biz_id).order_by(key).values(*fields)
    if detail:
        row = rows.first()
        if row is None:
            return denied
        if not collector:
            row["bk_biz_id"] = space.bk_biz_id
        result = {"collector" if collector else "index_set": row}
    else:
        page, size = query.get("page", 1), query.get("page_size", 20)
        start = (page - 1) * size
        items = list(rows[start : start + size])
        if not collector:
            for row in items:
                row["bk_biz_id"] = space.bk_biz_id
        result = {"items": items, "page": page, "page_size": size, "total": rows.count()}
    return {"allowed": True, "result": result}


FUNCTIONS = {
    NAME: {
        "func_name": NAME,
        "description": "查询用户在指定业务可查看的采集项或可检索的索引集。",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "required": ["operation", "username", "query"],
            "properties": {
                "operation": {"enum": list(OPERATIONS), "type": "string"},
                "username": {"type": "string", "minLength": 1},
                "bk_biz_id": {"type": "integer"},
                "space_uid": {"type": "string"},
                "query": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "minimum": 1},
                        "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
                        "collector_config_id": {"type": "integer"},
                        "index_set_id": {"type": "integer"},
                        "keyword": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "response_schema": {
            "type": "object",
            "properties": {"allowed": {"type": "boolean"}, "result": {"type": ["object", "null"]}},
            "required": ["allowed", "result"],
        },
        "examples": [
            {"params": {"operation": "bklog.collector.list", "username": "alice", "bk_biz_id": 2, "query": {"page": 1}}}
        ],
    }
}
HANDLERS = {NAME: read_user_query}
