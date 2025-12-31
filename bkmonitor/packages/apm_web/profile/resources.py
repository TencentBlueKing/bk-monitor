"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import itertools
import json
import logging
from collections import defaultdict

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apm_web.models import Application
from apm_web.profile.constants import GRAFANA_LABEL_MAX_SIZE
from apm_web.profile.doris.querier import APIType, QueryTemplate
from apm_web.profile.serializers import ProfileQuerySerializer, QueryBaseSerializer
from apm_web.utils import get_interval, split_by_interval
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource, api

logger = logging.getLogger("apm")


class QueryServicesDetailResource(Resource):
    """查询Profile服务详情信息"""

    COUNT_ALLOW_SAMPLE_TYPES = [
        "goroutine/count",
        "syscall/count",
        "allocations/count",
        "exception-samples/count",
        "alloc_objects/count",
        "inuse_objects/count",
    ]

    class RequestSerializer(serializers.Serializer):
        view_mode_choices = (
            ("default", "默认返回"),
            ("sidebar", "按照侧边栏格式返回"),
        )

        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        view_mode = serializers.ChoiceField(
            label="数据模式", default="default", choices=view_mode_choices, required=False
        )

    def perform_request(self, validated_data):
        app = Application.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(validated_data["app_name"]))

        if not app.is_enabled_profiling:
            raise ValueError(_(f"应用：{app.app_name} 未开启 Profile 功能，需先前往应用配置中开启"))

        services = api.apm_api.query_profile_services_detail(
            **{
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "service_name": validated_data["service_name"],
                "order": "-last_check_time",
            }
        )
        if not services:
            raise ValueError(f"Profile 服务: {validated_data['service_name']} 不存在，请确认数据是否上报或稍后再试")

        # 实时查询最近上报时间等信息
        last_report_time = QueryTemplate(validated_data["bk_biz_id"], validated_data["app_name"]).get_sample_info(
            validated_data["start_time"] * 1000,
            validated_data["end_time"] * 1000,
            sample_type=next((i["sample_type"] for i in services if i["sample_type"]), None),
            service_name=validated_data["service_name"],
        )

        res = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "name": validated_data["service_name"],
            "create_time": int(sorted([self.str_to_time(i["created_at"]) for i in services])[0].timestamp()),
            "last_check_time": self.time_to_str(
                sorted([self.str_to_time(i["last_check_time"]) for i in services], reverse=True)[0]
            ),
            "last_report_time": int(last_report_time) // 1000 if last_report_time else None,
            "data_types": self.to_data_types(services),
        }

        if validated_data["view_mode"] == "default":
            return res

        return self.convert_to_sidebar(res)

    @classmethod
    def to_data_types(cls, services):
        """
        将 service 转换为数据类型
        对于 count 类型 只允许以下:
        goroutine/syscall/allocations/exception-samples/alloc_objects/inuse_objects
        """
        res = []
        for svr in services:
            if not svr["sample_type"]:
                continue

            sample_type_parts = svr["sample_type"].split("/")
            key = svr["sample_type"]
            name = sample_type_parts[0].upper()
            default_agg_method = settings.APM_PROFILING_AGG_METHOD_MAPPING.get(name, "SUM")

            if sample_type_parts[-1] == "count" and key not in cls.COUNT_ALLOW_SAMPLE_TYPES:
                continue

            res.append(
                {
                    "key": key,
                    "name": name,
                    "is_large": svr.get("is_large", False),
                    "default_agg_method": default_agg_method,
                }
            )

        return res

    @classmethod
    def str_to_time(cls, time_str):
        return datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

    @classmethod
    def time_to_str(cls, t):
        return t.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def timestamp_to_time(cls, value):
        if not value:
            return None

        return datetime.datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def convert_to_sidebar(cls, data):
        """将返回转换为侧边栏的格式 用于图表配置右侧信息处展示"""
        field_mapping = {
            "name": {"text": _("服务名称"), "type": "string"},
            "create_time": {"text": _("创建时间"), "type": "time"},
            "last_report_time": {"text": _("最近上报时间"), "type": "time"},
        }

        return [
            {"name": field_mapping[k]["text"], "type": field_mapping[k]["type"], "value": v}
            for k, v in data.items()
            if k in field_mapping
        ]


