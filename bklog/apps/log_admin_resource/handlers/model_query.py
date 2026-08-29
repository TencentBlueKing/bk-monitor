from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DataError
from django.db.models import Q, Subquery

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import sanitize_sensitive_text
from apps.utils.local import get_request_tenant_id


DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MASKED_VALUE = "***"
LOOKUPS_EXACT = frozenset({"exact", "in", "isnull"})
LOOKUPS_TEXT = frozenset({"exact", "in", "contains", "startswith", "endswith", "isnull"})
LOOKUPS_ORDERED = frozenset({"exact", "in", "gte", "lte", "isnull"})
LOOKUPS_JSON = frozenset({"exact", "contains", "isnull"})
ALL_LOOKUPS = LOOKUPS_EXACT | LOOKUPS_TEXT | LOOKUPS_ORDERED | LOOKUPS_JSON

SENSITIVE_FIELD_PATTERN = re.compile(
    r"(^|_)(password|passwd|passphrase|secret|token|authorization|cookie|private_key|access_key|app_secret)($|_)",
    re.IGNORECASE,
)
SENSITIVE_TREE_KEY_PATTERN = re.compile(
    r"PASSWORD|PASSWD|PASSPHRASE|SECRET|TOKEN|AUTHORIZATION|COOKIE|PRIVATE|CREDENTIAL|WEBHOOK"
    r"|API_?KEY|ACCESS_KEY|APP_KEY|AES|RSA|DSN|BROKER|ACCOUNT|SALT|CIPHER",
    re.IGNORECASE,
)
CREDENTIAL_URL_PATTERN = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
GLOBAL_CONFIG_SENSITIVE_KEY_PATTERN = re.compile(
    r"SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|CREDENTIAL|WEBHOOK"
    r"|API_KEY|ACCESS_KEY|APP_KEY|AES|RSA|DSN|BROKER|ACCOUNT|SALT|CIPHER",
    re.IGNORECASE,
)

AUDIT_EXACT_FIELDS = ("created_by", "updated_by")
AUDIT_TIME_FIELDS = ("created_at", "updated_at")
SOFT_DELETE_EXACT_FIELDS = ("is_deleted", "deleted_by")
SOFT_DELETE_TIME_FIELDS = ("deleted_at",)


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    domain: str
    app_label: str
    model_name: str
    summary: str
    field_lookups: dict[str, frozenset[str]]
    default_fields: tuple[str, ...]
    allowed_order_by: tuple[str, ...]
    default_order_by: tuple[str, ...]
    scope: str
    server_scope: str
    max_limit: int = MAX_LIMIT
    manager_name: str = "objects"
    fixed_filters: dict[str, Any] = field(default_factory=dict)
    row_masker: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None
    row_mask_note: str = "JSON/object values are recursively redacted by sensitive key and credential URL shape."
    examples: tuple[dict[str, Any], ...] = ()


def _model_spec(
    alias,
    *,
    exact=(),
    text=(),
    ordered=(),
    json_fields=(),
    default=(),
    order_by=(),
    default_order_by=(),
    scope="global",
    summary="",
    audit=False,
    soft_delete=False,
    max_limit=MAX_LIMIT,
    fixed_filters=None,
    row_masker=None,
    examples=(),
):
    domain, model_name = alias.split(".", 1)
    field_lookups: dict[str, set[str]] = {}

    def add_fields(names, lookups):
        for name in names:
            field_lookups.setdefault(name, set()).update(lookups)

    add_fields(exact, LOOKUPS_EXACT)
    add_fields(text, LOOKUPS_TEXT)
    add_fields(ordered, LOOKUPS_ORDERED)
    add_fields(json_fields, LOOKUPS_JSON)
    if audit:
        add_fields(AUDIT_EXACT_FIELDS, LOOKUPS_EXACT)
        add_fields(AUDIT_TIME_FIELDS, LOOKUPS_ORDERED)
    if soft_delete:
        add_fields(SOFT_DELETE_EXACT_FIELDS, LOOKUPS_EXACT)
        add_fields(SOFT_DELETE_TIME_FIELDS, LOOKUPS_ORDERED)

    all_fields = set(field_lookups)
    default_fields = tuple(default or sorted(all_fields))
    allowed_order_by = tuple(order_by or default_fields[:1])
    normalized_default_order = tuple(default_order_by or allowed_order_by[:1])
    normalized_examples = tuple(examples) or (
        {
            "fields": list(default_fields),
            "order_by": list(normalized_default_order),
            "limit": min(DEFAULT_LIMIT, max_limit),
        },
    )
    scope_notes = {
        "global": "Environment-global control-plane facts; no business row scope exists on this model.",
        "tenant": "Forced to the current request tenant through bk_tenant_id.",
        "space": "Forced to space_uid values owned by the current request tenant.",
        "biz": "Forced to business IDs owned by the current request tenant; global bk_biz_id=0 rows remain visible.",
        "op_biz": "Forced to op_bk_biz_id values owned by the current request tenant.",
        "index_set": "Forced to index sets whose space belongs to the current request tenant.",
        "collector": "Forced through collector_config_id to collectors in the current request tenant.",
        "link": "Forced through link_id to extract links in the current request tenant.",
        "rule": "Forced through rule_id to collector configurations in the current request tenant.",
        "model": "Forced through model_id to clustering configurations in the current request tenant.",
    }
    return ModelSpec(
        alias=alias,
        domain=domain,
        app_label=domain,
        model_name=model_name,
        summary=summary or f"Read-only diagnostic facts for {alias}.",
        field_lookups={name: frozenset(lookups) for name, lookups in field_lookups.items()},
        default_fields=default_fields,
        allowed_order_by=allowed_order_by,
        default_order_by=normalized_default_order,
        scope=scope,
        server_scope=scope_notes[scope],
        max_limit=max_limit,
        manager_name="origin_objects" if soft_delete else "objects",
        fixed_filters=dict(fixed_filters or {}),
        row_masker=row_masker,
        examples=normalized_examples,
    )


