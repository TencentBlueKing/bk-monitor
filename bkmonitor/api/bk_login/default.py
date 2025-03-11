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
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource import APIResource


class UserManageAPIGWResource(APIResource):
    base_url = "%s/api/c/compapi/v2/usermanage/" % settings.BK_COMPONENT_API_URL
    module_name = "usermanage"

    @property
    def label(self):
        return self.__doc__


class GetUserResource(UserManageAPIGWResource):
    """
    获取用户信息
    """

    action = "/retrieve_user/"
    method = "GET"

    def full_request_data(self, validated_request_data):
        validated_request_data = super(GetUserResource, self).full_request_data(validated_request_data)
        validated_request_data.update({"id": validated_request_data["bk_username"]})
        return validated_request_data


class GetAllUserResource(UserManageAPIGWResource):
    """
    获取全部用户信息
    """

    action = "/list_users/"
    method = "GET"
    cache_type = CacheType.USER


class ListDepartmentsResource(UserManageAPIGWResource):
    """
    获取部门列表
    """

    action = "/list_departments/"
    method = "GET"
    cache_type = CacheType.USER

    class RequestSerializer(serializers.Serializer):
        lookup_field = serializers.CharField(label="查询字段")
        exact_lookups = serializers.CharField(label="精确查找")
        no_page = serializers.BooleanField(default=True, label="是否不分页")


class ListProfileDepartmentsResource(UserManageAPIGWResource):
    """
    获取用户的部门信息
    """

    action = "/list_profile_departments/"
    method = "GET"
    cache_type = CacheType.USER

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="用户 ID")
        with_family = serializers.BooleanField(label="是否返回部门树", default=True)


class UnityUserBaseResource(APIResource):
    base_url = settings.BK_USERINFO_API_BASE_URL
    module_name = "unity-user"


class GetUserSensitiveInfo(UnityUserBaseResource):
    """
    获取用户敏感信息
    """

    action = "/api/v1/open/odc-users/sensitive-info/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        usernames = serializers.CharField(required=True)
        fields = serializers.CharField(required=True)
