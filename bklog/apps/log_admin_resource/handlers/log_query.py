from __future__ import annotations

import copy
import json
from collections import defaultdict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import arrow
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from elasticsearch_dsl import Search

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import (
    SCENE_SEARCH,
    UNIFY_QUERY_SEARCH,
    UNIFY_QUERY_SEARCH_CLUSTERING,
)
from apps.log_admin_resource.handlers.inspection import sanitize_sensitive_text, scope_space_queryset
from apps.log_admin_resource.response_schema import object_schema
from apps.log_clustering.constants import (
    AGGS_FIELD_PREFIX,
    DEFULT_FILTER_NOT_CLUSTERING_OPERATOR,
    OwnerConfigEnum,
    PatternEnum,
    RemarkConfigEnum,
    StorageTypeEnum,
)
from apps.log_clustering.handlers.pattern import PatternHandler
from apps.log_clustering.models import ClusteringConfig
from apps.log_esquery.esquery.esquery import EsQuery
from apps.log_esquery.serializers import EsQueryMappingAttrSerializer
from apps.log_search.constants import MAX_RESULT_WINDOW, FieldDataTypeEnum, IndexSetDataType, SearchScopeEnum
from apps.log_search.handlers.index_set import BaseIndexSetHandler, IndexSetHandler
from apps.log_search.handlers.scene_search import AllConditionsBuilder
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers, AggsViewAdapter
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler as SearchHandlerEsquery
from apps.log_search.models import IndexSetTag, LogIndexSet, LogIndexSetData, Scenario, Space, TAG_TYPE_SCENE
from apps.log_unifyquery.constants import BASE_OP_MAP, FIELD_TYPE_MAP, AggTypeEnum
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.context import UnifyQueryContextHandler
from apps.log_unifyquery.handler.field import UnifyQueryFieldHandler
from apps.log_unifyquery.handler.pattern import UnifyQueryPatternHandler
from apps.log_unifyquery.handler.scene_field import SceneFieldHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.handler.scene_terms_aggs import SceneTermsAggsHandler
from apps.log_unifyquery.handler.terms_aggs import UnifyQueryTermsAggsHandler
from apps.utils.drf import custom_params_valid
from apps.utils.local import (
    del_local_param,
    get_local_param,
    get_request_tenant_id,
    set_local_param,
)
from bkm_space.utils import space_uid_to_bk_biz_id


SOURCE_INDEX_SET = "index_set"
SOURCE_SCENE = "scene"
SOURCE_CLUSTERING = "clustering"
MAX_QUERY_STRING_LENGTH = 4096
MAX_SEARCH_PAGE_SIZE = 200
MAX_PROJECTED_FIELDS = 50
MAX_SORT_FIELDS = 5
MAX_FILTERS = 50
MAX_AGG_BUCKETS = 100
MAX_CONTEXT_SIZE = 200
MAX_SCENE_TARGETS = 100
MAX_PATTERN_SIZE = 500
MAX_PATTERN_GROUP_FIELDS = 20
MAX_YEAR_ON_YEAR_HOURS = 31 * 24
MAX_LOG_ITEM_BYTES = 256 * 1024
MAX_LOG_FIELD_BYTES = 64 * 1024
MAX_LOG_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_AGG_RANGE_MILLISECONDS = 31 * 24 * 60 * 60 * 1000
ALLOWED_INTERVALS = {"auto", "1s", "10s", "30s", "1m", "5m", "10m", "30m", "1h", "6h", "12h", "1d"}
ALLOWED_FILTER_OPERATORS = set(BASE_OP_MAP)
_MISSING = object()

ERRORS = {
    "log_source_invalid": "3624101",
    "log_index_set_not_found": "3624102",
    "log_scene_invalid": "3624103",
    "log_time_range_invalid": "3624104",
    "log_query_limit_exceeded": "3624105",
    "log_context_anchor_invalid": "3624106",
    "log_context_source_mismatch": "3624107",
    "log_scene_disabled": "3624108",
    "log_query_timeout": "3624109",
    "log_query_rewrite_failed": "3624110",
    "log_query_execution_failed": "3624111",
    "log_clustering_config_not_found": "3624112",
    "log_clustering_result_table_missing": "3624113",
    "log_clustering_route_ambiguous": "3624114",
    "log_clustering_route_not_registered": "3624115",
    "log_clustering_pattern_failed": "3624116",
}


def _object(*required, properties=None, additional_properties=False):
    return object_schema(*required, properties=properties or {}, additional_properties=additional_properties)


SCENE_CONDITION_SCHEMA = _object(
    "field_name",
    "value",
    properties={
        "field_name": {"type": "string", "minLength": 1, "maxLength": 255},
        "value": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "uniqueItems": True,
            "items": {"type": "string", "maxLength": 255},
        },
        "op": {"type": "string", "enum": ["eq", "ne", "req", "nreq"], "default": "eq"},
    },
)

INDEX_SET_SOURCE_SCHEMA = _object(
    "type",
    "index_set_id",
    properties={
        "type": {"type": "string", "const": SOURCE_INDEX_SET},
        "index_set_id": {"type": "integer", "minimum": 1},
    },
)

SCENE_SOURCE_SCHEMA = _object(
    "type",
    "space_uid",
    "table_id_conditions",
    properties={
        "type": {"type": "string", "const": SOURCE_SCENE},
        "space_uid": {"type": "string", "minLength": 1, "maxLength": 256},
        "bk_biz_id": {"type": "integer", "minimum": 0},
        "table_id_conditions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": SCENE_CONDITION_SCHEMA,
            },
        },
        "scene_filter_values": {
            "type": "array",
            "maxItems": MAX_FILTERS,
            "items": {},
            "default": [],
        },
    },
)

CLUSTERING_SOURCE_SCHEMA = _object(
    "type",
    "index_set_id",
    properties={
        "type": {"type": "string", "const": SOURCE_CLUSTERING},
        "index_set_id": {"type": "integer", "minimum": 1},
    },
)

SOURCE_SCHEMA = {"oneOf": [INDEX_SET_SOURCE_SCHEMA, SCENE_SOURCE_SCHEMA]}
SEARCH_SOURCE_SCHEMA = {"oneOf": [INDEX_SET_SOURCE_SCHEMA, SCENE_SOURCE_SCHEMA, CLUSTERING_SOURCE_SCHEMA]}

TIME_RANGE_PROPERTIES = {
    "start_time": {"type": "integer", "minimum": 1},
    "end_time": {"type": "integer", "minimum": 1},
}

FILTER_SCHEMA = _object(
    "field",
    "operator",
    "value",
    properties={
        "field": {"type": "string", "minLength": 1, "maxLength": 255},
        "operator": {"type": "string", "enum": sorted(ALLOWED_FILTER_OPERATORS)},
        "value": {
            "anyOf": [
                {"type": "string", "maxLength": 4096},
                {
                    "type": "array",
                    "maxItems": 100,
                    "items": {"type": ["string", "integer", "number", "boolean"]},
                },
            ]
        },
        "condition": {"type": "string", "enum": ["and", "or"], "default": "and"},
    },
)

SCENE_SOURCE_SCHEMA["properties"]["scene_filter_values"]["items"] = FILTER_SCHEMA

SORT_SCHEMA = {
    "type": "array",
    "maxItems": MAX_SORT_FIELDS,
    "items": {
        "type": "array",
        "minItems": 2,
        "maxItems": 2,
        "items": {"anyOf": [{"type": "string", "minLength": 1, "maxLength": 255}]},
    },
}

FIELDS_PARAMS_SCHEMA = _object(
    "source",
    properties={
        "source": SOURCE_SCHEMA,
        **TIME_RANGE_PROPERTIES,
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "scope": {
            "type": "string",
            "enum": [choice[0] for choice in SearchScopeEnum.get_choices()],
            "default": SearchScopeEnum.DEFAULT.value,
        },
    },
)

SEARCH_PARAMS_SCHEMA = _object(
    "source",
    "start_time",
    "end_time",
    properties={
        "source": SEARCH_SOURCE_SCHEMA,
        **TIME_RANGE_PROPERTIES,
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "keyword": {"type": ["string", "null"], "maxLength": MAX_QUERY_STRING_LENGTH, "default": "*"},
        "addition": {"type": "array", "maxItems": MAX_FILTERS, "items": FILTER_SCHEMA, "default": []},
        "begin": {"type": "integer", "minimum": 0, "default": 0},
        "size": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_PAGE_SIZE, "default": 50},
        "sort_list": SORT_SCHEMA,
        "fields": {
            "type": "array",
            "maxItems": MAX_PROJECTED_FIELDS,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 255},
        },
        "track_total_hits": {"type": "boolean", "default": True},
        "is_desensitize": {"type": "boolean", "const": True, "default": True},
    },
)

AGGREGATION_SCHEMA = {
    "oneOf": [
        _object(
            "type",
            "field",
            properties={
                "type": {"type": "string", "const": "terms"},
                "field": {"type": "string", "minLength": 1, "maxLength": 255},
                "size": {"type": "integer", "minimum": 1, "maximum": MAX_AGG_BUCKETS, "default": 20},
            },
        ),
        _object(
            "type",
            properties={
                "type": {"type": "string", "const": "histogram"},
                "interval": {"type": "string", "enum": sorted(ALLOWED_INTERVALS), "default": "auto"},
                "group_field": {"type": ["string", "null"], "maxLength": 255},
            },
        ),
        _object(
            "type",
            "field",
            properties={
                "type": {"type": "string", "const": "field_stats"},
                "field": {"type": "string", "minLength": 1, "maxLength": 255},
            },
        ),
    ]
}

AGGREGATE_PARAMS_SCHEMA = _object(
    "source",
    "start_time",
    "end_time",
    "aggregation",
    properties={
        "source": SOURCE_SCHEMA,
        **TIME_RANGE_PROPERTIES,
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "keyword": {"type": ["string", "null"], "maxLength": MAX_QUERY_STRING_LENGTH, "default": "*"},
        "addition": {"type": "array", "maxItems": MAX_FILTERS, "items": FILTER_SCHEMA, "default": []},
        "is_desensitize": {"type": "boolean", "const": True, "default": True},
        "aggregation": AGGREGATION_SCHEMA,
    },
)

