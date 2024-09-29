# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
import json
import logging
import operator
import time
from datetime import datetime
from functools import reduce
from typing import Dict, List, Optional, Tuple, Union

from django.core.exceptions import EmptyResultSet
from django.db.models import Count, Q
from django.db.models.aggregates import Avg, Sum
from django.utils.translation import gettext as _
from rest_framework import serializers

from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_ci_space
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import (
    BCSBase,
    BCSCluster,
    BCSClusterLabels,
    BCSContainer,
    BCSContainerLabels,
    BCSLabel,
    BCSNode,
    BCSNodeLabels,
    BCSPod,
    BCSPodLabels,
    BCSPodMonitor,
    BCSPodMonitorLabels,
    BCSService,
    BCSServiceLabels,
    BCSServiceMonitor,
    BCSServiceMonitorLabels,
    BCSWorkload,
    BCSWorkloadLabels,
)
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.casting import force_float
from bkmonitor.utils.ip import is_v6
from bkmonitor.utils.kubernetes import (
    BcsClusterType,
    KubernetesServiceJsonParser,
    get_progress_value,
)
from bkmonitor.utils.thread_backend import ThreadPool
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.event import EventTypeNormal, EventTypeWarning
from core.drf_resource import Resource, api, resource
from core.unit import load_unit
from monitor_web.constants import (
    GRAPH_COLUMN_BAR,
    GRAPH_NUMBER_CHART,
    GRAPH_PERCENTAGE_BAR,
    GRAPH_RATIO_RING,
    GRAPH_RESOURCE,
    OVERVIEW_ICON,
)
from monitor_web.scene_view.resources.serializers import KubernetesListRequestSerializer

logger = logging.getLogger("kubernetes")


def params_to_conditions(params):
    conditions = {"bk_biz_id": params["bk_biz_id"]}
    # 以condition_list中的搜索条件为准，忽略外层除了bk_biz_id的其他搜索条件
    for condition in params.get("condition_list") or []:
        for key, value in condition.items():
            if not conditions.get(key):
                conditions[key] = []
            if not isinstance(value, list):
                value = [value]
            conditions[key] += value
    return conditions


class KubernetesResource(ApiAuthResource, abc.ABC):
    data = []
    model_class: BCSBase = None
    model_label_class = None
    query_set_list = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.space_associated_clusters = {}

    def get_columns(self):
        return self.model_class.get_columns()

    def get_condition_list(self, params):
        return []

    def preset(self, params):
        pass

    def get_overview_data(self, params, data):
        """获得概览数据 ."""
        # 根据是否有 overview_name 配置决定是否有概览数据
        has_data = False
        overview_data = {}
        for c in self.get_columns():
            overview_data[c["id"]] = ""
            if c.get("overview") == "name":
                has_data = True
                overview_data[c["id"]] = {
                    "icon": OVERVIEW_ICON,
                    "target": "null_event",
                    "key": "",
                    "url": "",
                    "value": c.get("overview_name", ""),
                }
        if not has_data:
            return None
        return overview_data

    @classmethod
    def get_data_params(cls, params):
        bk_biz_id = params["bk_biz_id"]
        view_options = params.get("view_options", {})
        view_options["keyword"] = params.get("keyword", "")
        view_options["filter"] = params.get("filter", "")
        view_options["bk_biz_id"] = bk_biz_id
        view_options["condition_list"] = params.get("condition_list", [])
        view_options["page"] = params.get("page", 1)
        view_options["page_size"] = params.get("page_size", 10)
        view_options["sort"] = params.get("sort")
        view_options["filter_dict"] = params.get("filter_dict", {})
        view_options["monitor_status"] = params.get("status", "all")
        for k, v in params_to_conditions(view_options).items():
            view_options[k] = v
        view_options["space_uid"] = bk_biz_id_to_space_uid(bk_biz_id)
        return view_options

    def perform_request(self, params):
        # 构造参数
        view_options = self.get_data_params(params)

        # 参数预处理
        self.preset(view_options)

        # 构造数据表搜索条件
        self.add_condition_filter(view_options)
        # 添加列搜索
        self.add_column_filter(view_options)

        # 计算每种状态的资源数量
        status_filter_data = self.get_status_filter_data(view_options)
        # 添加根据数据状态过滤的条件
        self.add_monitor_status_filter(view_options)
        # 计算资源总数
        total = self.get_total()
        # 根据分页获取一页的数据
        self.pagination_data(view_options)

        # 搜索条件
        label_condition_list = self.data_to_labels_condition_list(view_options)
        condition_list = self.get_condition_list(view_options) + label_condition_list

        data = self.rendered_data(view_options)

        # 获得需要显示的列
        columns = self.get_columns()
        # 生成概览数据
        overview_data = self.get_overview_data(params, data)
        # 解析需要排序的所有列
        sort = self.get_sort_columns(columns)
        # 格式化columns
        columns = self.format_columns(params, columns)
        overview_data_rendered = self.render_overview_data(params, overview_data, columns)
        # 格式化表格数据
        if overview_data:
            data = self.correct_data(params, overview_data, columns)
        # 格式化配置列
        columns = self.render_columns(columns)

        results = {
            "columns": columns,
            "data": data,
            "condition_list": condition_list,
            "total": total,
            "filter": status_filter_data,
            "sort": sort,
        }
        if overview_data_rendered:
            results["overview_data"] = overview_data_rendered

        return results

    @staticmethod
    def render_columns(columns):
        for column in columns:
            if "origin_type" in column:
                del column["origin_type"]
            if "sortable_type" in column:
                del column["sortable_type"]
        return columns

    def is_shared_cluster(self, bcs_cluster_id):
        """根据集群ID判断是否是共享集群 ."""
        cluster_info = self.space_associated_clusters.get(bcs_cluster_id, {})
        if cluster_info.get("namespace_list"):
            return True
        if cluster_info.get("cluster_type") == BcsClusterType.SHARED:
            return True

        return False

    def correct_data(self, params, overview_data, columns):
        """修改结果数据 ."""
        bk_biz_id = params["bk_biz_id"]
        sort = params.get("sort")
        sort_field_key = sort.lstrip("-") if sort else None
        if sort_field_key and overview_data:
            overview_value = overview_data.get(sort_field_key)
        else:
            overview_value = None
        data = []
        for item in self.data:
            row = item.render(bk_biz_id, render_type="list")
            for column in columns:
                field_key = column["id"]
                if field_key not in row:
                    continue
                # 如果列本身就是progress格式
                origin_type = column.get("origin_type")
                if origin_type == "progress":
                    continue
                # 如果排序列配置为progress
                field_type = column["type"]
                if sort_field_key == field_key:
                    if field_type == "progress":
                        # 计算数值列的概览值
                        if isinstance(overview_value, dict) and "value" in overview_value:
                            total = force_float(overview_value["value"])
                        else:
                            total = force_float(overview_value)
                        if not total:
                            value = 0
                        else:
                            item_value = force_float(getattr(item, sort_field_key))
                            if not item_value:
                                value = 0
                            else:
                                value = item_value / total * 100
                        # 计算标签
                        field_name = row[field_key]
                        if isinstance(field_name, dict):
                            label = field_name.get("value")
                        else:
                            label = field_name
                        row[field_key] = {"label": label, "status": "SUCCESS", "value": value}

            data.append(row)

        return data

    def render_overview_data(self, params, overview_data, columns):
        """渲染概览数据 ."""
        if not overview_data:
            return overview_data
        overview_data = copy.deepcopy(overview_data)
        # 获得当前排序列
        sort = params.get("sort")
        sort_field_key = sort.lstrip("-") if sort else None
        # 获得格式为进度条的所有排序列
        field_map = {column.get("id"): column for column in columns if column.get("sortable_type") == "progress"}
        # 给排序列渲染进度条
        for key, value in overview_data.items():
            # 获得列值
            column = field_map.get(key)
            if not column:
                continue
            origin_type = column.get("origin_type")
            origin_type = origin_type if origin_type else column.get("type")
            if isinstance(value, dict) and "label" in value:
                label = value["label"]
                process_value = value["value"]
            else:
                label = value
                process_value = value
            # 处理原始类型为link
            if isinstance(process_value, dict) and "value" in process_value:
                process_value = value.get("value")
            if isinstance(label, dict):
                if "label" in label:
                    label = label["label"]
                else:
                    label = process_value
            # 处理排序列
            overview_value = None
            if key == sort_field_key:
                if origin_type and origin_type in ["progress"]:
                    # 原始类型是progress
                    if isinstance(value, dict):
                        overview_value = {
                            "label": label,
                            "status": "SUCCESS",
                            "value": process_value,
                        }
                    else:
                        overview_value = {
                            "label": label,
                            "status": "SUCCESS",
                            "value": 100,
                        }
                else:
                    # 原始类型是其他类型
                    overview_value = {
                        "label": label,
                        "status": "SUCCESS",
                        "value": 100,
                    }
            else:
                # 非排序列
                if origin_type and origin_type != "progress":
                    if isinstance(value, dict) and "label" in value:
                        overview_value = value["label"]
                    else:
                        overview_value = value
            if overview_value:
                overview_data[key] = overview_value
        return overview_data

    def format_columns(self, params: Dict, columns: List) -> List:
        """对列配置添加额外的属性，并添加列排序配置 ."""
        sort = params.get("sort")
        sort_column = None
        new_columns = []
        has_sortable = False
        for index, column in enumerate(columns):
            column.pop("overview", None)
            # 修改第一列
            if index == 0:
                column["max_width"] = 300
                column["width"] = 248
            # 所有列设置最小宽度
            column["min_width"] = 120
            # 去掉列中的排序标志
            if column.get("sortable"):
                has_sortable = True
                column["sortable"] = False
            # 添加列过滤
            if column.get("filterable"):
                field_name = column.get("id")
                column["filter_list"] = self.get_column_filter_conf(params["bk_biz_id"], field_name)
            # 获得排序列
            if sort and column.get("id") == sort.lstrip("-"):
                sort_column = column
            else:
                new_columns.append(column)
        # 如果是排序列，将此列放到第2列，且设置为显示模式
        if sort_column:
            sort_column["checked"] = True
            # 切换排序列的类型
            sortable_type = sort_column.get("sortable_type")
            if sortable_type:
                # 原始类型
                sort_column["origin_type"] = sort_column["type"]
                # 新的类型
                sort_column["type"] = sortable_type
            new_columns.insert(1, sort_column)
        # 如果没有排序列，则重新设置第一列的宽度
        if not has_sortable:
            columns[0]["max_width"] = 400
        return new_columns

    def get_column_filter_conf(self, bk_biz_id: int, field_name: str) -> List:
        """获得列排序配置 ."""
        space_related_cluster_ids = list(self.space_associated_clusters.keys())
        field_filter_list = self.model_class.get_column_filter_conf(
            {"bk_biz_id": bk_biz_id, "space_related_cluster_ids": space_related_cluster_ids},
            field_name,
        )
        return field_filter_list

    @staticmethod
    def get_sort_columns(columns):
        sort = []
        for column in columns:
            if column.get("sortable"):
                sort.append(
                    {
                        "id": column["id"],
                        "name": column["name"],
                    }
                )
        return sort

    def get_total(self) -> int:
        """计算资源总数 ."""
        if not self.query_set_list:
            return 0
        return self.model_class.objects.filter(*self.query_set_list).count()

    def get_sort(self, params: Dict) -> str:
        """获得需要排序的列"""
        sort = params.get("sort")
        if not sort:
            return ""
        sort_type = "asc"
        sort_field = sort
        if sort[0] == "-":
            sort_type = "desc"
            sort_field = sort[1:]
        sort_field_map = {"age": "created_at"}
        sort_field = sort_field_map.get(sort_field, sort_field)
        if not hasattr(self.model_class, sort_field):
            return ""
        if sort_type == "desc":
            return f"-{sort_field}"
        return sort_field

    def pagination_data(self, params: Dict):
        """获得分页后的数据 ."""
        if not self.query_set_list:
            # 如果label查询失败空
            return []
        page = params.get("page", 1)
        page_size = params.get("page_size", 10)
        offset = (page - 1) * page_size
        sort_field = self.get_sort(params)
        if sort_field:
            result_data = self.model_class.objects.order_by(sort_field).filter(*self.query_set_list)[
                offset : offset + page_size
            ]
        else:
            result_data = self.model_class.objects.filter(*self.query_set_list)[offset : offset + page_size]
        self.data = result_data

    def patch_status_filter_data_wrap(self, data: Dict) -> List:
        return [
            {
                "id": "success",
                "status": "success",
                "tips": _("正常"),
                "name": data.get(self.model_class.METRICS_STATE_STATE_SUCCESS, 0),
            },
            {
                "id": "failed",
                "status": "failed",
                "tips": _("异常"),
                "name": data.get(self.model_class.METRICS_STATE_FAILURE, 0),
            },
            {
                "id": "disabled",
                "status": "disabled",
                "tips": _("无数据"),
                "name": data.get(self.model_class.METRICS_STATE_DISABLED, 0),
            },
        ]

    def get_status_filter_data(self, params: Dict) -> List:
        """计算每种状态的资源数量 ."""
        status_summary = self.model_class.objects.count_monitor_status_quantity(self.query_set_list)
        return self.patch_status_filter_data_wrap(status_summary)

    def rendered_data(self, params):
        bk_biz_id = params["bk_biz_id"]
        data = []
        for item in self.data:
            data.append(item.render(bk_biz_id, render_type="list"))
        return data

    def data_to_labels_condition_list(self, params):
        """生成标签搜索 ."""
        bk_biz_id = params["bk_biz_id"]
        if bk_biz_id >= 0:
            cluster_ids = [
                item["bcs_cluster_id"]
                for item in BCSCluster.objects.filter(bk_biz_id=bk_biz_id).values("bcs_cluster_id")
            ]
        else:
            cluster_ids = list(self.space_associated_clusters.keys())

        condition_list = []
        if not cluster_ids:
            return condition_list

        label_ids = [
            item["label_id"]
            for item in self.model_label_class.objects.filter(bcs_cluster_id__in=cluster_ids)
            .values("label_id")
            .distinct()
        ]
        labels = BCSLabel.objects.filter(hash_id__in=label_ids)
        label_key_map_values = {}
        for label in labels:
            label_key_map_values.setdefault(label.key, []).append(label.value)

        for key, values in label_key_map_values.items():
            values = sorted(list(set(values)))
            condition_list.append(
                {
                    "name": key,
                    "id": f"__label_{key}",
                    "multiable": True,
                    "children": [
                        {
                            "name": item,
                            "id": item,
                        }
                        for item in values
                    ],
                }
            )

        return condition_list

    def get_cluster_by_space_uid(self, space_uid) -> Dict:
        """根据容器空间uid获得关联的集群."""
        if not is_bk_ci_space(space_uid):
            return {}
        self.space_associated_clusters = api.kubernetes.get_cluster_info_from_bcs_space({"space_uid": space_uid})
        return self.space_associated_clusters

    def add_condition_filter(self, params):
        """构造搜索条件 ."""
        q_list = []
        filter_q = self.filtered_label(params)
        if filter_q is None:
            # 标签搜索不到，直接返回空数据
            return []
        # 添加标签搜索条件
        q_list.append(filter_q)
        for filter_q in [
            self.filtered_cluster(params),
            self.filtered_biz_id(params),
            self.filtered_space_uid(params),
            self.filtered_name(params),
        ]:
            if filter_q:
                q_list.append(filter_q)
        self.query_set_list = q_list

    def filtered_label(self, params: Dict) -> Optional[Q]:
        label_conditions = {k.replace("__label_", ""): v for k, v in params.items() if k.find("__label_") == 0}
        if not label_conditions:
            return Q()
        filter_q = self.model_class.label_query_set_parser(label_conditions)
        if not filter_q:
            return None
        return filter_q

    def filtered_cluster(self, params: Dict) -> Q:
        filter_q = Q()
        bcs_cluster_id = params.get("bcs_cluster_id")
        if bcs_cluster_id and hasattr(self.model_class, "bcs_cluster_id"):
            if isinstance(bcs_cluster_id, list):
                filter_q &= Q(bcs_cluster_id__in=bcs_cluster_id)
            else:
                filter_q &= Q(bcs_cluster_id=bcs_cluster_id)
        return filter_q

    def filtered_biz_id(self, params: Dict) -> Q:
        bk_biz_id = params["bk_biz_id"]
        space_uid = params.get("space_uid")
        filter_q = Q(bk_biz_id=bk_biz_id)
        space_associated_clusters = self.get_cluster_by_space_uid(space_uid)
        if bk_biz_id and hasattr(self.model_class, "bk_biz_id"):
            if isinstance(bk_biz_id, list):
                filter_q &= Q(bk_biz_id__in=bk_biz_id)
            elif bk_biz_id < 0 and space_associated_clusters:
                # 忽略此过滤，使用后续的共享集群过滤器过滤
                return Q()

        return filter_q

    def filtered_space_uid(self, params: Dict) -> Q:
        bk_biz_id = params["bk_biz_id"]
        space_uid = params.get("space_uid")
        space_associated_clusters = self.get_cluster_by_space_uid(space_uid)
        filter_q = Q(bk_biz_id=bk_biz_id)
        if bk_biz_id < 0 and space_associated_clusters:
            filter_q_list = []
            # 获得容器空间关联的集群
            for cluster_id, value in space_associated_clusters.items():
                cluster_type = value.get("cluster_type")
                namespace_list = value["namespace_list"]
                if cluster_type == BcsClusterType.SHARED and namespace_list and self.model_class.has_namespace_field():
                    # 支持ns分割的资源，在共享集群条件下查询，不支持ns分割，则不查询
                    filter_q_list.append(Q(bcs_cluster_id=cluster_id, namespace__in=namespace_list))
                else:
                    # 独立集群直接查询
                    filter_q_list.append(Q(bcs_cluster_id=cluster_id))

            if filter_q_list:
                filter_q = reduce(operator.or_, filter_q_list)

        return filter_q

    def filtered_name(self, params: Dict) -> Q:
        filter_q = Q()
        else_conditions = {k: v for k, v in params.items() if k.find("__label_") != 0}
        query_params = {k: v for k, v in params.items()}
        for k, v in else_conditions.items():
            query_params[k] = v
        for k, v in query_params.items():
            if hasattr(self.model_class, k) and k not in {
                "keyword",
                "bk_biz_id",
                "bcs_cluster_id",
                "space_uid",
                "monitor_status",
            }:
                if isinstance(v, list):
                    filter_q &= Q(**{f"{k}__in": v})
                else:
                    filter_q &= Q(**{f"{k}": v})
        # 添加name过滤
        name_value = query_params.get("keyword")
        if name_value and hasattr(self.model_class, "name"):
            for value in name_value:
                filter_q &= Q(name__contains=value)
        return filter_q

    def add_monitor_status_filter(self, params):
        """数据状态过滤 ."""
        status_param = params.get("monitor_status")
        if status_param and status_param != "all":
            self.query_set_list.append(Q(monitor_status=status_param))

    def add_column_filter(self, params):
        """列搜索 ."""
        filter_dict = params.get("filter_dict")
        if filter_dict:
            for key, value in filter_dict.items():
                self.query_set_list.append(Q(**{f"{key}__in": value}))

    def aggregate_by_biz_id(self, bk_biz_id, params: Dict) -> Dict:
        """按业务ID聚合 ."""
        filter_q = Q(bk_biz_id=bk_biz_id)
        if isinstance(bk_biz_id, list):
            filter_q = Q(bk_biz_id__in=bk_biz_id)
        elif bk_biz_id < 0 and self.space_associated_clusters:
            # 容器空间
            shared_filter_q_list = []
            for cluster_id, value in self.space_associated_clusters.items():
                cluster_type = value.get("cluster_type")
                namespace_list = value["namespace_list"]
                if cluster_type == BcsClusterType.SHARED and namespace_list and self.model_class.has_namespace_field():
                    # 共享集群
                    shared_filter_q_list.append(Q(bcs_cluster_id=cluster_id, namespace__in=namespace_list))
                else:
                    shared_filter_q_list.append(Q(bcs_cluster_id=cluster_id))
            if shared_filter_q_list:
                filter_q = reduce(operator.or_, shared_filter_q_list)

        query = self.model_class.objects.filter(filter_q)
        summary = query.aggregate(**params)
        return summary


