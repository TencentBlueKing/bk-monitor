"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import OrderedDict
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource
from metadata.models.storage import ClusterInfo
from metadata.service.storage_details import StorageClusterDetail


class ListClusters(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_type = serializers.CharField(label="集群类型", required=False, default="all")
        page_size = serializers.IntegerField(default=10, label="每页的条数")
        page = serializers.IntegerField(default=1, min_value=1, label="页数")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        cluster_type = validated_request_data["cluster_type"]
        objs = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type__in=[ClusterInfo.TYPE_ES, ClusterInfo.TYPE_INFLUXDB, ClusterInfo.TYPE_KAFKA],
        )
        if cluster_type != "all":
            objs = objs.filter(cluster_type=cluster_type)

        objs = objs.order_by("-last_modify_time")
        page, page_size = validated_request_data["page"], validated_request_data["page_size"]
        start, end = (page - 1) * page_size, page * page_size
        # 分页数据
        data = objs[start:end]
        ret_data = []
        for obj in data:
            item = obj.to_dict()
            item["pipeline_name"] = ""
            ret_data.append(item)

        return {"total": objs.count(), "data": ret_data}


class GetStorageClusterDetail(Resource):
    """获取存储集群的详情"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.CharField(label="集群 id", required=True)
        page_size = serializers.IntegerField(default=10, label="每页的条数")
        page = serializers.IntegerField(default=1, min_value=1, label="页数")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        return StorageClusterDetail.get_detail(
            bk_tenant_id=bk_tenant_id, cluster_id=validated_request_data["cluster_id"]
        )


class RegisterCluster(Resource):
    """注册集群资源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_name = serializers.CharField(label="集群名称")
        cluster_type = serializers.CharField(label="集群类型")
        domain = serializers.CharField(label="集群域名")
        port = serializers.IntegerField(label="集群端口")
        registered_system = serializers.CharField(label="注册来源系统")
        operator = serializers.CharField(label="创建者")
        description = serializers.CharField(label="描述", required=False, default="", allow_blank=True)
        username = serializers.CharField(label="访问集群的用户名", required=False, default="", allow_blank=True)
        password = serializers.CharField(label="访问集群的密码", required=False, default="", allow_blank=True)
        version = serializers.CharField(label="集群版本", required=False, default="", allow_blank=True)
        schema = serializers.CharField(label="访问协议", required=False, default="", allow_blank=True)
        is_ssl_verify = serializers.BooleanField(label="是否 ssl 验证", required=False, default=False)
        label = serializers.CharField(label="标签", required=False, default="", allow_blank=True)
        default_settings = serializers.JSONField(required=False, label="默认集群配置", default={})

    def perform_request(self, validated_request_data: OrderedDict):
        validated_request_data["domain_name"] = validated_request_data.pop("domain")
        cluster = ClusterInfo.create_cluster(**validated_request_data)
        return cluster.cluster_detail


class UpdateRegisteredCluster(Resource):
    """更新注册的集群资源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(label="集群 ID")
        operator = serializers.CharField(label="创建者")
        description = serializers.CharField(label="描述", required=False, default="", allow_blank=True)
        username = serializers.CharField(label="访问集群的用户名", required=False, default="", allow_blank=True)
        password = serializers.CharField(label="访问集群的密码", required=False, default="", allow_blank=True)
        version = serializers.CharField(label="集群版本", required=False, default="", allow_blank=True)
        schema = serializers.CharField(label="访问协议", required=False, default="", allow_blank=True)
        is_ssl_verify = serializers.BooleanField(label="是否 ssl 验证", required=False, default=False)
        label = serializers.CharField(label="标签", default="", required=False, allow_blank=True)
        default_settings = serializers.JSONField(required=False, label="默认集群配置", default={})

    def perform_request(self, validated_request_data: OrderedDict):
        cluster_id = validated_request_data.pop("cluster_id")
        bk_tenant_id = validated_request_data.pop("bk_tenant_id")
        try:
            cluster = ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=cluster_id)
        except ClusterInfo.DoesNotExist:
            raise ValidationError("cluster_id: %s not found", cluster_id)

        return cluster.modify(**validated_request_data)