ANCHOR_VALUE_SCHEMA = {"type": ["string", "integer", "number", "boolean", "null"]}
CONTEXT_PARAMS_SCHEMA = _object(
    "source",
    "context_anchor",
    properties={
        "source": SEARCH_SOURCE_SCHEMA,
        "context_anchor": {
            "type": "object",
            "minProperties": 3,
            "maxProperties": 8,
            "properties": {
                "index_set_id": {"type": "integer", "minimum": 1},
                "result_table_id": {"type": "string", "minLength": 1, "maxLength": 255},
                "scenario_id": {"type": "string", "minLength": 1, "maxLength": 64},
                "sort_values": {
                    "type": "object",
                    "minProperties": 1,
                    "maxProperties": 50,
                    "additionalProperties": ANCHOR_VALUE_SCHEMA,
                },
                "identity": {
                    "type": "object",
                    "minProperties": 0,
                    "maxProperties": 20,
                    "additionalProperties": ANCHOR_VALUE_SCHEMA,
                },
            },
            "required": ["index_set_id", "scenario_id", "sort_values", "identity"],
            "additionalProperties": False,
        },
        "size": {"type": "integer", "minimum": 1, "maximum": MAX_CONTEXT_SIZE // 2, "default": 50},
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "is_desensitize": {"type": "boolean", "const": True, "default": True},
    },
)

PATTERN_ADDITION_SCHEMA = _object(
    "field",
    "operator",
    "value",
    properties={
        "field": {"type": "string", "minLength": 1, "maxLength": 255},
        "operator": {"type": "string", "enum": sorted(ALLOWED_FILTER_OPERATORS)},
        "value": {
            "anyOf": [
                {"type": "string", "maxLength": 4096},
                {
                    "type": "array",
                    "maxItems": 100,
                    "items": {"type": ["string", "integer", "number", "boolean"]},
                },
            ]
        },
        "condition": {"type": "string", "enum": ["and", "or"], "default": "and"},
    },
)

CLUSTERING_PATTERN_PARAMS_SCHEMA = _object(
    "source",
    "start_time",
    "end_time",
    properties={
        "source": CLUSTERING_SOURCE_SCHEMA,
        **TIME_RANGE_PROPERTIES,
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "keyword": {"type": ["string", "null"], "maxLength": MAX_QUERY_STRING_LENGTH, "default": ""},
        "addition": {
            "type": "array",
            "maxItems": MAX_FILTERS,
            "items": PATTERN_ADDITION_SCHEMA,
            "default": [],
        },
        "size": {"type": "integer", "minimum": 1, "maximum": MAX_PATTERN_SIZE, "default": 100},
        "group_by": {
            "type": "array",
            "maxItems": MAX_PATTERN_GROUP_FIELDS,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 255},
            "default": [],
        },
        "show_new_pattern": {"type": "boolean", "default": False},
        "filter_not_clustering": {"type": "boolean", "default": True},
        "year_on_year_hour": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_YEAR_ON_YEAR_HOURS,
            "default": 0,
        },
        "remark_config": {
            "type": "string",
            "enum": [choice[0] for choice in RemarkConfigEnum.get_choices()],
            "default": RemarkConfigEnum.ALL.value,
        },
        "owner_config": {
            "type": "string",
            "enum": [choice[0] for choice in OwnerConfigEnum.get_choices()],
            "default": OwnerConfigEnum.ALL.value,
        },
        "owners": {
            "type": "array",
            "maxItems": 100,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1, "maxLength": 128},
            "default": [],
        },
    },
)

SCENE_RESOLVE_PARAMS_SCHEMA = _object(
    "source",
    "start_time",
    "end_time",
    properties={
        "source": SCENE_SOURCE_SCHEMA,
        **TIME_RANGE_PROPERTIES,
        "time_zone": {"type": "string", "minLength": 1, "maxLength": 64},
        "keyword": {"type": ["string", "null"], "maxLength": MAX_QUERY_STRING_LENGTH, "default": "*"},
        "addition": {"type": "array", "maxItems": MAX_FILTERS, "items": FILTER_SCHEMA, "default": []},
    },
)

ROUTE_EVIDENCE_SCHEMA = _object(
    "source_type",
    "requested_source_type",
    "result_table_ids",
    "data_labels",
    "storage_types",
    "route_reason",
    "fallback",
    "partial",
    properties={
        "source_type": {"type": "string", "enum": [SOURCE_INDEX_SET, SOURCE_SCENE, SOURCE_CLUSTERING]},
        "requested_source_type": {
            "type": "string",
            "enum": [SOURCE_INDEX_SET, SOURCE_SCENE, SOURCE_CLUSTERING],
        },
        "entry_index_set_id": {"type": ["integer", "null"]},
        "actual_index_set_ids": {"type": "array", "items": {"type": "integer"}},
        "clustering_config_id": {"type": ["integer", "null"]},
        "canonical_index_set_id": {"type": ["integer", "null"]},
        "new_class_index_set_id": {"type": ["integer", "null"]},
        "clustered_rt": {"type": ["string", "null"]},
        "result_table_ids": {"type": "array", "items": {"type": "string"}},
        "data_labels": {"type": "array", "items": {"type": "string"}},
        "storage_types": {"type": "array", "items": {"type": "string"}},
        "route_reason": {"type": "string"},
        "entry_resolution_reason": {"type": ["string", "null"]},
        "query_backend": {"type": ["string", "null"], "enum": ["unify_query", "esquery", None]},
        "related_space_uids": {"type": "array", "items": {"type": "string"}},
        "fallback": {"type": "boolean"},
        "partial": {"type": "boolean"},
    },
)

SOURCE_RESPONSE_SCHEMA = _object(
    "type",
    "space_uid",
    "bk_biz_id",
    properties={
        "type": {"type": "string", "enum": [SOURCE_INDEX_SET, SOURCE_SCENE, SOURCE_CLUSTERING]},
        "space_uid": {"type": "string"},
        "bk_biz_id": {"type": "integer"},
        "index_set_id": {"type": "integer"},
        "table_id_conditions": {"type": "array", "items": {"type": "array"}},
        "scene_filter_values": {"type": "array", "items": FILTER_SCHEMA},
    },
)

WARNING_SCHEMA = _object(
    "code",
    "message",
    "scope",
    "retryable",
    properties={
        "code": {"type": "string"},
        "message": {"type": "string"},
        "scope": {"type": "string"},
        "retryable": {"type": "boolean"},
    },
)


def _response_schema(*required, properties=None):
    return _object(
        *required,
        "source",
        "status",
        "observed_at",
        "route",
        "warnings",
        properties={
            "source": SOURCE_RESPONSE_SCHEMA,
            "status": {"type": "string", "enum": ["success", "partial", "failed"]},
            "observed_at": {"type": "string", "format": "date-time"},
            "route": ROUTE_EVIDENCE_SCHEMA,
            "warnings": {"type": "array", "items": WARNING_SCHEMA},
            **(properties or {}),
        },
    )


FIELDS_RESPONSE_SCHEMA = _response_schema(
    "fields",
    "common_fields",
    "field_conflicts",
    properties={
        "fields": {},
        "common_fields": {"type": "array", "items": {"type": "string"}},
        "field_conflicts": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "missing_snapshot_index_set_ids": {"type": "array", "items": {"type": "integer"}},
    },
)

SEARCH_RESPONSE_SCHEMA = _response_schema(
    "items",
    "total",
    "took",
    "fields",
    "pagination",
    "truncation",
    properties={
        "items": {
            "type": "array",
            "items": _object(
                "record",
                "context_anchor",
                properties={
                    "record": {"type": "object", "additionalProperties": True},
                    "context_anchor": {"type": "object", "additionalProperties": True},
                },
            ),
        },
        "total": {"type": "integer", "minimum": 0},
        "took": {"type": "number", "minimum": 0},
        "fields": {},
        "pagination": _object(
            "begin",
            "size",
            "returned",
            "has_more",
            properties={
                "begin": {"type": "integer", "minimum": 0},
                "size": {"type": "integer", "minimum": 1},
                "returned": {"type": "integer", "minimum": 0},
                "has_more": {"type": "boolean"},
            },
        ),
        "truncation": {"type": "object", "additionalProperties": True},
    },
)

AGGREGATE_RESPONSE_SCHEMA = _response_schema(
    "aggregation",
    properties={
        "aggregation": {"type": "object", "additionalProperties": True},
        "buckets": {"type": "array", "items": {}},
        "stats": {"type": ["object", "null"], "additionalProperties": True},
    },
)

CONTEXT_RESPONSE_SCHEMA = _response_schema(
    "items",
    "anchor_index",
    "pagination",
    "truncation",
    properties={
        "items": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "anchor_index": {"type": "integer"},
        "pagination": {"type": "object", "additionalProperties": True},
        "truncation": {"type": "object", "additionalProperties": True},
        "total": {"type": "integer", "minimum": 0},
        "took": {"type": "number", "minimum": 0},
    },
)

SCENE_RESOLVE_RESPONSE_SCHEMA = _response_schema(
    "targets",
    "excluded",
    "field_conflicts",
    properties={
        "targets": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "excluded": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "field_conflicts": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "common_fields": {"type": "array", "items": {"type": "string"}},
    },
)

PATTERN_RESPONSE_SCHEMA = _response_schema(
    "items",
    properties={
        "items": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
        "enrichment": {"type": "object", "additionalProperties": True},
    },
)


class ResourceTimeZoneMixin:
    """Honor the Resource request timezone without mutating request-local state."""

    def init_base_dict(self):
        base_dict = super().init_base_dict()
        if self.search_params.get("time_zone"):
            base_dict["timezone"] = self.search_params["time_zone"]
        return base_dict

    def _init_scene_base_dict(self):
        base_dict = super()._init_scene_base_dict()
        if self.search_params.get("time_zone"):
            base_dict["timezone"] = self.search_params["time_zone"]
        return base_dict

    def query_ts_reference(self, search_dict, raise_exception=True):
        """Resource evidence queries must not turn downstream failures into empty success results."""

        return super().query_ts_reference(search_dict, raise_exception=True)


class ResourceUnifyQueryHandler(ResourceTimeZoneMixin, UnifyQueryHandler):
    pass


class ResourceUnifyQueryTermsAggsHandler(ResourceTimeZoneMixin, UnifyQueryTermsAggsHandler):
    pass


class ResourceUnifyQueryFieldHandler(ResourceTimeZoneMixin, UnifyQueryFieldHandler):
    pass


class ResourceUnifyQueryContextHandler(ResourceTimeZoneMixin, UnifyQueryContextHandler):
    pass


class ResourceScenePermissionMixin:
    """Replace the user-IAM hook with Resource Call's tenant and scene-space boundary."""

    def _resource_allowed_space_uids(self):
        return set(_related_space_uids(self.space_uid))

    def _resolve_table_id_from_conditions(self):
        table_id = super()._resolve_table_id_from_conditions()
        if not table_id:
            return ""
        prefix = "bklog_index_set_"
        try:
            index_set_id = int(table_id.removeprefix(prefix).split("_", 1)[0])
        except (TypeError, ValueError, IndexError):
            return ""
        if (
            not table_id.startswith(prefix)
            or not scope_space_queryset(LogIndexSet.objects)
            .filter(
                index_set_id=index_set_id,
                space_uid__in=self._resource_allowed_space_uids(),
            )
            .exists()
        ):
            return ""
        return table_id

    def _get_result_table_index_set_map(self, result_table_ids):
        source = {
            "type": SOURCE_SCENE,
            "related_space_uids": list(self._resource_allowed_space_uids()),
        }
        return _result_table_index_set_map(
            source,
            [{"__result_table": result_table_id} for result_table_id in result_table_ids or []],
        )

    def _map_result_tables_to_index_sets(self, result_table_ids):
        return sorted(set(self._get_result_table_index_set_map(result_table_ids).values()))

    def verify_result_table_search_permission(self, result_table_ids: list[str]) -> None:
        result_table_ids = [value for value in result_table_ids or [] if value]
        if not result_table_ids:
            return
        allowed_spaces = self._resource_allowed_space_uids()
        index_set_ids, unknown_result_tables = _resource_index_set_ids_for_result_tables(
            result_table_ids, allowed_spaces
        )
        if unknown_result_tables:
            raise BklogPermissionError("scene result contains an unmapped result table")
        visible_ids = set(
            scope_space_queryset(LogIndexSet.objects)
            .filter(index_set_id__in=index_set_ids, space_uid__in=allowed_spaces)
            .values_list("index_set_id", flat=True)
        )
        if index_set_ids != visible_ids:
            raise BklogPermissionError("scene result contains an index set outside the Resource Call source scope")


