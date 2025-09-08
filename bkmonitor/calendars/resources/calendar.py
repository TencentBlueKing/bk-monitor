# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id
from calendars.models import CalendarItemModel, CalendarModel
from core.drf_resource import Resource


class SaveCalendarResource(Resource):
    """
    添加日历
    """

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(label="日历名称", max_length=15)
        light_color = serializers.CharField(label="日历浅色底色", max_length=7, min_length=7)
        deep_color = serializers.CharField(label="日历深色底色", max_length=7, min_length=7)

    def perform_request(self, params: dict):
        if CalendarModel.objects.filter(name=params["name"]).count() > 0:
            raise ValueError(_("日历保存失败，日历名称({})已存在").format(params["name"]))
        calendar = CalendarModel.objects.create(
            name=params["name"],
            light_color=params["light_color"],
            deep_color=params["deep_color"],
            classify="custom",
            bk_tenant_id=get_request_tenant_id(),
        )
        return {"id": calendar.id}


class EditCalendarResource(Resource):
    """
    编辑日历
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="日历ID")
        name = serializers.CharField(required=False, label="日历名称", max_length=15)
        light_color = serializers.CharField(required=False, label="日历浅色底色", max_length=7, min_length=7)
        deep_color = serializers.CharField(required=False, label="日历深色底色", max_length=7, min_length=7)

    def perform_request(self, params: dict):
        calendar = CalendarModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=params["id"])
        name = params.get("name")
        if name:
            if calendar.name != name and CalendarModel.objects.filter(name=name).count() > 0:
                raise ValueError(_("日历编辑失败，日历名称({})已存在").format(name))
            else:
                calendar.name = name
        if params.get("light_color"):
            calendar.light_color = params["light_color"]
        if params.get("deep_color"):
            calendar.deep_color = params["deep_color"]
        calendar.save()

        return calendar.to_json()


class GetCalendarResource(Resource):
    """
    获取单个日历
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False, label="日历ID")
        name = serializers.CharField(required=False, label="日历名称", max_length=15)

    def perform_request(self, params: dict):
        calendar_id = params.get("id")
        calendar_name = params.get("name")
        validated_data = {"bk_tenant_id": get_request_tenant_id()}
        if calendar_name:
            validated_data["name"] = calendar_name
        if calendar_id:
            validated_data["id"] = calendar_id
        if not validated_data:
            raise ValueError(_("ID和name传入的参数为空，着两个参数必须传入一个"))
        calendar = CalendarModel.objects.get(**validated_data)
        return calendar.to_json()


class ListCalendarResource(Resource):
    """
    批量获取日历信息
    """

    class RequestSerializer(serializers.Serializer):
        page = serializers.IntegerField(required=False, default=1, label="当前页")
        order = serializers.ChoiceField(
            required=False,
            default="-update_time",
            label="排序字段",
            choices=["-id", "id", "create_time", "-create_time", "update_time", "-update_time"],
        )
        page_size = serializers.IntegerField(required=False, default=10, max_value=1000, label="每页大小", min_value=1)

    def perform_request(self, params: dict):
        page = params["page"]
        order = params["order"]
        page_size = params["page_size"]

        all_calendars = CalendarModel.objects.filter(bk_tenant_id=get_request_tenant_id()).order_by(order)
        count = all_calendars.count()
        all_calendars = all_calendars[(page - 1) * page_size : page * page_size]
        calendar_list = []
        for calendar in all_calendars:
            calendar_list.append(calendar.to_json())
        return {"count": count, "data": calendar_list}


class DeleteCalendarResource(Resource):
    """
    删除日历
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="日历ID")

    def perform_request(self, params: dict):
        calendar = CalendarModel.objects.get(bk_tenant_id=get_request_tenant_id(), id=params["id"])

        # 删除日历之前需要先删除该日历下的所有日历事项
        CalendarItemModel.objects.filter(calendar_id=calendar.id, bk_tenant_id=get_request_tenant_id()).delete()
        calendar.delete()