class GetKubernetesGrafanaMetricRecords(ApiAuthResource, abc.ABC):
    """获得指标数据."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField()
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")

    def validate_request_data(self, request_data: Dict) -> Dict:
        bk_biz_id = int(request_data["bk_biz_id"])
        request_data["bk_biz_id"] = bk_biz_id
        start_time = request_data.get("start_time")
        end_time = request_data.get("end_time")
        if not start_time:
            end_time = int(time.time())
            start_time = int(time.time() - 3600)
        request_data["start_time"] = int(start_time)
        request_data["end_time"] = int(end_time)

        return request_data

    @staticmethod
    def request_graph_unify_query(validated_request_data) -> Tuple:
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        data_source_params = validated_request_data["data_source_params"]
        key_name = data_source_params["key_name"]
        promql = data_source_params["promql"]
        params = {
            "alias": "a",
            "start_time": start_time,
            "end_time": end_time,
            "down_sample_range": "11s",
            "expression": "",
            "slimit": 500,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": promql,
                    "interval": 60,
                    "alias": "a",
                }
            ],
            "bk_biz_id": bk_biz_id,
        }
        records = resource.grafana.graph_unify_query(params)
        result = (key_name, records)
        return result

    @staticmethod
    def format_performance_data(validated_request_data: Dict, performance_data):
        data = {}
        for key_name, records in performance_data:
            data[key_name] = records
        return data

    @staticmethod
    def is_shared_cluster(params: Dict) -> bool:
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        if bcs_cluster_id and api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
            return True
        return False

    def request_performance_data(self, validated_request_data: Dict) -> List:
        pool = ThreadPool()
        args = self.build_graph_unify_query_iterable(validated_request_data)
        performance_data = pool.map(self.request_graph_unify_query, args)
        pool.close()
        pool.join()
        return performance_data

    @abc.abstractmethod
    def build_graph_unify_query_iterable(self, validated_request_data: Dict) -> List:
        ...

    def perform_request(self, validated_request_data: Dict) -> Union[List, Dict]:
        performance_data = self.request_performance_data(validated_request_data)
        if not performance_data:
            return {}
        data = self.format_performance_data(validated_request_data, performance_data)
        result = self.to_graph(validated_request_data, data)
        return result


class GetKubernetesMetricQueryRecords(ApiAuthResource, abc.ABC):
    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.space_associated_clusters = {}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True)
        group_by = serializers.CharField(required=False, allow_null=True)
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")

    def validate_request_data(self, request_data: Dict) -> Dict:
        bk_biz_id = int(request_data["bk_biz_id"])
        request_data["bk_biz_id"] = bk_biz_id
        start_time = request_data.get("start_time")
        end_time = request_data.get("end_time")
        if not start_time:
            end_time = int(time.time())
            start_time = int(time.time() - 300)
        start_time = int(start_time) * 1000
        end_time = int(end_time) * 1000
        request_data["start_time"] = int(start_time)
        request_data["end_time"] = int(end_time)

        return request_data

    def is_shared_cluster(self, bcs_cluster_id: str) -> bool:
        cluster_info = self.space_associated_clusters.get(bcs_cluster_id, {})
        is_shared_cluster = cluster_info and cluster_info.get("cluster_type") == BcsClusterType.SHARED
        return is_shared_cluster

    def request_unify_query(self, validated_request_data) -> Tuple:
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        data_source_params = validated_request_data["data_source_params"]
        group_by = validated_request_data["group_by"]

        key_name = data_source_params["key_name"]
        expression = data_source_params["expression"]
        metrics = data_source_params["metrics"]

        data_sources = []
        for item in metrics:
            alias = item["alias"]
            field = item["field"]
            method = item["method"]
            where = item["where"]
            data_sources.append(
                self.DATA_SOURCE_CLASS(
                    bk_biz_id=bk_biz_id,
                    table="",
                    metrics=[{"field": field, "method": method, "alias": alias}],
                    interval=60,
                    group_by=group_by,
                    where=where,
                )
            )
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression=expression)
        records = query.query_data(start_time=start_time, end_time=end_time)
        result = (key_name, records)
        return result

    def request_performance_data(self, validated_request_data: Dict) -> List:
        pool = ThreadPool()
        args = self.build_unify_query_iterable(validated_request_data)
        performance_data = pool.map(self.request_unify_query, args)
        pool.close()
        pool.join()
        return performance_data

    def format_performance_data(self, performance_data: List) -> List:
        return performance_data

    @abc.abstractmethod
    def build_unify_query_iterable(self, validated_request_data: Dict) -> List:
        ...

    def perform_request(self, validated_request_data: Dict):
        bk_biz_id = validated_request_data["bk_biz_id"]

        self.space_associated_clusters = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
        performance_data = self.request_performance_data(validated_request_data)
        if not performance_data:
            return {}
        performance_data = self.format_performance_data(performance_data)
        result = self.to_graph(validated_request_data, performance_data)
        return result


class GetKubernetesPod(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
        namespace = serializers.CharField(required=False, allow_null=True)
        pod_name = serializers.CharField(required=False, allow_null=True)

    def validate_request_data(self, request_data):
        # 仅避免详情页面跳转报错，实际关联逻辑并不清晰，指标数据展示甚至有逻辑问题
        if isinstance(request_data["pod_name"], list):
            if len(request_data["pod_name"]) > 0:
                request_data["pod_name"] = request_data["pod_name"][0]
            else:
                request_data["pod_name"] = ""

        return super().validate_request_data(request_data)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        params["name"] = params.pop("pod_name")
        item = BCSPod.load_item(params)
        if item:
            return item.render(bk_biz_id, "detail")
        return []


class GetKubernetesPodList(KubernetesResource):
    model_class = BCSPod
    model_label_class = BCSPodLabels
    RequestSerializer = KubernetesListRequestSerializer

    @staticmethod
    def read_namespaced_service(params: Dict) -> Dict:
        """获取服务的pod选择器 ."""
        selector = {}
        if "bcs_cluster_id" in params and "namespace" in params and "service_name" in params:
            bcs_cluster_id = params["bcs_cluster_id"]
            namespace = params["namespace"]
            service_name = params["service_name"]
            if isinstance(bcs_cluster_id, list):
                bcs_cluster_id = bcs_cluster_id[0]
            if isinstance(namespace, list):
                namespace = namespace[0]
            if isinstance(service_name, list):
                service_name = service_name[0]
            try:
                cluster_model = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
            except BCSCluster.DoesNotExist:
                return selector
            try:
                api_client = cluster_model.core_v1_api
                svc = api_client.read_namespaced_service(name=service_name, namespace=namespace)
                service_parser = KubernetesServiceJsonParser(svc.to_dict())
                selector = service_parser.spec["selector"]
            except Exception as exc_info:  # noqa
                logger.error(exc_info)

        return selector

    def filtered_label(self, params: Dict) -> Optional[Q]:
        if "service_name" in params:
            # 获取服务的pod选择器
            selector = self.read_namespaced_service(params)
            if not selector:
                # 如果没有获取到pod选择器，pod列表返回空
                return None
            else:
                params.update({f"__label_{key}": [value] for key, value in selector.items()})
        return super().filtered_label(params)

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "total_container_count": Sum("total_container_count"),
                "restarts": Sum("restarts"),
                "resource_usage_cpu": Sum("resource_usage_cpu"),
                "resource_usage_memory": Sum("resource_usage_memory"),
                "resource_usage_disk": Sum("resource_usage_disk"),
                "resource_requests_cpu": Sum("resource_requests_cpu"),
                "resource_limits_cpu": Sum("resource_limits_cpu"),
                "resource_requests_memory": Sum("resource_requests_memory"),
                "resource_limits_memory": Sum("resource_limits_memory"),
            },
        )
        # 容器数量添加链接
        summary["total_container_count"] = self.model_class.build_search_link(
            bk_biz_id, "container", summary["total_container_count"], scene_type="overview"
        )

        # 获得资源使用量
        resource_usage_cpu = summary["resource_usage_cpu"]
        resource_usage_memory = summary["resource_usage_memory"]
        resource_usage_disk = summary["resource_usage_disk"]

        summary["resource_usage_cpu"] = {
            "value": resource_usage_cpu,
            "label": BCSPod.get_cpu_human_readable(summary["resource_usage_cpu"]),
        }
        summary["resource_usage_memory"] = {
            "value": resource_usage_memory,
            "label": BCSPod.get_bytes_unit_human_readable(summary["resource_usage_memory"]),
        }
        summary["resource_usage_disk"] = {
            "value": resource_usage_disk,
            "label": BCSPod.get_bytes_unit_human_readable(summary["resource_usage_disk"]),
        }

        # 计算资源使用率
        percent_precision = 4  # 使用率精度
        resource_requests_cpu = summary["resource_requests_cpu"]
        resource_limits_cpu = summary["resource_limits_cpu"]
        resource_requests_memory = summary["resource_requests_memory"]
        resource_limits_memory = summary["resource_limits_memory"]
        summary["resource_requests_cpu"] = {
            "value": resource_requests_cpu,
            "label": BCSPod.get_cpu_human_readable(summary["resource_requests_cpu"]),
        }
        summary["resource_limits_cpu"] = {
            "value": resource_limits_cpu,
            "label": BCSPod.get_cpu_human_readable(summary["resource_limits_cpu"]),
        }
        summary["resource_requests_memory"] = {
            "value": resource_requests_memory,
            "label": BCSPod.get_bytes_unit_human_readable(summary["resource_requests_memory"]),
        }
        summary["resource_limits_memory"] = {
            "value": resource_limits_memory,
            "label": BCSPod.get_bytes_unit_human_readable(summary["resource_limits_memory"]),
        }

        request_cpu_usage_ratio = (
            round(force_float(resource_usage_cpu / resource_requests_cpu), percent_precision)
            if resource_usage_cpu and resource_requests_cpu
            else 0
        ) * 100
        limit_cpu_usage_ratio = (
            round(force_float(resource_usage_cpu / resource_limits_cpu), percent_precision)
            if resource_usage_cpu and resource_limits_cpu
            else 0
        ) * 100
        request_memory_usage_ratio = (
            round(force_float(resource_usage_memory / resource_requests_memory), percent_precision)
            if resource_usage_memory and resource_requests_memory
            else 0
        ) * 100
        limit_memory_usage_ratio = (
            round(force_float(resource_usage_memory / resource_limits_memory), percent_precision)
            if resource_usage_memory and resource_limits_memory
            else 0
        ) * 100
        summary["request_cpu_usage_ratio"] = get_progress_value(request_cpu_usage_ratio)
        summary["limit_cpu_usage_ratio"] = get_progress_value(limit_cpu_usage_ratio)
        summary["request_memory_usage_ratio"] = get_progress_value(request_memory_usage_ratio)
        summary["limit_memory_usage_ratio"] = get_progress_value(limit_memory_usage_ratio)

        overview_data.update(summary)
        return overview_data

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_namespace(params),
            self.model_class.get_filter_name(params),
            self.model_class.get_filter_workload_type(params),
            self.model_class.get_filter_workload_name(params),
            self.model_class.get_filter_node_ip(params),
            self.model_class.get_filter_service_status(params),
        ]


class GetKubernetesContainer(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        namespace = serializers.CharField(required=False, allow_null=True)
        pod_name = serializers.CharField(required=False, allow_null=True)
        container_name = serializers.CharField(required=False, allow_null=True)

    def validate_request_data(self, request_data):
        # 仅避免详情页面跳转报错，实际关联逻辑并不清晰，指标数据展示甚至有逻辑问题
        if isinstance(request_data["pod_name"], list):
            if len(request_data["pod_name"]) > 0:
                request_data["pod_name"] = request_data["pod_name"][0]
            else:
                request_data["pod_name"] = ""
        return super().validate_request_data(request_data)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        params["name"] = params.pop("container_name")
        item = BCSContainer.load_item(params)
        if item:
            return item.render(bk_biz_id, "detail")
        return []


class GetKubernetesContainerList(KubernetesResource):
    model_class = BCSContainer
    model_label_class = BCSContainerLabels
    RequestSerializer = KubernetesListRequestSerializer

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "resource_usage_cpu": Sum("resource_usage_cpu"),
                "resource_usage_memory": Sum("resource_usage_memory"),
                "resource_usage_disk": Sum("resource_usage_disk"),
            },
        )
        resource_usage_cpu = self.model_class.get_cpu_human_readable(summary["resource_usage_cpu"])
        resource_usage_memory = self.model_class.get_bytes_unit_human_readable(summary["resource_usage_memory"])
        resource_usage_disk = self.model_class.get_bytes_unit_human_readable(summary["resource_usage_disk"])

        summary["resource_usage_cpu"] = resource_usage_cpu
        summary["resource_usage_memory"] = resource_usage_memory
        summary["resource_usage_disk"] = resource_usage_disk
        overview_data.update(summary)
        return overview_data

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_namespace(params),
            self.model_class.get_filter_workload_type(params),
            self.model_class.get_filter_workload_name(params),
            self.model_class.get_filter_pod_name(params),
            self.model_class.get_filter_node_ip(params),
            self.model_class.get_filter_service_status(params),
        ]


class GetKubernetesService(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        namespace = serializers.CharField(required=True)
        service_name = serializers.CharField(required=True)

    @staticmethod
    def refresh_monitor_status(item: BCSService) -> None:
        """更新采集器状态 ."""
        namespace = item.namespace
        bk_biz_id = item.bk_biz_id
        bcs_cluster_id = item.bcs_cluster_id
        service = item.name

        # 更新up指标的值
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "monitor_type": BCSServiceMonitor.PLURAL,
            "namespace": namespace,
            "service": service,
        }
        item.update_monitor_status(params)

    def perform_request(self, params: Dict) -> List[Dict]:
        bk_biz_id = params["bk_biz_id"]
        params["name"] = params.pop("service_name")
        item = BCSService.load_item(params)
        if item:
            self.refresh_monitor_status(item)
            result = item.render(bk_biz_id, "detail")
        else:
            result = []

        return result


class GetKubernetesServiceList(KubernetesResource):
    model_class = BCSService
    model_label_class = BCSServiceLabels
    RequestSerializer = KubernetesListRequestSerializer

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "endpoint_count": Sum("endpoint_count"),
                "pod_count": Sum("pod_count"),
            },
        )
        endpoint_count = summary["endpoint_count"]
        pod_count = self.model_class.build_search_link(bk_biz_id, "pod", summary["pod_count"], scene_type="overview")
        overview_data.update({"endpoint_count": endpoint_count, "pod_count": pod_count})
        overview_data.update(summary)
        return overview_data

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_namespace(params),
        ]


class GetKubernetesWorkload(Resource):
    workload_type = ""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        namespace = serializers.CharField(required=True)
        workload_name = serializers.CharField(required=True)
        workload_type = serializers.CharField(required=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        params["name"] = params.pop("workload_name")
        params["type"] = params.pop("workload_type")
        item = BCSWorkload.load_item(params)
        if item:
            return item.render(bk_biz_id, "detail")
        return []


class GetKubernetesWorkloadList(KubernetesResource):
    model_class = BCSWorkload
    model_label_class = BCSWorkloadLabels
    RequestSerializer = KubernetesListRequestSerializer

    def preset(self, params):
        super().preset(params)
        workload_type = params.pop("workload_type", "")
        if workload_type:
            params["type"] = workload_type

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "container_count": Sum("container_count"),
                "pod_count": Sum("pod_count"),
            },
        )
        container_count = self.model_class.build_search_link(
            bk_biz_id, "container", summary["container_count"], scene_type="overview"
        )
        pod_count = self.model_class.build_search_link(bk_biz_id, "pod", summary["pod_count"], scene_type="overview")
        overview_data.update({"container_count": container_count, "pod_count": pod_count})
        return overview_data

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_namespace(params),
            self.model_class.get_filter_workload_type(params),
            self.model_class.get_filter_service_status(params),
        ]


class GetKubernetesNode(ApiAuthResource):
    # 资源使用率列
    client_sort_fields = {
        "system_cpu_summary_usage": "progress",
        "system_mem_pct_used": "progress",
        "system_io_util": "progress",
        "system_disk_in_use": "progress",
        "system_load_load15": "number",
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True)
        node_ip = serializers.CharField(required=False, allow_null=True)

    @staticmethod
    def get_performance_data(bk_biz_id, bcs_cluster_id):
        """获得资源使用率 ."""
        if api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
            # 共享集群不需要返回资源使用率
            return {}
        performance_data = api.kubernetes.fetch_k8s_node_performance(
            {
                "bk_biz_id": bk_biz_id,
                "overview": False,
            }
        )
        return performance_data

    def render(self, params, item):
        bcs_cluster_id = params.get("bcs_cluster_id")
        bk_biz_id = params["bk_biz_id"]
        ip = params.get("ip")
        # 获得指定主机的资源使用率
        performance_data = self.get_performance_data(bk_biz_id, bcs_cluster_id)
        non_overview_data = performance_data.get("data", {})
        resource_performance = non_overview_data.get(ip, {})
        data = []
        render_type = "detail"
        for column in item.get_columns(render_type):
            key = column["id"]
            if key in self.client_sort_fields:
                field_type = self.client_sort_fields[key]
                value = resource_performance.get(key, "")
                if value:
                    value = round(force_float(value), 2)
                if field_type == "progress":
                    value = get_progress_value(value)
            else:
                render = getattr(item, "render_" + column["id"], "")
                if render and callable(render):
                    value = render(bk_biz_id, render_type)
                else:
                    value = getattr(item, column["id"], "")
            data.append(
                {
                    "key": key,
                    "name": column["name"],
                    "type": column["type"],
                    "value": value,
                }
            )
        return data

    @staticmethod
    def refresh_monitor_status(item: BCSNode) -> None:
        """更新采集器状态 ."""
        bk_biz_id = item.bk_biz_id
        bcs_cluster_id = item.bcs_cluster_id
        ip = item.ip
        # 更新up指标的值
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "monitor_type": BCSServiceMonitor.PLURAL,
            "node_ip": ip,
        }
        item.update_monitor_status(params)

    def perform_request(self, params: Dict) -> List[Dict]:
        ip = params.pop("node_ip")
        params["ip"] = ip
        item = BCSNode.load_item(params)
        if item:
            self.refresh_monitor_status(item)
            result = self.render(params, item)
        else:
            result = []

        return result


class GetKubernetesNodeList(KubernetesResource):
    model_class = BCSNode
    model_label_class = BCSNodeLabels
    RequestSerializer = KubernetesListRequestSerializer

    # 资源使用率列
    client_sort_fields = {
        "system_cpu_summary_usage": "progress",
        "system_mem_pct_used": "progress",
        "system_io_util": "progress",
        "system_disk_in_use": "progress",
        "system_load_load15": "number",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.performance_data = {}

    def filtered_space_uid(self, params: Dict) -> Q:
        """根据空间uid过滤 ."""
        bk_biz_id = params["bk_biz_id"]
        filter_q = Q(bk_biz_id=bk_biz_id)
        filter_q_list = []
        space_uid = params.get("space_uid")
        space_associated_clusters = self.get_cluster_by_space_uid(space_uid)
        # 获得容器空间关联的集群，忽略共享集群
        for cluster_id, value in space_associated_clusters.items():
            cluster_type = value["cluster_type"]
            if cluster_type == BcsClusterType.SINGLE:
                filter_q_list.append(Q(bcs_cluster_id=cluster_id))

        if filter_q_list:
            filter_q = reduce(operator.or_, filter_q_list)

        return filter_q

    def filtered_name(self, params: Dict) -> Q:
        control_plane_q = Q()
        if "roles" in params:
            roles_value = params.pop("roles")
            if isinstance(roles_value, list):
                roles_value = roles_value[0]
            if isinstance(roles_value, str):
                # 过滤控制平面节点
                if "master" in roles_value or "control-plane" in roles_value:
                    control_plane_q = Q(roles__contains="control-plane") | Q(roles__contains="master")
                else:
                    control_plane_q = Q(roles=roles_value)

        filter_q = super().filtered_name(params)
        if control_plane_q:
            filter_q &= control_plane_q
        return filter_q

    def pagination_data(self, params: Dict):
        """获得分页后的数据 ."""
        if not self.query_set_list:
            return []
        page = params.get("page", 1)
        page_size = params.get("page_size", 10)
        offset = (page - 1) * page_size
        sort_field = self.get_sort(params)
        if sort_field:
            if sort_field not in self.client_sort_fields:
                # 取一页数据
                result_data = self.model_class.objects.order_by(sort_field).filter(*self.query_set_list)[
                    offset : offset + page_size
                ]
            else:
                # 如果排序列是资源使用率列，则取全部数据，用于按资源使用率排序，排序后再取指定页
                result_data = self.model_class.objects.order_by(sort_field).filter(*self.query_set_list)
        else:
            result_data = self.model_class.objects.filter(*self.query_set_list)[offset : offset + page_size]
        self.data = result_data

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "endpoint_count": Sum("endpoint_count"),
                "pod_count": Sum("pod_count"),
            },
        )

        summary["pod_count"] = self.model_class.build_search_link(
            bk_biz_id, "pod", summary["pod_count"], scene_type="overview"
        )
        overview_data.update(summary)
        return overview_data

    def get_performance_data(self, bk_biz_id, group_by):
        """获得资源使用率 ."""
        if not self.performance_data:
            node_ips = [item.ip for item in self.data]
            performance_data = api.kubernetes.fetch_k8s_node_performance(
                {
                    "bk_biz_id": bk_biz_id,
                    "overview": True,
                    "group_by": group_by,
                    "node_ips": node_ips,
                }
            )
            self.performance_data = performance_data
        return self.performance_data

    def render_overview_data(self, params, overview_data, columns):
        """在概览中添加资源使用率 ."""
        overview_data = super().render_overview_data(params, overview_data, columns)
        # 概览添加资源使用率
        bk_biz_id = params["bk_biz_id"]
        if is_ipv6_biz(bk_biz_id):
            group_by = ["bk_host_id"]
        else:
            group_by = ["bk_target_ip", "bk_target_cloud_id"]

        performance_data = self.get_performance_data(bk_biz_id, group_by)
        overview_performance_data = performance_data.get("overview", {})
        for field, field_type in self.client_sort_fields.items():
            value = overview_performance_data.get(field, "")
            if value:
                value = round(force_float(value), 2)
            if field_type == "progress":
                value = get_progress_value(value)
            overview_data[field] = value
        return overview_data

    def correct_data(self, params, overview_data, columns):
        """添加Node资源使用率 ."""
        data = super().correct_data(params, overview_data, columns)
        # 补充bk_host_id
        for row, item in zip(data, self.data):
            row["bk_host_id"] = item.bk_host_id
        if not data:
            return data
        # 获得资源使用率
        bk_biz_id = params["bk_biz_id"]
        if is_ipv6_biz(bk_biz_id):
            group_by = ["bk_host_id"]
        else:
            group_by = ["bk_target_ip", "bk_target_cloud_id"]
        performance_data = self.get_performance_data(bk_biz_id, group_by)
        non_overview_data = performance_data.get("data", {})

        # 分页
        sort_field_key = None
        sort = params.get("sort")
        if sort:
            if sort.startswith("-"):
                reverse = True
                sort_field_key = sort.lstrip("-")
            else:
                reverse = False
                sort_field_key = sort
            if sort_field_key in self.client_sort_fields:
                # 取一页数据
                page = params.get("page", 1)
                page_size = params.get("page_size", 10)
                offset = (page - 1) * page_size
                data = data[offset : offset + page_size]

        # 添加资源列
        for item in data:
            bk_target_ip = item["node_ip"]["value"]
            resource_performance = non_overview_data.get(bk_target_ip, {})
            # 将资源使用率转交为progress格式
            for field, field_type in self.client_sort_fields.items():
                value = resource_performance.get(field, "")
                if value:
                    value = round(force_float(value), 2)
                if field_type == "progress":
                    value = get_progress_value(value)
                item[field] = value

        # 排序
        if sort_field_key in self.client_sort_fields:
            field_type = self.client_sort_fields[sort_field_key]
            if field_type == "progress":

                def sort_key(x):
                    return x[sort_field_key]["value"] if x[sort_field_key]["value"] else 0

            else:

                def sort_key(x):
                    return x[sort_field_key] if x[sort_field_key] else 0

            data = sorted(data, key=sort_key, reverse=reverse)

        return data

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_service_status(params),
            self.model_class.get_filter_roles(params),
        ]


class GetKubernetesNamespaces(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster = params.get("bcs_cluster_id", "")

        data = []
        namespaces = api.kubernetes.fetch_k8s_namespace_list(params)
        cluster_id_set = set()
        for namespace in namespaces:
            bcs_cluster_id = namespace["bcs_cluster_id"]
            if bcs_cluster != "" and bcs_cluster_id != bcs_cluster:
                continue
            cluster_id_set.add(bcs_cluster_id)
            namespace_name = namespace.get("namespace", {}).get("metadata", {}).get("name")
            item_id = f"{bcs_cluster_id}-{namespace_name}"
            data.append(
                {
                    "id": item_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "namespace_name": namespace_name,
                    "name": namespace_name,
                }
            )
        # 共享集群
        # 如果 space_uid 存在，则以 space_uid 为准
        if bk_biz_id < 0:
            space_associated_clusters = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
            for cluster_id, value in space_associated_clusters.items():
                if cluster_id in cluster_id_set:
                    # 当前空间已经可以管理该共享集群，因此不需要再重复
                    continue
                ns_list = value.get("namespace_list")
                if not ns_list:
                    continue
                data += [
                    {
                        "id": f"{cluster_id}-{ns}",
                        "bcs_cluster_id": cluster_id,
                        "namespace_name": ns,
                        "name": ns,
                    }
                    for ns in ns_list
                    if not bcs_cluster or bcs_cluster == cluster_id
                ]

        return data


class GetKubernetesWorkloadTypes(Resource):
    def perform_request(self, params):
        data = []
        workload_types = api.kubernetes.fetch_k8s_workload_type_list()
        for workload_type in workload_types:
            data.append({"id": workload_type, "workload_type": workload_type, "name": workload_type})
        return data


class GetKubernetesClusterList(KubernetesResource):
    model_class = BCSCluster
    model_label_class = BCSClusterLabels
    RequestSerializer = KubernetesListRequestSerializer

    def rendered_data(self, params) -> List:
        for item in self.data:
            bcs_cluster_id = item.bcs_cluster_id
            if self.is_shared_cluster(bcs_cluster_id):
                # 共享集群不展示资源使用情况
                item.memory_usage_ratio = None
                item.disk_usage_ratio = None
                item.cpu_usage_ratio = None
                # 共享集群不展示节点的数量
                item.node_count = None
        data = super().rendered_data(params)
        return data

    def aggregate_by_biz_id(self, bk_biz_id, params: Dict) -> Dict:
        """按业务ID聚合 ."""
        filter_q = Q(bk_biz_id=bk_biz_id)
        if isinstance(bk_biz_id, list):
            filter_q = Q(bk_biz_id__in=bk_biz_id)
        elif bk_biz_id < 0 and self.space_associated_clusters:
            # 容器空间忽略共享集群进行统计
            shared_q_list = []
            for cluster_id, value in self.space_associated_clusters.items():
                cluster_type = value.get("cluster_type")
                if cluster_type == BcsClusterType.SINGLE:
                    shared_q_list.append(Q(bcs_cluster_id=cluster_id))
            if shared_q_list:
                filter_q = reduce(operator.or_, shared_q_list)

        query = self.model_class.objects.filter(filter_q)
        summary = query.aggregate(**params)

        return summary

    def get_overview_data(self, params, data):
        bk_biz_id = params["bk_biz_id"]
        overview_data = super().get_overview_data(params, data)
        if not overview_data:
            return overview_data

        # 节点数量和资源使用率不包含共享集群
        summary = self.aggregate_by_biz_id(
            bk_biz_id,
            {
                "node_count": Sum("node_count"),
                "cpu_usage_ratio": Avg("cpu_usage_ratio"),
                "memory_usage_ratio": Avg("memory_usage_ratio"),
                "disk_usage_ratio": Avg("disk_usage_ratio"),
            },
        )
        summary["cpu_usage_ratio"] = get_progress_value(summary["cpu_usage_ratio"])
        summary["memory_usage_ratio"] = get_progress_value(summary["memory_usage_ratio"])
        summary["disk_usage_ratio"] = get_progress_value(summary["disk_usage_ratio"])
        overview_data.update(summary)

        return overview_data


class GetKubernetesCluster(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)

    @classmethod
    def refresh_monitor_status(cls, item: BCSCluster) -> None:
        """更新资源使用率 ."""
        bk_biz_id = item.bk_biz_id
        bcs_cluster_id = item.bcs_cluster_id
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
        }
        item.update_monitor_status(params)

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        item = BCSCluster.load_item(params)
        if not item:
            return []
        # 更新资源使用率
        self.refresh_monitor_status(item)
        # 获得空间下的集群信息
        shard_cluster = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
        # 共享集群详情不展示集群的实际性能数据
        if shard_cluster:
            value = shard_cluster.get(item.bcs_cluster_id, {})
            cluster_type = value.get("cluster_type")
            namespace_list = value.get("namespace_list")
            if cluster_type == BcsClusterType.SHARED or namespace_list:
                # 共享集群不展示资源使用情况
                item.memory_usage_ratio = None
                item.disk_usage_ratio = None
                item.cpu_usage_ratio = None
                # 共享集群不展示节点的数量
                item.node_count = None

        detail = item.render(bk_biz_id, "detail")
        return detail


class GetKubernetesClusterChoices(KubernetesResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        # todo 空间支持
        cluster_list = BCSCluster.objects.filter(bk_biz_id=bk_biz_id).values("bcs_cluster_id", "name")
        data = []
        for item in cluster_list:
            bcs_cluster_id = item["bcs_cluster_id"]
            name = item["name"]
            if name:
                full_name = f"{name}({bcs_cluster_id})"
            else:
                full_name = bcs_cluster_id
            data.append(
                {
                    "id": bcs_cluster_id,
                    "name": full_name,
                }
            )

        return data


class GetKubernetesMonitor(Resource, abc.ABC):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        namespace = serializers.CharField(required=True)
        name = serializers.CharField(required=True)
        metric_path = serializers.CharField(required=True)
        metric_port = serializers.CharField(required=True)

    @property
    @abc.abstractmethod
    def model_class(self):
        raise NotImplementedError

    def refresh_monitor_status(self, item: BCSBase) -> None:
        """更新采集器状态 ."""
        namespace = item.namespace
        bk_biz_id = item.bk_biz_id
        bcs_cluster_id = item.bcs_cluster_id
        bk_monitor_name = item.name

        # 更新up指标的值
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "monitor_type": self.model_class.PLURAL,
            "bk_monitor_name": bk_monitor_name,
            "bk_monitor_namespace": namespace,
        }
        item.update_monitor_status(params)

    def perform_request(self, params: Dict) -> List[Dict]:
        bk_biz_id = params["bk_biz_id"]
        item = self.model_class.load_item(params)
        if item:
            self.refresh_monitor_status(item)
            result = item.render(bk_biz_id, "detail")
        else:
            result = []

        return result


class GetKubernetesMonitorList(KubernetesResource, abc.ABC):
    RequestSerializer = KubernetesListRequestSerializer

    @property
    @abc.abstractmethod
    def model_class(self):
        raise NotImplementedError

    def get_status_filter_data(self, params) -> List:
        """计算每种状态的资源数量 ."""
        # 判断up指标是否存在
        bk_biz_id = params["bk_biz_id"]
        if not api.kubernetes.has_bkm_metricbeat_endpoint_up({"bk_biz_id": bk_biz_id}):
            # 没有up指标采集器状态默认为正常
            if self.query_set_list:
                count = self.model_class.objects.filter(*self.query_set_list).count()
            else:
                count = self.model_class.objects.filter().count()
            status_summary = {self.model_class.METRICS_STATE_STATE_SUCCESS: count}
            result = self.patch_status_filter_data_wrap(status_summary)
        else:
            result = super().get_status_filter_data(params)

        return result

    def get_condition_list(self, params):
        return [
            self.model_class.get_filter_cluster(params),
            self.model_class.get_filter_namespace(params),
        ]


class GetKubernetesMonitorEndpoints(Resource, abc.ABC):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False)
        namespace = serializers.CharField(required=False)
        name = serializers.CharField(required=False)
        metric_path = serializers.CharField(required=False)

    @property
    @abc.abstractmethod
    def model_class(self):
        raise NotImplementedError

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        namespace = params.get("namespace")
        name = params.get("name")
        metric_path = params.get("metric_path")
        if not (bcs_cluster_id and namespace and name and metric_path):
            return []
        # 获得endpoints配置
        response_data = api.kubernetes.fetch_k8s_monitor_endpoint_list(
            {
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
            }
        )
        if not response_data:
            return []
        # 找到指定的monitor
        monitor_item_list = []
        for item in response_data:
            if item["kind"] == self.model_class.PLURAL and item["namespace"] == namespace and item["name"] == name:
                monitor_item_list.append(item)
        if not monitor_item_list:
            return []
        # 解析出endpoints列表
        data = []
        for monitor_item in monitor_item_list:
            for item in monitor_item["location"]:
                address = item["address"]
                if not address:
                    continue
                target = item["target"]
                if not target.endswith(metric_path):
                    continue
                data.append(
                    {
                        "id": target,
                        "name": target,
                    }
                )

        return data


class GetKubernetesMonitorPanels(Resource, abc.ABC):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        name = serializers.CharField(required=True)
        namespace = serializers.CharField(required=False)

    @property
    @abc.abstractmethod
    def model_class(self):
        raise NotImplementedError

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        dimension_value = params["name"]
        namespace = params.get("namespace")

        is_shared_cluster = api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id)
        # 共享集群要结合namespace过滤指标
        if is_shared_cluster and namespace:
            dimension_name = "bk_monitor_namespace/bk_monitor_name"
            dimension_value = f"{namespace}/{dimension_value}"
        else:
            dimension_name = "bk_monitor_name"

        # 从metadata获取指标列表
        data = api.metadata.query_bcs_metrics(
            {
                "bk_biz_ids": [bk_biz_id],
                "cluster_ids": [bcs_cluster_id],
                "dimension_name": dimension_name,
                "dimension_value": dimension_value,
            }
        )

        # 根据指标名构造panel
        table_name = ""
        data_source_label = "bk_monitor"
        data_type_label = "time_series"
        monitor_type = self.model_class.PLURAL
        panels = []
        where = [
            {
                "key": "bcs_cluster_id",
                "method": "eq",
                "value": ["$bcs_cluster_id"],
            },
            {
                "key": "bk_monitor_name",
                "method": "eq",
                "value": ["$bk_monitor_name"],
            },
            {
                "key": "monitor_type",
                "method": "eq",
                "value": [monitor_type],
            },
        ]
        if is_shared_cluster:
            where.append({"key": "namespace", "method": "eq", "value": ["$namespace"]})
        filter_dict = {
            "bk_endpoint_url": [
                "$bk_bcs_monitor_endpoints_id",
            ],
        }
        for item in data:
            metrics_field = item["field_name"]
            panel = self.render_simple_panel_template(
                table_name, metrics_field, where, filter_dict, data_source_label, data_type_label
            )
            panels.append(panel)

        return panels

    @staticmethod
    def render_simple_panel_template(
        table_name: str,
        metrics_field: str,
        where: List,
        filter_dict: Dict,
        data_source_label: str,
        data_type_label: str,
    ) -> Dict:
        """构造一个panel ."""
        if not table_name:
            id_name = metrics_field
        else:
            id_name = f"{table_name}.{metrics_field}"
        filter_dict = filter_dict if filter_dict else {}
        panel = {
            "id": id_name,
            "type": "graph",
            "title": metrics_field,
            "subTitle": id_name,
            "targets": [
                {
                    "data": {
                        "expression": "A",
                        "query_configs": [
                            {
                                "metrics": [{"field": metrics_field, "method": "$method", "alias": "A"}],
                                "interval": "$interval",
                                "table": table_name,
                                "data_source_label": data_source_label,
                                "data_type_label": data_type_label,
                                "group_by": ["$group_by"],
                                "where": where,
                                "functions": [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}],
                                "filter_dict": filter_dict,
                            }
                        ],
                    },
                    "alias": "",
                    "datasource": "time_series",
                    "data_type": "time_series",
                    "api": "grafana.graphUnifyQuery",
                }
            ],
        }

        return panel


class GetKubernetesServiceMonitor(GetKubernetesMonitor):
    model_class = BCSServiceMonitor


class GetKubernetesServiceMonitorList(GetKubernetesMonitorList):
    model_class = BCSServiceMonitor
    model_label_class = BCSServiceMonitorLabels


class GetKubernetesServiceMonitorEndpoints(GetKubernetesMonitorEndpoints):
    model_class = BCSServiceMonitor


class GetKubernetesServiceMonitorPanels(GetKubernetesMonitorPanels):
    model_class = BCSServiceMonitor


class GetKubernetesPodMonitor(GetKubernetesMonitor):
    model_class = BCSPodMonitor


class GetKubernetesPodMonitorList(GetKubernetesMonitorList):
    model_class = BCSPodMonitor
    model_label_class = BCSPodMonitorLabels


class GetKubernetesPodMonitorEndpoints(GetKubernetesMonitorEndpoints):
    model_class = BCSPodMonitor


class GetKubernetesPodMonitorPanels(GetKubernetesMonitorPanels):
    model_class = BCSPodMonitor


class GetKubernetesObjectCount(ApiAuthResource):
    """获得集群资源的数量 ."""

    RESOURCE_TITLES = {
        "cluster": {
            "label": _("集群"),
        },
        "namespace": {
            "label": "Namespace",
        },
        "node": {
            "label": "Node",
        },
        "pod": {
            "label": "Pod",
        },
        "master_node": {
            "label": "Master Node",
        },
        "work_node": {
            "label": "Worker Node",
        },
        "container": {
            "label": "Container",
        },
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True)
        resources = serializers.ListField(required=False)

    def perform_request(self, params: Dict):
        bk_biz_id = params.get("bk_biz_id")
        bcs_cluster_id = params.get("bcs_cluster_id")
        resources = params.get("resources", [])
        if not resources:
            resources = ["cluster", "namespace", "node", "pod"]

        # namespace 单独处理（共享集群）
        bulk_params = [
            {
                "resource_type": resource,
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
            }
            for resource in resources
            if resource != "namespace"
        ]
        bulk_data = api.kubernetes.fetch_resource_count.bulk_request(bulk_params)
        object_counts = {}
        for index, param in enumerate(bulk_params):
            object_counts[param["resource_type"]] = bulk_data[index]

        results = []
        for resource_name in resources:
            if resource_name == "namespace":
                namespace_count = len(GetKubernetesNamespaces()(params))
                item = {"label": "Namespace", "value": namespace_count}
            else:
                config = self.RESOURCE_TITLES.get(resource_name, {})
                item = {
                    "label": config.get("label", ""),
                    "value": object_counts.get(resource_name, 0),
                }

                dashboard_id = None
                if resource_name in ("node", "pod", "container"):
                    dashboard_id = resource_name
                elif resource_name in ("master_node", "work_node"):
                    dashboard_id = "node"

                if dashboard_id:
                    search = None
                    if dashboard_id == "node":
                        if api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
                            # 共享集群不需要展示节点数量和链接
                            continue
                        if bcs_cluster_id:
                            if resource_name == "master_node":
                                search = [{"bcs_cluster_id": bcs_cluster_id}, {"roles": "control-plane"}]
                            elif resource_name == "work_node":
                                search = [{"bcs_cluster_id": bcs_cluster_id}, {"roles": ""}]
                    else:
                        if bcs_cluster_id:
                            search = [{"bcs_cluster_id": bcs_cluster_id}]

                    # 添加链接
                    url = f"?bizId={bk_biz_id}#/k8s?dashboardId={dashboard_id}&sceneId=kubernetes&sceneType=overview" ""
                    if search:
                        query_data = json.dumps({"selectorSearch": search})
                        url = f"{url}&queryData={query_data}"
                    item["link"] = {
                        "target": "blank",
                        "url": url,
                    }

            results.append(item)
        return results


class GetKubernetesControlPlaneStatus(ApiAuthResource):
    """
    获取K8S控制平面状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    @classmethod
    def get_kubelet_node_config_error_count(cls, params: Dict) -> int:
        metric_field = "kubelet_node_config_error"
        data_source = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES)(
            bk_biz_id=params["bk_biz_id"],
            table="",
            metrics=[{"field": metric_field, "method": "SUM", "alias": "A"}],
            interval=60,
            group_by=[],
            where=[{"key": "bcs_cluster_id", "method": "eq", "value": [params["bcs_cluster_id"]]}]
            if params.get("bcs_cluster_id")
            else [],
        )
        query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=[data_source], expression="A")

        end_time = int(time.time() * 1000)
        start_time = int((time.time() - 300) * 1000)
        records = query.query_data(start_time=start_time, end_time=end_time)
        for record in reversed(records):
            if record["_result_"] is not None:
                return record["_result_"]
        return 0

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        try:
            pod_list = BCSPod.objects.filter_by_biz_id(bk_biz_id)
        except EmptyResultSet:
            return []

        control_plane_status = {
            "etcd": [],
            "kube-apiserver": [],
            "kube-controller-manager": [],
            "kube-scheduler": [],
            "kube-proxy": [],
        }

        for po in pod_list:
            for prefix in control_plane_status.keys():
                if po.namespace == "kube-system" and po.name.startswith(prefix):
                    control_plane_status[prefix].append(po.status)

        data = []
        for label, status_list in control_plane_status.items():
            status_text = "SUCCESS"
            for status in status_list:
                if status != "Running":
                    status_text = "FAILED"
            data.append({"label": label, "status": status_text})
        # kubelet 判断异常指标 kubelet_node_config_error
        kubelet_error_count = self.get_kubelet_node_config_error_count(params)
        kubelet_status = "SUCCESS"
        if kubelet_error_count > 0:
            kubelet_status = "FAILED"

        data.append({"label": "Kubelet", "status": kubelet_status})
        return data


