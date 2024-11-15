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

from core.drf_resource import Resource


class ListResources(Resource):
    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)
        resource_type = serializers.ChoiceField(
            choices=['pod', 'node', 'workload', 'namespace', 'container'], label='资源类型'
        )
        query_string = serializers.CharField(required=False, default='', allow_blank=True, label='名字过滤')
        start_time = serializers.IntegerField(required=True, label='开始时间')
        end_time = serializers.IntegerField(required=True, label='结束时间')

    def perform_request(self, validated_request_data):
        pass
