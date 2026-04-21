"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import logging
from itertools import chain
from typing import Any
from collections.abc import Callable

from rest_framework import serializers

from concurrent.futures import ThreadPoolExecutor
from apm_web.handlers.log_handler import ServiceLogHandler, get_biz_index_sets_with_cache
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.constants import DEFAULT_APM_LOG_SEARCH_FIELD_NAME
from apm_web.models import LogServiceRelation
from bkmonitor.utils.cache import CacheType, using_cache
from constants.apm import Vendor, FIVE_MIN_SECONDS
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources import HostIndexQueryMixin
from utils import count_md5

logger = logging.getLogger("apm")


def _log_relation_task_safe(
    fn: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    """为 log_relation_list 子任务兜底异常，避免单个分支失败影响整体结果。"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        try:
            return fn(*args, **kwargs)
        except Exception:  # pylint: disable=broad-except
            # 仅打印关键参数，避免将 indexes_mapping 等大型参数干扰。
            bk_biz_id = args[0] if len(args) > 0 else kwargs.get("bk_biz_id")
            app_name = args[1] if len(args) > 1 else kwargs.get("app_name")
            service_name = args[2] if len(args) > 2 else kwargs.get("service_name")
            logger.exception(
                "[log_relation_list] task=%s failed, bk_biz_id=%s, app_name=%s, service_name=%s",
                fn.__name__,
                bk_biz_id,
                app_name,
                service_name,
            )
            return []

    return wrapper


def overwrite_with_addition(info: dict[str, str], overwrite_key: str | None = None) -> list[dict]:
    res = []
    for k, v in info.items():
        key = k
        if overwrite_key:
            key = overwrite_key
        res.append({"field": key, "operator": "=", "value": [v]})
    return res


@using_cache(CacheType.APM(FIVE_MIN_SECONDS))
def _get_span_detail(_bk_biz_id, _app_name, _span_id):
    return api.apm_api.query_span_detail(bk_biz_id=_bk_biz_id, app_name=_app_name, span_id=_span_id)


def _find_index_infos_from_cache(
    bk_biz_id: int, index_set_ids: list[str | int], indexes_mapping: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """从缓存的索引集列表中查找指定 index_set_ids 的索引信息。"""
    # 避免索引集 ID 类型不一致导致的匹配失败，统一转换为字符串进行比较。
    processed_index_set_ids: set[str] = {str(i) for i in index_set_ids}
    # 返回浅拷贝，避免原地修改缓存。
    return [{**i} for i in indexes_mapping.get(bk_biz_id, []) if str(i["index_set_id"]) in processed_index_set_ids]


@_log_relation_task_safe
def process_relation(
    bk_biz_id: int,
    app_name: str,
    service_name: str | None,
    indexes_mapping: dict[int, list[dict[str, Any]]],
    overwrite_method: Callable[..., list[dict]] | None = None,
) -> list[dict]:
    """根据服务关联关系获取日志索引集信息。关联关系可能涉及多个业务，因此需要根据不同的业务 ID 从缓存中获取对应的索引集列表进行匹配。"""
    result: list[dict] = []
    relations: list[LogServiceRelation] = ServiceLogHandler.get_log_relations(
        bk_biz_id, app_name, [service_name] if service_name else None
    )
    for relation in relations:
        relation_index_ids: set[str] = {str(index_id) for index_id in relation.value_list}
        if relation.related_bk_biz_id != bk_biz_id:
            relation_full_indexes: list[dict] = get_biz_index_sets_with_cache(bk_biz_id=relation.related_bk_biz_id)
            indexes_mapping[relation.related_bk_biz_id] = relation_full_indexes
            matched = [i for i in relation_full_indexes if str(i["index_set_id"]) in relation_index_ids]
        else:
            matched = _find_index_infos_from_cache(bk_biz_id, relation.value_list, indexes_mapping)
        for index_info in matched:
            index_info = {**index_info}
            if overwrite_method:
                index_info["addition"] = overwrite_method(overwrite_key=DEFAULT_APM_LOG_SEARCH_FIELD_NAME)
            result.append(index_info)
    return result


@_log_relation_task_safe
def process_span_host(
    bk_biz_id: int,
    app_name: str,
    service_name: str,
    indexes_mapping: dict[int, list[dict[str, Any]]],
    extra_info: dict[str, Any],
    overwrite_method: Callable[..., list[dict]] | None = None,
) -> list[dict]:
    """根据 Span 详情中的主机信息获取日志索引集。"""
    span_id: str | None = extra_info.get("span_id")
    span_detail: dict | None = extra_info.get("span_detail")
    if not span_id or not span_detail:
        return []

    result: list[dict] = []
    host_indexes: list[dict] = ServiceLogHandler.list_host_indexes_by_span(
        bk_biz_id, app_name, span_id, span_detail=span_detail
    )
    for item in host_indexes:
        index_infos: list[dict] = _find_index_infos_from_cache(bk_biz_id, [item["index_set_id"]], indexes_mapping)
        for index_info in index_infos:
            # 默认查询: 机器 IP
            index_info["addition"] = item.get("addition", [])
            if overwrite_method:
                index_info["addition"] = overwrite_method(overwrite_key=DEFAULT_APM_LOG_SEARCH_FIELD_NAME)
        result.extend(index_infos)
    return result


@_log_relation_task_safe
def process_datasource(
    bk_biz_id: int,
    app_name: str,
    service_name: str | None,
    indexes_mapping: dict[int, list[dict[str, Any]]],
    overwrite_method: Callable[..., list[dict]] | None = None,
) -> list[dict]:
    """根据应用数据源获取日志索引集，应用数据源是指通过日志上报能力上报日志的服务，通常会有一个固定的索引集与之对应。"""
    datasource_index_set_id: int | None = ServiceLogHandler.get_and_check_datasource_index_set_id(
        bk_biz_id, app_name, full_indexes=indexes_mapping.get(bk_biz_id, [])
    )
    if not datasource_index_set_id:
        return []

    result: list[dict] = []
    index_infos: list[dict] = _find_index_infos_from_cache(bk_biz_id, [datasource_index_set_id], indexes_mapping)
    for index_info in index_infos:
        result.append(index_info)
        index_info["is_app_datasource"] = True
        if overwrite_method:
            index_info["addition"] = overwrite_method()
            continue

        if not service_name:
            continue

        # 默认查询: 服务名称 / 根据不同 SDK 进行调整
        node = ServiceHandler.get_node(bk_biz_id, app_name, service_name, raise_exception=False)
        if node and Vendor.has_sdk(node.get("sdk"), Vendor.G):
            # G.SDK 中，日志 server 字段 = app.server。
            index_info["addition"] = [{"field": "resource.server", "operator": "=", "value": [service_name]}]
        else:
            index_info["addition"] = [{"field": "resource.service.name", "operator": "=", "value": [service_name]}]

    return result


@_log_relation_task_safe
def process_metric_relations(
    bk_biz_id: int,
    app_name: str,
    service_name: str | None,
    indexes_mapping: dict[int, list[dict[str, Any]]],
    start_time: int,
    end_time: int,
    overwrite_method: Callable[..., list[dict]] | None = None,
):
    """根据应用关联指标反查关联日志索引集。"""
    if not service_name:
        return []

    result = []
    relations = ServiceLogHandler.list_indexes_by_relation(bk_biz_id, app_name, service_name, start_time, end_time)
    for r in relations:
        index_infos: list[dict] = _find_index_infos_from_cache(bk_biz_id, [r["index_set_id"]], indexes_mapping)
        for index_info in index_infos:
            index_info["addition"] = r["addition"]
            if overwrite_method:
                index_info["addition"] = overwrite_method(overwrite_key=DEFAULT_APM_LOG_SEARCH_FIELD_NAME)
            result.append(index_info)
    return result


def _generate_cache_key(
    bk_biz_id: int,
    app_name: str,
    service_name: str | None,
    extra_info: dict[str, Any] | None,
    start_time: int | None,
    end_time: int | None,
) -> str:
    """生成日志关联列表的缓存 key。

    :param bk_biz_id: 业务 ID。
    :param app_name: 应用名称。
    :param extra_info: 额外过滤信息，如 span_id / trace_id。
    :param service_name: 服务名称。
    :param start_time: 开始时间戳。
    :param end_time: 结束时间戳。
    :return: 缓存 key。
    """

    key_parts: list[str] = [str(bk_biz_id), app_name]
    if service_name:
        key_parts.append(service_name)

    key_parts.append(count_md5(extra_info))
    if start_time and end_time and service_name:
        # 应用关联日志无需按时间范围缓存。
        key_parts.append(str((start_time // FIVE_MIN_SECONDS) * FIVE_MIN_SECONDS))
        key_parts.append(str((end_time // FIVE_MIN_SECONDS) * FIVE_MIN_SECONDS))

    return "-".join(key_parts + ["log_relation_list"])


def _build_extra_info(
    bk_biz_id: int,
    app_name: str,
    extra_info: dict[str, Any] | None,
) -> tuple[Callable[..., list[dict]] | None, dict[str, Any]]:
    """根据 extra_info 构建过滤信息和 overwrite_method。

    :param bk_biz_id: 业务 ID。
    :param app_name: 应用名称。
    :param extra_info: 额外过滤信息，目前支持 span_id / trace_id，后续按需求增加。
    :return: overwrite_method 和 处理后的 extra_info。
    """
    if not extra_info:
        return None, {}

    span_id: str | None = extra_info.get("span_id")
    info: dict[str, Any] = {k: v for k, v in extra_info.items() if v}
    span_detail: dict = _get_span_detail(bk_biz_id, app_name, span_id) if span_id else {}
    if span_detail and span_detail.get("trace_id"):
        info["trace_id"] = span_detail["trace_id"]

    overwrite_method: Callable[..., list[dict]] = functools.partial(overwrite_with_addition, info=info)
    return overwrite_method, {"span_id": span_id, "span_detail": span_detail}


def log_relation_list(
    bk_biz_id: int,
    app_name: str,
    service_name: str | None = None,
    extra_info: dict | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
) -> list[dict]:
    """获取应用/服务关联的日志索引集列表。

    :param bk_biz_id: 业务 ID。
    :param app_name: 应用名称。
    :param service_name: 服务名称。
    :param extra_info: 额外过滤信息，如 {"span_id": "xxx"} 或 {"trace_id": "yyy"}。
    :param start_time: 开始时间戳。
    :param end_time: 结束时间戳。
    :return: 去重后的索引集信息列表，is_app_datasource=True 的排在最前。
    """
    cache_key: str = _generate_cache_key(bk_biz_id, app_name, service_name, extra_info, start_time, end_time)
    cache_call = using_cache(CacheType.APM(FIVE_MIN_SECONDS))
    cached: list[dict] | None = cache_call.get_value(cache_key)
    if cached:
        return cached

    indexes_mapping: dict[int, list[dict]] = {bk_biz_id: get_biz_index_sets_with_cache(bk_biz_id)}
    overwrite_method, processed_extra_info = _build_extra_info(bk_biz_id, app_name, extra_info)

    common_args: tuple = (bk_biz_id, app_name, service_name, indexes_mapping)
    tasks: list[tuple[Callable[..., list[dict]], tuple]] = [
        (process_relation, (*common_args, overwrite_method)),
        (process_datasource, (*common_args, overwrite_method)),
        (process_metric_relations, (*common_args, start_time, end_time, overwrite_method)),
        (process_span_host, (*common_args, processed_extra_info, overwrite_method)),
    ]

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = [executor.submit(fn, *args) for fn, args in tasks]
        # 将应用自定义上报数据源的索引集排在最前面，优先使用标准索引集。
        results: list[dict] = sorted(
            list(chain.from_iterable(f.result() for f in futures)), key=lambda t: not t.get("is_app_datasource", False)
        )

    seen: set[str] = set()
    processed_index_infos: list[dict] = []
    for item in results:
        index_set_id: str = str(item["index_set_id"])
        if index_set_id in seen:
            continue

        seen.add(index_set_id)
        processed_index_infos.append(item)

    cache_call.set_value(cache_key, processed_index_infos)
    return processed_index_infos


class LogInfoResource(Resource, HostIndexQueryMixin):
    """
    判断是否有关联日志
    1. 是否开启了日志上报能力
    2. 是否手动关联了日志平台的日志索引集
    3. 自动关联（根据 pod 等信息，关联 pod 相关日志索引集）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField(required=False)
        span_id = serializers.CharField(label="SpanId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]
        service_name = data.get("service_name")

        # 1.是否开启了日志
        if ServiceLogHandler.get_log_datasource(bk_biz_id=bk_biz_id, app_name=app_name):
            return True

        # 2. 是否手动关联了日志索引集
        if ServiceLogHandler.get_log_relations(
            bk_biz_id=bk_biz_id, app_name=app_name, service_names=[service_name] if service_name else None
        ):
            return True

        # 3. 是否有关联的 pod 日志
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if ServiceLogHandler.list_indexes_by_relation(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name, start_time=start_time, end_time=end_time
        ):
            return True
        return False


class LogRelationListResource(Resource, HostIndexQueryMixin):
    """服务索引集列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField(required=False)
        # 场景 1：span_id & trace_id 都传递，Span 详情日志。
        # 场景 2：仅 trace_id 传递，Trace 详情日志。
        # 场景 3：span_id 和 trace_id 都不传递，观测场景日志。
        span_id = serializers.CharField(label="SpanId", required=False)
        trace_id = serializers.CharField(label="TraceId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        extra_info: dict[str, str] = {}
        span_id = data.pop("span_id", None)
        trace_id = data.pop("trace_id", None)
        if span_id:
            extra_info["span_id"] = span_id
        if trace_id:
            extra_info["trace_id"] = trace_id
        return log_relation_list(extra_info=extra_info or None, **data)
