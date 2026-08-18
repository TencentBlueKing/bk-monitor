from django.db.models import Q

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import optional_positive_int, reject_identity_params, sanitize_json
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.models import LogIndexSet


GENERATED_FLOW_CONFIG_FIELDS = {
    "pre_treat_flow",
    "after_treat_flow",
    "predict_flow",
    "log_count_aggregation_flow",
    "modify_flow",
}
ACCESS_RUNTIME_FIELDS = {"task_records", "task_details"}


def list_clustering_configs(params):
    params = params or {}
    reject_identity_params(params)
    page = optional_positive_int(params.get("page"), "page", default=1)
    page_size = optional_positive_int(params.get("page_size"), "page_size", default=20, maximum=100)
    qs = ClusteringConfig.objects.all()

    exact_filters = {
        "config_id": "id",
        "index_set_id": "index_set_id",
        "bk_biz_id": "bk_biz_id",
        "collector_config_id": "collector_config_id",
        "signature_enable": "signature_enable",
        "access_finished_stored": "access_finished",
    }
    for param_key, model_field in exact_filters.items():
        if params.get(param_key) not in (None, ""):
            qs = qs.filter(**{model_field: params[param_key]})
    if params.get("related_index_set_id") not in (None, ""):
        qs = qs.filter(
            Q(index_set_id=params["related_index_set_id"]) | Q(new_cls_index_set_id=params["related_index_set_id"])
        )
    if params.get("flow_id") not in (None, ""):
        flow_id = params["flow_id"]
        qs = qs.filter(
            Q(pre_treat_flow_id=flow_id)
            | Q(after_treat_flow_id=flow_id)
            | Q(predict_flow_id=flow_id)
            | Q(log_count_aggregation_flow_id=flow_id)
        )
    if params.get("result_table_id"):
        result_table_id = params["result_table_id"]
        qs = qs.filter(
            Q(bkdata_etl_result_table_id__icontains=result_table_id)
            | Q(source_rt_name__icontains=result_table_id)
            | Q(model_output_rt__icontains=result_table_id)
            | Q(clustered_rt__icontains=result_table_id)
            | Q(signature_pattern_rt__icontains=result_table_id)
            | Q(new_cls_pattern_rt__icontains=result_table_id)
            | Q(new_cls_strategy_output__icontains=result_table_id)
            | Q(normal_strategy_output__icontains=result_table_id)
        )

    ordering = params.get("ordering") or "-updated_at"
    allowed_ordering = {
        "id",
        "-id",
        "index_set_id",
        "-index_set_id",
        "updated_at",
        "-updated_at",
        "bk_biz_id",
        "-bk_biz_id",
    }
    qs = qs.order_by(ordering if ordering in allowed_ordering else "-updated_at")
    total = qs.count()
    start = (page - 1) * page_size
    configs = list(qs[start : start + page_size])
    index_set_map = _index_set_map(configs)
    return {
        "items": [_serialize_config_summary(config, index_set_map) for config in configs],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def get_clustering_config_detail(params):
    params = params or {}
    reject_identity_params(params)
    config_id = params.get("config_id")
    if config_id in (None, ""):
        raise ValidationError("config_id is required")
    try:
        config = ClusteringConfig.objects.get(id=int(config_id))
    except (TypeError, ValueError):
        raise ValidationError("config_id must be an integer")
    except ClusteringConfig.DoesNotExist:
        raise ValidationError(f"config_id does not exist: {config_id}")

    index_set_map = _index_set_map([config])
    include_flow_configs = params.get("include_flow_configs") is True
    fields = {}
    for field in config._meta.concrete_fields:
        if (
            field.name
            in {"is_deleted", "deleted_at", "deleted_by"} | GENERATED_FLOW_CONFIG_FIELDS | ACCESS_RUNTIME_FIELDS
        ):
            continue
        fields[field.name] = sanitize_json(getattr(config, field.name))

    available_flow_config_fields = sorted(
        field_name for field_name in GENERATED_FLOW_CONFIG_FIELDS if getattr(config, field_name) is not None
    )
    generated_flow_configs = {
        "included": include_flow_configs,
        "available_fields": available_flow_config_fields,
        "values": (
            {field_name: sanitize_json(getattr(config, field_name)) for field_name in available_flow_config_fields}
            if include_flow_configs
            else None
        ),
    }

    return {
        "config": fields,
        "summary": _serialize_config_summary(config, index_set_map),
        "flow_references": _flow_references(config),
        "generated_flow_configs": generated_flow_configs,
        "result_table_references": _result_table_references(config),
        "access_tasks": {
            "task_records": sanitize_json(config.task_records or []),
            "task_detail_ids": sorted((config.task_details or {}).keys()),
        },
    }


def _serialize_config_summary(config, index_set_map):
    primary_index = index_set_map.get(config.index_set_id)
    new_class_index = index_set_map.get(config.new_cls_index_set_id)
    return {
        "config_id": config.id,
        "bk_biz_id": config.bk_biz_id,
        "index_set_id": config.index_set_id,
        "index_set_name": primary_index.index_set_name if primary_index else None,
        "new_cls_index_set_id": config.new_cls_index_set_id,
        "new_cls_index_set_name": new_class_index.index_set_name if new_class_index else None,
        "collector_config_id": config.collector_config_id,
        "collector_config_name_en": config.collector_config_name_en,
        "signature_enable": config.signature_enable,
        "access_finished_stored": config.access_finished,
        "storage_type": config.storage_type,
        "flow_references": _flow_references(config),
        "result_table_references": _result_table_references(config),
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "created_by": config.created_by,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "updated_by": config.updated_by,
    }


def _flow_references(config):
    references = []
    for role, field_name in (
        ("pre_treat", "pre_treat_flow_id"),
        ("after_treat", "after_treat_flow_id"),
        ("predict", "predict_flow_id"),
        ("log_count_aggregation", "log_count_aggregation_flow_id"),
    ):
        flow_id = getattr(config, field_name)
        if flow_id:
            references.append({"role": role, "flow_id": flow_id})
    return references


def _result_table_references(config):
    references = []
    for role, field_name in (
        ("etl", "bkdata_etl_result_table_id"),
        ("source", "source_rt_name"),
        ("model_output", "model_output_rt"),
        ("clustered", "clustered_rt"),
        ("signature_pattern", "signature_pattern_rt"),
        ("new_class_pattern", "new_cls_pattern_rt"),
        ("new_class_strategy", "new_cls_strategy_output"),
        ("normal_strategy", "normal_strategy_output"),
    ):
        result_table_id = getattr(config, field_name)
        if result_table_id:
            references.append({"role": role, "result_table_id": result_table_id})
    return references


def _index_set_map(configs):
    index_set_ids = {
        index_set_id
        for config in configs
        for index_set_id in (config.index_set_id, config.new_cls_index_set_id)
        if index_set_id
    }
    return {item.index_set_id: item for item in LogIndexSet.objects.filter(index_set_id__in=index_set_ids)}
