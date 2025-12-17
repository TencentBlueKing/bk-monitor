"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import logging
import re
from collections import OrderedDict
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_app_code_by_request, get_request
from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource
from metadata import models
from metadata.models.storage import ClusterInfo
from metadata.service.storage_details import StorageClusterDetail

logger = logging.getLogger(__name__)


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
        cluster_name = serializers.RegexField(label="集群名称", regex=models.ClusterInfo.CLUSTER_NAME_REGEX, default="")
        cluster_type = serializers.CharField(label="集群类型")
        display_name = serializers.CharField(label="集群显示名称", required=False)
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


class CreateClusterInfoResource(Resource):
    """创建存储集群资源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_name = serializers.RegexField(
            label="集群名", regex=models.ClusterInfo.CLUSTER_NAME_REGEX, default=""
        )
        display_name = serializers.CharField(required=False, max_length=128, label="集群显示名称")
        cluster_type = serializers.CharField(required=True, label="集群类型")
        domain_name = serializers.CharField(required=True, label="集群域名")
        port = serializers.IntegerField(required=True, label="集群端口")
        description = serializers.CharField(required=False, label="集群描述数据", default="", allow_blank=True)
        auth_info = serializers.JSONField(required=False, label="身份认证信息", default={})
        version = serializers.CharField(required=False, label="版本信息", default="")
        custom_option = serializers.CharField(required=False, label="自定义标签", default="")
        schema = serializers.CharField(required=False, label="链接协议", default="")
        is_ssl_verify = serializers.BooleanField(required=False, label="是否需要SSL验证", default=False)
        ssl_verification_mode = serializers.CharField(required=False, label="校验模式", default="")
        ssl_certificate_authorities = serializers.CharField(required=False, label="CA 证书内容", default="")
        ssl_certificate = serializers.CharField(required=False, label="SSL/TLS 证书内容", default="")
        ssl_certificate_key = serializers.CharField(required=False, label="SSL/TLS 私钥内容", default="")
        ssl_insecure_skip_verify = serializers.BooleanField(required=False, label="是否跳过服务端校验", default=False)
        extranet_domain_name = serializers.CharField(required=False, label="外网集群域名", default="")
        extranet_port = serializers.IntegerField(required=False, label="外网集群端口", default=0)
        operator = serializers.CharField(required=True, label="操作者")

        def validate(self, attrs: dict[str, Any]):
            # 如果未提供显示名称，则使用集群名作为显示名称
            if not attrs.get("display_name"):
                attrs["display_name"] = attrs["cluster_name"]
            return super().validate(attrs)

    def perform_request(self, validated_request_data):
        # 获取请求来源系统
        request = get_request()
        bk_app_code = get_app_code_by_request(request)
        validated_request_data["registered_system"] = bk_app_code

        # 获取配置的用户名和密码
        auth_info = validated_request_data.pop("auth_info", {})
        # NOTE: 因为模型中字段没有设置允许为 null，所以不能赋值 None
        validated_request_data["username"] = auth_info.get("username", "")
        validated_request_data["password"] = auth_info.get("password", "")

        cluster = models.ClusterInfo.create_cluster(**validated_request_data)
        return cluster.cluster_id


class ModifyClusterInfoResource(Resource):
    """修改存储集群信息"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=False, label="存储集群ID", default=None)
        cluster_name = serializers.RegexField(
            required=False, label="存储集群名", regex=models.ClusterInfo.CLUSTER_NAME_REGEX
        )
        cluster_type = serializers.CharField(required=False, label="存储集群类型", default=None)
        display_name = serializers.CharField(required=False, max_length=128, label="集群显示名称", default=None)
        description = serializers.CharField(required=False, label="存储集群描述", default=None, allow_blank=True)
        auth_info = serializers.JSONField(required=False, label="身份认证信息", default={})
        custom_option = serializers.CharField(required=False, label="集群自定义标签", default=None)
        schema = serializers.CharField(required=False, label="集群链接协议", default=None)
        is_ssl_verify = serializers.BooleanField(required=False, label="是否需要强制SSL/TLS认证", default=None)
        ssl_verification_mode = serializers.CharField(required=False, label="校验模式", default=None)
        ssl_certificate_authorities = serializers.CharField(required=False, label="CA 证书内容", default=None)
        ssl_certificate = serializers.CharField(required=False, label="SSL/TLS 证书内容", default=None)
        ssl_certificate_key = serializers.CharField(required=False, label="SSL/TLS 私钥内容", default=None)
        ssl_insecure_skip_verify = serializers.BooleanField(required=False, label="是否跳过服务端校验", default=None)
        extranet_domain_name = serializers.CharField(required=False, label="外网集群域名", default=None)
        extranet_port = serializers.IntegerField(required=False, label="外网集群端口", default=None)
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        request = get_request()
        bk_app_code = get_app_code_by_request(request)
        bk_tenant_id = validated_request_data.pop("bk_tenant_id")

        # 1. 判断是否存在cluster_id或者cluster_name
        cluster_id: int = validated_request_data.pop("cluster_id")
        cluster_name: str = validated_request_data.pop("cluster_name", None)

        if cluster_id is None and cluster_name is None:
            raise ValueError(_("需要至少提供集群ID或集群名"))

        # 2. 判断是否可以拿到一个唯一的cluster_info
        query_dict = {}
        if cluster_id is not None:
            query_dict["cluster_id"] = cluster_id
        else:
            query_dict["cluster_name"] = cluster_name
            # 为了向前兼容，这里并不要求提供集群类型
            if validated_request_data.get("cluster_type") is not None:
                query_dict["cluster_type"] = validated_request_data["cluster_type"]

        try:
            cluster_info = models.ClusterInfo.objects.get(
                bk_tenant_id=bk_tenant_id,
                registered_system__in=[bk_app_code, models.ClusterInfo.DEFAULT_REGISTERED_SYSTEM],
                **query_dict,
            )
        except models.ClusterInfo.DoesNotExist:
            raise ValueError(_("找不到指定的集群配置，请确认后重试"))
        except models.ClusterInfo.MultipleObjectsReturned:
            raise ValueError(_("找到多个符合条件的集群配置，可能是不同类型的集群名相同，请提供集群类型后重试"))

        # 如果集群名不符合规范，则自动修正为合法名称并记录警告日志
        if not cluster_info.display_name:
            cluster_info.display_name = cluster_info.cluster_name

        if not re.match(models.ClusterInfo.CLUSTER_NAME_REGEX, cluster_info.cluster_name):
            original_cluster_name = cluster_info.cluster_name
            cluster_name = f"auto_cluster_name_{cluster_info.cluster_id}"
            cluster_info.cluster_name = cluster_name
            logger.warning(
                f"cluster({cluster_info.cluster_id}) cluster_name: {original_cluster_name} is not valid, set to: {cluster_name}"
            )

        # 3. 判断获取是否需要修改用户名和密码
        auth_info = validated_request_data.pop("auth_info", {})
        # NOTE: 因为模型中字段没有设置允许为 null，所以不能赋值 None
        validated_request_data["username"] = auth_info.get("username", "")
        validated_request_data["password"] = auth_info.get("password", "")

        # 4. 触发修改内容
        cluster_info.modify(**validated_request_data)
        return cluster_info.consul_config


