# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import functools
from concurrent.futures import ThreadPoolExecutor, as_completed

from rest_framework import serializers

from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.service_handler import ServiceHandler
from bkmonitor.utils.cache import CacheType, using_cache
from constants.apm import Vendor
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources import HostIndexQueryMixin


def overwrite_with_span_addition(info, overwrite_key=None):
    res = []
    for k, v in info.items():
        key = k
        if overwrite_key:
            key = overwrite_key
        res.append({"field": key, "operator": "=", "value": [v]})
    return res


def log_relation_list(bk_biz_id, app_name, service_name, span_id=None, start_time=None, end_time=None):
    cache_call = using_cache(CacheType.APM(1 * 60))
    cache_key = f"{bk_biz_id}-{app_name}-{service_name}-{span_id}-log_relation_list"
    index_info_list = cache_call.get_value(cache_key)
    if index_info_list:
        for index_info in index_info_list:
            yield index_info
    else:
        # 缓存增强：对 search_index_set 添加缓存
        @using_cache(CacheType.APM(1 * 60))
        def _cached_search_index_set(_bk_biz_id):
            return api.log_search.search_index_set(bk_biz_id=_bk_biz_id)

        @using_cache(CacheType.APM(1 * 60))
        def _cached_query_index_set(_bk_biz_id, _app_name, _span_id):
            return api.apm_api.query_span_detail(bk_biz_id=_bk_biz_id, app_name=_app_name, span_id=_span_id)

        # 并行获取基础信息
        def _retrieve_base_info(_bk_biz_id, _app_name, _span_id):
            # 获取当前业务的索引集和 span 详情 减少耗时
            with ThreadPoolExecutor(max_workers=10) as _executor:
                search_future = _executor.submit(_cached_search_index_set, _bk_biz_id)
                query_future = (
                    _executor.submit(_cached_query_index_set, _bk_biz_id, _app_name, _span_id) if _span_id else None
                )

                try:
                    search_result = search_future.result()
                    query_result = query_future.result() if query_future else None
                    return search_result, query_result
                except Exception:
                    return [], None

        # 使用缓存获取基础信息
        biz_indices, span_detail = _retrieve_base_info(bk_biz_id, app_name, span_id)
        indexes_mapping = {bk_biz_id: biz_indices}

        overwrite_method = None
        if span_id:
            info = {"span_id": span_id}
            if span_detail and span_detail.get("trace_id"):
                info["trace_id"] = span_detail["trace_id"]
            overwrite_method = functools.partial(overwrite_with_span_addition, info=info)

        # 需要并行处理的任务列表
        tasks = []

        # 从服务关联中找日志
        def process_service_relation():
            result = []
            # Resource: 从服务关联中找日志
            relation = ServiceLogHandler.get_log_relation(bk_biz_id, app_name, service_name)
            if relation:
                if relation.related_bk_biz_id != bk_biz_id:
                    relation_full_indexes = _cached_search_index_set(_bk_biz_id=relation.related_bk_biz_id)
                    indexes_mapping[relation.related_bk_biz_id] = relation_full_indexes
                    index_info = next(
                        (i for i in relation_full_indexes if str(i["index_set_id"]) == relation.value),
                        None,
                    )
                else:
                    index_info = next(
                        (i for i in indexes_mapping.get(bk_biz_id, []) if str(i["index_set_id"]) == relation.value),
                        None,
                    )
                if index_info:
                    if overwrite_method:
                        index_info["addition"] = overwrite_method(overwrite_key="log")

                    result.append(index_info)
            return result

        tasks.append(process_service_relation)

        # 任务2: Span关联主机
        if span_id:

            def process_span_host():
                result = []
                host_indexes = ServiceLogHandler.list_host_indexes_by_span(
                    bk_biz_id,
                    app_name,
                    span_id,
                    span_detail=span_detail,
                )
                for item in host_indexes:
                    index_info = next(
                        (
                            i
                            for i in indexes_mapping.get(bk_biz_id, [])
                            if str(i["index_set_id"]) == str(item["index_set_id"])
                        ),
                        None,
                    )
                    if index_info:
                        # 默认查询: 机器 IP
                        index_info["addition"] = item.get("addition", [])
                        if overwrite_method:
                            index_info["addition"] = overwrite_method(overwrite_key="log")
                    result.append(index_info)
                return result

            tasks.append(process_span_host)

            # 任务3: 自定义上报

        def process_datasource():
            result = []
            # Resource: 从自定义上报中找日志
            datasource_index_set_id = ServiceLogHandler.get_and_check_datasource_index_set_id(
                bk_biz_id,
                app_name,
                full_indexes=indexes_mapping.get(bk_biz_id, []),
            )
            if datasource_index_set_id:
                index_info = next(
                    (
                        i
                        for i in indexes_mapping.get(bk_biz_id, [])
                        if str(i["index_set_id"]) == str(datasource_index_set_id)
                    ),
                    None,
                )
                if index_info:
                    # 默认查询: 服务名称 / 根据不同 SDK 进行调整
                    node = ServiceHandler.get_node(bk_biz_id, app_name, service_name, raise_exception=False)
                    if node and Vendor.has_sdk(node.get("sdk"), Vendor.G):
                        # G.SDK 中，日志 server 字段 = app.server。
                        index_info["addition"] = [
                            {"field": "resource.server", "operator": "=", "value": [service_name]}
                        ]
                    else:
                        index_info["addition"] = [
                            {"field": "resource.service.name", "operator": "=", "value": [service_name]}
                        ]

                    if overwrite_method:
                        index_info["addition"] = overwrite_method()

                    result.append(index_info)
            return result

        tasks.append(process_datasource)

        # 任务4: 关联指标
        def process_metric_relations():
            result = []
            # Resource: 从关联指标中找
            relations = ServiceLogHandler.list_indexes_by_relation(
                bk_biz_id,
                app_name,
                service_name,
                start_time,
                end_time,
            )
            if relations:
                for r in relations:
                    index_info = next(
                        (
                            j
                            for j in indexes_mapping.get(bk_biz_id, [])
                            if str(j["index_set_id"]) == str(r["index_set_id"])
                        ),
                        None,
                    )
                    if index_info:
                        index_info["addition"] = r["addition"]
                        if overwrite_method:
                            index_info["addition"] = overwrite_method(overwrite_key="log")
                        result.append(index_info)
            return result

        tasks.append(process_metric_relations)

        # 并行执行所有任务
        index_set_ids = set()
        index_info_list = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(task) for task in tasks]
            for future in as_completed(futures):
                try:
                    for item in future.result():
                        index_id = str(item["index_set_id"])
                        if index_id not in index_set_ids:
                            index_set_ids.add(index_id)
                            index_info_list.append(item)
                except Exception:
                    continue

        cache_call.set_value(cache_key, index_info_list)
        for index_info in index_info_list:
            yield index_info


class ServiceLogInfoResource(Resource, HostIndexQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        span_id = serializers.CharField(label="SpanId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        return any(log_relation_list(**data))


class ServiceRelationListResource(Resource, HostIndexQueryMixin):
    """服务索引集列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        # [!!!] 当传递 span_id 时候 场景为 span 检索日志处
        # [!!!] 当没有传递 span_id 时候 场景为观测场景 span 日志处
        span_id = serializers.CharField(label="SpanId", required=False)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, data):
        return list(log_relation_list(**data))