class GetKubernetesWorkloadStatus(ApiAuthResource):
    """
    获取K8S workload状态
    目前显示的类型有Deployment,StatefulSet,DaemonSet,Job,CronJob
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
        type = serializers.CharField(required=True, label="工作负载类型")

    def perform_request(self, params):
        data = []
        name = params.get("type")
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        workload_type = params["type"]
        try:
            queryset = BCSWorkload.objects.filter_by_biz_id(bk_biz_id)
        except EmptyResultSet:
            return {
                "name": name,
                "data": [],
            }
        if bcs_cluster_id:
            queryset = queryset.filter(bcs_cluster_id=bcs_cluster_id)
        # 按状态分组计算每种状态的数量
        model_items = queryset.filter(type=workload_type).values("status").annotate(count=Count("status"))
        status_summary = {model["status"]: model["count"] for model in model_items}
        # 计算成功和失败的数量
        success_count = status_summary.get(BCSWorkload.STATE_SUCCESS, 0)
        failure_count = status_summary.get(BCSWorkload.STATE_FAILURE, 0)

        if success_count:
            selector_search = []
            if bcs_cluster_id:
                selector_search.append({"bcs_cluster_id": bcs_cluster_id})
            selector_search.extend([{"workload_type": name}, {"status": BCSWorkload.STATE_SUCCESS}])
            query_data = json.dumps(
                {
                    "selectorSearch": selector_search,
                }
            )

            data.append(
                {
                    "name": _("健康"),
                    "value": success_count,
                    "color": "#2dcb56",
                    "borderColor": "#2dcb56",
                    "link": {
                        "target": "blank",
                        "url": (
                            f"?bizId={bk_biz_id}#/k8s?"
                            f"sceneId=kubernetes&dashboardId=workload&sceneType=overview&queryData={query_data}"
                        ),
                    },
                }
            )

        if failure_count:
            selector_search = []
            if bcs_cluster_id:
                selector_search.append({"bcs_cluster_id": bcs_cluster_id})
            selector_search.extend([{"workload_type": name}, {"status": BCSWorkload.STATE_FAILURE}])
            query_data = json.dumps({"selectorSearch": selector_search})
            data.append(
                {
                    "name": _("异常"),
                    "value": failure_count,
                    "color": "#ea3636",
                    "borderColor": "#ea3636",
                    "link": {
                        "target": "blank",
                        "url": (
                            f"?bizId={bk_biz_id}#/k8s?"
                            f"sceneId=kubernetes&dashboardId=workload&sceneType=overview&queryData={query_data}"
                        ),
                    },
                }
            )

        return {
            "name": name,
            "data": data,
        }


class GetKubernetesUsageRatio(GetKubernetesGrafanaMetricRecords):
    """获得集群或节点的资源使用率."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        usage_type = serializers.ChoiceField(choices=("cpu", "memory"))
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="集群ID")

    def build_graph_unify_query_iterable(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        usage_type = validated_request_data.get("usage_type")
        start_time = int(start_time)
        end_time = int(end_time)
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")

        args = []

        if bcs_cluster_id:
            instance = BCSNode.objects.build_promql_param_instance(bk_biz_id, bcs_cluster_id)
            if not instance:
                return []
            cpu_summary_promql = (
                '(1 - avg(irate(node_cpu_seconds_total{mode="idle",'
                'instance=~"%(instance)s", '
                'bcs_cluster_id="%(bcs_cluster_id)s"}[5m]))) * 100'
            ) % {"bcs_cluster_id": bcs_cluster_id, "instance": instance}
            memory_summary_promql = (
                '(SUM by(bcs_cluster_id)'
                ' (node_memory_MemTotal_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"})'
                ' - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id)'
                ' (node_memory_MemFree_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"})'
                ' - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) '
                '(node_memory_Cached_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"})'
                ' - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) '
                '(node_memory_Buffers_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"})'
                ' + on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) '
                '(node_memory_Shmem_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"}))'
                ' / on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id)'
                ' (node_memory_MemTotal_bytes{'
                'instance=~"%(instance)s",bcs_cluster_id="%(bcs_cluster_id)s"}) * 100'
            ) % {"bcs_cluster_id": bcs_cluster_id, "instance": instance}
        else:
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []

            cpu_summary_promql = (
                '(1 - avg(irate(node_cpu_seconds_total{mode="idle",'
                'bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"}[5m]))) * 100'
            ) % {"bcs_cluster_id": "|".join(bcs_cluster_ids)}
            memory_summary_promql = (
                '(SUM(node_memory_MemTotal_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"})'
                '-SUM(node_memory_MemFree_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"})'
                '-SUM(node_memory_Cached_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"})'
                '-SUM(node_memory_Buffers_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"})'
                '+SUM(node_memory_Shmem_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"}))'
                '/(SUM(node_memory_MemTotal_bytes{bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"})) *100'
            ) % {"bcs_cluster_id": "|".join(bcs_cluster_ids)}

        data_source_param_map = [
            {"key_name": "cpu", "promql": cpu_summary_promql},
            {"key_name": "memory", "promql": memory_summary_promql},
        ]

        for data_source_params in data_source_param_map:
            key_name = data_source_params["key_name"]
            if usage_type and key_name != usage_type:
                continue
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                }
            )

        return args

    @staticmethod
    def to_graph(params: Dict, data: Dict) -> List:
        usage_type = params.get("usage_type")
        if usage_type == "cpu":
            target = _("CPU实际使用率(avg)")
        elif usage_type == "memory":
            target = _("内存实际使用率(avg)")
        else:
            target = ""

        response = data.get(usage_type)
        for item in response.get("series", []):
            item["dimensions"] = {}
            item["unit"] = "percent"
            item["target"] = target

        return response

    def perform_request(self, params):
        usage_type = params.get("usage_type")
        if self.is_shared_cluster(params):
            # 共享集群不需要返回资源使用率
            response = {
                "metrics": [],
                "name": f"{usage_type}使用率",
                "series": [],
            }
            return response

        result = super().perform_request(params)
        return result