def _mask_sensitive_tree(value):
    if isinstance(value, dict):
        return {
            key: MASKED_VALUE
            if isinstance(key, str) and SENSITIVE_TREE_KEY_PATTERN.search(key)
            else _mask_sensitive_tree(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask_sensitive_tree(item) for item in value]
    if isinstance(value, str):
        if CREDENTIAL_URL_PATTERN.search(value):
            return MASKED_VALUE
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return sanitize_sensitive_text(value, maximum=None)
            return json.dumps(_mask_sensitive_tree(parsed), ensure_ascii=False, default=str)
        return sanitize_sensitive_text(value, maximum=None)
    return value


def _mask_global_config_row(item, instance):
    if "configs" not in item:
        return item
    config_id = str(getattr(instance, "config_id", "") or "")
    if GLOBAL_CONFIG_SENSITIVE_KEY_PATTERN.search(config_id):
        item["configs"] = MASKED_VALUE
    return item


SPECS = {
    spec.alias: spec
    for spec in (
        _model_spec(
            "feature_toggle.FeatureToggle",
            exact=("id", "name", "alias", "status", "is_viewed"),
            text=("description",),
            json_fields=("feature_config", "biz_id_white_list", "biz_id_black_list"),
            default=("id", "name", "status", "is_viewed", "is_deleted", "updated_at"),
            order_by=("id", "name", "updated_at"),
            default_order_by=("name",),
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_clustering.SampleSet",
            exact=("id", "sample_set_id"),
            text=("sample_set_name",),
            default=("sample_set_id", "sample_set_name", "is_deleted", "updated_at"),
            order_by=("sample_set_id", "updated_at"),
            default_order_by=("sample_set_id",),
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.AiopsModel",
            exact=("id", "model_id"),
            text=("model_name",),
            default=("model_id", "model_name", "is_deleted", "updated_at"),
            order_by=("model_id", "updated_at"),
            default_order_by=("model_id",),
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.AiopsModelExperiment",
            exact=("id", "model_id", "experiment_id", "status", "basic_model_id"),
            text=("experiment_alias",),
            json_fields=("node_id_list",),
            default=("experiment_id", "experiment_alias", "model_id", "status", "is_deleted"),
            order_by=("experiment_id", "model_id", "updated_at"),
            default_order_by=("-experiment_id",),
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.AiopsSignatureAndPattern",
            exact=("id", "model_id", "signature"),
            text=("pattern", "origin_pattern", "label", "origin_log"),
            json_fields=("remark", "owners"),
            default=("id", "model_id", "signature", "pattern", "label", "is_deleted"),
            order_by=("id", "model_id", "updated_at"),
            default_order_by=("-id",),
            scope="model",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_clustering.ClusteringRemark",
            exact=(
                "id",
                "bk_biz_id",
                "signature",
                "group_hash",
                "strategy_id",
                "strategy_enabled",
                "source_app_code",
                "notice_group_id",
            ),
            text=("origin_pattern",),
            json_fields=("groups", "remark", "owners"),
            default=("id", "bk_biz_id", "signature", "strategy_id", "strategy_enabled", "is_deleted"),
            order_by=("id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.ClusteringConfig",
            exact=(
                "id",
                "collector_config_id",
                "collector_config_name_en",
                "index_set_id",
                "sample_set_id",
                "model_id",
                "min_members",
                "max_log_length",
                "is_case_sensitive",
                "depth",
                "max_child",
                "bk_biz_id",
                "related_space_pre_bk_biz_id",
                "new_cls_index_set_id",
                "bkdata_data_id",
                "log_bk_data_id",
                "signature_enable",
                "pre_treat_flow_id",
                "after_treat_flow_id",
                "predict_flow_id",
                "online_task_id",
                "log_count_aggregation_flow_id",
                "new_cls_strategy_enable",
                "normal_strategy_enable",
                "access_finished",
                "regex_rule_type",
                "regex_template_id",
                "use_mini_link",
                "storage_type",
            ),
            text=(
                "clustering_fields",
                "max_dist_list",
                "st_list",
                "predefined_varibles",
                "delimeter",
                "new_cls_pattern_rt",
                "bkdata_etl_result_table_id",
                "bkdata_etl_processing_id",
                "source_rt_name",
                "category_id",
                "es_storage",
                "model_output_rt",
                "clustered_rt",
                "signature_pattern_rt",
                "new_cls_strategy_output",
                "normal_strategy_output",
                "predict_cluster",
                "doris_storage",
            ),
            json_fields=(
                "group_fields",
                "filter_rules",
                "pre_treat_flow",
                "after_treat_flow",
                "modify_flow",
                "options",
                "task_records",
                "task_details",
                "predict_flow",
                "log_count_aggregation_flow",
            ),
            default=(
                "id",
                "bk_biz_id",
                "collector_config_id",
                "index_set_id",
                "model_id",
                "access_finished",
                "storage_type",
                "is_deleted",
                "updated_at",
            ),
            order_by=("id", "bk_biz_id", "collector_config_id", "index_set_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_clustering.SignatureStrategySettings",
            exact=(
                "id",
                "signature",
                "index_set_id",
                "strategy_id",
                "enabled",
                "bk_biz_id",
                "pattern_level",
                "strategy_type",
            ),
            default=("id", "bk_biz_id", "index_set_id", "signature", "strategy_id", "enabled", "is_deleted"),
            order_by=("id", "bk_biz_id", "index_set_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.NoticeGroup",
            exact=("id", "index_set_id", "notice_group_id", "bk_biz_id"),
            default=("id", "bk_biz_id", "index_set_id", "notice_group_id", "is_deleted"),
            order_by=("id", "bk_biz_id", "index_set_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.ClusteringSubscription",
            exact=(
                "id",
                "subscription_type",
                "space_uid",
                "index_set_id",
                "pattern_level",
                "log_display_count",
                "log_col_show_type",
                "year_on_year_hour",
                "year_on_year_change",
                "is_show_new_pattern",
                "is_enabled",
            ),
            text=("title", "query_string"),
            json_fields=("receivers", "managers", "frequency", "group_by", "addition", "host_scopes"),
            ordered=("last_run_at",),
            default=(
                "id",
                "space_uid",
                "index_set_id",
                "title",
                "subscription_type",
                "is_enabled",
                "last_run_at",
                "is_deleted",
            ),
            order_by=("id", "space_uid", "index_set_id", "last_run_at", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="space",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_clustering.RegexTemplate",
            exact=("id", "space_uid"),
            text=("template_name", "predefined_varibles"),
            default=("id", "space_uid", "template_name"),
            order_by=("id", "space_uid", "template_name"),
            default_order_by=("-id",),
            scope="space",
        ),
        _model_spec(
            "log_commons.ExternalPermission",
            exact=("id", "space_uid", "authorized_user", "action_id"),
            json_fields=("resources",),
            ordered=("expire_time",),
            default=("id", "space_uid", "authorized_user", "action_id", "expire_time", "updated_at"),
            order_by=("id", "space_uid", "expire_time", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="space",
            audit=True,
        ),
        _model_spec(
            "log_commons.ExternalPermissionApplyRecord",
            exact=("id", "space_uid", "action_id", "operate", "approval_sn", "status"),
            json_fields=("authorized_users", "resources"),
            ordered=("expire_time",),
            default=("id", "space_uid", "action_id", "operate", "approval_sn", "status", "expire_time", "updated_at"),
            order_by=("id", "space_uid", "status", "expire_time", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="space",
            audit=True,
        ),
        _model_spec(
            "log_databus.CollectorConfig",
            exact=(
                "collector_config_id",
                "bk_biz_id",
                "bkdata_biz_id",
                "collector_plugin_id",
                "bk_app_code",
                "collector_scenario_id",
                "custom_type",
                "category_id",
                "target_object_type",
                "target_node_type",
                "is_active",
                "data_link_id",
                "bk_data_id",
                "table_id",
                "bkbase_table_id",
                "processing_id",
                "etl_processor",
                "subscription_id",
                "bkdata_data_id",
                "index_set_id",
                "data_encoding",
                "itsm_ticket_sn",
                "itsm_ticket_status",
                "can_use_independent_es_cluster",
                "collector_package_count",
                "collector_output_format",
                "storage_shards_nums",
                "storage_shards_size",
                "storage_replies",
                "collector_config_name_en",
                "environment",
                "bcs_cluster_id",
                "add_pod_label",
                "add_pod_annotation",
                "yaml_config_enabled",
                "rule_id",
                "is_display",
                "log_group_id",
                "is_nanos",
                "enable_v4",
                "storage_cluster_type",
                "clean_template_id",
            ),
            text=("collector_config_name", "bk_data_name", "description", "target_nodes", "params", "task_id_list"),
            json_fields=("collector_config_overlay", "extra_labels"),
            default=(
                "collector_config_id",
                "bk_biz_id",
                "collector_config_name",
                "collector_scenario_id",
                "is_active",
                "subscription_id",
                "bk_data_id",
                "index_set_id",
                "is_deleted",
                "updated_at",
            ),
            order_by=("collector_config_id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-collector_config_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.ContainerCollectorConfig",
            exact=(
                "id",
                "collector_config_id",
                "collector_type",
                "any_namespace",
                "data_encoding",
                "workload_type",
                "workload_name",
                "all_container",
                "status",
                "parent_container_config_id",
                "rule_id",
            ),
            text=("container_name", "container_name_exclude", "status_detail"),
            json_fields=(
                "namespaces",
                "namespaces_exclude",
                "params",
                "match_labels",
                "match_annotations",
                "match_expressions",
                "raw_config",
            ),
            default=(
                "id",
                "collector_config_id",
                "collector_type",
                "workload_type",
                "workload_name",
                "status",
                "is_deleted",
                "updated_at",
            ),
            order_by=("id", "collector_config_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="collector",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.BcsRule",
            exact=("id", "bcs_project_id"),
            text=("rule_name",),
            default=("id", "rule_name", "bcs_project_id", "is_deleted", "updated_at"),
            order_by=("id", "bcs_project_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="rule",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_databus.BcsStorageClusterConfig",
            exact=("id", "bk_biz_id", "bcs_cluster_id", "storage_cluster_id"),
            default=("id", "bk_biz_id", "bcs_cluster_id", "storage_cluster_id", "is_deleted", "updated_at"),
            order_by=("id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_databus.DataLinkConfig",
            exact=(
                "data_link_id",
                "link_group_name",
                "bk_biz_id",
                "kafka_cluster_id",
                "transfer_cluster_id",
                "is_active",
                "is_edge_transport",
                "bk_tenant_id",
            ),
            text=("description",),
            json_fields=("es_cluster_ids", "deploy_options"),
            default=(
                "data_link_id",
                "link_group_name",
                "bk_biz_id",
                "is_active",
                "bk_tenant_id",
                "is_deleted",
                "updated_at",
            ),
            order_by=("data_link_id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-data_link_id"),
            scope="tenant",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.StorageCapacity",
            exact=("id", "bk_biz_id"),
            ordered=("storage_capacity",),
            default=("id", "bk_biz_id", "storage_capacity", "updated_at"),
            order_by=("id", "bk_biz_id", "storage_capacity", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
        ),
        _model_spec(
            "log_databus.StorageUsed",
            exact=("id", "bk_biz_id", "storage_cluster_id", "index_count", "biz_count"),
            ordered=("storage_used", "storage_usage", "storage_total"),
            default=(
                "id",
                "bk_biz_id",
                "storage_cluster_id",
                "storage_used",
                "storage_usage",
                "storage_total",
                "updated_at",
            ),
            order_by=("id", "bk_biz_id", "storage_cluster_id", "storage_usage", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
        ),
        _model_spec(
            "log_databus.BKDataClean",
            exact=(
                "id",
                "status",
                "status_en",
                "result_table_id",
                "raw_data_id",
                "data_type",
                "storage_type",
                "storage_cluster",
                "collector_config_id",
                "bk_biz_id",
                "log_index_set_id",
                "is_authorized",
                "etl_config",
            ),
            text=("result_table_name", "result_table_name_alias", "data_name", "data_alias"),
            default=(
                "id",
                "bk_biz_id",
                "collector_config_id",
                "result_table_id",
                "status",
                "storage_type",
                "log_index_set_id",
                "is_deleted",
                "updated_at",
            ),
            order_by=("id", "bk_biz_id", "collector_config_id", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_databus.CleanTemplate",
            exact=("clean_template_id", "name", "clean_type", "bk_biz_id", "visible_type", "status"),
            text=("visible_bk_biz_id", "description"),
            json_fields=("etl_params", "etl_fields", "alias_settings", "snapshot"),
            default=(
                "clean_template_id",
                "name",
                "clean_type",
                "bk_biz_id",
                "visible_type",
                "status",
                "is_deleted",
                "updated_at",
            ),
            order_by=("clean_template_id", "bk_biz_id", "name", "updated_at"),
            default_order_by=("-updated_at", "-clean_template_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.CleanStash",
            exact=("clean_stash_id", "clean_template_id", "clean_type", "collector_config_id", "bk_biz_id"),
            json_fields=("etl_params", "etl_fields"),
            default=(
                "clean_stash_id",
                "bk_biz_id",
                "collector_config_id",
                "clean_template_id",
                "clean_type",
                "is_deleted",
                "updated_at",
            ),
            order_by=("clean_stash_id", "bk_biz_id", "collector_config_id", "updated_at"),
            default_order_by=("-updated_at", "-clean_stash_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.ArchiveConfig",
            exact=(
                "archive_config_id",
                "instance_id",
                "instance_type",
                "bk_biz_id",
                "snapshot_days",
                "target_snapshot_repository_name",
            ),
            default=(
                "archive_config_id",
                "bk_biz_id",
                "instance_type",
                "instance_id",
                "snapshot_days",
                "is_deleted",
                "updated_at",
            ),
            order_by=("archive_config_id", "bk_biz_id", "instance_id", "updated_at"),
            default_order_by=("-updated_at", "-archive_config_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_databus.RestoreConfig",
            exact=(
                "restore_config_id",
                "bk_biz_id",
                "archive_config_id",
                "meta_restore_id",
                "is_done",
                "duration",
                "total_store_size",
                "total_doc_count",
                "index_set_id",
            ),
            text=("index_set_name", "notice_user"),
            ordered=("start_time", "end_time", "expired_time"),
            default=(
                "restore_config_id",
                "bk_biz_id",
                "archive_config_id",
                "index_set_id",
                "is_done",
                "start_time",
                "end_time",
                "is_deleted",
            ),
            order_by=("restore_config_id", "bk_biz_id", "index_set_id", "start_time", "updated_at"),
            default_order_by=("-updated_at", "-restore_config_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_databus.CollectorPlugin",
            exact=(
                "collector_plugin_id",
                "bk_biz_id",
                "bkdata_biz_id",
                "collector_plugin_name_en",
                "collector_scenario_id",
                "category_id",
                "data_encoding",
                "is_display_collector",
                "is_allow_alone_data_id",
                "bk_data_id",
                "data_link_id",
                "processing_id",
                "is_allow_alone_etl_config",
                "etl_processor",
                "etl_config",
                "table_id",
                "bkbase_table_id",
                "is_allow_alone_storage",
                "is_create_storage",
                "storage_cluster_id",
                "retention",
                "allocation_min_days",
                "storage_replies",
                "storage_shards_nums",
                "storage_shards_size",
            ),
            text=("collector_plugin_name", "description"),
            json_fields=("etl_params", "fields", "params", "index_settings"),
            default=(
                "collector_plugin_id",
                "bk_biz_id",
                "collector_plugin_name",
                "collector_scenario_id",
                "bk_data_id",
                "storage_cluster_id",
                "is_deleted",
                "updated_at",
            ),
            order_by=("collector_plugin_id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-collector_plugin_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
            max_limit=100,
        ),
        _model_spec(
            "log_databus.FieldDateFormat",
            exact=("id", "es_type", "timestamp_unit"),
            text=("name", "description", "es_format"),
            default=("id", "name", "es_format", "es_type", "timestamp_unit"),
            order_by=("id", "name", "created_at", "updated_at"),
            default_order_by=("id",),
            audit=True,
        ),
        _model_spec(
            "log_databus.GrokInfo",
            exact=("id", "bk_biz_id", "name", "is_builtin"),
            text=("pattern", "sample", "description"),
            json_fields=("sample_result",),
            default=("id", "bk_biz_id", "name", "pattern", "is_builtin", "updated_at"),
            order_by=("id", "bk_biz_id", "name", "created_at", "updated_at"),
            default_order_by=("name", "-id"),
            scope="biz",
            audit=True,
        ),
        _model_spec(
            "log_desensitize.DesensitizeRule",
            exact=("id", "rule_name", "operator", "space_uid", "is_public", "is_active"),
            text=("match_pattern",),
            json_fields=("params", "match_fields"),
            default=("id", "space_uid", "rule_name", "operator", "is_public", "is_active", "is_deleted", "updated_at"),
            order_by=("id", "space_uid", "rule_name", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="space",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_desensitize.DesensitizeConfig",
            exact=("id", "index_set_id"),
            json_fields=("text_fields",),
            default=("id", "index_set_id", "text_fields", "updated_at"),
            order_by=("id", "index_set_id", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="index_set",
            audit=True,
        ),
        _model_spec(
            "log_desensitize.DesensitizeFieldConfig",
            exact=("id", "index_set_id", "field_name", "rule_id", "operator", "sort_index"),
            text=("match_pattern",),
            json_fields=("params",),
            default=("id", "index_set_id", "field_name", "rule_id", "operator", "sort_index", "updated_at"),
            order_by=("id", "index_set_id", "sort_index", "created_at", "updated_at"),
            default_order_by=("index_set_id", "sort_index", "id"),
            scope="index_set",
            audit=True,
        ),
        _model_spec(
            "log_extract.Strategies",
            exact=("strategy_id", "bk_biz_id", "select_type", "operator"),
            text=("strategy_name", "user_list", "modules", "visible_dir", "file_type"),
            default=(
                "strategy_id",
                "bk_biz_id",
                "strategy_name",
                "select_type",
                "operator",
                "is_deleted",
                "updated_at",
            ),
            order_by=("strategy_id", "bk_biz_id", "updated_at"),
            default_order_by=("-updated_at", "-strategy_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_extract.ExtractLink",
            exact=(
                "link_id",
                "link_type",
                "operator",
                "op_bk_biz_id",
                "qcloud_cos_bucket",
                "qcloud_cos_region",
                "is_enable",
            ),
            text=("name",),
            default=(
                "link_id",
                "name",
                "link_type",
                "op_bk_biz_id",
                "qcloud_cos_bucket",
                "qcloud_cos_region",
                "is_enable",
                "updated_at",
            ),
            order_by=("link_id", "op_bk_biz_id", "name", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-link_id"),
            scope="op_biz",
            audit=True,
        ),
        _model_spec(
            "log_extract.ExtractLinkHost",
            exact=("id", "link_id", "bk_cloud_id", "ip"),
            text=("target_dir",),
            default=("id", "link_id", "bk_cloud_id", "ip", "target_dir"),
            order_by=("id", "link_id", "bk_cloud_id", "ip"),
            default_order_by=("link_id", "id"),
            scope="link",
        ),
        _model_spec(
            "log_search.GlobalConfig",
            exact=("config_id",),
            text=("configs",),
            default=("config_id", "configs"),
            order_by=("config_id",),
            default_order_by=("config_id",),
            row_masker=_mask_global_config_row,
            max_limit=100,
        ),
        _model_spec(
            "log_search.ProjectInfo",
            exact=(
                "project_id",
                "bk_biz_id",
                "bk_app_code",
                "time_zone",
                "ip_topo_switch",
                "is_v3_biz",
                "is_v3_mixed",
                "feature_toggle",
            ),
            text=("project_name", "description"),
            default=("project_id", "project_name", "bk_biz_id", "bk_app_code", "is_v3_biz", "is_deleted", "updated_at"),
            order_by=("project_id", "bk_biz_id", "project_name", "updated_at"),
            default_order_by=("-updated_at", "-project_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.AccessSourceConfig",
            exact=("source_id", "scenario_id", "space_uid", "project_id", "orders", "is_editable"),
            text=("source_name", "properties"),
            default=(
                "source_id",
                "source_name",
                "scenario_id",
                "space_uid",
                "orders",
                "is_editable",
                "is_deleted",
                "updated_at",
            ),
            order_by=("source_id", "space_uid", "orders", "updated_at"),
            default_order_by=("space_uid", "orders", "source_id"),
            scope="space",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.LogIndexSet",
            exact=(
                "index_set_id",
                "space_uid",
                "project_id",
                "category_id",
                "bkdata_project_id",
                "collector_config_id",
                "scenario_id",
                "storage_cluster_id",
                "source_id",
                "orders",
                "pre_check_tag",
                "is_active",
                "is_trace_log",
                "source_app_code",
                "time_field",
                "time_field_type",
                "time_field_unit",
                "bcs_project_id",
                "is_editable",
                "result_window",
                "max_analyzed_offset",
                "max_async_count",
                "support_doris",
                "doris_table_id",
                "is_group",
                "is_platform_index",
            ),
            text=("index_set_name", "view_roles", "pre_check_msg", "fields_snapshot", "tag_ids"),
            json_fields=(
                "target_fields",
                "sort_fields",
                "query_alias_settings",
                "platform_index_visibility",
                "platform_index_filter",
            ),
            default=(
                "index_set_id",
                "index_set_name",
                "space_uid",
                "collector_config_id",
                "scenario_id",
                "is_active",
                "is_group",
                "is_deleted",
                "updated_at",
            ),
            order_by=("index_set_id", "space_uid", "collector_config_id", "orders", "updated_at"),
            default_order_by=("-updated_at", "-index_set_id"),
            scope="space",
            audit=True,
            soft_delete=True,
            max_limit=200,
            examples=(
                {
                    "filter": {"space_uid": "bkcc__2", "index_set_id__in": [1001, 1002]},
                    "fields": ["index_set_id", "index_set_name", "space_uid", "collector_config_id"],
                    "order_by": ["-index_set_id"],
                    "limit": 20,
                },
            ),
        ),
        _model_spec(
            "log_search.LogIndexSetData",
            exact=(
                "index_id",
                "index_set_id",
                "bk_biz_id",
                "result_table_id",
                "time_field",
                "apply_status",
                "scenario_id",
                "storage_cluster_id",
                "time_field_type",
                "time_field_unit",
                "type",
            ),
            text=("result_table_name",),
            default=(
                "index_id",
                "index_set_id",
                "bk_biz_id",
                "result_table_id",
                "apply_status",
                "storage_cluster_id",
                "type",
                "is_deleted",
                "updated_at",
            ),
            order_by=("index_id", "index_set_id", "bk_biz_id", "updated_at"),
            default_order_by=("index_set_id", "index_id"),
            scope="biz",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.ResourceChange",
            exact=(
                "id",
                "space_uid",
                "project_id",
                "change_type",
                "group_id",
                "resource_id",
                "resource_scope_id",
                "sync_status",
            ),
            ordered=("sync_time",),
            default=(
                "id",
                "space_uid",
                "change_type",
                "resource_id",
                "resource_scope_id",
                "sync_status",
                "sync_time",
                "updated_at",
            ),
            order_by=("id", "space_uid", "sync_status", "sync_time", "created_at", "updated_at"),
            default_order_by=("-updated_at", "-id"),
            scope="space",
            audit=True,
        ),
        _model_spec(
            "log_search.IndexSetTag",
            exact=("tag_id", "space_uid", "name", "value", "color", "tag_type"),
            default=("tag_id", "space_uid", "name", "value", "color", "tag_type"),
            order_by=("tag_id", "space_uid", "name"),
            default_order_by=("space_uid", "name", "tag_id"),
            scope="space",
        ),
        _model_spec(
            "log_search.BizProperty",
            exact=("id", "bk_biz_id", "biz_property_id"),
            text=("biz_property_name", "biz_property_value"),
            default=("id", "bk_biz_id", "biz_property_id", "biz_property_name", "biz_property_value"),
            order_by=("id", "bk_biz_id", "biz_property_id"),
            default_order_by=("bk_biz_id", "biz_property_id", "id"),
            scope="biz",
        ),
        _model_spec(
            "log_search.SpaceType",
            exact=("type_id",),
            text=("type_name",),
            json_fields=("properties",),
            default=("type_id", "type_name", "properties", "is_deleted", "updated_at"),
            order_by=("type_id", "type_name", "updated_at"),
            default_order_by=("type_id",),
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.Space",
            exact=("id", "space_uid", "bk_biz_id", "space_type_id", "space_id", "space_code", "bk_tenant_id"),
            text=("space_type_name", "space_name"),
            json_fields=("properties",),
            default=(
                "id",
                "space_uid",
                "bk_biz_id",
                "space_type_id",
                "space_id",
                "space_name",
                "bk_tenant_id",
                "is_deleted",
            ),
            order_by=("id", "space_uid", "bk_biz_id", "space_type_id", "space_id", "updated_at"),
            default_order_by=("space_type_id", "space_id", "id"),
            scope="tenant",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.IndexSetFieldsConfig",
            exact=("id", "name", "index_set_id", "scope", "source_app_code", "index_set_ids_hash", "index_set_type"),
            text=("display_fields", "sort_list"),
            json_fields=("index_set_ids",),
            default=("id", "name", "index_set_id", "scope", "source_app_code", "index_set_type"),
            order_by=("id", "index_set_id", "name"),
            default_order_by=("index_set_id", "id"),
            scope="index_set",
        ),
        _model_spec(
            "log_search.StorageClusterRecord",
            exact=("id", "index_set_id", "storage_cluster_id"),
            default=("id", "index_set_id", "storage_cluster_id", "is_deleted", "updated_at"),
            order_by=("id", "index_set_id", "storage_cluster_id", "updated_at"),
            default_order_by=("index_set_id", "-updated_at", "-id"),
            scope="index_set",
            audit=True,
            soft_delete=True,
        ),
        _model_spec(
            "log_search.IndexSetCustomConfig",
            exact=("id", "index_set_id", "index_set_hash"),
            json_fields=("index_set_ids", "index_set_config"),
            default=("id", "index_set_id", "index_set_ids", "index_set_hash", "index_set_config"),
            order_by=("id", "index_set_id", "index_set_hash"),
            default_order_by=("index_set_id", "id"),
            scope="index_set",
            max_limit=100,
        ),
        _model_spec(
            "log_search.SceneFieldsConfig",
            exact=("id", "name", "bk_biz_id", "scene_id", "scope", "source_app_code"),
            text=("display_fields", "sort_list"),
            default=("id", "name", "bk_biz_id", "scene_id", "scope", "source_app_code", "updated_at"),
            order_by=("id", "bk_biz_id", "scene_id", "name", "created_at", "updated_at"),
            default_order_by=("bk_biz_id", "scene_id", "id"),
            scope="biz",
            audit=True,
        ),
        _model_spec(
            "tgpa.TGPATask",
            exact=("id", "task_id", "task_type", "bk_biz_id", "task_status", "file_status", "process_status"),
            text=("log_path", "error_message"),
            ordered=("processed_at", "created_at"),
            default=(
                "id",
                "task_id",
                "task_type",
                "bk_biz_id",
                "task_status",
                "file_status",
                "process_status",
                "processed_at",
                "created_at",
            ),
            order_by=("id", "task_id", "bk_biz_id", "processed_at", "created_at"),
            default_order_by=("-created_at", "-id"),
            scope="biz",
        ),
        _model_spec(
            "tgpa.TGPAReportSyncRecord",
            exact=("id", "bk_biz_id", "status", "created_by"),
            text=("error_message",),
            json_fields=("openid_list", "file_name_list"),
            ordered=("created_at",),
            default=("id", "bk_biz_id", "status", "created_by", "created_at"),
            order_by=("id", "bk_biz_id", "status", "created_at"),
            default_order_by=("-created_at", "-id"),
            scope="biz",
        ),
        _model_spec(
            "tgpa.TGPAReport",
            exact=("id", "bk_biz_id", "file_name", "openid", "process_status", "record_id"),
            text=("error_message",),
            ordered=("processed_at",),
            default=("id", "bk_biz_id", "file_name", "openid", "process_status", "record_id", "processed_at"),
            order_by=("id", "bk_biz_id", "record_id", "processed_at"),
            default_order_by=("-processed_at", "-id"),
            scope="biz",
        ),
    )
}


def list_model_specs(params):
    params = params or {}
    domain = str(params.get("domain") or "").strip()
    available = [spec for spec in SPECS.values() if _is_model_available(spec) and (not domain or spec.domain == domain)]
    if domain and not available:
        raise ValidationError(f"unknown or unavailable model domain: {domain}")
    items = [
        {"model": spec.alias, "domain": spec.domain, "summary": spec.summary, "safety_level": "read"}
        for spec in sorted(available, key=lambda item: item.alias)
    ]
    return {
        "count": len(items),
        "items": items,
        "next_call": {"func_name": "bklog.model.detail", "params": {"model": "<items[].model>"}},
    }


def get_model_spec_detail(params):
    spec, _model = _resolve_model(str((params or {}).get("model") or "").strip())
    return _serialize_spec(spec)


def query_model(params):
    params = params or {}
    spec, model = _resolve_model(str(params.get("model") or "").strip())
    limit = _normalize_limit(params.get("limit"), spec.max_limit)
    selected_fields = _normalize_selected_fields(params.get("fields"), params.get("exclude_fields"), spec)
    filters = _normalize_filter(params.get("filter", {}), spec)
    ordering = _normalize_order_by(params.get("order_by"), spec)

    queryset = getattr(model, spec.manager_name).all()
    queryset = _apply_scope(queryset, spec)
    try:
        queryset = queryset.filter(**filters)
        if ordering:
            queryset = queryset.order_by(*ordering)
        rows = list(queryset[: limit + 1])
    except (DjangoValidationError, DataError, TypeError, ValueError) as error:
        raise ValidationError("filter values are incompatible with the selected model fields") from error
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for row in rows:
        item = _serialize_instance(row, selected_fields)
        if spec.row_masker:
            item = spec.row_masker(item, row)
        items.append(item)
    return {
        "model": spec.alias,
        "fields": list(selected_fields),
        "count": len(items),
        "limit": limit,
        "has_more": has_more,
        "items": items,
        "scope": spec.server_scope,
    }


def _serialize_spec(spec):
    return {
        "model": spec.alias,
        "domain": spec.domain,
        "summary": spec.summary,
        "default_fields": list(spec.default_fields),
        "allowed_fields": sorted(spec.field_lookups),
        "field_lookups": {name: sorted(lookups) for name, lookups in sorted(spec.field_lookups.items())},
        "allowed_order_by": list(spec.allowed_order_by),
        "default_order_by": list(spec.default_order_by),
        "default_limit": min(DEFAULT_LIMIT, spec.max_limit),
        "max_limit": spec.max_limit,
        "fixed_filters": spec.fixed_filters,
        "server_scope": spec.server_scope,
        "manager": spec.manager_name,
        "row_masking": spec.row_mask_note,
        "examples": list(spec.examples),
        "next_call": {"func_name": "bklog.model.query", "params": {"model": spec.alias}},
    }


def _is_model_available(spec):
    try:
        django_apps.get_model(spec.app_label, spec.model_name)
    except LookupError:
        return False
    return True


def _resolve_model(alias):
    spec = SPECS.get(alias)
    if spec is None:
        raise ValidationError(f"model is outside the Resource Call allowlist: {alias}")
    try:
        model = django_apps.get_model(spec.app_label, spec.model_name)
    except LookupError:
        raise ValidationError(f"model is unavailable in this environment: {alias}")
    _validate_spec(spec, model)
    return spec, model


def _validate_spec(spec, model):
    concrete_fields = {}
    for model_field in model._meta.get_fields():
        if not getattr(model_field, "concrete", False):
            continue
        concrete_fields[model_field.name] = model_field
        attname = getattr(model_field, "attname", model_field.name)
        concrete_fields[attname] = model_field

    for field_name, lookups in spec.field_lookups.items():
        model_field = concrete_fields.get(field_name)
        if model_field is None:
            raise RuntimeError(f"invalid ModelSpec field: {spec.alias}.{field_name}")
        if model_field.is_relation and field_name == model_field.name:
            raise RuntimeError(f"relation object is forbidden in ModelSpec: {spec.alias}.{field_name}")
        if SENSITIVE_FIELD_PATTERN.search(field_name) or SENSITIVE_TREE_KEY_PATTERN.search(field_name):
            raise RuntimeError(f"sensitive field is forbidden in ModelSpec: {spec.alias}.{field_name}")
        if not lookups or not set(lookups).issubset(ALL_LOOKUPS):
            raise RuntimeError(f"invalid ModelSpec lookups: {spec.alias}.{field_name}")
    if not set(spec.default_fields).issubset(spec.field_lookups):
        raise RuntimeError(f"default fields are outside ModelSpec allowlist: {spec.alias}")
    if not set(spec.fixed_filters).issubset(spec.field_lookups):
        raise RuntimeError(f"fixed filters are outside ModelSpec allowlist: {spec.alias}")
    if not set(spec.allowed_order_by).issubset(spec.field_lookups):
        raise RuntimeError(f"order fields are outside ModelSpec allowlist: {spec.alias}")
    if not {item.lstrip("-") for item in spec.default_order_by}.issubset(spec.allowed_order_by):
        raise RuntimeError(f"default ordering is outside ModelSpec allowlist: {spec.alias}")
    if not hasattr(model, spec.manager_name):
        raise RuntimeError(f"ModelSpec manager does not exist: {spec.alias}.{spec.manager_name}")
    if spec.max_limit < 1 or spec.max_limit > MAX_LIMIT:
        raise RuntimeError(f"invalid ModelSpec max limit: {spec.alias}.{spec.max_limit}")


def _normalize_limit(value, maximum):
    if value in (None, ""):
        return min(DEFAULT_LIMIT, maximum)
    if isinstance(value, bool):
        raise ValidationError("limit must be an integer")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError("limit must be an integer")
    if value < 1:
        raise ValidationError("limit must be positive")
    if value > maximum:
        raise ValidationError(f"limit must be at most {maximum}")
    return value


def _normalize_selected_fields(fields, exclude_fields, spec):
    if fields is None:
        selected = list(spec.default_fields)
    else:
        if not isinstance(fields, list) or not fields:
            raise ValidationError("fields must be a non-empty array")
        selected = [str(item) for item in fields]
    if exclude_fields is not None:
        if not isinstance(exclude_fields, list):
            raise ValidationError("exclude_fields must be an array")
        excluded = {str(item) for item in exclude_fields}
        _validate_fields(excluded, spec)
        selected = [item for item in selected if item not in excluded]
    _validate_fields(selected, spec)
    if not selected:
        raise ValidationError("field selection must not be empty")
    return tuple(dict.fromkeys(selected))


def _validate_fields(fields, spec):
    for field_name in fields:
        if field_name not in spec.field_lookups:
            if SENSITIVE_FIELD_PATTERN.search(field_name) or SENSITIVE_TREE_KEY_PATTERN.search(field_name):
                raise ValidationError(f"sensitive field is not readable: {field_name}")
            raise ValidationError(f"field is outside the ModelSpec allowlist: {field_name}")


def _normalize_filter(raw_filter, spec):
    if not isinstance(raw_filter, dict):
        raise ValidationError("filter must be an object")
    normalized = {}
    for raw_key, value in raw_filter.items():
        parts = str(raw_key or "").split("__")
        if len(parts) == 1:
            field_name, lookup = parts[0], "exact"
        elif len(parts) == 2:
            field_name, lookup = parts
        else:
            raise ValidationError(f"relation traversal is forbidden: {raw_key}")
        _validate_fields((field_name,), spec)
        if lookup not in ALL_LOOKUPS:
            raise ValidationError(f"unsupported lookup: {lookup}")
        if lookup not in spec.field_lookups[field_name]:
            raise ValidationError(f"lookup is not allowed for {field_name}: {lookup}")
        if lookup == "in" and (not isinstance(value, list) or not value or len(value) > MAX_LIMIT):
            raise ValidationError(f"{raw_key} must be a non-empty array with at most {MAX_LIMIT} items")
        if lookup == "isnull" and not isinstance(value, bool):
            raise ValidationError(f"{raw_key} must be boolean")
        normalized_key = field_name if lookup == "exact" else f"{field_name}__{lookup}"
        if normalized_key in normalized:
            raise ValidationError(f"duplicate filter: {normalized_key}")
        normalized[normalized_key] = value

    for fixed_field, fixed_value in spec.fixed_filters.items():
        for key, value in normalized.items():
            field_name, _, lookup = key.partition("__")
            if field_name == fixed_field and (lookup or "exact") != "exact":
                raise ValidationError(f"filter conflicts with fixed scope: {fixed_field}")
            if field_name == fixed_field and value != fixed_value:
                raise ValidationError(f"filter conflicts with fixed scope: {fixed_field}")
        normalized[fixed_field] = fixed_value
    return normalized


def _normalize_order_by(raw_order_by, spec):
    if raw_order_by is None:
        return list(spec.default_order_by)
    if not isinstance(raw_order_by, list):
        raise ValidationError("order_by must be an array")
    if len(raw_order_by) > 5:
        raise ValidationError("order_by must contain at most 5 fields")
    normalized = []
    for raw_field in raw_order_by:
        field = str(raw_field or "").strip()
        if not field:
            raise ValidationError("order_by fields must be non-empty strings")
        field_name = field[1:] if field.startswith("-") else field
        if field_name not in spec.allowed_order_by:
            raise ValidationError(f"order field is outside the ModelSpec allowlist: {field_name}")
        normalized.append(field)
    return normalized or list(spec.default_order_by)


def _apply_scope(queryset, spec):
    if spec.scope == "global":
        return queryset
    tenant_id = get_request_tenant_id()
    if not tenant_id:
        raise ValidationError("request tenant is required for this model")

    from apps.log_databus.models import CollectorConfig
    from apps.log_extract.models import ExtractLink
    from apps.log_search.models import LogIndexSet, Space

    tenant_spaces = Space.origin_objects.filter(bk_tenant_id=tenant_id)
    tenant_space_uids = tenant_spaces.values("space_uid")
    tenant_biz_ids = tenant_spaces.values("bk_biz_id")
    tenant_index_sets = LogIndexSet.origin_objects.filter(space_uid__in=Subquery(tenant_space_uids))

    if spec.scope == "tenant":
        return queryset.filter(bk_tenant_id=tenant_id)
    if spec.scope == "space":
        return queryset.filter(space_uid__in=Subquery(tenant_space_uids))
    if spec.scope == "biz":
        return queryset.filter(Q(bk_biz_id=0) | Q(bk_biz_id__in=Subquery(tenant_biz_ids)))
    if spec.scope == "op_biz":
        return queryset.filter(op_bk_biz_id__in=Subquery(tenant_biz_ids))
    if spec.scope == "index_set":
        return queryset.filter(index_set_id__in=Subquery(tenant_index_sets.values("index_set_id")))
    if spec.scope == "collector":
        tenant_collectors = CollectorConfig.origin_objects.filter(
            Q(bk_biz_id=0) | Q(bk_biz_id__in=Subquery(tenant_biz_ids))
        )
        return queryset.filter(collector_config_id__in=Subquery(tenant_collectors.values("collector_config_id")))
    if spec.scope == "link":
        tenant_links = ExtractLink.objects.filter(op_bk_biz_id__in=Subquery(tenant_biz_ids))
        return queryset.filter(link_id__in=Subquery(tenant_links.values("link_id")))
    if spec.scope == "rule":
        tenant_rules = CollectorConfig.origin_objects.filter(
            Q(bk_biz_id=0) | Q(bk_biz_id__in=Subquery(tenant_biz_ids)), rule_id__isnull=False
        )
        return queryset.filter(id__in=Subquery(tenant_rules.values("rule_id")))
    if spec.scope == "model":
        from apps.log_clustering.models import ClusteringConfig

        tenant_models = ClusteringConfig.origin_objects.filter(
            Q(bk_biz_id=0) | Q(bk_biz_id__in=Subquery(tenant_biz_ids))
        )
        return queryset.filter(model_id__in=Subquery(tenant_models.values("model_id")))
    raise RuntimeError(f"unsupported ModelSpec scope: {spec.scope}")


def _serialize_instance(instance, selected_fields):
    item = {}
    for field_name in selected_fields:
        try:
            value = getattr(instance, field_name)
            normalized = json.loads(json.dumps(value, default=str))
        except Exception:
            normalized = "<unserializable>"
        item[field_name] = _mask_sensitive_tree(normalized)
    return item


FUNCTIONS = {
    "bklog.model.list": {
        "func_name": "bklog.model.list",
        "description": "List the currently available allowlisted ModelSpecs without expanding field schemas.",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string", "maxLength": 64}},
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [{"params": {}}, {"params": {"domain": "log_search"}}],
    },
    "bklog.model.detail": {
        "func_name": "bklog.model.detail",
        "description": "Describe fields, lookups, limits, tenant scope, masking and examples for one ModelSpec.",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {"model": {"type": "string", "minLength": 1, "maxLength": 128}},
            "required": ["model"],
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [{"params": {"model": "log_search.LogIndexSet"}}],
    },
    "bklog.model.query": {
        "func_name": "bklog.model.query",
        "description": "Execute a bounded, tenant-scoped, read-only query against one allowlisted ModelSpec.",
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "minLength": 1, "maxLength": 128},
                "filter": {"type": "object"},
                "fields": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 200},
                "exclude_fields": {"type": "array", "items": {"type": "string"}, "maxItems": 200},
                "order_by": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
            },
            "required": ["model"],
            "additionalProperties": False,
        },
        "response_schema": {"type": "object"},
        "examples": [
            {
                "params": {
                    "model": "log_search.LogIndexSet",
                    "filter": {"space_uid": "bkcc__2", "index_set_id__in": [1001, 1002]},
                    "fields": ["index_set_id", "index_set_name", "space_uid", "collector_config_id"],
                    "order_by": ["-index_set_id"],
                    "limit": 20,
                }
            }
        ],
    },
}

HANDLERS = {
    "bklog.model.list": list_model_specs,
    "bklog.model.detail": get_model_spec_detail,
    "bklog.model.query": query_model,
}
