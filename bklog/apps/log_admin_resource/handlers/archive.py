from apps.exceptions import ValidationError
from apps.log_admin_resource.response_schema import object_schema, pagination_schema
from apps.log_databus.models import ArchiveConfig, RestoreConfig
from apps.log_search.models import Space
from apps.utils.local import get_request_tenant_id


def _list(model, fields, filters, p):
    tenant = get_request_tenant_id()
    if not tenant:
        raise ValidationError("请选择具体租户")
    businesses = Space.objects.filter(bk_tenant_id=tenant).values("bk_biz_id")
    rows = model.objects.filter(bk_biz_id__in=businesses, **{key: p[key] for key in filters if key in p})
    page, size = p.get("page", 1), p.get("page_size", 20)
    start = (page - 1) * size
    return {
        "items": list(rows.order_by("-pk").values(*fields)[start : start + size]),
        "total": rows.count(),
        "page": page,
        "page_size": size,
    }


CONFIG_FIELDS = {
    "archive_config_id": "integer",
    "bk_biz_id": "integer",
    "instance_type": "string",
    "instance_id": "integer",
    "snapshot_days": "integer",
    "target_snapshot_repository_name": "string",
}
RESTORE_FIELDS = {
    "restore_config_id": "integer",
    "archive_config_id": "integer",
    "bk_biz_id": "integer",
    "meta_restore_id": ["integer", "null"],
    "index_set_name": "string",
    "index_set_id": ["integer", "null"],
    "is_done": "boolean",
    "start_time": "string",
    "end_time": "string",
    "expired_time": "string",
    "duration": "integer",
    "total_store_size": ["integer", "null"],
    "total_doc_count": ["integer", "null"],
}
CONFIG_FILTERS = ("bk_biz_id", "archive_config_id", "instance_id", "instance_type", "target_snapshot_repository_name")
RESTORE_FILTERS = ("bk_biz_id", "archive_config_id", "restore_config_id", "index_set_id")


def list_configs(p):
    return _list(ArchiveConfig, CONFIG_FIELDS, CONFIG_FILTERS, p)


def list_restores(p):
    return _list(RestoreConfig, RESTORE_FIELDS, RESTORE_FILTERS, p)


def metadata(name, description, fields, filters):
    params = {key: {"type": "integer" if isinstance(fields[key], list) else fields[key]} for key in filters}
    params.update(
        page={"type": "integer", "minimum": 1, "default": 1},
        page_size={"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    )
    return {
        "func_name": name,
        "description": description,
        "safety_level": "read",
        "validate_params": True,
        "params_schema": object_schema(properties=params),
        "response_schema": pagination_schema(
            object_schema(*fields, properties={k: {"type": v} for k, v in fields.items()})
        ),
        "examples": [{"params": {"bk_biz_id": 2, "page": 1, "page_size": 20}}],
    }


FUNCTIONS = {
    "bklog.archive.config_list": metadata(
        "bklog.archive.config_list", "查询日志归档配置及关联资源", CONFIG_FIELDS, CONFIG_FILTERS
    ),
    "bklog.archive.restore_list": metadata(
        "bklog.archive.restore_list", "查询日志回溯请求、索引集及执行任务编号", RESTORE_FIELDS, RESTORE_FILTERS
    ),
}
HANDLERS = {"bklog.archive.config_list": list_configs, "bklog.archive.restore_list": list_restores}
