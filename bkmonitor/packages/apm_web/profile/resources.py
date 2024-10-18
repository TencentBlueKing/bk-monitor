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
import datetime
import logging
from collections import defaultdict

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apm_web.models import Application
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.utils import get_interval, split_by_interval
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource, api

logger = logging.getLogger("apm")


class QueryServicesDetailResource(Resource):
    """查询Profile服务详情信息"""

    COUNT_ALLOW_SAMPLE_TYPES = ["goroutine/count", "syscall/count", "allocations/count", "exception-samples/count"]

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
        view_mode = serializers.ChoiceField(label="数据模式", default="default", choices=view_mode_choices, required=False)

    def perform_request(self, validated_data):
        app = Application.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(validated_data['app_name']))

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
            "create_time": self.time_to_str(sorted([self.str_to_time(i["created_at"]) for i in services])[0]),
            "last_check_time": self.time_to_str(
                sorted([self.str_to_time(i["last_check_time"]) for i in services], reverse=True)[0]
            ),
            "last_report_time": self.timestamp_to_time(last_report_time) if last_report_time else None,
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
        goroutine/syscall/allocations/exception-samples
        """
        res = []
        for svr in services:
            if not svr["sample_type"]:
                continue

            sample_type_parts = svr["sample_type"].split("/")
            key = svr["sample_type"]
            name = sample_type_parts[0].upper()

            if sample_type_parts[-1] == "count" and key not in cls.COUNT_ALLOW_SAMPLE_TYPES:
                continue

            res.append({"key": key, "name": name, "is_large": svr.get("is_large", False)})

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
        text_mapping = {
            "name": _("服务名称"),
            "create_time": _("创建时间"),
            "last_report_time": _("最近上报时间"),
        }
        res = []

        for k, v in data.items():
            if k not in text_mapping:
                continue

            res.append({"name": text_mapping[k], "type": "string", "value": v})

        return res


class ListApplicationServicesResource(Resource):
    """查询所有应用/服务信息列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()

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
            label_filter={"profile_id": "op_is_not_null", **filter_labels},
            limit=self.POINT_LABEL_LIMIT,
        )
        if labels:
            trace_data[timestamp] = [
                {
                    "time": datetime.datetime.fromtimestamp(i["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    "span_id": i.get("labels", {}).get("profile_id", "unknown"),
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
            label_filter={"profile_id": "op_is_not_null", **validate_data["filter_labels"]},
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
