"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from . import mock_data, serializers


class QueryTemplateViewSet(GenericViewSet):
    def get_serializer_class(self):
        action_serializer_map = {
            "retrieve": serializers.QueryTemplateDetailRequestSerializer,
            "list": serializers.QueryTemplateListRequestSerializer,
            "create": serializers.QueryTemplateCreateRequestSerializer,
            "update": serializers.QueryTemplateUpdateRequestSerializer,
            "preview": serializers.QueryTemplatePreviewRequestSerializer,
            "relation": serializers.QueryTemplateRelationRequestSerializer,
            "relations": serializers.QueryTemplateRelationsRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        query_template_id = int(kwargs[self.lookup_field])
        if validated_data.get("is_mock"):
            if query_template_id == 1:
                response_data = mock_data.AvgDurationQueryTemplateDetail
            elif query_template_id == 2:
                response_data = mock_data.RPCCalleeQueryTemplateDetail
        return Response(response_data)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.QueryTemplateList
        return Response(response_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.RPCCalleeQueryTemplateDetail
        return Response(response_data)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.RPCCalleeQueryTemplateDetail
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def preview(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.RPCCalleeQueryTemplatePreview
        return Response(response_data)

    @action(methods=["POST"], detail=True)
    def relation(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.RPCCalleeQueryTemplateRelation
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def relations(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.QueryTemplateRelations
        return Response(response_data)
