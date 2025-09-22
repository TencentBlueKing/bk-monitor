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
from rest_framework import serializers

from bkmonitor.utils.user import get_global_user
from core.drf_resource import Resource, api


class GetUserDepartmentsResource(Resource):
    def perform_request(self, validated_request_data):
        validated_request_data.update({"id": get_global_user()})
        user_info = api.bk_login.list_profile_departments(validated_request_data)
        department_list = []
        if user_info:
            department_list = user_info[0].get("family", [])
        return department_list


class ListDepartmentsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        type = serializers.ChoiceField(required=False, label="组织架构类型", default="bg", choices=("bg", "dept", "center"))
        id = serializers.IntegerField(required=False, label="组织架构id", default=0)

    def perform_request(self, validated_request_data):
        if validated_request_data["type"] == "bg":
            query_params = {"lookup_field": "level", "exact_lookups": 1}
        else:
            query_params = {"lookup_field": "parent", "exact_lookups": validated_request_data["id"]}
        return api.bk_login.list_departments(**query_params)
