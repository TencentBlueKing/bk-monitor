"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy
import csv
import json
from io import StringIO
from typing import Any, Dict, List

from django.conf import settings

from apps.api import UnifyQueryApi
from apps.log_desensitize.handlers.desensitize import DesensitizeHandler
from apps.log_desensitize.utils import merge_nested_data
from apps.log_esquery.esquery.builder.query_string_builder import QueryStringBuilder
from apps.log_search.constants import (
    ASYNC_EXPORT_SCROLL,
    MAX_ASYNC_COUNT,
    MAX_QUICK_EXPORT_ASYNC_COUNT,
    MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT,
    MAX_RESULT_WINDOW,
)
from apps.log_unifyquery.constants import BASE_OP_MAP, SEARCH_AFTER_KEY
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.utils import deal_time_format, transform_advanced_addition
from apps.utils.local import get_local_param, get_request_external_username, get_request_username
from apps.utils.log import logger


class SceneUnifyQueryHandler(UnifyQueryHandler):
    """
    Scene-based search handler built on top of UnifyQueryHandler.
    Uses space_uid + table_id_conditions for routing instead of index_set_ids.
    Reuses parent's query_ts_raw (with pre_search), _deal_query_result, _enhance, etc.
    """

    def __init__(self, params):
        # Bypass parent __init__ entirely — it requires index_set_ids.
        self.search_params: dict[str, Any] = params
        self.space_uid: str = params["space_uid"]
        self.table_id_conditions: List[List[Dict]] = params["table_id_conditions"]
        self.bk_biz_id = params.get("bk_biz_id")

        # query string — reuse parent's _enhance + QueryStringBuilder
        self.query_string: str = params.get("keyword", "") or ""
        self.origin_query_string: str = params.get("keyword")
        self._enhance()
        self.query_string = QueryStringBuilder(self.query_string).query_string

        self._agg_field_name: str = params.get("agg_field", "")
        self.request_username = get_request_external_username() or get_request_username()

        # sort — use frontend-provided sort_list directly, no DB lookup
        self.order_by: list = []
        self.origin_order_by: list = params.get("sort_list") or [["dtEventTimeStamp", "desc"]]
        for param in self.origin_order_by:
            if param[1] == "desc":
                self.order_by.append(f"-{param[0]}")
            else:
                self.order_by.append(param[0])

        self.is_multi_rt: bool = False
        self.index_set_ids: list = []

        # time — fields endpoint may pass empty strings
        raw_start = params.get("start_time", "")
        raw_end = params.get("end_time", "")
        if raw_start and raw_end:
            # HTTP params may arrive as numeric strings; convert so deal_time_format
            # takes the fast int path instead of falling into dateutil.parser.parse
            # which overflows on 13-digit millisecond strings.
            if isinstance(raw_start, str) and raw_start.isdigit():
                raw_start = int(raw_start)
            if isinstance(raw_end, str) and raw_end.isdigit():
                raw_end = int(raw_end)
            self.start_time, self.end_time = deal_time_format(raw_start, raw_end)
        else:
            self.start_time, self.end_time = "", ""

        self.field: dict = {}

        # desensitize — no index_set_id, skip DB queries
        self.is_desensitize = False
        self.field_configs: list = []
        self.text_fields: list = []
        self.text_fields_field_configs: list = []
        self.desensitize_handler = DesensitizeHandler([])
        self.text_fields_desensitize_handler = DesensitizeHandler([])

        self.export_fields = params.get("export_fields")
        self.highlight: bool = params.get("can_highlight", True)
        self.time_field: str = "dtEventTimeStamp"
        self.log_bcs_cluster_name_dict: dict = {}

        # Build base_dict using table_id_conditions routing
        self.base_dict = self._init_scene_base_dict()
        self.result_merge_base_dict = self.init_result_merge_base_dict(self.base_dict)

    # ------------------------------------------------------------------
    # Base dict construction
    # ------------------------------------------------------------------

    def _init_scene_base_dict(self) -> dict:
        conditions = self._transform_scene_additions()
        query_dict = {
            "data_source": "bklog",
            "table_id": "",
            "table_id_conditions": self.table_id_conditions,
            "query_string": self.query_string,
            "time_field": "dtEventTimeStamp",
            "conditions": conditions,
            "field_name": "dtEventTimeStamp",
            "function": [],
            "reference_name": "a",
        }
        base = {
            "space_uid": self.space_uid,
            "query_list": [query_dict],
            "metric_merge": "a",
            "order_by": self.order_by,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": get_local_param("time_zone", settings.TIME_ZONE),
        }
        if self.bk_biz_id:
            base["bk_biz_id"] = self.bk_biz_id
        return base

    def _transform_scene_additions(self) -> dict:
        """Convert addition to unify-query conditions format, without index_info dependency."""
        field_list = []
        condition_list = []
        addition = self.search_params.get("addition", [])
        for item in addition:
            field = item.get("key") or item.get("field", "")
            operator = item.get("method") or item.get("operator", "")
            value = item.get("value", "")

            if field in ["*", "__query_string__"]:
                value_list = value if isinstance(value, list) else (value.split(",") if value else [])
                new_value_list = []
                for v in value_list:
                    if field == "*":
                        v = '"' + v.replace('"', '\\"') + '"'
                    if v:
                        new_value_list.append(v)
                if new_value_list:
                    new_query_string = " OR ".join(new_value_list)
                    if field == "*" and self.query_string != "*":
                        self.query_string = self.query_string + " AND (" + new_query_string + ")"
                    else:
                        self.query_string = new_query_string
                continue

            if field_list:
                condition_list.append("and")

            if operator in BASE_OP_MAP:
                field_list.append({
                    "field_name": field,
                    "op": BASE_OP_MAP[operator],
                    "value": value if isinstance(value, list) else (value.split(",") if value else []),
                })
            else:
                new_field_list, new_condition_list = transform_advanced_addition(
                    {"field": field, "operator": operator, "value": value}
                )
                field_list.extend(new_field_list)
                condition_list.extend(new_condition_list)

        for f in field_list:
            f["value"] = [str(v) for v in f["value"]]

        return {"field_list": field_list, "condition_list": condition_list}

    # ------------------------------------------------------------------
    # Override _deal_query_result to handle missing index_set_ids
    # ------------------------------------------------------------------

    def _deal_query_result(self, result_dict: dict) -> dict:
        log_list = []
        origin_log_list = []
        for log in result_dict.get("list", []):
            log = merge_nested_data(log)
            if (self.field_configs or self.text_fields_field_configs) and self.is_desensitize:
                log = self._log_desensitize(log)
            log = self._add_cmdb_fields(log)
            log = self._add_bcs_cluster_fields(log)

            if self.export_fields:
                new_origin_log = {}
                for _export_field in self.export_fields:
                    if _export_field in log:
                        new_origin_log[_export_field] = log[_export_field]
                    elif "." in _export_field:
                        key, *field_list = _export_field.split(".")
                        _result = log.get(key, {})
                        for _field in field_list:
                            if isinstance(_result, dict) and _field in _result:
                                _result = _result[_field]
                            else:
                                _result = ""
                                break
                        new_origin_log[_export_field] = _result
                    else:
                        new_origin_log[_export_field] = log.get(_export_field, "")
                origin_log = new_origin_log
            else:
                origin_log = log

            _index = log.pop("__index", None)
            log.update({"index": _index})
            doc_id = log.pop("__doc_id", None)
            log.update({"__id__": doc_id})

            if "__highlight" not in log:
                origin_log_list.append(origin_log)
                log_list.append(log)
                continue
            else:
                origin_log_list.append(copy.deepcopy(origin_log))

            if not (self.field_configs or self.text_fields_field_configs) or not self.is_desensitize:
                log = self._deal_object_highlight(log=log, highlight=log["__highlight"])

            del log["__highlight"]
            log_list.append(log)

        result_dict.update({
            "aggregations": {},
            "aggs": {},
            "list": log_list,
            "origin_log_list": origin_log_list,
            "total": result_dict.get("total", 0),
            "took": result_dict.get("took", 0),
        })
        return result_dict

    # ------------------------------------------------------------------
    # Override _save_history — scene search has no index_set_id
    # ------------------------------------------------------------------

    def _save_history(self, result, search_type):
        pass

    # ------------------------------------------------------------------
    # Override search — skip pre_search to avoid arrow.get() overflow
    # with millisecond timestamps (parent pre_search calls
    # arrow.get(self.start_time) which interprets ms as seconds → year 58000+).
    # ------------------------------------------------------------------

    def search(self, search_type="default", is_export=False):
        search_dict = copy.deepcopy(self.base_dict)
        if self.search_params["size"] > MAX_RESULT_WINDOW:
            self.search_params["size"] = MAX_RESULT_WINDOW

        once_size = min(self.search_params["size"], MAX_RESULT_WINDOW)

        if is_export:
            once_size = MAX_RESULT_WINDOW
            self.search_params["size"] = MAX_RESULT_WINDOW

        search_dict["from"] = self.search_params["begin"]
        search_dict["limit"] = once_size
        search_dict["highlight"] = {"enable": self.highlight}

        result = self.query_ts_raw(search_dict)
        result = self._deal_query_result(result)

        if self.search_params.get("original_search"):
            return result

        field_dict = self._analyze_field_length(result.get("list"))
        result.update({"fields": field_dict})

        return result

    # ------------------------------------------------------------------
    # Scene-specific query methods
    # ------------------------------------------------------------------

    def fields(self, scope="default") -> dict:
        query_body = {
            "space_uid": self.space_uid,
            "data_source": "bklog",
            "table_id": "",
            "table_id_conditions": self.table_id_conditions,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
        }
        if self.bk_biz_id:
            query_body["bk_biz_id"] = self.bk_biz_id

        logger.info("[scene_fields] space_uid=%s, conditions=%s", self.space_uid, json.dumps(self.table_id_conditions))
        field_data = UnifyQueryApi.query_field_map(query_body)

        field_list = []
        for field_name, field_info in field_data.get("fields", {}).items():
            field_list.append({
                "field_name": field_name,
                "field_type": field_info.get("type", "object"),
                "is_analyzed": field_info.get("type") == "text",
                "es_doc_values": field_info.get("type") != "text",
                "description": field_info.get("description", ""),
                "field_alias": field_info.get("alias", ""),
                "is_display": True,
                "is_editable": True,
            })

        sort_list = self.origin_order_by or [["dtEventTimeStamp", "desc"]]

        return {
            "fields": field_list,
            "display_fields": ["dtEventTimeStamp", "log"],
            "sort_list": sort_list,
            "default_sort_list": sort_list,
            "time_field": self.time_field,
            "time_field_type": "date",
            "time_field_unit": "millisecond",
            "config": [],
        }

    def date_histogram(self, interval: str = "auto") -> dict:
        conditions = self._transform_scene_additions()
        query_body = {
            "space_uid": self.space_uid,
            "query_list": [
                {
                    "data_source": "bklog",
                    "table_id": "",
                    "table_id_conditions": self.table_id_conditions,
                    "query_string": self.query_string or "*",
                    "time_field": "dtEventTimeStamp",
                    "conditions": conditions,
                    "field_name": "dtEventTimeStamp",
                    "function": [{"method": "count"}],
                    "time_aggregation": {
                        "function": "count_over_time",
                        "window": interval if interval != "auto" else "1m",
                    },
                    "reference_name": "a",
                }
            ],
            "metric_merge": "a",
            "step": interval if interval != "auto" else "1m",
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
        }
        if self.bk_biz_id:
            query_body["bk_biz_id"] = self.bk_biz_id

        logger.info("[scene_date_histogram] space_uid=%s", self.space_uid)
        return self.query_ts(query_body)

    def agg_field(self, agg_field: str) -> dict:
        conditions = self._transform_scene_additions()
        query_body = {
            "space_uid": self.space_uid,
            "query_list": [
                {
                    "data_source": "bklog",
                    "table_id": "",
                    "table_id_conditions": self.table_id_conditions,
                    "query_string": self.query_string or "*",
                    "time_field": "dtEventTimeStamp",
                    "conditions": conditions,
                    "field_name": agg_field,
                    "function": [
                        {"method": "count", "dimensions": [agg_field]},
                    ],
                    "reference_name": "a",
                }
            ],
            "metric_merge": "a",
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
        }
        if self.bk_biz_id:
            query_body["bk_biz_id"] = self.bk_biz_id

        logger.info("[scene_agg_field] space_uid=%s, field=%s", self.space_uid, agg_field)
        return self.query_ts_reference(query_body)

    def total(self) -> dict:
        search_dict = copy.deepcopy(self.base_dict)
        search_dict["from"] = 0
        search_dict["limit"] = 1
        search_dict["highlight"] = {"enable": False}

        logger.info("[scene_total] space_uid=%s", self.space_uid)
        result = self.query_ts_raw(search_dict)
        return {"total": result.get("total", 0)}

    def aggs_date_histogram(self, interval: str = "auto", group_field: str = None) -> dict:
        params = copy.deepcopy(self.base_dict)
        response = self._date_histogram_unify_query(interval, group_field, params)
        if not response.get("series"):
            return {"aggs": {}}
        return self.obtain_result_data(interval, group_field, response)

    # ------------------------------------------------------------------
    # Export overrides — bypass index_set_obj / scenario_id dependencies
    # ------------------------------------------------------------------

    def pre_get_result(self, sorted_fields: list, size: int, scroll=None):
        search_dict = copy.deepcopy(self.base_dict)
        # Scene mode always uses bklog data_source; always apply order_by
        order_by = []
        for param in sorted_fields:
            if param[1] == "asc":
                order_by.append(param[0])
            elif param[1] == "desc":
                order_by.append(f"-{param[0]}")
        search_dict["order_by"] = order_by

        search_dict["from"] = self.search_params.get("begin", 0)
        search_dict["limit"] = size
        search_dict["scroll"] = scroll
        search_dict["is_search_after"] = True
        return UnifyQueryApi.query_ts_raw(search_dict)

    def search_after_result(self, search_result, sorted_fields):
        search_dict = copy.deepcopy(self.base_dict)
        order_by = []
        for param in sorted_fields:
            if param[1] == "asc":
                order_by.append(param[0])
            elif param[1] == "desc":
                order_by.append(f"-{param[0]}")
        search_dict["order_by"] = order_by

        result_size = len(search_result["list"])
        max_result_window = MAX_RESULT_WINDOW
        max_export_count = MAX_ASYNC_COUNT

        search_dict["from"] = self.search_params.get("begin", 0)
        search_dict["limit"] = max_result_window
        search_dict["is_search_after"] = True
        while result_size < max_export_count:
            result_table_options = {
                key: value
                for key, value in search_result.get("result_table_options", {}).items()
                if value.get(SEARCH_AFTER_KEY)
            }

            if not result_table_options:
                break

            search_dict["result_table_options"] = result_table_options
            search_result = UnifyQueryApi.query_ts_raw(search_dict)
            new_result_size = len(search_result.get("list", []))

            if new_result_size == 0:
                break

            result_size += new_result_size
            yield self._deal_query_result(search_result)

    def export_data(self, is_quick_export: bool = False):
        search_params = copy.deepcopy(self.base_dict)
        search_params["limit"] = MAX_RESULT_WINDOW
        search_params["scroll"] = ASYNC_EXPORT_SCROLL
        search_params["slice_max"] = MAX_QUICK_EXPORT_ASYNC_SLICE_COUNT if is_quick_export else 0

        max_result_count = MAX_QUICK_EXPORT_ASYNC_COUNT if is_quick_export else MAX_ASYNC_COUNT
        total_count = 0
        while total_count < max_result_count:
            search_params["clear_cache"] = total_count == 0
            search_result = UnifyQueryHandler.query_ts_raw_with_scroll(search_params)
            if not search_result.get("list"):
                break

            yield self._deal_query_result(search_result)

            total_count += len(search_result["list"])

            if search_result.get("done", False):
                break

    def export_chart_data(self):
        """Stream chart data as CSV rows — scene variant without index_set_id."""
        search_params = copy.deepcopy(self.base_dict)
        search_params["limit"] = MAX_RESULT_WINDOW
        max_result_count = MAX_ASYNC_COUNT
        total_count = 0

        header_written = False
        fields = []
        row_buffer = StringIO()
        csv_writer = csv.writer(row_buffer)
        while total_count < max_result_count:
            search_params["clear_cache"] = total_count == 0
            search_result = UnifyQueryHandler.query_ts_raw_with_scroll(search_params)
            if not search_result.get("list"):
                break
            if not header_written:
                result_table_options = list(search_result.get("result_table_options", {}).values())
                result_schema = result_table_options[0]["result_schema"] if result_table_options else []
                fields = [field["field_alias"] for field in result_schema]
                csv_writer.writerow(fields)
                header_written = True
            for record in search_result["list"]:
                csv_writer.writerow([record.get(field, "") for field in fields])
            yield row_buffer.getvalue()
            row_buffer.seek(0)
            row_buffer.truncate()

            total_count += len(search_result["list"])
            if search_result.get("done", False):
                break
