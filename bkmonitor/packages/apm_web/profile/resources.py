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

from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apm_web.models import Application
from apm_web.profile.constants import DataType
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.utils import get_interval, split_by_interval
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource, api


class QueryServicesDetailResource(Resource):
    """查询Profile服务详情信息"""

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
            }
        )

        if not services:
            raise ValueError(f"Profile 服务: {validated_data['service_name']} 不存在，请确认数据是否上报或稍后再试")

        # 实时查询最近上报时间等信息
        data_type_info_mapping = QueryTemplate(validated_data["bk_biz_id"], validated_data["app_name"]).get_sample_info(
            validated_data["start_time"] * 1000,
            validated_data["end_time"] * 1000,
            data_types=[i["data_type"] for i in services],
            service_name=validated_data["service_name"],
        )
        last_report_time = sorted([i["last_report_time"] for i in data_type_info_mapping.values()], reverse=True)

        res = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "name": validated_data["service_name"],
            "create_time": self.time_to_str(sorted([self.str_to_time(i["created_at"]) for i in services])[0]),
            "last_check_time": self.time_to_str(
                sorted([self.str_to_time(i["last_check_time"]) for i in services], reverse=True)[0]
            ),
            "last_report_time": self.timestamp_to_time(last_report_time[0]) if last_report_time else None,
            "data_types": [{"key": i["data_type"], "name": DataType.get_name(i["data_type"])} for i in services],
        }

        if validated_data["view_mode"] == "default":
            return res

        return self.convert_to_sidebar(res)

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

    def perform_request(self, data):
        applications = Application.objects.filter(bk_biz_id=data["bk_biz_id"])

        apps = []
        nodata_apps = []

        for application in applications:
            services = api.apm_api.query_profile_services_detail(
                **{"bk_biz_id": application.bk_biz_id, "app_name": application.app_name}
            )
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

    def _query_by_timerange(self, datapoints, trace_data, query_template, query_params, filter_labels):
        point_count = query_template.get_count(
            **query_params,
            label_filter={"profile_id": "op_is_not_null", **filter_labels},
        )

        labels = query_template.parse_labels(
            **query_params,
            label_filter={"profile_id": "op_is_not_null", **filter_labels},
            limit=self.POINT_LABEL_LIMIT,
        )
        trace_data[int(query_params["start_time"])] = [
            {
                "time": datetime.datetime.fromtimestamp(i["time"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                "span_id": i.get("labels", {}).get("profile_id", "unknown"),
            }
            for i in labels
        ]
        datapoints.append([point_count, int(query_params["start_time"])])

    def perform_request(self, validate_data):
        interval = get_interval(validate_data["start_time"], validate_data["end_time"])
        datapoints = split_by_interval(validate_data["start_time"], validate_data["end_time"], interval)

        query_template = QueryTemplate(validate_data["bk_biz_id"], validate_data["app_name"])

        res = []
        trace_data = {}
        if not datapoints:
            # 时间查询范围过小的时候，用参数的范围
            datapoints = [[validate_data["start_time"], validate_data["end_time"]]]

        pool = ThreadPool()
        pool.map_ignore_exception(
            self._query_by_timerange,
            [
                (
                    res,
                    trace_data,
                    query_template,
                    {
                        "start_time": start_time * 1000,
                        "end_time": end_time * 1000,
                        "data_type": validate_data["data_type"],
                        "service_name": validate_data["service_name"],
                    },
                    validate_data["filter_labels"],
                )
                for start_time, end_time in datapoints
            ],
        )

        return {
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": res,
                    "dimensions": {},
                    "target": "",
                    "type": "line",
                    "unit": "",
                    "trace_data": trace_data,
                }
            ]
        }