class DeleteClusterInfoResource(Resource):
    """删除存储集群信息"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=False, label="存储集群ID", default=None)
        cluster_name = serializers.CharField(required=False, label="存储集群名", default=None)

    def perform_request(self, validated_request_data):
        request = get_request()
        bk_app_code = get_app_code_by_request(request)

        #  判断是否存在cluster_id或者cluster_name
        cluster_id = validated_request_data.pop("cluster_id")
        cluster_name = validated_request_data.pop("cluster_name")

        if cluster_id is None and cluster_name is None:
            raise ValueError(_("需要至少提供集群ID或集群名"))

        #  判断是否可以拿到一个唯一的cluster_info
        query_dict = {"cluster_id": cluster_id} if cluster_id is not None else {"cluster_name": cluster_name}
        try:
            cluster_info = models.ClusterInfo.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"], registered_system=bk_app_code, **query_dict
            )
        except models.ClusterInfo.DoesNotExist:
            raise ValueError(_("找不到指定的集群配置，请确认后重试"))

        cluster_info.delete()


class QueryClusterInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=False, label="存储集群ID", default=None)
        cluster_name = serializers.CharField(required=False, label="存储集群名", default=None)
        cluster_type = serializers.CharField(required=False, label="存储集群类型", default=None)
        is_plain_text = serializers.BooleanField(required=False, label="是否需要明文显示登陆信息", default=False)

    def perform_request(self, validated_request_data):
        query_dict = {}
        if validated_request_data["cluster_id"] is not None:
            query_dict = {"cluster_id": validated_request_data["cluster_id"]}

        elif validated_request_data["cluster_name"] is not None:
            query_dict = {"cluster_name": validated_request_data["cluster_name"]}

        if validated_request_data["cluster_type"] is not None:
            query_dict["cluster_type"] = validated_request_data["cluster_type"]

        query_result = models.ClusterInfo.objects.filter(
            bk_tenant_id=validated_request_data["bk_tenant_id"], **query_dict
        )

        result_list = []
        is_plain_text = validated_request_data["is_plain_text"]

        for cluster_info in query_result:
            cluster_consul_config = cluster_info.consul_config

            # 如果不是明文的方式，需要进行base64编码
            if not is_plain_text:
                cluster_consul_config["auth_info"] = base64.b64encode(
                    json.dumps(cluster_consul_config["auth_info"]).encode("utf-8")
                )
                cluster_config = cluster_consul_config["cluster_config"]
                # 添加证书相关处理
                if cluster_config["raw_ssl_certificate_authorities"]:
                    cluster_consul_config["cluster_config"]["raw_ssl_certificate_authorities"] = base64.b64encode(
                        cluster_config["raw_ssl_certificate_authorities"].encode("utf-8")
                    )
                if cluster_config["raw_ssl_certificate"]:
                    cluster_consul_config["cluster_config"]["raw_ssl_certificate"] = base64.b64encode(
                        cluster_config["raw_ssl_certificate"].encode("utf-8")
                    )
                if cluster_config["raw_ssl_certificate_key"]:
                    cluster_consul_config["cluster_config"]["raw_ssl_certificate_key"] = base64.b64encode(
                        cluster_config["raw_ssl_certificate_key"].encode("utf-8")
                    )

            result_list.append(cluster_consul_config)

        return result_list
