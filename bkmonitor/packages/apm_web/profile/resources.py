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
        services = api.apm_api.query_profile_services_detail(
            **{
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "service_name": validated_data["service_name"],
            }
        )

        if not services:
            raise ValueError(f"服务: {validated_data['service_name']} 不存在")

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
                        "services": [{"id": i["id"], "name": i["name"], "has_data": True} for i in services],
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