class GetKubernetesWorkloadCountByNamespace(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField()

        keyword = serializers.CharField(required=False, allow_null=True, label="查询关键词", allow_blank=True)
        page = serializers.IntegerField(required=False, allow_null=True, label="页码")
        page_size = serializers.IntegerField(required=False, allow_null=True, label="每页条数")

    @staticmethod
    def get_columns():
        return [
            {
                "id": "namespace",
                "name": "Namespace",
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
            {
                "id": "count",
                "name": "Workload",
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
        ]

    def get_data(self, params: Dict):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        workloads = api.kubernetes.fetch_k8s_workload_list_by_cluster(params)
        shard_cluster = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id, "shard_only": True})
        filter_ns = shard_cluster.get(bcs_cluster_id, {}).get("namespace_list")
        namespace_counter = {}
        for w in workloads:
            ns = w["namespace"]
            if filter_ns is not None:
                if ns not in filter_ns:
                    continue

            if not namespace_counter.get(ns):
                namespace_counter[ns] = 0
            namespace_counter[ns] += 1

        self.data = []
        keyword = params.get("keyword", "")
        for namespace, count in namespace_counter.items():
            if keyword and namespace.find(keyword) == -1:
                continue
            self.data.append(
                {
                    "namespace": namespace,
                    "count": count,
                }
            )
        return self.data

    def perform_request(self, params):
        self.data = self.get_data(params)
        total = len(self.data)

        page = params.get("page", 1)
        page_size = params.get("page_size", 10)
        offset = (page - 1) * page_size
        self.data = self.data[offset : offset + page_size]

        return {
            "columns": self.get_columns(),
            "data": self.data,
            "total": total,
        }


class GetKubernetesWorkloadStatusList(Resource):
    def perform_request(self, params):
        return [
            {
                "id": k,
                "name": k,
            }
            for k in [
                "available",
                "unavailable",
                "active",
                "failed",
                "complete",
            ]
        ]


class GetKubernetesEvents(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(
            required=False, allow_null=True, allow_blank=True, label="bcs_cluster_id"
        )
        start_time = serializers.CharField(required=True, label="start_time")
        end_time = serializers.CharField(required=True, label="end_time")
        data_type = serializers.ChoiceField(default="list", choices=("list", "chart"))
        namespace = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="namespace")
        kind = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="kind")
        name = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="name")
        offset = serializers.IntegerField(default=0)
        limit = serializers.IntegerField(default=10)

        class ViewOptionsSerializer(serializers.Serializer):
            filters = serializers.DictField(required=False, allow_null=True)

        view_options = ViewOptionsSerializer(required=False, allow_null=True)

    def validate_request_data(self, request_data):
        # 仅避免详情页面跳转报错，实际关联逻辑并不清晰，指标数据展示甚至有逻辑问题
        name = request_data.get("name")
        if isinstance(name, list):
            if len(name) > 0:
                request_data["name"] = name[0]
            else:
                request_data["name"] = ""

        return super().validate_request_data(request_data)

    @classmethod
    def get_columns(cls):
        return [
            {
                "id": "time",
                "name": "Time",
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
            {
                "id": "namespace/name",
                "name": "Namespace/Name",
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
            {
                "id": "event_name",
                "name": "Event Name",
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
            {
                "id": "count",
                "name": "Count",
                "props": {"width": 70},
                "type": "string",
                "sortable": False,
                "disabled": False,
                "checked": True,
            },
        ]

    @classmethod
    def get_chart_data(cls, data: List) -> Dict:
        return {
            "metrics": [
                {
                    "data_type_label": "k8s",
                    "data_source_label": "event",
                    "metric_field": "result",
                }
            ],
            "series": data,
        }

    @classmethod
    def get_table_data(cls, data: Dict) -> Dict:
        if not data:
            return {"columns": cls.get_columns(), "data": [], "total": 0}
        result = []
        for item in data["list"]:
            source = item["_source"]
            dimensions = source["dimensions"]
            kind = dimensions["kind"]
            namespace = dimensions["namespace"]
            name = dimensions["name"]
            result.append(
                {
                    "data": item,
                    "kind": kind,
                    "namespace/name": f"{namespace}/{name}",
                    "event_name": source["event_name"],
                    "count": source["event"]["count"],
                    "time": datetime.fromtimestamp(int(source["time"]) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return {"columns": cls.get_columns(), "data": result, "total": data["total"]}

    def perform_request(self, params):
        data = api.kubernetes.fetch_k8s_event_list(params)
        data_type = params.get("data_type")
        if data_type == "chart":
            return self.get_chart_data(data)

        return self.get_table_data(data)


class GetKubernetesNetworkTimeSeries(Resource):
    """获得网络流量 ."""

    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="start_time")
        end_time = serializers.IntegerField(required=True, label="end_time")
        scope = serializers.ChoiceField(choices=("cluster", "node"))
        usage_type = serializers.ChoiceField(choices=("receive_bytes_total", "transmit_bytes_total"))

    @classmethod
    def get_node_network_receive_bytes_total(cls, start_time, end_time, bk_biz_id, where):
        data_sources = [
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[{"field": "node_network_receive_bytes_total", "method": "sum_without_time", "alias": "a"}],
                interval=60,
                group_by=[],
                functions=[{"id": "rate", "params": [{"id": "window", "value": "2m"}]}],
                where=where,
            )
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="a")
        records = query.query_data(start_time=start_time, end_time=end_time)
        return records

    @classmethod
    def get_node_network_transmit_bytes_total(cls, start_time, end_time, bk_biz_id, where):
        data_sources = [
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[{"field": "node_network_transmit_bytes_total", "method": "sum_without_time", "alias": "a"}],
                interval=60,
                functions=[{"id": "rate", "params": [{"id": "window", "value": "2m"}]}],
                group_by=[],
                where=where,
            )
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="a")
        records = query.query_data(start_time=start_time, end_time=end_time)
        return records

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        usage_type = params["usage_type"]
        target = "unknown"
        if usage_type == "receive_bytes_total":
            target = _("网卡进流量(avg)")
        elif usage_type == "transmit_bytes_total":
            target = _("网卡出流量(avg)")

        if bcs_cluster_id and api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
            # 共享集群不需要返回资源使用率
            response = {
                "metrics": [],
                "name": target,
                "series": [],
            }
            return response

        scope = params["scope"]
        end_time = params["end_time"] * 1000
        start_time = params["start_time"] * 1000

        where = []
        if bcs_cluster_id:
            where.append({"key": "bcs_cluster_id", "method": "eq", "value": [bcs_cluster_id]})
            try:
                node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                if not node_list:
                    return []
            except EmptyResultSet:
                return []
            where.append(
                {
                    "key": "instance",
                    "method": "reg",
                    "value": [
                        fr"^\[{node.ip}\]:" if is_v6(node.ip) else f"{node.ip}:" for node in node_list if node.ip
                    ],
                }
            )
        else:
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []
            where.extend([{"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_ids}])

        records = []
        if usage_type == "receive_bytes_total":
            records = self.get_node_network_receive_bytes_total(start_time, end_time, bk_biz_id, where)
        elif usage_type == "transmit_bytes_total":
            records = self.get_node_network_transmit_bytes_total(start_time, end_time, bk_biz_id, where)

        data_points = []
        for record in reversed(records):
            if record["_result_"] is not None and scope == "cluster":
                data_points.append([record["_result_"], record["_time_"]])

        response = {
            "series": [
                {
                    "dimensions": {},
                    "target": target,
                    "metric_field": "_result_",
                    "datapoints": data_points,
                    "alias": "_result_",
                    "type": "line",
                    "unit": "bytes",
                }
            ],
            "metrics": [],
        }
        return response


class GetKubernetesPreAllocatableUsageRatio(Resource):
    """获得CPU/内存预资源预分配率 ."""

    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="start_time")
        end_time = serializers.IntegerField(required=True, label="end_time")
        scope = serializers.ChoiceField(choices=("cluster",))
        usage_type = serializers.ChoiceField(choices=("cpu", "memory"))

    @classmethod
    def get_cpu_pre_allocatable_usage_ratio(cls, start_time, end_time, bk_biz_id, group_by, where):
        data_sources = [
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[
                    {
                        "field": "kube_pod_container_resource_requests_cpu_cores",
                        "method": "sum_without_time",
                        "alias": "A",
                    }
                ],
                interval=60,
                group_by=group_by,
                where=where,
            ),
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[
                    {"field": "kube_node_status_allocatable_cpu_cores", "method": "sum_without_time", "alias": "B"}
                ],
                interval=60,
                group_by=group_by,
                where=where,
            ),
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A/B*100")
        records = query.query_data(start_time=start_time, end_time=end_time)
        return records

    @classmethod
    def get_memory_pre_allocatable_usage_ratio(cls, start_time, end_time, bk_biz_id, group_by, where):
        data_sources = [
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[
                    {
                        "field": "kube_pod_container_resource_requests_memory_bytes",
                        "method": "sum_without_time",
                        "alias": "A",
                    }
                ],
                interval=60,
                group_by=group_by,
                where=where,
            ),
            cls.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[
                    {"field": "kube_node_status_allocatable_memory_bytes", "method": "sum_without_time", "alias": "B"}
                ],
                interval=60,
                group_by=group_by,
                where=where,
            ),
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A/B*100")
        records = query.query_data(start_time=start_time, end_time=end_time)
        return records

    def perform_request(self, params):
        usage_type = params["usage_type"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        if usage_type == "cpu":
            target = _("CPU预分配率(avg)")
        elif usage_type == "memory":
            target = _("内存预分配率(avg)")

        bk_biz_id = params["bk_biz_id"]
        if bcs_cluster_id and api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
            # 共享集群不需要返回资源使用率
            response = {
                "metrics": [],
                "name": target,
                "series": [],
            }
            return response

        scope = params["scope"]
        start_time = params["start_time"]
        end_time = params["end_time"]
        start_time = start_time * 1000
        end_time = end_time * 1000
        group_by = []

        where = []
        if scope == "cluster":
            if bcs_cluster_id:
                where.append({"key": "bcs_cluster_id", "method": "eq", "value": [bcs_cluster_id]})
                try:
                    node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                    if not node_list:
                        return []
                except EmptyResultSet:
                    return []
                where.append(
                    {
                        "key": "node",
                        "method": "eq",
                        "value": [node.ip for node in node_list if node.ip],
                    }
                )
            else:
                try:
                    bcs_cluster_ids = list(
                        BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                    )
                except EmptyResultSet:
                    bcs_cluster_ids = []
                if not bcs_cluster_ids:
                    return []
                where.extend([{"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_ids}])

            where.append({"key": "node", "method": "neq", "value": [""]})

        records = []
        if usage_type == "cpu":
            records = self.get_cpu_pre_allocatable_usage_ratio(start_time, end_time, bk_biz_id, group_by, where)
        elif usage_type == "memory":
            records = self.get_memory_pre_allocatable_usage_ratio(start_time, end_time, bk_biz_id, group_by, where)

        data_points = []
        for record in reversed(records):
            if record["_result_"] is not None and scope == "cluster":
                data_points.append([record["_result_"], record["_time_"]])

        response = {
            "series": [
                {
                    "dimensions": {},
                    "target": target,
                    "metric_field": "_result_",
                    "datapoints": data_points,
                    "alias": "_result_",
                    "type": "line",
                    "unit": "percent",
                }
            ],
            "metrics": [],
        }
        return response


class GetKubernetesEventCountByType(Resource):
    """根据事件类型统计事件的数量 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="开始时间（秒）")
        end_time = serializers.IntegerField(required=True, label="结束时间（秒）")

    @classmethod
    def aggregate_by_event_type(cls, params):
        """按事件类型聚合 ."""
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        start_time = params["start_time"]
        end_time = params["end_time"]
        # 设置按事件类型过滤，仅包含正常和警告
        where = [{"key": "type", "method": "eq", "value": [EventTypeNormal, EventTypeWarning]}]
        # 设置按事件类型聚合
        group_by = "dimensions.type"
        # 设置聚合函数，计算每种事件类型的数量
        select = f"count({group_by}) as {group_by}"
        # 设置为聚合操作
        limit = 0
        # 根据事件类型聚合
        es_params = {
            "bk_biz_id": bk_biz_id,
            "start_time": start_time,
            "end_time": end_time,
            "where": where,
            "bcs_cluster_id": bcs_cluster_id,
            "limit": limit,
            "select": [select],
            "group_by": [group_by],
        }
        event_result = api.kubernetes.fetch_k8s_event_log(es_params)
        return event_result

    @classmethod
    def to_ratio_ring_graph(cls, params, event_result):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        # 获得事件 result_table_id
        result_table_id = api.kubernetes.fetch_k8s_event_table_id({"bcs_cluster_id": bcs_cluster_id})
        data = []
        group_by = "dimensions.type"
        buckets = event_result.get("aggregations", {}).get(group_by, {}).get("buckets", [])
        for bucket in buckets:
            event_type = bucket["key"]
            query_config = {
                "result_table_id": result_table_id,
                "data_source_label": "custom",
                "data_type_label": "event",
                "where": [{"key": "type", "method": "eq", "value": [event_type]}],
            }
            url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"

            if event_type == "Warning":
                value = bucket["doc_count"]
                data.append(
                    {
                        "name": "Warning",
                        "value": value,
                        "color": "#e89e42",
                        "borderColor": "#e89e42",
                        "link": {"target": "blank", "url": url},
                    }
                )
            elif event_type == "Normal":
                value = bucket["doc_count"]
                data.append(
                    {
                        "name": "Normal",
                        "value": value,
                        "color": "#2dcb56",
                        "borderColor": "#2dcb56",
                        "link": {"target": "blank", "url": url},
                    }
                )
        name = _("事件数量")

        return {
            "name": name,
            "data": data,
        }

    def perform_request(self, params):
        bcs_cluster_id = params.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return {"name": _("事件数量"), "data": []}
        # 根据事件类型聚合
        event_result = self.aggregate_by_event_type(params)
        # 将结果转换ratio-ring类型的图表数据格式
        data = self.to_ratio_ring_graph(params, event_result)
        return data


class GetKubernetesEventCountByEventName(Resource):
    """根据事件名称统计事件的数量 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="开始时间（秒）")
        end_time = serializers.IntegerField(required=True, label="结束时间（秒）")
        event_names = serializers.ListField(required=False, label="事件类型", default=[])
        data_type = serializers.ChoiceField(
            required=False,
            default=GRAPH_RATIO_RING,
            choices=(
                GRAPH_RATIO_RING,
                GRAPH_PERCENTAGE_BAR,
                GRAPH_NUMBER_CHART,
                GRAPH_RESOURCE,
                GRAPH_COLUMN_BAR,
            ),
        )
        top_n = serializers.IntegerField(required=False, label="前几名", min_value=1, default=10)

    def to_graph(cls, params: Dict, event_result: Dict) -> Union[List, Dict]:
        data_type = params["data_type"]
        top_n = params["top_n"]
        group_by = "event_name"
        buckets = event_result.get("aggregations", {}).get(group_by, {}).get("buckets", [])
        data = {}
        if data_type == GRAPH_RATIO_RING:
            data = cls.to_ratio_ring_graph(params, buckets, top_n)
        elif data_type == GRAPH_PERCENTAGE_BAR:
            data = cls.to_percentage_bar_graph(buckets, top_n)
        elif data_type == GRAPH_NUMBER_CHART:
            data = cls.to_number_chart_graph(buckets)
        elif data_type == GRAPH_RESOURCE:
            data = cls.to_number_resource_graph(params, buckets)
        elif data_type == GRAPH_COLUMN_BAR:
            data = cls.to_column_bar_graph(params, buckets, top_n)
        return data

    @classmethod
    def to_ratio_ring_graph(cls, params: Dict, buckets: List, top_n: int) -> Dict:
        bcs_cluster_id = params.get("bcs_cluster_id")
        name = _("事件分布")
        if not bcs_cluster_id:
            return {
                "name": name,
                "data": [],
            }
        bk_biz_id = params["bk_biz_id"]
        # 获得事件 result_table_id
        result_table_id = api.kubernetes.fetch_k8s_event_table_id({"bcs_cluster_id": bcs_cluster_id})
        graph_data = []
        for bucket in buckets:
            event_name = bucket["key"]
            event_count = bucket["doc_count"]
            query_config = {
                "result_table_id": result_table_id,
                "data_source_label": "custom",
                "data_type_label": "event",
                "where": [{"key": "event_name", "method": "eq", "value": [event_name]}],
            }
            url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"
            graph_data.append(
                {
                    "name": event_name,
                    "value": event_count,
                    "link": {"target": "blank", "url": url},
                }
            )
        graph_data = graph_data[:top_n]
        name = _("事件分布")
        data = {
            "name": name,
            "data": graph_data,
        }
        return data

    @classmethod
    def to_percentage_bar_graph(cls, buckets: List, top_n: int) -> Dict:
        graph_data = []
        if buckets:
            # 取最大值
            total = buckets[0]["doc_count"]
            for bucket in buckets:
                event_name = bucket["key"]
                event_count = bucket["doc_count"]
                graph_data.append(
                    {
                        "name": event_name,
                        "value": event_count,
                        "unit": "",
                        "total": total,
                    }
                )

        graph_data = graph_data[:top_n]
        name = _("Top {} 事件").format(top_n)
        data = {
            "name": name,
            "data": graph_data,
        }
        return data

    @classmethod
    def to_column_bar_graph(cls, params: Dict, buckets: List, top_n: int) -> Dict:
        bcs_cluster_id = params.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return []
        bk_biz_id = params["bk_biz_id"]
        # 获得事件 result_table_id
        result_table_id = api.kubernetes.fetch_k8s_event_table_id({"bcs_cluster_id": bcs_cluster_id})

        graph_data = []
        if buckets:
            for bucket in buckets:
                event_name = bucket["key"]
                event_count = bucket["doc_count"]
                query_config = {
                    "result_table_id": result_table_id,
                    "data_source_label": "custom",
                    "data_type_label": "event",
                    "where": [{"key": "event_name", "method": "eq", "value": [event_name]}],
                }
                url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"
                graph_data.append(
                    {
                        "name": event_name,
                        "value": event_count,
                        "link": {"target": "blank", "url": url},
                        "color": "#699df4",
                    }
                )

        graph_data = graph_data[:top_n]
        return graph_data

    @classmethod
    def to_number_chart_graph(cls, buckets: List) -> List:
        graph_data = []
        for bucket in buckets:
            event_name = bucket["key"]
            event_count = bucket["doc_count"]
            graph_data.append(
                {
                    "label": event_name,
                    "value": event_count,
                }
            )
        return graph_data

    @classmethod
    def to_number_resource_graph(cls, params: Dict, buckets: List) -> Dict:
        bcs_cluster_id = params.get("bcs_cluster_id")
        event_names = params["event_names"]
        if not bcs_cluster_id:
            return [
                {
                    "name": event_names[0],
                    "value": 0,
                }
            ]
        bk_biz_id = params["bk_biz_id"]
        # 获得事件 result_table_id
        result_table_id = api.kubernetes.fetch_k8s_event_table_id({"bcs_cluster_id": bcs_cluster_id})

        graph_data = []
        for bucket in buckets:
            event_name = bucket["key"]
            event_count = bucket["doc_count"]
            query_config = {
                "result_table_id": result_table_id,
                "data_source_label": "custom",
                "data_type_label": "event",
                "where": [{"key": "event_name", "method": "eq", "value": [event_name]}],
            }
            url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"

            graph_data.append(
                {
                    "name": event_name,
                    "value": event_count,
                    "link": {"target": "blank", "url": url},
                }
            )
        if not graph_data:
            event_name = event_names[0]
            query_config = {
                "result_table_id": result_table_id,
                "data_source_label": "custom",
                "data_type_label": "event",
                "where": [{"key": "event_name", "method": "eq", "value": [event_name]}],
            }
            url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"

            graph_data = [
                {
                    "name": event_name,
                    "value": 0,
                    "link": {"target": "blank", "url": url},
                }
            ]

        return graph_data

    def validate_request_data(self, request_data):
        event_names = request_data.get("event_names", [])
        # 将逗号分隔的事件名称转换为数组格式
        if isinstance(event_names, str):
            event_names = event_names.split(",")
            request_data["event_names"] = event_names
        return super().validate_request_data(request_data)

    @classmethod
    def aggregate_by_event_name(cls, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return {}
        start_time = params["start_time"]
        end_time = params["end_time"]
        # 设置按事件名称聚合
        group_by = "event_name"
        select = f"count({group_by}) as {group_by}"
        where = [{"key": "type", "method": "eq", "value": [EventTypeNormal, EventTypeWarning]}]
        event_names = params["event_names"]
        if event_names:
            where.append({"key": "event_name", "method": "eq", "value": event_names})
        # 设置为聚合操作
        limit = 0
        es_params = {
            "start_time": start_time,
            "end_time": end_time,
            "bcs_cluster_id": bcs_cluster_id,
            "limit": limit,
            "bk_biz_id": bk_biz_id,
            "where": where,
            "select": [select],
            "group_by": [group_by],
        }
        # 根据事件类型聚合
        event_result = api.kubernetes.fetch_k8s_event_log(es_params)
        return event_result

    def perform_request(self, params):
        # 根据事件类型聚合
        event_result = self.aggregate_by_event_name(params)
        # 将结果转换为图表数据
        data = self.to_graph(params, event_result)
        return data


class GetKubernetesEventCountByKind(Resource):
    """根据事件名称统计事件的数量 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="开始时间（秒）")
        end_time = serializers.IntegerField(required=True, label="结束时间（秒）")

    @classmethod
    def aggregate_by_kind(cls, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        start_time = params["start_time"]
        end_time = params["end_time"]
        where = [{"key": "type", "method": "eq", "value": [EventTypeNormal, EventTypeWarning]}]
        group_by = "dimensions.kind"
        select = f"count({group_by}) as {group_by}"
        limit = 0
        es_params = {
            "start_time": start_time,
            "end_time": end_time,
            "bcs_cluster_id": bcs_cluster_id,
            "limit": limit,
            "bk_biz_id": bk_biz_id,
            "where": where,
            "select": [select],
            "group_by": [group_by],
        }
        # 根据事件类型聚合
        event_result = api.kubernetes.fetch_k8s_event_log(es_params)
        return event_result

    @classmethod
    def to_graph(cls, params, event_result):
        bk_biz_id = params["bk_biz_id"]
        data = []
        group_by = "dimensions.kind"
        bcs_cluster_id = params["bcs_cluster_id"]
        # 获得事件 result_table_id
        result_table_id = api.kubernetes.fetch_k8s_event_table_id({"bcs_cluster_id": bcs_cluster_id})

        buckets = event_result.get("aggregations", {}).get(group_by, {}).get("buckets", [])
        for bucket in buckets:
            event_name = bucket["key"]
            event_count = bucket["doc_count"]
            query_config = {
                "result_table_id": result_table_id,
                "data_source_label": "custom",
                "data_type_label": "event",
                "where": [{"key": "kind", "method": "eq", "value": [event_name]}],
            }
            url = f"?bizId={bk_biz_id}#/event-retrieval?queryConfig={json.dumps(query_config)}"
            data.append(
                {
                    "name": event_name,
                    "value": event_count,
                    "link": {"target": "blank", "url": url},
                }
            )
        name = _("事件类型")

        return {
            "name": name,
            "data": data,
        }

    def perform_request(self, params):
        bcs_cluster_id = params.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return {}
        # 根据事件类型聚合
        event_result = self.aggregate_by_kind(params)
        # 将结果转换ratio-ring类型的图表数据格式
        data = self.to_graph(params, event_result)
        return data


class GetKubernetesEventTimeSeries(Resource):
    """获得事件的按时间汇总数量 ."""

    # 时间点的数量
    DATA_POINTS_COUNT = 10

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        start_time = serializers.IntegerField(required=True, label="start_time")
        end_time = serializers.IntegerField(required=True, label="end_time")
        event_type = serializers.CharField(required=True, label="事件类型")
        time_scope = serializers.ChoiceField(
            required=False, choices=("current", "last_day", "last_week"), default="today"
        )

    @classmethod
    def format_time_series_records(cls, data_points: List, end_time: int, time_scope: str, interval: int) -> List:
        """格式化时间点数据 ."""
        # 转换为当前时间
        if time_scope == "last_day":
            end_time += 3600 * 24
        elif time_scope == "last_week":
            end_time += 3600 * 24 * 7
        # 根据当前时间往前取n个时间点
        range_end_time = end_time // interval * interval + interval
        range_begin_time = range_end_time - interval * cls.DATA_POINTS_COUNT
        time_range = range(range_begin_time, range_end_time, interval)
        # 将点转换为字典格式
        data_points_map = {time_value: event_count for event_count, time_value in data_points}
        # 添加缺失的点
        data = []
        for time_value in time_range:
            key = time_value * 1000
            value = data_points_map.get(key, 0)
            data.append([value, key])

        return data

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        if not bcs_cluster_id:
            return {}
        start_time = params["start_time"]
        end_time = params["end_time"]
        duration = end_time - start_time
        if duration <= 2 * 60 * 60:
            interval = 60 * 5
        elif duration > 2 * 60 * 60:
            interval = 3600
        elif duration > 2 * 24 * 60 * 60:
            interval = 3600 * 24
        else:
            interval = 60
        time_scope = params["time_scope"]
        if time_scope == "last_day":
            start_time -= 3600 * 24
            end_time -= 3600 * 24
        elif time_scope == "last_week":
            start_time -= 3600 * 24 * 7
            end_time -= 3600 * 24 * 7

        event_type = params.get("event_type")
        group_by = "dimensions.type"
        select = f"count({group_by}) as {group_by}"
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "start_time": start_time,
            "end_time": end_time,
            "limit": 0,
            "select": [select],
            "group_by": [group_by, f"time({interval}s)"],
        }
        where = []
        if event_type:
            where.append({"key": "type", "method": "eq", "value": event_type})
        if where:
            params["where"] = where

        # 根据事件类型聚合
        event_result = api.kubernetes.fetch_k8s_event_log(params)

        # 格式化为图表格式
        data_points = []
        buckets = event_result.get("aggregations", {}).get(group_by, {}).get("buckets", [])
        for bucket in buckets:
            time_buckets = bucket.get("time", {}).get("buckets", [])
            for time_bucket in time_buckets:
                time_value = time_bucket["key"]
                # 转换为毫秒
                if time_scope == "last_day":
                    time_value += 3600 * 24 * 1000
                elif time_scope == "last_week":
                    time_value += 3600 * 24 * 7 * 1000
                event_count = time_bucket["doc_count"]
                data_points.append([event_count, time_value])

        # 添加缺失的点
        data_points = self.format_time_series_records(data_points, end_time, time_scope, interval)

        time_series = {
            "series": [
                {
                    "dimensions": {},
                    "target": event_type,
                    "metric_field": "_result_",
                    "datapoints": data_points,
                    "alias": "_result_",
                    "type": "line",
                    "unit": "",
                }
            ],
            "metrics": [],
        }

        return time_series


class GetKubernetesCpuAnalysis(GetKubernetesMetricQueryRecords):
    """获得CPU资源配置."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True)
        group_by = serializers.CharField(required=False, allow_null=True)
        usage_type = serializers.CharField(required=False, allow_null=True)
        top_n = serializers.IntegerField(required=False, label="前几名", min_value=1, default=5)
        data_type = serializers.ChoiceField(
            required=False,
            default=GRAPH_RATIO_RING,
            choices=(
                GRAPH_PERCENTAGE_BAR,
                GRAPH_RESOURCE,
            ),
        )
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")

    def build_unify_query_iterable(self, params: Dict) -> List:
        bk_biz_id = params["bk_biz_id"]
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        bcs_cluster_id = params.get("bcs_cluster_id")
        usage_type = params.get("usage_type")
        group_by = params.get("group_by")
        if not group_by:
            group_by = []
        else:
            group_by = group_by.split(",")

        namespace_list = []
        if bcs_cluster_id:
            where = [{"key": "bcs_cluster_id", "method": "eq", "value": [bcs_cluster_id]}]
            if not self.is_shared_cluster(bcs_cluster_id):
                try:
                    node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                    if not node_list:
                        return []
                except EmptyResultSet:
                    return []
                where.append(
                    {
                        "key": "node",
                        "method": "eq",
                        "value": [node.name for node in node_list if node.name],
                    }
                )
        else:
            where = [{"key": "node", "method": "neq", "value": [""]}]
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []
            where.extend([{"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_ids}])

        args = []
        for data_source_params in [
            {
                "key_name": "cpu_cores",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_node_status_capacity_cpu_cores",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "requests_cpu_cores",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_requests_cpu_cores",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "limits_cpu_cores",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_limits_cpu_cores",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "pre_allocatable_usage_ratio",
                "expression": "A/B*100",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_requests_cpu_cores",
                        "method": "sum_without_time",
                        "where": where,
                    },
                    {
                        "alias": "B",
                        "field": "kube_node_status_capacity_cpu_cores",
                        "method": "sum_without_time",
                        "where": where,
                    },
                ],
            },
        ]:
            key_name = data_source_params["key_name"]
            if usage_type and key_name != usage_type:
                continue
            if bcs_cluster_id and namespace_list and key_name not in ["requests_cpu_cores", "limits_cpu_cores"]:
                # 共享集群只保留CPU request核数和CPU limit核数
                continue

            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                    "group_by": group_by,
                }
            )

        return args

    def to_graph(self, params: Dict, performance_data: Dict) -> List:
        data_type = params.get("data_type", GRAPH_RESOURCE)
        top_n = int(params.get("top_n", 5))

        graph_data = {}
        if data_type == GRAPH_PERCENTAGE_BAR:
            graph_data = self.to_percentage_bar_graph(params, performance_data, top_n)
        elif data_type == GRAPH_RESOURCE:
            graph_data = self.to_number_resource_graph(params, performance_data)
        return graph_data

    @staticmethod
    def to_percentage_bar_graph(params: Dict, performance_data: List, top_n: int) -> Dict:
        result = {"data": []}
        usage_type = params.get("usage_type")
        if not usage_type:
            return result

        group_by = params.get("group_by")
        if group_by != "namespace":
            return result

        # 获得指标数据
        performance_data_by_usage_type = []
        for record in performance_data:
            if record[0] == usage_type:
                performance_data_by_usage_type = record[1]
                break
        # 格式化为字典格式
        data = {}
        for record in sorted(performance_data_by_usage_type, key=lambda d: d["_time_"], reverse=True):
            namespace = record.get("namespace")
            if not namespace:
                continue
            value = round(record.get("_result_", 0), 2)
            if namespace not in data:
                data[namespace] = value

        # 计算total
        total = 0
        for value in data.values():
            total += value

        # 按从小到大取部分数据
        sorted_data = sorted(data.items(), key=lambda d: d[1] if d[1] else 0, reverse=True)[:top_n]
        graph_data = []
        for namespace, value in sorted_data:
            graph_data.append(
                {
                    "name": namespace,
                    "value": value,
                    "unit": _("核"),
                    "total": total,
                }
            )

        result = {
            "data": graph_data,
        }
        return result

    def to_number_resource_graph(self, params: Dict, performance_data: Dict) -> List:
        bcs_cluster_id = params.get("bcs_cluster_id")
        data = {}
        for key_name, records in performance_data:
            if records:
                records = sorted(records, key=lambda d: d["_time_"], reverse=True)
                record = records[0]
                value = record["_result_"]
            else:
                value = 0
            data[key_name] = value

        pre_allocatable_usage_ratio = round(data.get('pre_allocatable_usage_ratio', 0), 2)
        if pre_allocatable_usage_ratio > 80:
            color = "#f8c554"
        else:
            color = "#6bd58f"
        if bcs_cluster_id:
            if self.is_shared_cluster(bcs_cluster_id):
                graph_data = [
                    {
                        "name": _("CPU request 核数"),
                        "value": round(data.get("requests_cpu_cores", 0), 2),
                    },
                    {
                        "name": _("CPU limit 核数"),
                        "value": round(data.get("limits_cpu_cores", 0), 2),
                    },
                ]
                return graph_data

        graph_data = [
            {
                "name": _("CPU总核数"),
                "value": round(data.get("cpu_cores", 0), 2),
            },
            {
                "name": _("CPU request 核数"),
                "value": round(data.get("requests_cpu_cores", 0), 2),
            },
            {
                "name": _("CPU limit 核数"),
                "value": round(data.get("limits_cpu_cores", 0), 2),
            },
            {
                "name": _("CPU预分配率"),
                "value": f"{pre_allocatable_usage_ratio}%",
                "color": color,
            },
        ]
        return graph_data


class GetKubernetesMemoryAnalysis(GetKubernetesMetricQueryRecords):
    """获得内存资源配置."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True)
        group_by = serializers.CharField(required=False, allow_null=True)
        usage_type = serializers.CharField(required=False, allow_null=True)
        top_n = serializers.IntegerField(required=False, label="前几名", min_value=1, default=5)
        data_type = serializers.ChoiceField(
            required=False,
            default=GRAPH_RATIO_RING,
            choices=(
                GRAPH_PERCENTAGE_BAR,
                GRAPH_RESOURCE,
            ),
        )
        start_time = serializers.CharField(required=False, label="start_time")
        end_time = serializers.CharField(required=False, label="end_time")

    def build_unify_query_iterable(self, params: Dict) -> List:
        bk_biz_id = params["bk_biz_id"]
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        bcs_cluster_id = params.get("bcs_cluster_id")
        usage_type = params.get("usage_type")
        group_by = params.get("group_by")
        if not group_by:
            group_by = []
        else:
            group_by = group_by.split(",")

        namespace_list = []
        if bcs_cluster_id:
            where = [{"key": "bcs_cluster_id", "method": "eq", "value": [bcs_cluster_id]}]
            if not self.is_shared_cluster(bcs_cluster_id):
                try:
                    node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                    if not node_list:
                        return []
                except EmptyResultSet:
                    return []
                where.append(
                    {
                        "key": "node",
                        "method": "eq",
                        "value": [node.name for node in node_list if node.name],
                    }
                )
        else:
            where = [{"key": "node", "method": "neq", "value": [""]}]
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []
            where.extend([{"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_ids}])
        args = []
        for data_source_params in [
            {
                "key_name": "allocatable_memory_bytes",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_node_status_capacity_memory_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "requests_memory_bytes",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_requests_memory_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "limits_memory_bytes",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_limits_memory_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    }
                ],
            },
            {
                "key_name": "pre_allocatable_usage_ratio",
                "expression": "A/B*100",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "kube_pod_container_resource_requests_memory_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                    {
                        "alias": "B",
                        "field": "kube_node_status_capacity_memory_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                ],
            },
        ]:
            key_name = data_source_params["key_name"]
            if usage_type and key_name != usage_type:
                continue
            if bcs_cluster_id and namespace_list and key_name not in ("requests_memory_bytes", "limits_memory_bytes"):
                continue
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                    "group_by": group_by,
                }
            )

        return args

    def to_graph(self, params: Dict, performance_data: Dict) -> List:
        data_type = params.get("data_type", GRAPH_RESOURCE)
        top_n = int(params.get("top_n", 5))

        graph_data = {}
        if data_type == GRAPH_PERCENTAGE_BAR:
            graph_data = self.to_percentage_bar_graph(params, performance_data, top_n)
        elif data_type == GRAPH_RESOURCE:
            graph_data = self.to_number_resource_graph(params, performance_data)
        return graph_data

    @staticmethod
    def to_percentage_bar_graph(params: Dict, performance_data: List, top_n: int) -> Dict:
        result = {"data": []}
        usage_type = params.get("usage_type")
        if not usage_type:
            return result

        group_by = params.get("group_by")
        if group_by != "namespace":
            return result

        # 获得指标数据
        performance_data_by_usage_type = []
        for record in performance_data:
            if record[0] == usage_type:
                performance_data_by_usage_type = record[1]
                break
        # 格式化为字典格式
        data = {}
        for record in sorted(performance_data_by_usage_type, key=lambda d: d["_time_"], reverse=True):
            namespace = record.get("namespace")
            if not namespace:
                continue
            value = round(record.get("_result_", 0), 2)
            if namespace not in data:
                data[namespace] = value

        # 计算total
        total = 0
        for value in data.values():
            total += value

        # 按从小到大取部分数据
        sorted_data = sorted(data.items(), key=lambda d: d[1] if d[1] else 0, reverse=True)[:top_n]
        graph_data = []
        for namespace, value in sorted_data:
            # 不知道哪里调用这块， value 和 total 共用G 单位， 暂不改
            graph_data.append(
                {
                    "name": namespace,
                    "value": round(value / 1024 / 1024 / 1024, 2),
                    "unit": "G",
                    "total": total / 1024 / 1024 / 1024,
                }
            )

        result = {
            "data": graph_data,
        }
        return result

    def to_number_resource_graph(self, params: Dict, performance_data: Dict) -> List:
        bcs_cluster_id = params.get("bcs_cluster_id")
        data = {}
        for key_name, records in performance_data:
            if records:
                records = sorted(records, key=lambda d: d["_time_"], reverse=True)
                record = records[0]
                value = record["_result_"]
            else:
                value = 0
            data[key_name] = value

        allocatable_memory = data.get("allocatable_memory_bytes", 0)
        requests_memory = data.get("requests_memory_bytes", 0)
        limits_memory = data.get("limits_memory_bytes", 0)

        pre_allocatable_usage_ratio = round(data.get('pre_allocatable_usage_ratio', 0), 2)
        if pre_allocatable_usage_ratio > 80:
            color = "#f8c554"
        else:
            color = "#6bd58f"
        if bcs_cluster_id:
            if self.is_shared_cluster(bcs_cluster_id):
                graph_data = [
                    {
                        "name": _("内存 request 量"),
                        "value": "%s %s" % load_unit("bytes").auto_convert(requests_memory, decimal=2),
                    },
                    {
                        "name": _("内存 limit 量"),
                        "value": "%s %s" % load_unit("bytes").auto_convert(limits_memory, decimal=2),
                    },
                ]
                return graph_data

        graph_data = [
            {
                "name": _("内存总量"),
                "value": "%s %s" % load_unit("bytes").auto_convert(allocatable_memory, decimal=2),
            },
            {
                "name": _("内存 request 量"),
                "value": "%s %s" % load_unit("bytes").auto_convert(requests_memory, decimal=2),
            },
            {
                "name": _("内存 limit 量"),
                "value": "%s %s" % load_unit("bytes").auto_convert(limits_memory, decimal=2),
            },
            {
                "name": _("内存预分配率"),
                "value": f"{pre_allocatable_usage_ratio}%",
                "color": color,
            },
        ]
        return graph_data


class GetKubernetesDiskAnalysis(GetKubernetesMetricQueryRecords):
    """获得磁盘资源配置."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True)
        start_time = serializers.CharField(required=False, label="start_time")
        end_time = serializers.CharField(required=False, label="end_time")

    @staticmethod
    def format_performance_data(performance_data):
        data = {}
        for key_name, records in performance_data:
            if records:
                record = records[0]
                value = record["_result_"]
            else:
                value = 0
            data[key_name] = value
        return data

    @staticmethod
    def build_unify_query_iterable(params: Dict) -> List:
        bk_biz_id = int(params["bk_biz_id"])
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        bcs_cluster_id = params.get("bcs_cluster_id")
        group_by = []
        args = []
        if bcs_cluster_id:
            where = [{"key": "bcs_cluster_id", "method": "eq", "value": [bcs_cluster_id]}]
            try:
                node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                if not node_list:
                    return []
            except EmptyResultSet:
                return []
            where.append(
                {
                    "key": "instance",
                    "method": "reg",
                    "value": [f"^{node.ip}:" for node in node_list if node.ip],
                }
            )
        else:
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []
            where = [{"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_ids}]
        where.extend([{"key": "fstype", "method": "eq", "value": ["ext2", "ext3", "ext4", "btrfs", "xfs", "zfs"]}])

        for data_source_params in [
            {
                "key_name": "system_disk_total",
                "expression": "A",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "node_filesystem_size_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                ],
            },
            {
                "key_name": "system_disk_used",
                "expression": "A-B",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "node_filesystem_size_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                    {
                        "alias": "B",
                        "field": "node_filesystem_free_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                ],
            },
            {
                "key_name": "disk_usage_ratio",
                "expression": "(A-B)/A*100",
                "metrics": [
                    {
                        "alias": "A",
                        "field": "node_filesystem_size_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                    {
                        "alias": "B",
                        "field": "node_filesystem_free_bytes",
                        "method": "sum_without_time",
                        "where": where,
                    },
                ],
            },
        ]:
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                    "group_by": group_by,
                }
            )

        return args

    @staticmethod
    def to_graph(validated_request_data: Dict, performance_data: List) -> List:
        system_disk_total = performance_data.get("system_disk_total", 0)
        system_disk_used = performance_data.get("system_disk_used", 0)

        disk_usage_ratio = round(performance_data.get('disk_usage_ratio', 0), 2)
        if disk_usage_ratio > 80:
            color = "#f8c554"
        else:
            color = "#6bd58f"
        graph_data = [
            {
                "name": _("磁盘总量"),
                "value": "%s %s" % load_unit("bytes").auto_convert(system_disk_total, decimal=2),
            },
            {
                "name": _("磁盘已使用量"),
                "value": "%s %s" % load_unit("bytes").auto_convert(system_disk_used, decimal=2),
            },
            {
                "name": _("磁盘使用率"),
                "value": f"{disk_usage_ratio}%",
                "color": color,
            },
        ]
        return graph_data

    def perform_request(self, validated_request_data: Dict):
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")

        # 共享集群不返还信息
        if bcs_cluster_id and api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id):
            return []

        performance_data = self.request_performance_data(validated_request_data)
        if not performance_data:
            return []

        performance_data = self.format_performance_data(performance_data)
        result = self.to_graph(validated_request_data, performance_data)
        return result


class GetKubernetesOverCommitAnalysis(Resource):
    """获得CPU和内存资源分配过载状态."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True)
        start_time = serializers.CharField(required=False, label="start_time")
        end_time = serializers.CharField(required=False, label="end_time")

    @staticmethod
    def request_single_performance_data(params):
        bk_biz_id = params["bk_biz_id"]
        start_time = params["start_time"]
        end_time = params["end_time"]
        data_source_params = params["data_source_params"]
        key_name = data_source_params["key_name"]
        promql = data_source_params["promql"]
        params = {
            "alias": "a",
            "start_time": start_time,
            "end_time": end_time,
            "down_sample_range": "11s",
            "expression": "",
            "slimit": 500,
            "query_configs": [
                {
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "promql": promql,
                    "interval": 60,
                    "alias": "a",
                }
            ],
            "bk_biz_id": bk_biz_id,
        }
        records = resource.grafana.graph_unify_query(params)
        result = (key_name, records)
        return result

    @staticmethod
    def format_performance_data(performance_data):
        data = {}
        for key_name, records in performance_data:
            value = -1
            series = records["series"]
            if series:
                series_item = series[0]
                datapoints = series_item["datapoints"]
                if datapoints:
                    value = datapoints[-1][0]
            data[key_name] = value
        return data

    def request_performance_data(self, params):
        bk_biz_id = int(params["bk_biz_id"])
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        if not start_time:
            end_time = int(time.time())
            start_time = int(time.time() - 300)
        start_time = int(start_time)
        end_time = int(end_time)
        bcs_cluster_id = params.get("bcs_cluster_id")

        args = []

        if bcs_cluster_id:
            try:
                node_list = BCSNode.objects.search_work_nodes(bk_biz_id, bcs_cluster_id)
                if not node_list:
                    return []
            except EmptyResultSet:
                return []
            node_ips = "|".join(node.name for node in node_list)
            cpu_over_commit_promql = (
                'sum by(bcs_cluster_id)'
                ' (kube_pod_container_resource_requests_cpu_cores{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""})'
                ' / on(bcs_cluster_id) group_right()'
                ' sum by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_cpu_cores{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""})'
                ' - on(bcs_cluster_id) group_right()'
                ' (count by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_cpu_cores{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""}) - 1) '
                ' / on(bcs_cluster_id) group_right()'
                ' count by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_cpu_cores{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""})'
            ) % {"bcs_cluster_id": bcs_cluster_id, "node_ips": node_ips}
            memory_over_commit_promql = (
                'sum by(bcs_cluster_id) '
                ' (kube_pod_container_resource_requests_memory_bytes{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""})'
                ' / on(bcs_cluster_id) group_right() '
                ' sum by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_memory_bytes{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""}) '
                ' - on(bcs_cluster_id) group_right() '
                ' (count by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_memory_bytes{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""}) - 1)'
                ' / on(bcs_cluster_id) group_right() '
                ' count by(bcs_cluster_id) '
                ' (kube_node_status_allocatable_memory_bytes{'
                'node=~"^(%(node_ips)s)$",bcs_cluster_id="%(bcs_cluster_id)s",node!=""})'
            ) % {"bcs_cluster_id": bcs_cluster_id, "node_ips": node_ips}
        else:
            try:
                bcs_cluster_ids = list(
                    BCSCluster.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                bcs_cluster_ids = []
            if not bcs_cluster_ids:
                return []
            # CPU节流次数
            cpu_throttling_high = (
                'sum'
                ' (increase(container_cpu_cfs_throttled_periods_total{'
                'namespace!="bkmonitor-operator",'
                'container!="tke-monitor-agent",'
                'bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"}[5m]))'
                ' / on(bcs_cluster_id, namespace, pod, container)'
                ' group_right()'
                ' sum'
                ' (increase(container_cpu_cfs_periods_total{'
                'namespace!="bkmonitor-operator",container!="tke-monitor-agent"}[5m])) * 100'
            ) % {"bcs_cluster_id": "|".join(bcs_cluster_ids)}
            # 内存触顶次数
            memory_oom_times = (
                'sum'
                '(increase(kube_pod_container_status_terminated_reason{'
                'namespace!="",pod_name!="",reason="OOMKilled",namespace!="bkmonitor-operator",'
                'container!="tke-monitor-agent",'
                'bcs_cluster_id=~"^(%(bcs_cluster_id)s)$"}[2m]))'
            ) % {"bcs_cluster_id": "|".join(bcs_cluster_ids)}

        if bcs_cluster_id:
            data_source_param_map = [
                {"key_name": "cpu_over_commit", "promql": cpu_over_commit_promql},
                {
                    "key_name": "memory_over_commit",
                    "promql": memory_over_commit_promql,
                },
            ]
        else:
            data_source_param_map = [
                {"key_name": "cpu_throttling_high", "promql": cpu_throttling_high},
                {
                    "key_name": "memory_oom_times",
                    "promql": memory_oom_times,
                },
            ]

        for data_source_params in data_source_param_map:
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                }
            )

        pool = ThreadPool()
        performance_data = pool.map(self.request_single_performance_data, args)
        pool.close()
        pool.join()
        return performance_data

    @classmethod
    def format_value(cls, title: str, value: float, bcs_cluster_id: str) -> Dict:
        if bcs_cluster_id:
            if value >= 0:
                color = "#6bd58f"
                value_label = _("不足")
            else:
                color = "#f8c554"
                value_label = _("充足")

            result = {
                "name": title,
                "value": value_label,
                "color": color,
            }
        else:
            result = {
                "name": title,
                "value": int(value),
            }
        return result

    @classmethod
    def to_graph(cls, params: Dict, data: Dict) -> List:
        bcs_cluster_id = params.get("bcs_cluster_id")

        if bcs_cluster_id:
            cpu_over_commit_value = data.get("cpu_over_commit", -1)
            memory_over_commit_value = data.get("memory_over_commit", -1)
            graph_data = [
                cls.format_value(_("CPU资源是否充足"), cpu_over_commit_value, bcs_cluster_id),
                cls.format_value(_("内存资源是否充足"), memory_over_commit_value, bcs_cluster_id),
            ]
        else:
            cpu_throttling_high_value = data.get("cpu_throttling_high", 0)
            memory_oom_times_value = data.get("memory_oom_times", 0)
            graph_data = [
                cls.format_value(_("CPU节流次数"), cpu_throttling_high_value, bcs_cluster_id),
                cls.format_value(_("内存触顶次数"), memory_oom_times_value, bcs_cluster_id),
            ]

        return graph_data

    def perform_request(self, params: Dict):
        bk_biz_id = int(params["bk_biz_id"])
        bcs_cluster_id = params.get("bcs_cluster_id")
        if bcs_cluster_id:
            is_shared_cluster = api.kubernetes.is_shared_cluster(bcs_cluster_id, bk_biz_id)
            if is_shared_cluster:
                return {}

        performance_data = self.request_performance_data(params)
        if not performance_data:
            return {}
        data = self.format_performance_data(performance_data)
        result = self.to_graph(params, data)
        return result


class GetKubernetesNodeUsageBase(GetKubernetesGrafanaMetricRecords):
    """获得节点各资源使用率."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")
        top_n = serializers.IntegerField(required=False, label="前几名", min_value=1, default=10)

    @staticmethod
    def format_performance_data(validated_request_data: Dict, performance_data):
        """格式化数据 ."""
        data = {}
        if not performance_data:
            return {}
        for key_name, records in performance_data:
            if key_name != "cpu":
                continue
            series = records.get("series", [])
            for series_item in series:
                dimensions = series_item.get("dimensions", [])
                datapoints = series_item.get("datapoints", [])
                if not datapoints:
                    continue
                instance = dimensions.get("instance")
                if not instance:
                    continue
                bk_target_ip = instance.rsplit(":")[0]
                value = datapoints[-1][0]
                data[bk_target_ip] = value

        return data

    @staticmethod
    def get_more_data_url(params):
        dashboard_id = "node"
        scene_type = "overview"
        bk_biz_id = int(params["bk_biz_id"])
        bcs_cluster_id = params["bcs_cluster_id"]
        url = f"?bizId={bk_biz_id}#/k8s?sceneId=kubernetes&dashboardId={dashboard_id}&sceneType={scene_type}"
        search = [{"bcs_cluster_id": bcs_cluster_id}]
        query_data = json.dumps({"selectorSearch": search})
        url = f"{url}&queryData={query_data}"
        return url

    def to_graph(self, validated_request_data: Dict, data: Dict) -> Dict:
        """转换为指定格式的图表数据 ."""
        top_n = int(validated_request_data["top_n"])
        more_data_url = self.get_more_data_url(validated_request_data)
        response = {
            "metrics": [],
            "name": self.GRAPH_NAME,
            "series": [],
            "data": [],
            "more_data_url": more_data_url,
        }
        graph_data = [
            {
                "total": 100,
                "unit": "%",
                "name": bk_target_ip,
                "value": None if value is None else round(value, 2),
            }
            for bk_target_ip, value in data.items()
        ]
        value = sorted(graph_data, key=lambda item: -item["value"] if item["value"] else 0)
        value = value[:top_n]
        response["data"] = value

        return response

    def build_graph_unify_query_iterable(self, validated_request_data: Dict) -> List:
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")

        args = []
        promql = self.build_promql(validated_request_data)

        data_source_param_map = [
            {"key_name": "cpu", "promql": promql},
        ]
        for data_source_params in data_source_param_map:
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                }
            )

        return args

    def build_promql(self, validated_request_data: Dict) -> str:
        ...

    def perform_request(self, validated_request_data: Dict) -> Dict:
        # 共享集群不返还信息
        if self.is_shared_cluster(validated_request_data):
            return {}

        # 查询使用率
        performance_data = self.request_performance_data(validated_request_data)
        if not performance_data:
            return {}

        result = super().perform_request(validated_request_data)
        return result


class GetKubernetesNodeCpuUsage(GetKubernetesNodeUsageBase):
    GRAPH_NAME = _("节点CPU使用率")

    def build_promql(self, validated_request_data: Dict) -> str:
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        promql = (
            '(1 - avg by(instance) '
            '(irate(node_cpu_seconds_total{mode="idle", '
            'bcs_cluster_id="%(bcs_cluster_id)s"}[5m]))) * 100'
        ) % {"bcs_cluster_id": bcs_cluster_id}

        return promql


class GetKubernetesNodeMemoryUsage(GetKubernetesNodeUsageBase):
    GRAPH_NAME = _("节点内存使用率")

    def build_promql(self, validated_request_data: Dict) -> str:
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        promql = (
            '(SUM by(bcs_cluster_id,instance)'
            ' (node_memory_MemTotal_bytes{bcs_cluster_id="%(bcs_cluster_id)s"})'
            ' - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)'
            ' (node_memory_MemFree_bytes{bcs_cluster_id="%(bcs_cluster_id)s"})'
            ' - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) '
            '(node_memory_Cached_bytes{bcs_cluster_id="%(bcs_cluster_id)s"})'
            ' - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) '
            '(node_memory_Buffers_bytes{bcs_cluster_id="%(bcs_cluster_id)s"})'
            ' + on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) '
            '(node_memory_Shmem_bytes{bcs_cluster_id="%(bcs_cluster_id)s"}))'
            ' / on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)'
            ' (node_memory_MemTotal_bytes{bcs_cluster_id="%(bcs_cluster_id)s"}) * 100'
        ) % {"bcs_cluster_id": bcs_cluster_id}

        return promql


class GetKubernetesNodeDiskSpaceUsage(GetKubernetesNodeUsageBase):
    GRAPH_NAME = _("硬盘空间使用率")

    def build_promql(self, validated_request_data: Dict) -> str:
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        promql = (
            '(sum by(bcs_cluster_id, instance)'
            ' (node_filesystem_size_bytes{bcs_cluster_id="%(bcs_cluster_id)s",fstype=~"ext[234]|btrfs|xfs|zfs"})'
            ' - on(bcs_cluster_id, instance) group_right()'
            ' sum by(bcs_cluster_id, instance)'
            ' (node_filesystem_free_bytes{bcs_cluster_id="%(bcs_cluster_id)s",fstype=~"ext[234]|btrfs|xfs|zfs"}))'
            ' / on(bcs_cluster_id, instance) group_right()'
            ' sum by(bcs_cluster_id, instance)'
            ' (node_filesystem_size_bytes{bcs_cluster_id="%(bcs_cluster_id)s",fstype=~"ext[234]|btrfs|xfs|zfs"})'
            ' * 100'
        ) % {"bcs_cluster_id": bcs_cluster_id}

        return promql


class GetKubernetesNodeDiskIoUsage(GetKubernetesNodeUsageBase):
    GRAPH_NAME = _("硬盘IO使用率")

    def build_promql(self, validated_request_data: Dict) -> str:
        bcs_cluster_id = validated_request_data["bcs_cluster_id"]
        promql = (
            'sum by(bcs_cluster_id, instance)'
            ' (rate(node_disk_io_time_seconds_total{bcs_cluster_id="%(bcs_cluster_id)s"}[2m])) * 100'
        ) % {"bcs_cluster_id": bcs_cluster_id}

        return promql


class GetKubernetesConsistencyCheck(Resource):
    """BCS资源同步校验 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        check_type = serializers.ChoiceField(required=True, choices=("workload", "pod", "node", "service", "endpoint"))
        data_type = serializers.ChoiceField(
            required=False, choices=("simple", "full"), default="simple", allow_blank=True
        )
        name = serializers.CharField(required=False, allow_null=True)

    def perform_request(self, params):
        bk_biz_id = params.get("bk_biz_id")
        bcs_cluster_id = params.get("bcs_cluster_id")
        check_type = params.get("check_type")
        data_type = params.get("data_type")
        name = params.get("name")

        data = {}
        params = {"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id, "data_type": data_type, "name": name}
        if check_type == "workload":
            data = api.kubernetes.fetch_kubernetes_workload_consistency_check(params)
        elif check_type == "pod":
            data = api.kubernetes.fetch_kubernetes_pod_consistency_check(params)
        elif check_type == "node":
            data = api.kubernetes.fetch_kubernetes_node_consistency_check(params)
        elif check_type == "service":
            data = api.kubernetes.fetch_kubernetes_service_consistency_check(params)
        elif check_type == "endpoint":
            data = api.kubernetes.fetch_kubernetes_endpoint_consistency_check(params)
        return data