class ResourceSceneUnifyQueryHandler(ResourceTimeZoneMixin, ResourceScenePermissionMixin, SceneUnifyQueryHandler):
    pass


class ResourceSceneTermsAggsHandler(ResourceTimeZoneMixin, ResourceScenePermissionMixin, SceneTermsAggsHandler):
    pass


class ResourceSceneFieldHandler(ResourceTimeZoneMixin, ResourceScenePermissionMixin, SceneFieldHandler):
    pass


class ExplicitClusteringRouteMixin:
    """Pin UnifyQuery to the selected clustering result table before conditions are transformed."""

    def __init__(self, params, *, clustering_config):
        self.resource_clustering_config = clustering_config
        super().__init__(params)

    def _init_index_info_list(self, index_set_ids):
        entry_index_set_id = index_set_ids[0]
        index_info_list = super()._init_index_info_list([self.resource_clustering_config.index_set_id])
        index_info = index_info_list[0]
        index_info["index_set_id"] = entry_index_set_id
        index_info["scenario_id"] = Scenario.BKDATA
        index_info["using_clustering_proxy"] = True
        index_info["indices"] = self.resource_clustering_config.clustered_rt
        return [index_info]


class ResourceClusteringUnifyQueryHandler(ResourceTimeZoneMixin, ExplicitClusteringRouteMixin, UnifyQueryHandler):
    pass


class ResourceClusteringContextHandler(ResourceTimeZoneMixin, ExplicitClusteringRouteMixin, UnifyQueryContextHandler):
    pass


class ResourceClusteringUnifyQueryPatternHandler(
    ResourceTimeZoneMixin, ExplicitClusteringRouteMixin, UnifyQueryPatternHandler
):
    pass


class ResourceMappingHandlers(MappingHandlers):
    """Use the local read-only mapping client for application-authenticated Resource calls."""

    def _direct_latest_mapping(self, params):
        data = custom_params_valid(EsQueryMappingAttrSerializer, params)
        return EsQuery(data).mapping()


class ResourceSearchHandler(SearchHandlerEsquery):
    mapping_handler_class = ResourceMappingHandlers


class ResourceAggsHandlers(AggsHandlers):
    search_handler_class = ResourceSearchHandler


class ResourceAggsViewAdapter(AggsViewAdapter):
    def __init__(self):
        self._aggs_handlers = ResourceAggsHandlers


class ResourceClusteringSearchHandler(ResourceSearchHandler):
    """Pin the legacy search chain to clustered_rt without keyword/addition probing."""

    def __init__(self, index_set_id, search_dict, *, clustering_config, **kwargs):
        self.resource_clustering_config = clustering_config
        super().__init__(index_set_id, search_dict, **kwargs)

    def _init_indices_str(self):
        super()._init_indices_str()
        self.scenario_id = Scenario.BKDATA
        self.using_clustering_proxy = True
        return self.resource_clustering_config.clustered_rt


class ResourcePatternHandler(PatternHandler):
    """Reuse PatternHandler.pattern_search while replacing only its query-route primitive."""

    def __init__(self, entry_index_set_id, query, clustering_config):
        super().__init__(clustering_config.index_set_id, query)
        self._index_set_id = entry_index_set_id
        self._clustering_config = clustering_config

    def _get_pattern_aggs_result(self, index_set_id, query):
        pattern_aggs_field = self.pattern_aggs_field
        use_unify_query = self._clustering_config.storage_type == StorageTypeEnum.DORIS.value or (
            FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, query.get("bk_biz_id"))
            and FeatureToggleObject.switch(UNIFY_QUERY_SEARCH_CLUSTERING, query.get("bk_biz_id"))
        )
        if use_unify_query:
            query["index_set_ids"] = [index_set_id]
            query["agg_field"] = pattern_aggs_field
            return ResourceClusteringUnifyQueryPatternHandler(
                query, clustering_config=self._clustering_config
            ).query_pattern()

        query = copy.deepcopy(query)
        query["fields"] = [{"field_name": pattern_aggs_field, "sub_fields": self._build_aggs_group}]
        search = AggsHandlers._build_terms_aggs(
            Search(),
            query["fields"],
            query.get("size", AggsHandlers.AGGS_BUCKET_SIZE),
            query.get("order", AggsHandlers.DEFAULT_ORDER),
        ).extra(size=0)
        query.update(search.to_dict())
        aggs_result = ResourceClusteringSearchHandler(
            index_set_id,
            query,
            clustering_config=self._clustering_config,
            only_for_agg=True,
        ).search(search_type=None)
        return self._parse_pattern_aggs_result(pattern_aggs_field, aggs_result)


def get_log_fields(params):
    source = _resolve_source(params["source"])
    _validate_time_zone(params.get("time_zone"))
    scope = params.get("scope") or SearchScopeEnum.DEFAULT.value
    if source["type"] == SOURCE_INDEX_SET:
        data = _run_query(lambda: _index_set_fields(source, params, scope), time_zone=params.get("time_zone"))
        compatibility = _field_compatibility([source["index_set"]])
    else:
        query = _scene_query_params(source, params)
        data = _run_query(
            lambda: ResourceSceneUnifyQueryHandler(query).fields(scope=scope),
            time_zone=params.get("time_zone"),
        )
        candidates = _scene_candidates(source)
        compatibility = _field_compatibility([item["index_set"] for item in candidates if item["matched"] is not False])
    data = dict(data or {})
    return _result(
        source,
        route=_route_evidence(source, result_table_ids=_configured_result_table_ids(source)),
        fields=data.get("fields", data),
        common_fields=compatibility["common_fields"],
        field_conflicts=compatibility["differences"],
        missing_snapshot_index_set_ids=compatibility["missing_snapshot_index_set_ids"],
    )


def search_logs(params):
    source = _resolve_source(params["source"])
    start_time, end_time = _time_range(params)
    begin = params.get("begin", 0)
    size = params.get("size", 50)
    if begin + size > MAX_RESULT_WINDOW:
        _error("log_query_limit_exceeded", f"query exceeds the existing result window of {MAX_RESULT_WINDOW}")
    query = _base_query_params(params, start_time, end_time)
    query.update({"begin": begin, "size": size})

    if source["type"] == SOURCE_INDEX_SET:
        data = _run_query(lambda: _index_set_search(source, query), time_zone=params.get("time_zone"))
    elif source["type"] == SOURCE_SCENE:
        query.update(_scene_query_params(source, params))
        data = _run_query(lambda: ResourceSceneUnifyQueryHandler(query).search(), time_zone=params.get("time_zone"))
    else:
        data = _run_query(
            lambda: _clustering_search(source, query),
            clustering=True,
            time_zone=params.get("time_zone"),
        )

    warnings = _downstream_warnings(data)
    normalized_items = _search_result_items(source, data.get("list") or [], params.get("fields"))
    items, truncation = _bounded_items(normalized_items)
    if truncation["truncated"]:
        warnings.append(
            {
                "code": "log_items_truncated",
                "message": "log items exceeded the Resource Call response limits",
                "scope": "response.items",
                "retryable": False,
            }
        )
    result_table_ids = _string_list(data.get("result_table_id"))
    if source["type"] == SOURCE_CLUSTERING:
        result_table_ids = [source["route"]["clustered_rt"]]
    total = _total_value(data.get("total"))
    return _result(
        source,
        status=_downstream_status(data, warnings),
        route=_route_evidence(
            source,
            result_table_ids=result_table_ids,
            index_set_ids=_result_index_set_ids(source, data.get("list") or []),
            partial=bool(warnings),
        ),
        warnings=warnings,
        items=items,
        total=total,
        took=float(data.get("took") or 0),
        fields=data.get("fields", {}),
        pagination={
            "begin": begin,
            "size": size,
            "returned": len(items),
            "has_more": begin + len(items) < total,
        },
        truncation=truncation,
    )


def aggregate_logs(params):
    source = _resolve_source(params["source"])
    start_time, end_time = _time_range(params, maximum=MAX_AGG_RANGE_MILLISECONDS)
    query = _base_query_params(params, start_time, end_time)
    aggregation = params["aggregation"]
    aggregation_type = aggregation["type"]

    if aggregation_type == "terms":
        _resolve_field_type(source, aggregation["field"], params)
        query.update({"fields": [aggregation["field"]], "size": aggregation.get("size", 20)})
        if source["type"] == SOURCE_INDEX_SET:
            data = _run_query(lambda: _index_set_terms(source, query), time_zone=params.get("time_zone"))
        else:
            query.update(_scene_query_params(source, params))
            data = _run_query(
                lambda: ResourceSceneTermsAggsHandler(query["fields"], query).terms(),
                time_zone=params.get("time_zone"),
            )
    elif aggregation_type == "histogram":
        if aggregation.get("group_field"):
            _resolve_field_type(source, aggregation["group_field"], params)
        query.update(
            {
                "interval": aggregation.get("interval", "auto"),
                "group_field": aggregation.get("group_field"),
                "fields": [],
            }
        )
        if source["type"] == SOURCE_INDEX_SET:
            data = _run_query(lambda: _index_set_histogram(source, query), time_zone=params.get("time_zone"))
        else:
            query.update(_scene_query_params(source, params))
            data = _run_query(
                lambda: ResourceSceneUnifyQueryHandler(query).aggs_date_histogram(
                    interval=query["interval"], group_field=query.get("group_field")
                ),
                time_zone=params.get("time_zone"),
            )
    else:
        field_type = _resolve_field_type(source, aggregation["field"], params)
        query.update({"agg_field": aggregation["field"], "field_type": field_type})
        if source["type"] == SOURCE_INDEX_SET:
            query["index_set_ids"] = [source["index_set_id"]]
            query["bk_biz_id"] = source["bk_biz_id"]
            handler = ResourceUnifyQueryFieldHandler(query)
        else:
            query.update(_scene_query_params(source, params))
            handler = ResourceSceneFieldHandler(query)
        data = _run_query(lambda: _field_statistics(handler, field_type), time_zone=params.get("time_zone"))

    warnings = _downstream_warnings(data)
    buckets, stats = _normalize_aggregation_result(aggregation, data)
    return _result(
        source,
        status=_downstream_status(data, warnings),
        route=_route_evidence(source, result_table_ids=_configured_result_table_ids(source), partial=bool(warnings)),
        warnings=warnings,
        aggregation=aggregation,
        buckets=buckets,
        stats=stats,
    )


