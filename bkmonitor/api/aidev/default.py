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

from core.drf_resource import APIResource


class AidevAPIGWResource(APIResource):
    base_url = settings.AIDEV_API_BASE_URL
    # 模块名
    module_name = "aidev"


class CreateKnowledgebaseQueryResource(AidevAPIGWResource):
    """
    创建知识库查询
    """

    class RequestSerializer(serializers.Serializer):
        query = serializers.CharField(required=True, allow_blank=False)
        type = serializers.ChoiceField(required=True, allow_blank=False, choices=["nature", "index_specific"])
        knowledge_base_id = serializers.ListField(required=True, child=serializers.IntegerField())
        polish = serializers.BooleanField(required=False, default=True)
        stream = serializers.BooleanField(required=False, default=True)

    action = "/aidev/resource/knowledgebase/query/"
    method = "POST"