class ListApplicationServicesResource(Resource):
    """查询所有应用/服务信息列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        is_get_ebpf = serializers.BooleanField(required=False, default=False)

    @classmethod
    def batch_query_profile_services_detail(cls, validated_data):
        """
        batch query profile services detail
        """
        service_map = defaultdict(dict)
        bk_biz_id = validated_data["bk_biz_id"]
        services = api.apm_api.query_profile_services_detail(**{"bk_biz_id": bk_biz_id})

        for obj in services:
            service_map.setdefault((obj["bk_biz_id"], obj["app_name"]), list()).append(obj)

        return service_map

    def perform_request(self, data):
        applications = Application.objects.filter(bk_biz_id=data["bk_biz_id"])

        apps = []
        nodata_apps = []

        service_map = self.batch_query_profile_services_detail(data)
        for application in applications:
            services = service_map.get((application.bk_biz_id, application.app_name), [])
            # 如果曾经发现过 service，都认为是有数据应用
            if len(services) > 0:
                apps.append(
                    {
                        "bk_biz_id": application.bk_biz_id,
                        "application_id": application.application_id,
                        "description": application.description,
                        "app_name": application.app_name,
                        "app_alias": application.app_alias,
                        "services": list({i["name"]: i for i in services}.values()),
                    }
                )
            else:
                nodata_apps.append(
                    {
                        "bk_biz_id": application.bk_biz_id,
                        "application_id": application.application_id,
                        "description": application.description,
                        "app_name": application.app_name,
                        "app_alias": application.app_alias,
                        "services": [],
                    }
                )
        if data.get("is_get_ebpf", False):
            deepflow_data = api.apm_api.query_ebpf_service_list(bk_biz_id=data["bk_biz_id"])
            # 查询 deepflow 集群和 service 装载入结果
            # 其他 ebpf 数据源数据 可横向拓展
            apps.extend(deepflow_data)
        return {
            "normal": apps,
            "no_data": nodata_apps,
        }


class QueryProfileBarGraphResource(Resource):
    """获取 profile 数据柱状图"""

    # 每个时间点获取 spanId 数量为前 10 条
    POINT_LABEL_LIMIT = 10

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称")
        data_type = serializers.CharField(label="Sample 数据类型")
        start_time = serializers.IntegerField(label="开始时间", help_text="请使用 Second")
        end_time = serializers.IntegerField(label="结束时间", help_text="请使用 Second")
        filter_labels = serializers.DictField(label="标签过滤", default={}, required=False)

    def _query_profile_id_by_timerange(self, timestamp, trace_data, query_template, query_params, filter_labels):
        start_time, end_time = self.timestamp_to_interval(timestamp)
        query_params.update({"start_time": start_time, "end_time": end_time})

        labels = query_template.parse_labels(
            **query_params,
            label_filter={"span_id": "op_is_not_null", **filter_labels},
            limit=self.POINT_LABEL_LIMIT,
        )
        if labels:
            trace_data[timestamp] = [
                {
                    "time": datetime.datetime.fromtimestamp(i["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    "span_id": i.get("labels", {}).get("span_id", "unknown"),
                }
                for i in labels
            ]

    def perform_request(self, validate_data):
        interval = get_interval(validate_data["start_time"], validate_data["end_time"])
        _, start_time, end_time = split_by_interval(
            validate_data["start_time"],
            validate_data["end_time"],
            interval,
        )
        query_template = QueryTemplate(validate_data["bk_biz_id"], validate_data["app_name"])

        count_points = query_template.get_count(
            start_time=start_time * 1000,
            end_time=end_time * 1000,
            sample_type=validate_data["data_type"],
            service_name=validate_data["service_name"],
            label_filter={"span_id": "op_is_not_null", **validate_data["filter_labels"]},
        )

        trace_data = {}

        pool = ThreadPool()
        pool.map_ignore_exception(
            self._query_profile_id_by_timerange,
            [
                (
                    i[-1],
                    trace_data,
                    query_template,
                    {
                        "sample_type": validate_data["data_type"],
                        "service_name": validate_data["service_name"],
                    },
                    validate_data["filter_labels"],
                )
                for i in count_points
            ],
        )

        return {
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": [i for i in count_points if i[-1] in trace_data],
                    "dimensions": {},
                    "target": "",
                    "type": "line",
                    "unit": "",
                    "trace_data": trace_data,
                }
            ]
            if trace_data
            else []
        }

    @classmethod
    def timestamp_to_interval(cls, timestamp):
        # 为了减少查询次数 根据上一步的查询来确定接下来查询的时间范围

        base_datetime = datetime.datetime.fromtimestamp(timestamp / 1000.0)

        start_datetime = base_datetime
        end_datetime = base_datetime + datetime.timedelta(minutes=1)

        start_timestamp = int(start_datetime.timestamp() * 1000)
        end_timestamp = int(end_datetime.timestamp() * 1000)

        return start_timestamp, end_timestamp


class GrafanaQueryProfileResource(Resource):
    """Grafana 查询 Profile 数据"""

    class RequestSerializer(ProfileQuerySerializer):
        def validate(self, attrs):
            # 使用 grafana 转换器
            attrs["diagram_types"] = ["grafana_flame"]
            return attrs

    def perform_request(self, data):
        from apm_web.profile.views import ProfileQueryViewSet

        validate_data, essentials, extra_params = ProfileQueryViewSet.get_query_params(data)
        tree_converter = ProfileQueryViewSet.converter_query(essentials, validate_data, extra_params)
        res = ProfileQueryViewSet.converter_to_data(validate_data, tree_converter)
        # 返回符合 grafana flame graph 的格式
        return res.get("frame_data", {})


class GrafanaQueryProfileLabelResource(Resource):
    """Grafana 查询 label"""

    RequestSerializer = QueryBaseSerializer

    def perform_request(self, validated_request_data):
        return {"label_keys": self.get_labels_keys(validated_request_data)}

    @classmethod
    def get_labels_keys(cls, validated_data: dict = None):
        from apm_web.profile.views import ProfileQueryViewSet

        instance = ProfileQueryViewSet()

        essentials = instance.get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = instance.enlarge_duration(
            validated_data["start"], validated_data["end"], offset=validated_data.get("offset", 0)
        )

        results = instance.query(
            api_type=APIType.LABELS,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            result_table_id=result_table_id,
            start=start,
            end=end,
            extra_params={"limit": {"rows": GRAFANA_LABEL_MAX_SIZE}},
        )

        label_keys = set(
            itertools.chain(*[list(json.loads(i["labels"]).keys()) for i in results.get("list", []) if i.get("labels")])
        )
        return label_keys


class GrafanaQueryProfileLabelValuesResource(Resource):
    """Grafana 查询 label.value"""

    class RequestSerializer(QueryBaseSerializer):
        label_key = serializers.CharField(label="label名")
        offset = serializers.IntegerField(label="label_values查询起点")
        rows = serializers.IntegerField(label="label_values查询条数")

    def perform_request(self, validated_request_data):
        """获取 profiling 数据的 label_values 列表"""

        results = self.get_label_values(validated_request_data)
        return {"label_values": [i["label_value"] for i in results.get("list", {}) if i.get("label_value")]}

    @classmethod
    def get_label_values(cls, validated_data: dict = None):
        from apm_web.profile.views import ProfileQueryViewSet

        instance = ProfileQueryViewSet()

        offset, rows = validated_data["offset"], validated_data["rows"]
        essentials = instance.get_essentials(validated_data)
        bk_biz_id = essentials["bk_biz_id"]
        app_name = essentials["app_name"]
        service_name = essentials["service_name"]
        result_table_id = essentials["result_table_id"]

        start, end = instance.enlarge_duration(validated_data["start"], validated_data["end"], offset=offset)
        results = instance.query(
            api_type=APIType.LABEL_VALUES,
            app_name=app_name,
            bk_biz_id=bk_biz_id,
            service_name=service_name,
            extra_params={
                "label_key": validated_data["label_key"],
                "limit": {"offset": offset, "rows": rows},
            },
            result_table_id=result_table_id,
            start=start,
            end=end,
        )
        return results