def get_log_context(params):
    source = _resolve_source(params["source"])
    _validate_time_zone(params.get("time_zone"))
    anchor = _flatten_context_anchor(params["context_anchor"])
    start_time, end_time = _context_time_bounds(anchor.get("dtEventTimeStamp"))
    index_set = source.get("index_set")
    if source["type"] != SOURCE_SCENE and anchor["index_set_id"] != source["index_set_id"]:
        _error("log_context_source_mismatch", "context anchor index_set_id does not match the requested source")
    if source["type"] == SOURCE_SCENE:
        index_set = _resolve_scene_anchor(source, anchor)
    elif source["type"] == SOURCE_CLUSTERING:
        _validate_clustering_anchor(source, anchor)
    if source["type"] != SOURCE_CLUSTERING:
        _validate_context_anchor(index_set, anchor)
    query = dict(anchor)
    query.update(
        {
            "index_set_id": index_set.index_set_id,
            "size": params.get("size", 50),
            "start": 0,
            "begin": 0,
            "zero": True,
            "search_type_tag": "context",
            "bk_biz_id": space_uid_to_bk_biz_id(index_set.space_uid, id=None),
            "start_time": start_time,
            "end_time": end_time,
            "index_set_ids": [index_set.index_set_id],
            "time_zone": params.get("time_zone"),
            "is_desensitize": True,
        }
    )
    if source["type"] == SOURCE_CLUSTERING:
        data = _run_query(
            lambda: _clustering_context(source, query),
            clustering=True,
            time_zone=params.get("time_zone"),
        )
    elif FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, query["bk_biz_id"]):
        data = _run_query(lambda: ResourceUnifyQueryContextHandler(query).search(), time_zone=params.get("time_zone"))
    else:
        data = _run_query(
            lambda: ResourceSearchHandler(index_set.index_set_id, query).search_context(),
            time_zone=params.get("time_zone"),
        )
    warnings = []
    if data.get("zero_index", -1) < 0:
        warnings.append(
            {
                "code": "context_anchor_not_found",
                "message": "the bounded context result does not contain the requested anchor",
                "scope": "context.anchor",
                "retryable": False,
            }
        )
    items, truncation = _bounded_items(data.get("list") or [])
    if truncation["truncated"]:
        warnings.append(
            {
                "code": "log_items_truncated",
                "message": "context items exceeded the Resource Call response limits",
                "scope": "response.items",
                "retryable": False,
            }
        )
    anchor_index = int(data.get("zero_index", -1))
    result_table_ids = [anchor["result_table_id"]] if anchor.get("result_table_id") else []
    if source["type"] == SOURCE_CLUSTERING:
        result_table_ids = [source["route"]["clustered_rt"]]
    return _result(
        source,
        status="partial" if warnings else "success",
        route=_route_evidence(
            source,
            result_table_ids=result_table_ids,
            index_set_ids=[index_set.index_set_id],
            partial=bool(warnings),
        ),
        warnings=warnings,
        items=items,
        anchor_index=anchor_index,
        pagination={
            "size": params.get("size", 50),
            "returned": len(items),
            "has_before": anchor_index > 0,
            "has_after": 0 <= anchor_index < len(items) - 1,
        },
        truncation=truncation,
        total=_total_value(data.get("total")),
        took=float(data.get("took") or 0),
    )


def resolve_log_scene(params):
    source = _resolve_source(params["source"])
    start_time, end_time = _time_range(params)
    query = _base_query_params(params, start_time, end_time)
    query.update(_scene_query_params(source, params))
    handler = ResourceSceneUnifyQueryHandler(query)
    runtime_query = copy.deepcopy(handler.base_dict)
    runtime_query.update({"from": 0, "limit": 1, "highlight": {"enable": False}})
    runtime = _run_query(lambda: handler.query_ts_raw(runtime_query), time_zone=params.get("time_zone"))
    actual_result_tables = _string_list(runtime.get("result_table_id"))
    actual_index_set_ids, unknown_result_tables = _resource_index_set_ids_for_result_tables(
        actual_result_tables, set(source["related_space_uids"])
    )
    candidates = _scene_candidates(source)

    matched_targets = []
    excluded_targets = []
    for candidate in candidates:
        target = _scene_target(candidate["index_set"])
        if candidate["matched"] is False:
            target["reason"] = candidate["reason"]
            excluded_targets.append(target)
        elif candidate["index_set"].index_set_id in actual_index_set_ids:
            matched_targets.append(target)
        else:
            target["reason"] = "no_data_or_runtime_condition_excluded"
            excluded_targets.append(target)

    warnings = _downstream_warnings(runtime)
    if source.get("candidates_truncated"):
        warnings.append(
            {
                "code": "scene_candidate_limit_reached",
                "message": f"scene resolution returned at most {MAX_SCENE_TARGETS} candidate index sets",
                "scope": "scene.candidates",
                "retryable": False,
            }
        )
    if excluded_targets:
        warnings.append(
            {
                "code": "scene_targets_excluded",
                "message": f"{len(excluded_targets)} scene targets were excluded or returned no data",
                "scope": "scene.targets",
                "retryable": False,
            }
        )
    if unknown_result_tables:
        warnings.append(
            {
                "code": "scene_result_table_unmapped",
                "message": f"{len(unknown_result_tables)} result tables could not be mapped to an index set",
                "scope": "scene.result_tables",
                "retryable": False,
            }
        )
    compatibility = _field_compatibility(
        [item["index_set"] for item in candidates if item["index_set"].index_set_id in actual_index_set_ids]
    )
    return _result(
        source,
        status=_downstream_status(runtime, warnings),
        route=_route_evidence(
            source,
            result_table_ids=actual_result_tables,
            index_set_ids=sorted(actual_index_set_ids),
            partial=bool(warnings),
        ),
        warnings=warnings,
        targets=matched_targets,
        excluded=excluded_targets,
        common_fields=compatibility["common_fields"],
        field_conflicts=compatibility["differences"],
    )


def search_clustering_patterns(params):
    start_time, end_time = _time_range(params)
    _validate_time_zone(params.get("time_zone"))
    source = _resolve_source(params["source"])
    pattern_level = PatternEnum.LEVEL_05.value
    addition = [_normalize_pattern_addition(item) for item in params.get("addition") or []]
    if params.get("filter_not_clustering", True):
        addition.append(
            {
                "field": f"{AGGS_FIELD_PREFIX}_{pattern_level}",
                "operator": DEFULT_FILTER_NOT_CLUSTERING_OPERATOR,
                "value": "",
                "condition": "and",
            }
        )
    query = {
        "start_time": arrow.get(start_time / 1000).datetime,
        "end_time": arrow.get(end_time / 1000).datetime,
        "time_range": "customized",
        "keyword": params.get("keyword") or "",
        "addition": addition,
        "ip_chooser": {},
        "host_scopes": {},
        "size": params.get("size", 100),
        "pattern_level": pattern_level,
        "show_new_pattern": params.get("show_new_pattern", False),
        "year_on_year_hour": params.get("year_on_year_hour", 0),
        "group_by": list(params.get("group_by") or []),
        "include_origin_log": False,
        "remark_config": params.get("remark_config", RemarkConfigEnum.ALL.value),
        "owner_config": params.get("owner_config", OwnerConfigEnum.ALL.value),
        "owners": list(params.get("owners") or []),
        "bk_biz_id": source["bk_biz_id"],
        "time_zone": params.get("time_zone"),
    }
    source["route"]["query_backend"] = (
        "unify_query"
        if source["clustering_config"].storage_type == StorageTypeEnum.DORIS.value
        or (
            FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"])
            and FeatureToggleObject.switch(UNIFY_QUERY_SEARCH_CLUSTERING, source["bk_biz_id"])
        )
        else "esquery"
    )
    items = _run_query(
        lambda: ResourcePatternHandler(source["index_set_id"], query, source["clustering_config"]).pattern_search(),
        clustering=True,
        pattern=True,
        time_zone=params.get("time_zone"),
    )
    mapped_count = sum(bool(item.get("pattern")) for item in items)
    missing_count = len(items) - mapped_count
    warnings = []
    if missing_count:
        warnings.append(
            {
                "code": "clustering_pattern_enrichment_incomplete",
                "message": f"{missing_count} pattern rows could not be enriched with pattern text",
                "scope": "clustering.pattern.enrichment",
                "retryable": True,
            }
        )
    items, truncation = _bounded_items(items)
    if truncation["truncated"]:
        warnings.append(
            {
                "code": "clustering_pattern_items_truncated",
                "message": "clustering pattern items exceeded the Resource Call response limits",
                "scope": "response.items",
                "retryable": False,
            }
        )
    return _result(
        source,
        status="partial" if warnings else "success",
        route=_route_evidence(
            source,
            result_table_ids=[source["route"]["clustered_rt"]],
            index_set_ids=[source["index_set_id"]],
            partial=bool(warnings),
        ),
        warnings=warnings,
        items=items,
        enrichment={
            "status": "partial" if warnings else "success",
            "mapped_count": mapped_count,
            "missing_count": missing_count,
            "truncation": truncation,
        },
    )


def _resolve_source(raw_source):
    source_type = raw_source.get("type")
    if source_type in {SOURCE_INDEX_SET, SOURCE_CLUSTERING}:
        index_set_id = raw_source["index_set_id"]
        try:
            index_set = scope_space_queryset(LogIndexSet.objects).get(index_set_id=index_set_id)
        except LogIndexSet.DoesNotExist:
            _error("log_index_set_not_found", f"index set does not exist in the Resource Call tenant: {index_set_id}")
        source = {
            "type": source_type,
            "index_set_id": index_set.index_set_id,
            "index_set": index_set,
            "space_uid": index_set.space_uid,
            "bk_biz_id": space_uid_to_bk_biz_id(index_set.space_uid),
        }
        if source_type == SOURCE_CLUSTERING:
            return _resolve_clustering_route(source)
        return source
    if source_type != SOURCE_SCENE:
        _error("log_source_invalid", f"unsupported source type: {source_type}")

    space_uid = raw_source["space_uid"]
    try:
        space = scope_space_queryset(Space.objects).get(space_uid=space_uid)
    except Space.DoesNotExist:
        if settings.ENABLE_MULTI_TENANT_MODE:
            raise BklogPermissionError("scene space does not belong to the Resource Call tenant")
        bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        if not bk_biz_id:
            _error("log_scene_invalid", f"scene space does not exist: {space_uid}")
    else:
        bk_biz_id = space.bk_biz_id
    requested_bk_biz_id = raw_source.get("bk_biz_id")
    if requested_bk_biz_id is not None and requested_bk_biz_id != bk_biz_id:
        _error("log_scene_invalid", "scene bk_biz_id does not match space_uid")

    if not FeatureToggleObject.switch(SCENE_SEARCH, bk_biz_id):
        _error("log_scene_disabled", f"scene search is disabled for bk_biz_id={bk_biz_id}")
    try:
        conditions = AllConditionsBuilder.from_raw(copy.deepcopy(raw_source["table_id_conditions"]))
    except (TypeError, ValueError, KeyError) as error:
        _error("log_scene_invalid", f"invalid scene table_id_conditions: {error}")
    related_space_uids = _related_space_uids(space_uid)
    scene_filter_values = [_normalize_filter(item) for item in raw_source.get("scene_filter_values") or []]
    return {
        "type": SOURCE_SCENE,
        "space_uid": space_uid,
        "bk_biz_id": bk_biz_id,
        "table_id_conditions": conditions,
        "scene_filter_values": scene_filter_values,
        "related_space_uids": related_space_uids,
    }


