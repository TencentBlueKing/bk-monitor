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

from rest_framework import serializers


class ExternalPermissionSerializer(serializers.Serializer):
    authorized_user = serializers.CharField(required=False, label="被授权人")
    bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
    action_id = serializers.CharField(required=False, label="操作类型")
    resources = serializers.ListField(required=False, label="资源列表")
    status = serializers.CharField(required=False, label="状态")
    expire_time = serializers.DateTimeField(required=False, label="过期时间", allow_null=True)


class ExternalPermissionApplyRecordSerializer(serializers.Serializer):
    authorized_users = serializers.ListField(required=True, label="被授权人")
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    action_id = serializers.CharField(required=True, label="操作类型")
    resources = serializers.ListField(required=True, label="资源列表")
    status = serializers.CharField(required=True, label="状态")
    expire_time = serializers.DateTimeField(required=True, label="过期时间", allow_null=True)
    approval_url = serializers.URLField(required=False, label="审批地址", allow_null=True, allow_blank=True)
