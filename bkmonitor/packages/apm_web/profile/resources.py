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
import time

from rest_framework import serializers

from apm_web.models import Application
from apm_web.profile.doris.querier import QueryTemplate
from core.drf_resource import Resource, api


class QueryServicesDetailResource(Resource):
    """查询Profile服务详情信息"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        data_type = serializers.CharField(required=True, label="数据类型")

    def perform_request(self, validated_data):
        services = api.apm_api.query_profile_services_detail(
            **{
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "service_name": validated_data["service_name"],
                "data_type": validated_data["data_type"],
            }
        )

        if not services:
            raise ValueError(f"服务: {validated_data['service_name']} 不存在")

        # 实时查询最近上报时间等信息
        info = QueryTemplate(validated_data["bk_biz_id"], validated_data["app_name"]).get_sample_info(
            validated_data["start_time"], validated_data["end_time"], validated_data["data_type"]
        )
        return {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
            "period": ",".join([i["period"] for i in services if i.get("period")]),
            "period_type": ",".join([i["period_type"] for i in services if i.get("period_type")]),
            "frequency": ",".join([f"{i['frequency']}Hz" for i in services if i.get("frequency")]),
            "create_time": services[0].get("created_at"),
            "last_check_time": services[0].get("last_check_time"),
            "last_report_time": self.format_time(info["last_report_time"]) if info else None,
        }

    @classmethod
    def format_time(cls, value):
        return datetime.datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %H:%M:%S")


class ListApplicationServicesResource(Resource):
    """查询所有应用/服务信息列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    def perform_request(self, validated_data):
        applications = Application.objects.filter(bk_biz_id=validated_data["bk_biz_id"])

        apps = []
        nodata_apps = []

        for application in applications:
            services = api.apm_api.query_profile_services_detail(
                **{"bk_biz_id": application.bk_biz_id, "app_name": application.app_name}
            )
            app_has_data = False
            app_services = []

            for svr in services:
                # 如果上次检查时间在start-end范围内 说明此范围此服务有数据
                check_timestamp = int(time.mktime(time.strptime(svr["last_check_time"], "%Y-%m-%d %H:%M:%S")))
                if validated_data["start_time"] <= check_timestamp <= validated_data["end_time"]:
                    app_has_data = True
                    app_services.append(
                        {
                            "id": svr["id"],
                            "name": svr["name"],
                            "has_data": True,
                        }
                    )
                else:
                    app_services.append(
                        {
                            "id": svr["id"],
                            "name": svr["name"],
                            "has_data": False,
                        }
                    )
            [nodata_apps, apps][app_has_data].append(
                {
                    "bk_biz_id": application.bk_biz_id,
                    "application_id": application.application_id,
                    "description": application.description,
                    "app_name": application.app_name,
                    "app_alias": application.app_alias,
                    "services": app_services,
                }
            )

        return {
            "normal": apps,
            "no_data": nodata_apps,
        }