def _resolve_clustering_route(source):
    index_set = source["index_set"]
    direct_configs = list(
        ClusteringConfig.objects.filter(
            Q(index_set_id=index_set.index_set_id) | Q(new_cls_index_set_id=index_set.index_set_id)
        )[:2]
    )
    route_reason = "direct_index_set"
    configs = direct_configs
    if not configs and index_set.is_group:
        child_index_set_ids = index_set.get_child_index_set_ids()
        configs = list(
            ClusteringConfig.objects.filter(
                Q(index_set_id__in=child_index_set_ids) | Q(new_cls_index_set_id__in=child_index_set_ids)
            ).distinct()[:2]
        )
        route_reason = "index_group_members_share_clustering_config"
    if not configs:
        _error(
            "log_clustering_config_not_found",
            f"clustering config does not exist for entry index set: {index_set.index_set_id}",
        )
    if len(configs) != 1:
        _error(
            "log_clustering_route_ambiguous",
            f"entry index set maps to multiple clustering configs: {index_set.index_set_id}",
        )
    clustering_config = configs[0]
    if not clustering_config.clustered_rt:
        _error(
            "log_clustering_result_table_missing",
            f"clustering result table is not configured for entry index set: {index_set.index_set_id}",
        )
    linked_index_set_ids = [clustering_config.index_set_id]
    if clustering_config.new_cls_index_set_id:
        linked_index_set_ids.append(clustering_config.new_cls_index_set_id)
    visible_linked_ids = set(
        scope_space_queryset(LogIndexSet.objects)
        .filter(index_set_id__in=linked_index_set_ids)
        .values_list("index_set_id", flat=True)
    )
    if clustering_config.index_set_id not in visible_linked_ids:
        raise BklogPermissionError("clustering config is outside the Resource Call tenant")
    if index_set.index_set_id == clustering_config.new_cls_index_set_id:
        route_reason = "new_class_index_set"
    data_label = BaseIndexSetHandler.get_data_label(index_set.index_set_id, clustered_rt=clustering_config.clustered_rt)
    source.update(
        {
            "clustering_config": clustering_config,
            "route": {
                "entry_index_set_id": index_set.index_set_id,
                "clustering_config_id": clustering_config.id,
                "canonical_index_set_id": clustering_config.index_set_id,
                "new_class_index_set_id": clustering_config.new_cls_index_set_id,
                "clustered_rt": clustering_config.clustered_rt,
                "data_label": data_label,
                "route_reason": route_reason,
                "storage_type": clustering_config.storage_type,
            },
        }
    )
    return source


def _related_space_uids(space_uid):
    related = list(dict.fromkeys(IndexSetHandler.get_all_related_space_uids(space_uid)))
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return related
    tenant_id = get_request_tenant_id()
    return list(Space.objects.filter(space_uid__in=related, bk_tenant_id=tenant_id).values_list("space_uid", flat=True))


def _index_set_fields(source, params, scope):
    index_set = source["index_set"]
    start_time = params.get("start_time")
    end_time = params.get("end_time")
    if (start_time is None) != (end_time is None):
        _error("log_time_range_invalid", "start_time and end_time must be provided together")
    if start_time is None and scope == SearchScopeEnum.DEFAULT.value:
        return index_set.get_fields(use_snapshot=True)
    if start_time is None:
        end_time = arrow.now().int_timestamp * 1000
        start_time = arrow.now().shift(days=-1).int_timestamp * 1000
    _validate_time_range(start_time, end_time)
    query = {
        "start_time": start_time,
        "end_time": end_time,
        "index_set_ids": [index_set.index_set_id],
        "bk_biz_id": source["bk_biz_id"],
        "time_zone": params.get("time_zone"),
    }
    if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"]):
        return ResourceUnifyQueryHandler(query).fields(scope)
    return ResourceSearchHandler(index_set.index_set_id, query).fields(scope)


def _index_set_search(source, query):
    index_set_id = source["index_set_id"]
    if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"]):
        query.update({"index_set_ids": [index_set_id], "bk_biz_id": source["bk_biz_id"]})
        return ResourceUnifyQueryHandler(query).search(search_type=None)
    return ResourceSearchHandler(index_set_id, query).search()


def _clustering_search(source, query):
    clustering_config = source["clustering_config"]
    use_unify_query = clustering_config.storage_type == StorageTypeEnum.DORIS.value or FeatureToggleObject.switch(
        UNIFY_QUERY_SEARCH, source["bk_biz_id"]
    )
    if use_unify_query:
        source["route"]["query_backend"] = "unify_query"
        query.update({"index_set_ids": [source["index_set_id"]], "bk_biz_id": source["bk_biz_id"]})
        return ResourceClusteringUnifyQueryHandler(query, clustering_config=clustering_config).search(search_type=None)
    source["route"]["query_backend"] = "esquery"
    return ResourceClusteringSearchHandler(
        source["index_set_id"],
        query,
        clustering_config=clustering_config,
        export_fields=query.get("export_fields"),
    ).search(search_type=None)


def _clustering_context(source, query):
    clustering_config = source["clustering_config"]
    use_unify_query = clustering_config.storage_type == StorageTypeEnum.DORIS.value or FeatureToggleObject.switch(
        UNIFY_QUERY_SEARCH, source["bk_biz_id"]
    )
    if use_unify_query:
        source["route"]["query_backend"] = "unify_query"
        return ResourceClusteringContextHandler(query, clustering_config=clustering_config).search()
    source["route"]["query_backend"] = "esquery"
    return ResourceClusteringSearchHandler(
        source["index_set_id"], query, clustering_config=clustering_config
    ).search_context()


def _index_set_terms(source, query):
    if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"]):
        query.update({"index_set_ids": [source["index_set_id"]], "bk_biz_id": source["bk_biz_id"]})
        return ResourceUnifyQueryTermsAggsHandler(query["fields"], query).terms()
    return ResourceAggsViewAdapter().terms(source["index_set_id"], query)


def _index_set_histogram(source, query):
    if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"]):
        query.update({"index_set_ids": [source["index_set_id"]], "bk_biz_id": source["bk_biz_id"]})
        return ResourceUnifyQueryHandler(query).date_histogram()
    return ResourceAggsViewAdapter().date_histogram(source["index_set_id"], query)


def _scene_query_params(source, params):
    query = {
        "space_uid": source["space_uid"],
        "bk_biz_id": source["bk_biz_id"],
        "table_id_conditions": copy.deepcopy(source["table_id_conditions"]),
        "record_history": False,
        "time_zone": params.get("time_zone"),
    }
    if params.get("start_time") is not None:
        query["start_time"] = params["start_time"]
    if params.get("end_time") is not None:
        query["end_time"] = params["end_time"]
    additions = [_normalize_filter(item) for item in params.get("addition") or []]
    additions.extend(copy.deepcopy(source.get("scene_filter_values") or []))
    if additions:
        query["addition"] = additions
    return query


def _base_query_params(params, start_time, end_time):
    _validate_time_zone(params.get("time_zone"))
    query_string = params.get("keyword", "*") or "*"
    filters = [_normalize_filter(item) for item in params.get("addition") or []]
    sort_list = params.get("sort_list") or [["dtEventTimeStamp", "desc"]]
    _validate_sort(sort_list)
    return {
        "start_time": start_time,
        "end_time": end_time,
        "time_range": "customized",
        "keyword": query_string,
        "addition": filters,
        "ip_chooser": {},
        "filter": [],
        "sort_list": sort_list,
        "search_mode": "ui",
        "is_desensitize": True,
        "can_highlight": False,
        "track_total_hits": params.get("track_total_hits", True),
        "time_zone": params.get("time_zone"),
    }


def _normalize_filter(item):
    operator = item["operator"]
    if operator not in ALLOWED_FILTER_OPERATORS:
        _error("log_source_invalid", f"unsupported filter operator: {operator}")
    value = item["value"]
    if isinstance(value, list):
        normalized_value = [str(part) for part in value]
    else:
        normalized_value = str(value)
    return {
        "field": item["field"],
        "operator": operator,
        "value": normalized_value,
        "condition": item.get("condition", "and"),
    }


def _normalize_pattern_addition(item):
    return _normalize_filter(item)


def _validate_sort(sort_list):
    for item in sort_list:
        if len(item) != 2 or item[1] not in {"asc", "desc"}:
            _error("log_source_invalid", "sort must contain [field, asc|desc] pairs")


def _validate_time_zone(time_zone):
    if not time_zone:
        return
    try:
        ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        _error("log_source_invalid", f"invalid time_zone: {time_zone}")


def _string_list(value):
    if value in (None, ""):
        return []
    values = value if isinstance(value, list | tuple | set) else [value]
    return list(dict.fromkeys(str(item) for item in values if item not in (None, "")))


def _total_value(value):
    if isinstance(value, dict):
        value = value.get("value", 0)
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _configured_result_table_ids(source):
    if source["type"] == SOURCE_CLUSTERING:
        return [source["route"]["clustered_rt"]]
    if source["type"] == SOURCE_INDEX_SET:
        index_sets = [source["index_set"]]
    else:
        index_sets = [item["index_set"] for item in _scene_candidates(source) if item["matched"] is not False]
    result_table_ids = []
    for index_set in index_sets:
        result_table_ids.extend(
            str(value)
            for value in index_set.get_log_index_set_data().values_list("result_table_id", flat=True)
            if value
        )
    return list(dict.fromkeys(result_table_ids))


def _route_evidence(source, *, result_table_ids=None, index_set_ids=None, partial=False):
    result_table_ids = list(dict.fromkeys(str(value) for value in result_table_ids or [] if value))
    if not result_table_ids:
        result_table_ids = _configured_result_table_ids(source)
    if index_set_ids is None:
        index_set_ids = (
            [item["index_set"].index_set_id for item in _scene_candidates(source) if item["matched"] is not False]
            if source["type"] == SOURCE_SCENE
            else [source["index_set_id"]]
        )
    index_set_ids = list(dict.fromkeys(int(value) for value in index_set_ids if value is not None))

    if source["type"] == SOURCE_CLUSTERING:
        internal_route = source["route"]
        return {
            "source_type": SOURCE_CLUSTERING,
            "requested_source_type": SOURCE_CLUSTERING,
            "entry_index_set_id": source["index_set_id"],
            "actual_index_set_ids": index_set_ids,
            "clustering_config_id": internal_route["clustering_config_id"],
            "canonical_index_set_id": internal_route["canonical_index_set_id"],
            "new_class_index_set_id": internal_route["new_class_index_set_id"],
            "clustered_rt": internal_route["clustered_rt"],
            "result_table_ids": result_table_ids,
            "data_labels": [internal_route["data_label"]],
            "storage_types": [internal_route["storage_type"]],
            "route_reason": "explicit_source",
            "entry_resolution_reason": internal_route["route_reason"],
            "query_backend": internal_route.get("query_backend"),
            "related_space_uids": [],
            "fallback": False,
            "partial": partial,
        }

    visible_index_sets = list(
        scope_space_queryset(LogIndexSet.objects).filter(index_set_id__in=index_set_ids).order_by("index_set_id")
    )
    visible_ids = [item.index_set_id for item in visible_index_sets]
    if set(visible_ids) != set(index_set_ids):
        raise BklogPermissionError("query result contains an index set outside the Resource Call tenant")
    data_labels = [BaseIndexSetHandler.get_data_label(index_set_id) for index_set_id in visible_ids]
    storage_types = sorted({"doris" if item.is_native_doris() else "es" for item in visible_index_sets})
    query_backend = (
        "unify_query"
        if source["type"] == SOURCE_SCENE
        else ("unify_query" if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, source["bk_biz_id"]) else "esquery")
    )
    return {
        "source_type": source["type"],
        "requested_source_type": source["type"],
        "entry_index_set_id": source.get("index_set_id"),
        "actual_index_set_ids": visible_ids,
        "clustering_config_id": None,
        "canonical_index_set_id": None,
        "new_class_index_set_id": None,
        "clustered_rt": None,
        "result_table_ids": result_table_ids,
        "data_labels": data_labels,
        "storage_types": storage_types,
        "route_reason": "scene_conditions" if source["type"] == SOURCE_SCENE else "index_set",
        "entry_resolution_reason": None,
        "query_backend": query_backend,
        "related_space_uids": list(source.get("related_space_uids") or []),
        "fallback": False,
        "partial": partial,
    }


