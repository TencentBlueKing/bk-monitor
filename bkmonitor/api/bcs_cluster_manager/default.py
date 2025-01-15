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
import logging
from urllib.parse import urljoin

from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.bcs import BcsApiGatewayBaseResource

logger = logging.getLogger(__name__)


class BcsClusterManagerBaseResource(BcsApiGatewayBaseResource):
    """bcs-cluster-manager请求基类 ."""

    base_url = urljoin(
        f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
        "/bcsapi/v4/clustermanager/v1",
    )
    module_name = "bcs-cluster-manager"

    # BCS目前是非蓝鲸标准的返回格式，所以需要兼容
    IS_STANDARD_FORMAT = False

    def get_request_url(self, validated_request_data):
        return (
            super(BcsClusterManagerBaseResource, self)
            .get_request_url(validated_request_data)
            .format(**validated_request_data)
        )

    def render_response_data(self, validated_request_data, response_data):
        return response_data.get("data", [])


class FetchClustersResource(BcsClusterManagerBaseResource):
    """从bcs-cluster-manager获取集群列表 ."""

    action = "cluster"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(required=False, label="集群ID")
        businessID = serializers.CharField(required=False, label="集群类型")
        engineType = serializers.CharField(required=False, label="集群类型", default="k8s")

    @classmethod
    def get_cluster_id_mapping_biz_id(cls):
        cluster_id_mapping_biz_id = {}

        # 是否只同步指定业务的集群列表
        # DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID 格式: cluster_id_1:biz_id1,cluster_id_2:biz_id2
        if settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID:
            items = settings.DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID.split(",")
            for item in items:
                mapping = item.split(":")
                if len(mapping) == 2:
                    cluster_id_mapping_biz_id[mapping[0]] = mapping[1]
        return cluster_id_mapping_biz_id

    def perform_request(self, params):
        clusters = super(FetchClustersResource, self).perform_request(params)
        cluster_id_mapping_biz_id = self.get_cluster_id_mapping_biz_id()
        for cluster in clusters:
            # 标记需要同步的业务集群列表
            business_id = cluster_id_mapping_biz_id.get(cluster["clusterID"], cluster["businessID"])
            cluster["businessID"] = business_id

        return clusters


class GetProjectClustersResource(BcsClusterManagerBaseResource):
    """获取项目下的集群信息, 返回必要数据"""

    action = "cluster"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        project_id = serializers.CharField(required=False, label="项目 ID", default="")
        exclude_shared_cluster = serializers.BooleanField(required=False, label="是否过滤掉共享集群", default=False)

    def perform_request(self, validated_request_data):
        clusters = super(GetProjectClustersResource, self).perform_request(
            {"projectID": validated_request_data["project_id"]}
        )
        # 过滤掉共享集群
        if validated_request_data["exclude_shared_cluster"]:
            return [
                {
                    "project_id": c["projectID"],
                    "cluster_id": c["clusterID"],
                    "bk_biz_id": c["businessID"],
                    "cluster_type": c["clusterType"],
                }
                for c in clusters or []
                if not c.get("is_shared")
            ]
        # 返回所有集群
        return [
            {
                "project_id": c["projectID"],
                "cluster_id": c["clusterID"],
                "bk_biz_id": c["businessID"],
                "is_shared": c.get("is_shared", False),
                "cluster_type": c["clusterType"],
            }
            for c in clusters or []
        ]


class GetProjectK8sNonSharedClustersResource(BcsClusterManagerBaseResource):
    """获取项目下的非共享的K8S集群信息, 返回必要数据"""

    action = "cluster"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        project_id = serializers.CharField(required=False, label="项目 ID", default="")

    def perform_request(self, validated_request_data):
        clusters = super(GetProjectK8sNonSharedClustersResource, self).perform_request(
            {"projectID": validated_request_data["project_id"]}
        )
        # 过滤掉共享集群
        return [
            {
                "project_id": c["projectID"],
                "cluster_id": c["clusterID"],
                "bk_biz_id": c["businessID"],
            }
            for c in clusters or []
            if not c.get("is_shared") and c.get("engineType") == "k8s"
        ]


class GetSharedClustersResource(BcsClusterManagerBaseResource):
    """获取共享集群"""

    action = "sharedclusters"
    method = "GET"

    def render_response_data(self, validated_request_data, response_data):
        return [
            {"project_id": c["projectID"], "cluster_id": c["clusterID"], "bk_biz_id": c["businessID"]}
            for c in response_data or []
        ]
