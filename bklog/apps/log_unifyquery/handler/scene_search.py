"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy
import csv
import json
from io import StringIO
from typing import Any

from django.conf import settings
from django.utils.translation import gettext_lazy as _

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
    OPERATORS,
    FieldBuiltInEnum,
    IndexSetDataType,
)
from apps.log_search.models import LogIndexSetData
from apps.log_unifyquery.constants import BASE_OP_MAP, SEARCH_AFTER_KEY
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.mapping import UnifyQueryMappingHandler
from apps.log_unifyquery.utils import deal_time_format, transform_advanced_addition
from apps.utils.local import (
    get_local_param,
    get_request_external_username,
    get_request_username,
)
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
        self.table_id_conditions: list[list[dict]] = params["table_id_conditions"]
        self.bk_biz_id = params.get("bk_biz_id")

        # query string — reuse parent's _enhance + QueryStringBuilder
        self.query_string: str = params.get("keyword", "") or ""
        self.origin_query_string: str = params.get("keyword")
        self._enhance()
        self.query_string = QueryStringBuilder(self.query_string).query_string

        self.agg_field: str = params.get("agg_field", "")
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

        # desensitize — 场景化检索没有固定 index_set_id，命中的结果表只有在 ts/raw
        # 返回后才知道。这里先按请求语义（含全局/特权用户判定）确定是否脱敏，
        # 真正的脱敏规则在取数后由 _init_scene_desensitize 按命中索引集懒加载。
        self.is_desensitize = self._init_desensitize()
        self.field_configs: list = []
        self.text_fields: list = []
        self.text_fields_field_configs: list = []
        self.desensitize_handler = DesensitizeHandler([])
        self.text_fields_desensitize_handler = DesensitizeHandler([])
        self._desensitize_initialized = False

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
        if self.search_params.get("interval", "auto") == "auto":
            interval = self._init_default_interval()
        else:
            interval = self.search_params["interval"]

        conditions = self._transform_scene_additions()
        field_name = self.agg_field if self.agg_field else self.time_field
        query_dict = {
            "data_source": "bklog",
            "table_id": "",
            "table_id_conditions": self.table_id_conditions,
            "query_string": self.query_string,
            "time_field": self.time_field,
            "conditions": conditions,
            "field_name": field_name,
            "dimensions": [],
            "function": [],
            "reference_name": "a",
        }
        base = {
            "space_uid": self.space_uid,
            "query_list": [query_dict],
            "metric_merge": "a",
            "order_by": self.order_by,
            "step": interval,
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
                field_list.append(
                    {
                        "field_name": field,
                        "op": BASE_OP_MAP[operator],
                        "value": value if isinstance(value, list) else (value.split(",") if value else []),
                    }
                )
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

    @staticmethod
    def _get_result_table_index_set_map(result_table_ids: set[str]) -> dict[str, int]:
        """将结果表映射为索引集。"""
        result_table_ids = {result_table_id for result_table_id in result_table_ids if result_table_id}
        if not result_table_ids:
            return {}

        return dict(
            LogIndexSetData.objects.filter(
                result_table_id__in=result_table_ids,
                type=IndexSetDataType.RESULT_TABLE.value,
                is_deleted=False,
            ).values_list("result_table_id", "index_set_id")
        )

    def _deal_query_result(self, result_dict: dict) -> dict:
        log_list = []
        origin_log_list = []
        logs = result_dict.get("list", [])
        result_table_index_set_map = self._get_result_table_index_set_map({log.get("__result_table") for log in logs})
        for log in logs:
            log = merge_nested_data(log)
            index_set_id = result_table_index_set_map.get(log.get("__result_table"))
            if index_set_id:
                log["__index_set_id__"] = index_set_id
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

        result_dict.update(
            {
                "aggregations": {},
                "aggs": {},
                "list": log_list,
                "origin_log_list": origin_log_list,
                "total": result_dict.get("total", 0),
                "took": result_dict.get("took", 0),
            }
        )
        return result_dict

    # ------------------------------------------------------------------
    # Override _save_history — scene search has no index_set_id
    # ------------------------------------------------------------------

    def _save_history(self, result, search_type):
        pass

    # ------------------------------------------------------------------
    # Query primitives override — unified post-query SEARCH_LOG verification
    #
    # 场景检索没有固定 index_set_id，命中的结果表只有在 unify-query 返回后才知道。
    # ts/raw、ts、ts/reference 三类出数接口的响应都带 result_table_id，这里在
    # 查询原语层统一做后置鉴权（单一卡点）：任何方法只要经 self.query_ts* 取数，
    # 都会自动按命中结果表校验 SEARCH_LOG，避免逐个 call site 手动加导致遗漏。
    # ------------------------------------------------------------------

    def _verify_scene_permission(self, result) -> None:
        self.verify_result_table_search_permission((result or {}).get("result_table_id"))

    def query_ts(self, search_dict, raise_exception=True):
        result = super().query_ts(search_dict, raise_exception=raise_exception)
        self._verify_scene_permission(result)
        return result

    def query_ts_reference(self, search_dict, raise_exception=False):
        result = super().query_ts_reference(search_dict, raise_exception=raise_exception)
        self._verify_scene_permission(result)
        return result

    def query_ts_raw(self, search_dict, raise_exception=True, pre_search=False):
        result = super().query_ts_raw(search_dict, raise_exception=raise_exception, pre_search=pre_search)
        self._verify_scene_permission(result)
        return result

    def query_ts_raw_with_scroll(self, search_dict, raise_exception=True):
        # 父类是 staticmethod，子类用实例方法重写；super() 调用静态实现，
        # 经 self. 调用即命中本重写，从而获得后置鉴权。
        result = super().query_ts_raw_with_scroll(search_dict, raise_exception=raise_exception)
        self._verify_scene_permission(result)
        return result

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
        self._init_scene_desensitize(result.get("result_table_id"))
        result = self._deal_query_result(result)

        if self.search_params.get("original_search"):
            return result

        field_dict = self._analyze_field_length(result.get("list"))
        result.update({"fields": field_dict})

        return result

    # ------------------------------------------------------------------
    # Scene-specific query methods
    # ------------------------------------------------------------------

    def _resolve_table_id_from_conditions(self) -> str:
        """Fallback: resolve table_id_conditions → first matching index_set data_label.

        Used when UnifyQuery's field_map endpoint does not yet support
        table_id_conditions routing.
        """
        from apps.log_search.models import IndexSetTag, LogIndexSet, TAG_TYPE_SCENE

        for and_group in self.table_id_conditions:
            tag_ids = set()
            all_found = True
            for cond in and_group:
                values = cond.get("value", [])
                if not values:
                    all_found = False
                    break
                try:
                    tag = IndexSetTag.objects.get(
                        name=cond["field_name"],
                        value=values[0],
                        tag_type=TAG_TYPE_SCENE,
                    )
                    tag_ids.add(str(tag.tag_id))
                except IndexSetTag.DoesNotExist:
                    all_found = False
                    break
            if not all_found or not tag_ids:
                continue
            for idx_set in LogIndexSet.objects.filter(
                space_uid=self.space_uid,
                is_active=True,
            ).values("index_set_id", "tag_ids"):
                idx_tag_ids = {str(t) for t in idx_set["tag_ids"] if t}
                if tag_ids.issubset(idx_tag_ids):
                    return f"bklog_index_set_{idx_set['index_set_id']}"
        return ""

    # ------------------------------------------------------------------
    # Result-table level search permission (post ts/raw)
    # ------------------------------------------------------------------

    @staticmethod
    def _map_result_tables_to_index_sets(rt_ids: list[str]) -> list[int]:
        """Map unify-query result_table_id list to index_set_id list.

        result_table_id may arrive as the real result table id (e.g. ``2_bklog.xxx``)
        or as the data_label (``bklog_index_set_{index_set_id}``). Handle both so the
        permission check never silently misses a table.
        """
        from apps.log_search.models import LogIndexSetData

        index_set_ids: set = set()
        remaining: list = []
        for rt in rt_ids:
            if rt.startswith("bklog_index_set_"):
                try:
                    index_set_ids.add(int(rt.rsplit("_", 1)[-1]))
                except (ValueError, IndexError):
                    remaining.append(rt)
            else:
                remaining.append(rt)

        if remaining:
            index_set_ids.update(
                LogIndexSetData.objects.filter(result_table_id__in=remaining)
                .values_list("index_set_id", flat=True)
                .distinct()
            )
        return list(index_set_ids)

    def verify_result_table_search_permission(self, result_table_ids: list[str]) -> None:
        """Verify current user has SEARCH_LOG permission on every index set hit.

        Called after ts/raw returns, using the response's ``result_table_id`` list.
        Strict semantics: if the user lacks SEARCH_LOG on any matched index set,
        raise PermissionDeniedError listing the denied index sets (with apply url),
        consistent with the index-set search permission flow.
        """
        if getattr(self, "_rt_perm_verified", False):
            return
        if settings.IGNORE_IAM_PERMISSION:
            self._rt_perm_verified = True
            return

        rt_ids = [rt for rt in (result_table_ids or []) if rt]
        if not rt_ids:
            self._rt_perm_verified = True
            return

        index_set_ids = self._map_result_tables_to_index_sets(rt_ids)
        if not index_set_ids:
            self._rt_perm_verified = True
            return

        from apps.iam import ActionEnum, ResourceEnum
        from apps.iam.exceptions import PermissionDeniedError
        from apps.iam.handlers.permission import Permission
        from apps.log_search.models import LogIndexSet

        # 必须显式带上空间/业务属性：场景检索命中的索引集都属于同一个 space_uid，
        # 而用户的 SEARCH_LOG 策略通常是空间级下发（条件里含 indices._bk_iam_path_）。
        # IAM SDK 本地求值（含 expr.render 的 debug 日志）会遍历该字段，
        # 资源缺 _bk_iam_path_ 时直接 KeyError 整批 500。
        #
        # 同时必须带上 name：ResourceEnum.INDICES.create_simple_instance 一旦收到非空
        # attribute 就提前返回、不再反查 LogIndexSet，导致申请数据里索引集名称为空。
        # 这里一次性批量查出名称塞进 attribute，兼顾本地求值（_bk_iam_path_）与申请展示（name），
        # 且避免逐资源反查 DB。
        name_map = dict(
            LogIndexSet.objects.filter(index_set_id__in=index_set_ids).values_list("index_set_id", "index_set_name")
        )

        def _build_indices_attribute(index_set_id) -> dict:
            attribute = {
                "space_uid": self.space_uid,
                "id": str(index_set_id),
                "name": name_map.get(index_set_id, ""),
            }
            if self.bk_biz_id:
                attribute["bk_biz_id"] = self.bk_biz_id
            return attribute

        perm = Permission()
        resources = [
            [
                ResourceEnum.INDICES.create_simple_instance(
                    instance_id=str(index_set_id), attribute=_build_indices_attribute(index_set_id)
                )
            ]
            for index_set_id in index_set_ids
        ]
        permission_result = perm.batch_is_allowed([ActionEnum.SEARCH_LOG], resources)
        denied = [
            index_set_id
            for index_set_id in index_set_ids
            if not permission_result.get(str(index_set_id), {}).get(ActionEnum.SEARCH_LOG.id)
        ]
        if denied:
            denied_resources = [
                ResourceEnum.INDICES.create_simple_instance(
                    instance_id=str(index_set_id), attribute=_build_indices_attribute(index_set_id)
                )
                for index_set_id in denied
            ]
            apply_data, apply_url = perm.get_apply_data([ActionEnum.SEARCH_LOG], denied_resources)
            raise PermissionDeniedError(
                action_name=ActionEnum.SEARCH_LOG.name,
                apply_url=apply_url,
                permission=apply_data,
            )

        self._rt_perm_verified = True

    def _init_scene_desensitize(self, result_table_ids: list[str]) -> None:
        """按命中的结果表懒加载并合并脱敏配置。

        场景化检索没有单一 index_set_id，且 ts/raw 返回的每行不携带来源结果表标记。
        因此在取数后用 result_table_id 解析出全部命中索引集，把每个索引集的
        DesensitizeConfig / DesensitizeFieldConfig **并集** 合并到一个脱敏 handler：
        某字段只要在任一命中索引集被配置脱敏，就对所有行脱敏（宁可过度脱敏也不泄漏）。

        幂等：scroll / 分页多次取数只初始化一次。
        """
        if self._desensitize_initialized:
            return
        if not self.is_desensitize:
            self._desensitize_initialized = True
            return

        rt_ids = [rt for rt in (result_table_ids or []) if rt]
        if not rt_ids:
            self._desensitize_initialized = True
            return

        index_set_ids = self._map_result_tables_to_index_sets(rt_ids)
        if not index_set_ids:
            self._desensitize_initialized = True
            return

        from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig

        text_fields: set = set()
        for cfg in DesensitizeConfig.objects.filter(index_set_id__in=index_set_ids):
            for text_field in cfg.text_fields or []:
                text_fields.add(text_field)
        self.text_fields = list(text_fields)

        field_configs: list = []
        text_fields_field_configs: list = []
        seen: set = set()
        for obj in DesensitizeFieldConfig.objects.filter(index_set_id__in=index_set_ids):
            _config = {
                "field_name": obj.field_name or "",
                "rule_id": obj.rule_id or 0,
                "operator": obj.operator,
                "params": obj.params,
                "match_pattern": obj.match_pattern,
                "sort_index": obj.sort_index,
            }
            # 多个索引集合并时去掉完全相同的规则，避免重复脱敏
            dedupe_key = (
                _config["field_name"],
                _config["rule_id"],
                _config["operator"],
                _config["sort_index"],
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            if _config["field_name"] not in self.text_fields:
                field_configs.append(_config)
            else:
                text_fields_field_configs.append(_config)

        self.field_configs = field_configs
        self.text_fields_field_configs = text_fields_field_configs
        self.desensitize_handler = DesensitizeHandler(self.field_configs)
        self.text_fields_desensitize_handler = DesensitizeHandler(self.text_fields_field_configs)
        self._desensitize_initialized = True

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
        try:
            field_data = UnifyQueryApi.query_field_map(query_body)
        except Exception:
            fallback_table_id = self._resolve_table_id_from_conditions()
            if fallback_table_id:
                logger.info("[scene_fields] fallback to table_id=%s", fallback_table_id)
                query_body.pop("table_id_conditions", None)
                query_body["table_id"] = fallback_table_id
                field_data = UnifyQueryApi.query_field_map(query_body)
            else:
                raise

        field_list: list = []
        built_in_fields = FieldBuiltInEnum.get_choices()
        raw_fields = field_data.get("data") or field_data.get("fields") or {}
        if isinstance(raw_fields, list):
            for item in raw_fields:
                ft = item.get("field_type", "object")
                tokenize_on_chars = item.get("tokenize_on_chars", "")
                if isinstance(tokenize_on_chars, list | tuple):
                    tokenize_on_chars = "".join(tokenize_on_chars)
                elif not isinstance(tokenize_on_chars, str):
                    tokenize_on_chars = ""
                field_list.append(
                    {
                        "field_name": item.get("field_name", ""),
                        "field_type": ft,
                        "field_alias": item.get("field_alias", ""),
                        "query_alias": item.get("alias_name", ""),
                        "is_display": True,
                        "is_editable": True,
                        "tag": item.get("tag", ""),
                        "origin_field": item.get("origin_field", ""),
                        "es_doc_values": item.get("is_agg", ft != "text"),
                        "is_analyzed": item.get("is_analyzed", ft == "text"),
                        "field_operator": OPERATORS.get(ft, []),
                        "is_case_sensitive": item.get("is_case_sensitive", False),
                        "tokenize_on_chars": tokenize_on_chars,
                        "description": item.get("description", ""),
                    }
                )
        elif isinstance(raw_fields, dict):
            for field_name, field_info in raw_fields.items():
                ft = field_info.get("type", "object")
                field_list.append(
                    {
                        "field_name": field_name,
                        "field_type": ft,
                        "field_alias": field_info.get("alias", ""),
                        "query_alias": "",
                        "is_display": True,
                        "is_editable": True,
                        "tag": "",
                        "origin_field": "",
                        "es_doc_values": ft != "text",
                        "is_analyzed": ft == "text",
                        "field_operator": OPERATORS.get(ft, []),
                        "is_case_sensitive": False,
                        "tokenize_on_chars": "",
                        "description": field_info.get("description", ""),
                    }
                )

        for field in field_list:
            tag = "metric"
            if field.get("field_type") == "date":
                tag = "timestamp"
            elif field.get("es_doc_values"):
                tag = "dimension"
            field["tag"] = tag
            field_name_lower = field.get("field_name", "").lower()
            field["is_built_in"] = field_name_lower in built_in_fields or field_name_lower.startswith("__ext.")

        sort_list = self.origin_order_by or [["dtEventTimeStamp", "desc"]]

        field_name_set = {f.get("field_name", "") for f in field_list}
        config_list: list = []

        analyze = UnifyQueryMappingHandler.analyze_fields(field_list)
        ctx_active = bool(analyze.get("context_search_usable"))
        config_list.append(
            {
                "name": "context_and_realtime",
                "is_active": ctx_active,
                "extra": (
                    {"reason": "", "context_fields": analyze.get("context_fields", [])}
                    if ctx_active
                    else {"reason": analyze.get("usable_reason", "")}
                ),
            }
        )

        bkm_active = ("ip" in field_name_set) or ("serverIp" in field_name_set)
        config_list.append(
            {
                "name": "bkmonitor",
                "is_active": bkm_active,
                "extra": {} if bkm_active else {"reason": _("缺少字段, ip 和 serverIp 不能同时为空")},
            }
        )

        bcs_domain = getattr(settings, "BCS_WEB_CONSOLE_DOMAIN", "") or ""
        if not bcs_domain:
            bcs_active, bcs_extra = False, {"reason": _("未配置BCS WEB CONSOLE")}
        else:
            container_field_pairs = (
                ("cluster", "container_id"),
                ("__ext.io_tencent_bcs_cluster", "__ext.container_id"),
                ("__ext.bk_bcs_cluster_id", "__ext.container_id"),
            )
            bcs_active = any(c in field_name_set and ci in field_name_set for c, ci in container_field_pairs)
            bcs_extra = {} if bcs_active else {"reason": _("{} 不能同时为空").format(container_field_pairs)}
        config_list.append(
            {
                "name": "bcs_web_console",
                "is_active": bcs_active,
                "extra": bcs_extra,
            }
        )

        result = {
            "fields": field_list,
            "display_fields": ["dtEventTimeStamp", "log"],
            "sort_list": sort_list,
            "default_sort_list": sort_list,
            "time_field": self.time_field,
            "time_field_type": "date",
            "time_field_unit": "millisecond",
            "config": config_list,
        }

        # 合入当前用户在该业务-场景-范围下的 UI 偏好（7 字段 camelCase JSON，与 user_custom_config GET 一致）
        scene_id = self._extract_scene_id()
        if self.bk_biz_id and scene_id:
            from apps.log_search.handlers.search.scene_fields_config import UserSceneCustomConfigHandler

            result["user_custom_config"] = UserSceneCustomConfigHandler.get(
                bk_biz_id=self.bk_biz_id,
                username=self.request_username,
                scene_id=scene_id,
                scope=scope,
            )
        return result

    def _extract_scene_id(self) -> str:
        """从 table_id_conditions 中提取 scene 维度值；任一 AND 组命中即返回。"""
        for and_group in self.table_id_conditions or []:
            for c in and_group:
                if c.get("field_name") == "scene":
                    values = c.get("value") or []
                    if values:
                        return values[0]
        return ""

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
        return self.query_ts_raw(search_dict)

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
            search_result = self.query_ts_raw(search_dict)
            new_result_size = len(search_result.get("list", []))

            if new_result_size == 0:
                break

            result_size += new_result_size
            self._init_scene_desensitize(search_result.get("result_table_id"))
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
            search_result = self.query_ts_raw_with_scroll(search_params)
            if not search_result.get("list"):
                break

            self._init_scene_desensitize(search_result.get("result_table_id"))
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
            search_result = self.query_ts_raw_with_scroll(search_params)
            if not search_result.get("list"):
                break
            self._init_scene_desensitize(search_result.get("result_table_id"))
            if not header_written:
                result_table_options = list(search_result.get("result_table_options", {}).values())
                result_schema = result_table_options[0]["result_schema"] if result_table_options else []
                fields = [field["field_alias"] for field in result_schema]
                csv_writer.writerow(fields)
                header_written = True
            apply_desensitize = (self.field_configs or self.text_fields_field_configs) and self.is_desensitize
            for record in search_result["list"]:
                if apply_desensitize:
                    # export_chart_data 不走 _deal_query_result，需显式逐行脱敏
                    record = self._log_desensitize(record)
                csv_writer.writerow([record.get(field, "") for field in fields])
            yield row_buffer.getvalue()
            row_buffer.seek(0)
            row_buffer.truncate()

            total_count += len(search_result["list"])
            if search_result.get("done", False):
                break