def _result_table_index_set_map(source, records):
    if source["type"] != SOURCE_SCENE:
        return {}
    allowed_spaces = set(source["related_space_uids"])
    result_table_ids = {record.get("__result_table") for record in records if record.get("__result_table")}
    mapping = {}
    logical_result_tables = {}
    physical_result_table_ids = set()
    prefix = "bklog_index_set_"
    for result_table_id in result_table_ids:
        if result_table_id.startswith(prefix):
            try:
                logical_result_tables[result_table_id] = int(result_table_id.removeprefix(prefix).split("_", 1)[0])
            except (TypeError, ValueError):
                continue
        else:
            physical_result_table_ids.add(result_table_id)
    if logical_result_tables:
        visible_ids = set(
            scope_space_queryset(LogIndexSet.objects)
            .filter(
                index_set_id__in=set(logical_result_tables.values()),
                space_uid__in=allowed_spaces,
            )
            .values_list("index_set_id", flat=True)
        )
        mapping.update(
            {
                result_table_id: index_set_id
                for result_table_id, index_set_id in logical_result_tables.items()
                if index_set_id in visible_ids
            }
        )
    if physical_result_table_ids:
        visible_ids = set(
            scope_space_queryset(LogIndexSet.objects)
            .filter(space_uid__in=allowed_spaces)
            .values_list("index_set_id", flat=True)
        )
        mapping.update(
            {
                result_table_id: index_set_id
                for result_table_id, index_set_id in LogIndexSetData.objects.filter(
                    result_table_id__in=physical_result_table_ids,
                    index_set_id__in=visible_ids,
                    type=IndexSetDataType.RESULT_TABLE.value,
                ).values_list("result_table_id", "index_set_id")
            }
        )
    return mapping


def _result_index_set_ids(source, records):
    if source["type"] != SOURCE_SCENE:
        return [source["index_set_id"]]
    result_table_map = _result_table_index_set_map(source, records)
    return sorted(
        {
            int(record.get("__index_set_id__") or result_table_map.get(record.get("__result_table")))
            for record in records
            if record.get("__index_set_id__") or result_table_map.get(record.get("__result_table"))
        }
    )


def _search_result_items(source, records, projected_fields=None):
    result_table_map = _result_table_index_set_map(source, records)
    index_set_ids = _result_index_set_ids(source, records)
    index_sets = {
        item.index_set_id: item
        for item in scope_space_queryset(LogIndexSet.objects).filter(index_set_id__in=index_set_ids)
    }
    result = []
    for record in records:
        index_set_id = source.get("index_set_id")
        if source["type"] == SOURCE_SCENE:
            index_set_id = record.get("__index_set_id__") or result_table_map.get(record.get("__result_table"))
        index_set = index_sets.get(int(index_set_id)) if index_set_id is not None else None
        if not index_set:
            _error("log_context_anchor_invalid", "search result cannot be mapped to a visible context index set")
        context_anchor = _build_context_anchor(source, index_set, record)
        public_record = _project_record(record, projected_fields)
        result.append({"record": public_record, "context_anchor": context_anchor})
    return result


def _project_record(record, projected_fields):
    if not projected_fields:
        return copy.deepcopy(record)
    projected = {}
    for field in projected_fields:
        value = record
        for part in field.split("."):
            if not isinstance(value, dict) or part not in value:
                value = ""
                break
            value = value[part]
        projected[field] = value
    return projected


def _build_context_anchor(source, index_set, record):
    scenario_id = Scenario.BKDATA if source["type"] == SOURCE_CLUSTERING else index_set.scenario_id
    if index_set.sort_fields:
        sort_fields = ["dtEventTimeStamp", *(index_set.sort_fields or []), *(index_set.target_fields or [])]
    elif scenario_id == Scenario.LOG:
        sort_fields = ["dtEventTimeStamp", "gseIndex", "iterationIndex"]
    else:
        sort_fields = ["dtEventTimeStamp", "gseindex", "_iteration_idx"]
    sort_values = {field: record.get(field) for field in dict.fromkeys(sort_fields)}
    identity_fields = ["bk_host_id", "serverIp", "ip", "path", "container_id", "logfile"]
    identity = {field: record.get(field) for field in identity_fields if record.get(field) not in (None, "")}
    result_table_id = record.get("__result_table")
    if source["type"] == SOURCE_CLUSTERING:
        result_table_id = result_table_id or source["route"]["clustered_rt"]
    elif not result_table_id:
        configured = list(index_set.get_log_index_set_data().values_list("result_table_id", flat=True)[:2])
        if len(configured) == 1:
            result_table_id = configured[0]
    anchor = {
        "index_set_id": index_set.index_set_id,
        "scenario_id": scenario_id,
        "sort_values": sort_values,
        "identity": identity,
    }
    if result_table_id:
        anchor["result_table_id"] = result_table_id
    return anchor


def _flatten_context_anchor(context_anchor):
    anchor = {
        "index_set_id": context_anchor["index_set_id"],
        "scenario_id": context_anchor["scenario_id"],
        "result_table_id": context_anchor.get("result_table_id"),
    }
    anchor.update(context_anchor.get("sort_values") or {})
    anchor.update(context_anchor.get("identity") or {})
    if anchor.get("dtEventTimeStamp") in (None, ""):
        _error("log_context_anchor_invalid", "context anchor is missing dtEventTimeStamp")
    return anchor


def _resolve_field_type(source, field_name, params):
    if source["type"] == SOURCE_INDEX_SET:
        index_sets = [source["index_set"]]
    else:
        index_sets = [item["index_set"] for item in _scene_candidates(source) if item["matched"] is not False]
    field_types = {
        field.get("field_type")
        for index_set in index_sets
        for field in (index_set.get_fields(use_snapshot=True) or {}).get("fields", [])
        if field.get("field_name") == field_name and field.get("field_type")
    }
    if not field_types:
        if source["type"] == SOURCE_INDEX_SET:
            runtime_fields = _run_query(
                lambda: _index_set_fields(source, params, SearchScopeEnum.DEFAULT.value),
                time_zone=params.get("time_zone"),
            )
        else:
            runtime_fields = _run_query(
                lambda: ResourceSceneUnifyQueryHandler(_scene_query_params(source, params)).fields(
                    scope=SearchScopeEnum.DEFAULT.value
                ),
                time_zone=params.get("time_zone"),
            )
        field_types = {
            field.get("field_type")
            for field in (runtime_fields or {}).get("fields", [])
            if field.get("field_name") == field_name and field.get("field_type")
        }
    if not field_types:
        _error("log_source_invalid", f"aggregation field does not exist: {field_name}")
    if len(field_types) != 1:
        _error("log_source_invalid", f"aggregation field has conflicting types: {field_name}")
    return field_types.pop()


def _normalize_aggregation_result(aggregation, data):
    if aggregation["type"] == "field_stats":
        return [], data
    aggs = data.get("aggs") or {}
    if aggregation["type"] == "terms":
        buckets = (aggs.get(aggregation["field"]) or {}).get("buckets") or []
        return buckets, None
    buckets = (aggs.get("group_by_histogram") or {}).get("buckets") or []
    return buckets, None


def _time_range(params, maximum=None):
    start_time = params["start_time"]
    end_time = params["end_time"]
    _validate_time_range(start_time, end_time, maximum=maximum)
    return start_time, end_time


def _validate_time_range(start_time, end_time, maximum=None):
    if start_time >= end_time:
        _error("log_time_range_invalid", "start_time must be earlier than end_time")
    if maximum is not None and end_time - start_time > maximum:
        _error("log_time_range_invalid", f"time range must not exceed {maximum} milliseconds")


def _context_time_bounds(value):
    try:
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if isinstance(value, int | float):
            seconds = float(value)
            if seconds >= 10**14:
                seconds /= 10**6
            elif seconds >= 10**11:
                seconds /= 10**3
            log_time = arrow.get(seconds)
        else:
            log_time = arrow.get(value)
    except Exception as error:
        _error("log_context_anchor_invalid", f"invalid dtEventTimeStamp: {error}")
    return int(log_time.shift(hours=-12).timestamp()), int(log_time.shift(hours=12).timestamp())


def _validate_context_anchor(index_set, anchor, scenario_id=None, allowed_result_table_ids=None):
    result_table_id = anchor.get("result_table_id")
    if result_table_id:
        if allowed_result_table_ids is None:
            related_index_set_ids = [index_set.index_set_id]
            if index_set.is_group:
                related_index_set_ids.extend(index_set.get_child_index_set_ids())
            allowed_result_table_ids = {
                BaseIndexSetHandler.get_data_label(index_set_id) for index_set_id in related_index_set_ids
            }
            allowed_result_table_ids.update(
                str(value)
                for value in index_set.get_log_index_set_data()
                .filter(
                    type=IndexSetDataType.RESULT_TABLE.value,
                    apply_status=LogIndexSetData.Status.NORMAL,
                )
                .values_list("result_table_id", flat=True)
                if value
            )
        if result_table_id not in allowed_result_table_ids:
            _error("log_context_source_mismatch", "context anchor result table does not belong to the index set")

    if index_set.sort_fields:
        required = list(index_set.sort_fields or []) + list(index_set.target_fields or [])
        missing = [field for field in required if anchor.get(field) in (None, "")]
        if missing:
            _error("log_context_anchor_invalid", f"anchor is missing configured context fields: {', '.join(missing)}")
        return
    scenario_id = scenario_id or index_set.scenario_id
    if scenario_id == Scenario.LOG:
        required = ["gseIndex", "iterationIndex"]
        if any(anchor.get(field) in (None, "") for field in required):
            _error("log_context_anchor_invalid", "log anchor requires gseIndex and iterationIndex")
        if anchor.get("bk_host_id") in (None, "") and anchor.get("serverIp") in (None, ""):
            _error("log_context_anchor_invalid", "log anchor requires bk_host_id or serverIp")
        return
    if scenario_id == Scenario.BKDATA:
        if anchor.get("gseindex") in (None, "") or anchor.get("_iteration_idx") in (None, ""):
            _error("log_context_anchor_invalid", "bkdata anchor requires gseindex and _iteration_idx")
        host_locator = anchor.get("bk_host_id") not in (None, "") or anchor.get("ip") not in (None, "")
        container_locator = anchor.get("container_id") not in (None, "") and anchor.get("logfile") not in (None, "")
        if not (host_locator or container_locator):
            _error("log_context_anchor_invalid", "bkdata anchor requires a host or container locator")


