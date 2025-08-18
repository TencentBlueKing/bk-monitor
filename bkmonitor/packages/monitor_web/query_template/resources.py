"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource import Resource

from . import serializers
from .mock_data import (
    AvgDurationQueryTemplateDetail,
    AvgDurationQueryTemplateRelation,
    QueryTemplateList,
    QueryTemplateRelations,
    RPCCalleeQueryTemplateDetail,
    RPCCalleeQueryTemplatePreview,
    RPCCalleeQueryTemplateRelation,
)


class QueryTemplateDetailResource(Resource):
    RequestSerializer = serializers.QueryTemplateDetailRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            if validated_data["query_template_id"] == 1:
                return AvgDurationQueryTemplateDetail
            elif validated_data["query_template_id"] == 2:
                return RPCCalleeQueryTemplateDetail

        raise ValueError("query_template_id is invalid")


class QueryTemplateListResource(Resource):
    RequestSerializer = serializers.QueryTemplateListRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            return QueryTemplateList
        return []


class QueryTemplateCreateResource(Resource):
    RequestSerializer = serializers.QueryTemplateCreateRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            return AvgDurationQueryTemplateDetail
        return {}


class QueryTemplateUpdateResource(Resource):
    RequestSerializer = serializers.QueryTemplateUpdateRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            return AvgDurationQueryTemplateDetail
        return {}


class QueryTemplatePreviewResource(Resource):
    """根据查询模板和变量值预览查询配置和结果"""

    RequestSerializer = serializers.QueryTemplatePreviewRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            return RPCCalleeQueryTemplatePreview
        return {}


class QueryTemplateRelationsResource(Resource):
    """根据查询模板 id 列表查对应的关联资源数量"""

    RequestSerializer = serializers.QueryTemplateRelationsRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            return QueryTemplateRelations
        return []


class QueryTemplateRelationResource(Resource):
    """单个查询模板的关联资源列表"""

    RequestSerializer = serializers.QueryTemplateRelationRequestSerializer

    def perform_request(self, validated_data):
        if validated_data.get("is_mock"):
            if validated_data["query_template_id"] == 1:
                return AvgDurationQueryTemplateRelation
            elif validated_data["query_template_id"] == 2:
                return RPCCalleeQueryTemplateRelation
        return []