def _validate_clustering_anchor(source, anchor):
    result_table_id = anchor.get("result_table_id")
    if not result_table_id:
        _error("log_context_anchor_invalid", "clustering context requires anchor.result_table_id")
    allowed_result_tables = {
        source["route"]["clustered_rt"],
        source["route"]["data_label"],
    }
    if result_table_id not in allowed_result_tables:
        _error(
            "log_context_source_mismatch",
            "clustering anchor result table does not match the explicitly resolved clustering route",
        )
    _validate_context_anchor(
        source["index_set"],
        anchor,
        scenario_id=Scenario.BKDATA,
        allowed_result_table_ids=allowed_result_tables,
    )


def _resolve_scene_anchor(source, anchor):
    index_set_id = anchor.get("index_set_id")
    result_table_id = anchor.get("result_table_id")
    if not index_set_id or not result_table_id:
        _error("log_context_anchor_invalid", "scene context requires anchor.index_set_id and anchor.result_table_id")
    try:
        index_set = scope_space_queryset(LogIndexSet.objects).get(
            index_set_id=index_set_id, space_uid__in=source["related_space_uids"]
        )
    except LogIndexSet.DoesNotExist:
        _error("log_context_source_mismatch", "scene anchor index set is outside the resolved scene source")
    mapped_ids, unknown_result_tables = _resource_index_set_ids_for_result_tables(
        [result_table_id], set(source["related_space_uids"])
    )
    if unknown_result_tables or index_set.index_set_id not in mapped_ids:
        _error("log_context_source_mismatch", "scene anchor result table does not belong to anchor.index_set_id")
    matched_ids = {item["index_set"].index_set_id for item in _scene_candidates(source) if item["matched"]}
    if index_set.index_set_id not in matched_ids:
        _error("log_context_source_mismatch", "scene anchor index set does not match table_id_conditions")
    return index_set


def _scene_candidates(source):
    queryset = scope_space_queryset(LogIndexSet.objects).filter(space_uid__in=source["related_space_uids"])
    index_sets = list(queryset.order_by("index_set_id")[: MAX_SCENE_TARGETS + 1])
    source["candidates_truncated"] = len(index_sets) > MAX_SCENE_TARGETS
    index_sets = index_sets[:MAX_SCENE_TARGETS]
    tag_ids = {int(tag_id) for item in index_sets for tag_id in item.tag_ids or [] if str(tag_id).isdigit()}
    tags = {str(item.tag_id): item for item in IndexSetTag.objects.filter(tag_id__in=tag_ids, tag_type=TAG_TYPE_SCENE)}
    candidates = []
    for index_set in index_sets:
        tag_values = defaultdict(set)
        for tag_id in index_set.tag_ids or []:
            tag = tags.get(str(tag_id))
            if tag:
                tag_values[tag.name].add(tag.value)
        group_results = [
            [_scene_condition_matches(tag_values, condition) for condition in group]
            for group in source["table_id_conditions"]
        ]
        matched = any(all(result is True for result in group) for group in group_results)
        if not matched and any(
            all(result is not False for result in group) and any(result is None for result in group)
            for group in group_results
        ):
            matched = None
        reason = None
        if not index_set.is_active:
            matched = False
            reason = "index_set_inactive"
        elif matched is False:
            reason = "route_condition_mismatch"
        elif not LogIndexSetData.objects.filter(
            index_set_id=index_set.index_set_id,
            type=IndexSetDataType.RESULT_TABLE.value,
            apply_status=LogIndexSetData.Status.NORMAL,
        ).exists():
            matched = False
            reason = "result_table_missing"
        candidates.append({"index_set": index_set, "matched": matched, "reason": reason})
    return candidates


def _scene_condition_matches(tag_values, condition):
    actual_values = tag_values.get(condition["field_name"], set())
    expected_values = set(str(value) for value in condition.get("value") or [])
    op = condition.get("op", "eq")
    if op == "eq":
        return bool(actual_values & expected_values)
    if op == "ne":
        return not bool(actual_values & expected_values)
    # Regex conditions are deliberately evaluated by UnifyQuery's scene router.  Re-running
    # caller-controlled regexes in the Resource process would create a second, divergent and
    # potentially expensive regex engine.  ``None`` means runtime routing decides the target.
    return None


def _resource_index_set_ids_for_result_tables(result_table_ids, allowed_spaces):
    index_set_ids = set()
    remaining = set()
    prefix = "bklog_index_set_"
    for result_table_id in result_table_ids:
        if result_table_id.startswith(prefix):
            try:
                index_set_ids.add(int(result_table_id.removeprefix(prefix).split("_", 1)[0]))
                continue
            except (TypeError, ValueError, IndexError):
                pass
        remaining.add(result_table_id)

    if remaining:
        physical_rows = list(
            LogIndexSetData.objects.filter(
                result_table_id__in=remaining,
                type=IndexSetDataType.RESULT_TABLE.value,
                apply_status=LogIndexSetData.Status.NORMAL,
            ).values_list("result_table_id", "index_set_id")
        )
        candidate_ids = set()
        for result_table_id, index_set_id in physical_rows:
            candidate_ids.add(index_set_id)
        visible_ids = set(
            scope_space_queryset(LogIndexSet.objects)
            .filter(index_set_id__in=candidate_ids, space_uid__in=allowed_spaces)
            .values_list("index_set_id", flat=True)
        )
        index_set_ids.update(visible_ids)
        visible_result_tables = {
            result_table_id for result_table_id, index_set_id in physical_rows if index_set_id in visible_ids
        }
        remaining -= visible_result_tables

    return index_set_ids, sorted(remaining)


def _scene_target(index_set):
    return {
        "index_set_id": index_set.index_set_id,
        "index_set_name": index_set.index_set_name,
        "space_uid": index_set.space_uid,
        "scenario_id": index_set.scenario_id,
        "result_table_ids": list(
            LogIndexSetData.objects.filter(
                index_set_id=index_set.index_set_id,
                type=IndexSetDataType.RESULT_TABLE.value,
                apply_status=LogIndexSetData.Status.NORMAL,
            ).values_list("result_table_id", flat=True)[:MAX_SCENE_TARGETS]
        ),
    }


def _field_compatibility(index_sets):
    field_variants = defaultdict(lambda: defaultdict(list))
    missing_snapshots = []
    for index_set in index_sets[:MAX_SCENE_TARGETS]:
        snapshot = index_set.get_fields(use_snapshot=True) or {}
        fields = snapshot.get("fields") or []
        if not fields:
            missing_snapshots.append(index_set.index_set_id)
            continue
        for field in fields:
            field_name = field.get("field_name")
            if field_name:
                field_variants[field_name][field.get("field_type") or "unknown"].append(index_set.index_set_id)
    index_set_count = len(index_sets[:MAX_SCENE_TARGETS])
    common_fields = []
    differences = []
    for field_name, variants in sorted(field_variants.items()):
        covered = {index_set_id for ids in variants.values() for index_set_id in ids}
        item = {
            "field_name": field_name,
            "variants": [
                {"field_type": field_type, "index_set_ids": sorted(index_set_ids)}
                for field_type, index_set_ids in sorted(variants.items())
            ],
            "present_in_all": len(covered) == index_set_count,
        }
        if len(variants) == 1 and item["present_in_all"]:
            common_fields.append(field_name)
        else:
            differences.append(item)
    return {
        "index_set_count": index_set_count,
        "common_fields": common_fields,
        "differences": differences,
        "missing_snapshot_index_set_ids": missing_snapshots,
    }


def _field_statistics(handler, field_type):
    total_count = handler.get_total_count()
    field_count = handler.get_field_count()
    data = {
        "total_count": total_count,
        "field_count": field_count,
        "distinct_count": handler.get_distinct_count(),
        "field_percent": round(field_count / total_count, 2) if total_count and field_count else 0,
    }
    if FIELD_TYPE_MAP.get(field_type, "") == FieldDataTypeEnum.INT.value:
        data["value_analysis"] = {
            "max": handler.get_agg_value(AggTypeEnum.MAX.value),
            "min": handler.get_agg_value(AggTypeEnum.MIN.value),
            "avg": handler.get_agg_value(AggTypeEnum.AVG.value),
            "median": handler.get_agg_value(AggTypeEnum.MEDIAN.value),
        }
    return data


def _run_query(callback, *, clustering=False, pattern=False, time_zone=None):
    previous_time_zone = get_local_param("time_zone", _MISSING)
    if time_zone:
        set_local_param("time_zone", time_zone)
    try:
        return callback()
    except BklogPermissionError:
        raise
    except ValidationError as error:
        if str(getattr(error, "code", "")) in set(ERRORS.values()):
            raise
        _raise_query_error(error, clustering=clustering, pattern=pattern)
    except Exception as error:
        _raise_query_error(error, clustering=clustering, pattern=pattern)
    finally:
        if time_zone:
            if previous_time_zone is _MISSING:
                del_local_param("time_zone")
            else:
                set_local_param("time_zone", previous_time_zone)


def _raise_query_error(error, *, clustering=False, pattern=False):
    message = sanitize_sensitive_text(getattr(error, "message", None) or str(error), maximum=None).lower()
    if any(token in message for token in ("timeout", "timed out", "read timed out", "deadline exceeded")):
        _error("log_query_timeout", "the downstream query timed out")
    if clustering and any(
        token in message
        for token in ("router", "routing", "data label", "data_label", "table_id not found", "route not found")
    ):
        _error("log_clustering_route_not_registered", "the explicitly resolved clustering route is not registered")
    if any(token in message for token in ("rewrite", "parse sql", "sql parser", "syntax error", "invalid sql")):
        _error("log_query_rewrite_failed", "the downstream query could not be rewritten")
    if pattern:
        _error("log_clustering_pattern_failed", "the clustering pattern query failed")
    _error("log_query_execution_failed", "the downstream query failed")


def _bounded_items(items):
    returned = []
    returned_bytes = 0
    original_item_sizes = [len(json.dumps(item, ensure_ascii=False, default=str).encode("utf-8")) for item in items]
    original_bytes = sum(original_item_sizes)
    field_truncations = 0
    item_truncations = 0
    for item, original_item_bytes in zip(items, original_item_sizes):
        stats = {"field_truncations": 0}
        bounded_item = _truncate_log_value(item, stats)
        bounded_item_bytes = len(json.dumps(bounded_item, ensure_ascii=False, default=str).encode("utf-8"))
        if bounded_item_bytes > MAX_LOG_ITEM_BYTES:
            if isinstance(bounded_item, dict) and "record" in bounded_item:
                bounded_item = {
                    "record": {
                        "__truncated__": True,
                        "__original_size_bytes__": original_item_bytes,
                    },
                    "context_anchor": bounded_item.get("context_anchor", {}),
                }
            else:
                bounded_item = {
                    "__truncated__": True,
                    "__original_size_bytes__": original_item_bytes,
                    **{
                        key: bounded_item[key]
                        for key in (
                            "dtEventTimeStamp",
                            "signature",
                            "pattern",
                            "__id__",
                            "index",
                            "__index_set_id__",
                            "__result_table",
                        )
                        if isinstance(bounded_item, dict) and key in bounded_item
                    },
                }
            bounded_item_bytes = len(json.dumps(bounded_item, ensure_ascii=False, default=str).encode("utf-8"))
            item_truncations += 1
        if returned_bytes + bounded_item_bytes > MAX_LOG_RESPONSE_BYTES:
            break
        returned.append(bounded_item)
        returned_bytes += bounded_item_bytes
        field_truncations += stats["field_truncations"]
    return returned, {
        "truncated": len(returned) < len(items) or bool(field_truncations or item_truncations),
        "original_item_count": len(items),
        "returned_item_count": len(returned),
        "original_size_bytes": original_bytes,
        "returned_size_bytes": returned_bytes,
        "field_truncation_count": field_truncations,
        "item_truncation_count": item_truncations,
        "max_field_bytes": MAX_LOG_FIELD_BYTES,
        "max_item_bytes": MAX_LOG_ITEM_BYTES,
        "max_response_bytes": MAX_LOG_RESPONSE_BYTES,
    }


def _truncate_log_value(value, stats):
    if isinstance(value, dict):
        return {str(key): _truncate_log_value(child, stats) for key, child in value.items()}
    if isinstance(value, list):
        return [_truncate_log_value(item, stats) for item in value]
    if isinstance(value, tuple):
        return [_truncate_log_value(item, stats) for item in value]
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        if len(encoded) <= MAX_LOG_FIELD_BYTES:
            return value
        stats["field_truncations"] += 1
        return encoded[:MAX_LOG_FIELD_BYTES].decode("utf-8", errors="ignore")
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)


def _downstream_warnings(data):
    status = data.get("status") if isinstance(data, dict) else None
    if not status:
        return []
    if isinstance(status, dict):
        code = status.get("code")
        message = status.get("message") or "downstream query returned a status object"
    else:
        code = str(status)
        message = "downstream query returned a non-empty status"
    return [
        {
            "code": f"downstream_{code or 'status'}",
            "message": sanitize_sensitive_text(message),
            "scope": "downstream.query",
            "retryable": True,
        }
    ]


def _downstream_status(data, warnings):
    if not warnings:
        return "success"
    has_data = bool(
        isinstance(data, dict) and (data.get("list") or data.get("series") or data.get("aggs") or data.get("total"))
    )
    return "partial" if has_data else "failed"


def _public_source(source):
    public = {
        "type": source["type"],
        "space_uid": source["space_uid"],
        "bk_biz_id": source["bk_biz_id"],
    }
    if source["type"] in {SOURCE_INDEX_SET, SOURCE_CLUSTERING}:
        public["index_set_id"] = source["index_set_id"]
    else:
        public["table_id_conditions"] = source["table_id_conditions"]
        public["scene_filter_values"] = copy.deepcopy(source.get("scene_filter_values") or [])
    return public


def _result(source, *, route, status="success", warnings=None, **payload):
    return {
        "source": _public_source(source),
        "status": status,
        "observed_at": timezone.now().isoformat(),
        **payload,
        "route": route,
        "warnings": warnings or [],
    }


def _error(name, message):
    raise ValidationError(f"{name}: {message}", code=ERRORS[name])


FUNCTIONS = {
    "bklog.log.fields": {
        "func_name": "bklog.log.fields",
        "description": "Discover current query fields and cross-index field compatibility for an index set or scene.",
        "safety_level": "read",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": FIELDS_PARAMS_SCHEMA,
        "response_schema": FIELDS_RESPONSE_SCHEMA,
        "limits": {"max_scene_targets": MAX_SCENE_TARGETS, "desensitization_required": True},
        "errors": [
            "log_source_invalid",
            "log_index_set_not_found",
            "log_scene_invalid",
            "log_scene_disabled",
            "log_time_range_invalid",
            "log_query_timeout",
            "log_query_execution_failed",
        ],
        "examples": [
            {"params": {"source": {"type": "index_set", "index_set_id": 16462}}},
            {
                "params": {
                    "source": {
                        "type": "scene",
                        "space_uid": "bkcc__2",
                        "table_id_conditions": [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]],
                    },
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                }
            },
        ],
    },
    "bklog.log.search": {
        "func_name": "bklog.log.search",
        "description": "Search bounded desensitized log details through the existing BKLog search chain.",
        "safety_level": "read",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": SEARCH_PARAMS_SCHEMA,
        "response_schema": SEARCH_RESPONSE_SCHEMA,
        "limits": {
            "max_page_size": MAX_SEARCH_PAGE_SIZE,
            "max_result_window": MAX_RESULT_WINDOW,
            "max_response_bytes": MAX_LOG_RESPONSE_BYTES,
        },
        "errors": [
            "log_source_invalid",
            "log_index_set_not_found",
            "log_scene_invalid",
            "log_scene_disabled",
            "log_time_range_invalid",
            "log_query_limit_exceeded",
            "log_context_anchor_invalid",
            "log_query_timeout",
            "log_query_rewrite_failed",
            "log_query_execution_failed",
            "log_clustering_config_not_found",
            "log_clustering_result_table_missing",
            "log_clustering_route_ambiguous",
            "log_clustering_route_not_registered",
        ],
        "examples": [
            {
                "params": {
                    "source": {"type": "index_set", "index_set_id": 16462},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "keyword": "error",
                    "addition": [],
                    "sort_list": [["dtEventTimeStamp", "desc"]],
                    "begin": 0,
                    "size": 50,
                    "track_total_hits": True,
                    "is_desensitize": True,
                }
            },
            {
                "params": {
                    "source": {"type": "clustering", "index_set_id": 16462},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "addition": [{"field": "signature", "operator": "is", "value": "example-signature"}],
                    "begin": 0,
                    "size": 20,
                }
            },
        ],
    },
    "bklog.log.aggregate": {
        "func_name": "bklog.log.aggregate",
        "description": "Run bounded terms, histogram, or field-statistics aggregation without raw DSL or SQL.",
        "safety_level": "read",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": AGGREGATE_PARAMS_SCHEMA,
        "response_schema": AGGREGATE_RESPONSE_SCHEMA,
        "limits": {
            "max_fields_per_request": 1,
            "max_buckets": MAX_AGG_BUCKETS,
            "max_time_range_milliseconds": MAX_AGG_RANGE_MILLISECONDS,
            "raw_aggregation_dsl": False,
        },
        "errors": [
            "log_source_invalid",
            "log_index_set_not_found",
            "log_scene_invalid",
            "log_scene_disabled",
            "log_time_range_invalid",
            "log_query_timeout",
            "log_query_rewrite_failed",
            "log_query_execution_failed",
        ],
        "examples": [
            {
                "params": {
                    "source": {"type": "index_set", "index_set_id": 16462},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "keyword": "*",
                    "addition": [],
                    "aggregation": {"type": "terms", "field": "level", "size": 20},
                }
            },
            {
                "params": {
                    "source": {"type": "index_set", "index_set_id": 16462},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "aggregation": {"type": "histogram", "interval": "5m"},
                }
            },
        ],
    },
    "bklog.log.context": {
        "func_name": "bklog.log.context",
        "description": "Get bounded before/after context after validating an immutable log anchor.",
        "safety_level": "inspect",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": CONTEXT_PARAMS_SCHEMA,
        "response_schema": CONTEXT_RESPONSE_SCHEMA,
        "limits": {"max_context_size_per_direction": MAX_CONTEXT_SIZE // 2, "desensitization_required": True},
        "errors": [
            "log_source_invalid",
            "log_index_set_not_found",
            "log_scene_invalid",
            "log_scene_disabled",
            "log_context_anchor_invalid",
            "log_context_source_mismatch",
            "log_query_timeout",
            "log_query_rewrite_failed",
            "log_query_execution_failed",
            "log_clustering_config_not_found",
            "log_clustering_result_table_missing",
            "log_clustering_route_not_registered",
        ],
        "examples": [
            {
                "params": {
                    "source": {"type": "index_set", "index_set_id": 16462},
                    "context_anchor": {
                        "index_set_id": 16462,
                        "result_table_id": "2_bklog_app",
                        "scenario_id": "log",
                        "sort_values": {
                            "dtEventTimeStamp": 1767227400000,
                            "gseIndex": 100,
                            "iterationIndex": 1,
                        },
                        "identity": {"serverIp": "127.0.0.1", "path": "/var/log/app.log"},
                    },
                    "size": 50,
                }
            }
        ],
    },
    "bklog.log.scene.resolve": {
        "func_name": "bklog.log.scene.resolve",
        "description": "Resolve scene conditions into related spaces, actual result tables, matched targets, and exclusions.",
        "safety_level": "inspect",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": SCENE_RESOLVE_PARAMS_SCHEMA,
        "response_schema": SCENE_RESOLVE_RESPONSE_SCHEMA,
        "limits": {"max_scene_targets": MAX_SCENE_TARGETS},
        "errors": [
            "log_scene_invalid",
            "log_scene_disabled",
            "log_time_range_invalid",
            "log_query_timeout",
            "log_query_rewrite_failed",
            "log_query_execution_failed",
        ],
        "examples": [
            {
                "params": {
                    "source": {
                        "type": "scene",
                        "space_uid": "bkcc__2",
                        "table_id_conditions": [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]],
                    },
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                }
            }
        ],
    },
    "bklog.clustering.pattern.search": {
        "func_name": "bklog.clustering.pattern.search",
        "description": "Query clustering patterns through the existing PatternHandler with explicit entry-index routing.",
        "safety_level": "read",
        "data_classification": "sensitive_logs",
        "validate_params": True,
        "params_schema": CLUSTERING_PATTERN_PARAMS_SCHEMA,
        "response_schema": PATTERN_RESPONSE_SCHEMA,
        "limits": {
            "max_patterns": MAX_PATTERN_SIZE,
            "max_group_fields": MAX_PATTERN_GROUP_FIELDS,
            "include_origin_log": False,
            "pattern_level": "server_managed",
        },
        "errors": [
            "log_source_invalid",
            "log_index_set_not_found",
            "log_time_range_invalid",
            "log_clustering_config_not_found",
            "log_clustering_result_table_missing",
            "log_clustering_route_ambiguous",
            "log_clustering_route_not_registered",
            "log_clustering_pattern_failed",
            "log_query_timeout",
            "log_query_rewrite_failed",
            "log_query_execution_failed",
        ],
        "examples": [
            {
                "params": {
                    "source": {"type": "clustering", "index_set_id": 16462},
                    "start_time": 1767225600000,
                    "end_time": 1767229200000,
                    "keyword": "error",
                    "addition": [],
                    "size": 100,
                    "group_by": ["serverIp"],
                    "show_new_pattern": False,
                    "year_on_year_hour": 24,
                    "filter_not_clustering": True,
                }
            }
        ],
    },
}

HANDLERS = {
    "bklog.log.fields": get_log_fields,
    "bklog.log.search": search_logs,
    "bklog.log.aggregate": aggregate_logs,
    "bklog.log.context": get_log_context,
    "bklog.log.scene.resolve": resolve_log_scene,
    "bklog.clustering.pattern.search": search_clustering_patterns,
}
