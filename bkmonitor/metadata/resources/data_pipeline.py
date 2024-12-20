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
from collections import OrderedDict
from typing import Optional

from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata.models.data_pipeline import (
    DataPipeline,
    DataPipelineDataSource,
    constants,
)
from metadata.models.data_pipeline import utils as dp_utils
from metadata.models.space.constants import SpaceTypes
from metadata.models.storage import ClusterInfo
from metadata.service.storage_details import (
    ClusterHealthCheck,
    StorageCluster,
    StorageClusterDetail,
)


class ListDataPipeline(Resource):
    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=False, label="链路名称", default=None)
        chinese_name = serializers.CharField(required=False, label="链路中文名称", default=None)
        etl_config = serializers.CharField(required=False, label="链路场景类型", default=None)
        space_type = serializers.CharField(required=False, label="空间类型", default=None)
        space_id = serializers.CharField(required=False, label="空间 ID", default=None)
        is_enable = serializers.CharField(required=False, label="是否启用", default="all")
        page_size = serializers.IntegerField(default=constants.DEFAULT_PAGE_SIZE, label="每页的条数")
        page = serializers.IntegerField(default=constants.MIN_PAGE_NUM, min_value=constants.MIN_PAGE_NUM, label="页数")

        def validate_is_enable(self, is_enable: str) -> Optional[bool]:
            if is_enable == "all":
                return None
            if is_enable == "true":
                return True
            else:
                return False

    def perform_request(self, validated_request_data: OrderedDict):
        resp = DataPipeline.filter_data(**validated_request_data)
        # 添加集群名称
        cluster_id_name = StorageCluster.get_all_clusters()
        data = resp["data"]
        for d in data:
            d["kafka_cluster_name"] = cluster_id_name.get(d["kafka_cluster_id"], None)
            d["influxdb_storage_cluster_name"] = cluster_id_name.get(d["influxdb_storage_cluster_id"], None)
            d["kafka_storage_cluster_name"] = cluster_id_name.get(d["kafka_storage_cluster_id"], None)
            d["es_storage_cluster_name"] = cluster_id_name.get(d["es_storage_cluster_id"], None)
            d["vm_storage_cluster_name"] = cluster_id_name.get(d["vm_storage_cluster_id"], None)

        resp["data"] = data
        return resp


class ListDataSourceByDataPipeline(Resource):
    """获取管道下的数据源信息"""

    class RequestSerializer(serializers.Serializer):
        data_pipeline_name = serializers.CharField(required=True, label="链路名称")
        page_size = serializers.IntegerField(default=constants.DEFAULT_PAGE_SIZE, label="每页的条数")
        page = serializers.IntegerField(default=constants.MIN_PAGE_NUM, min_value=constants.MIN_PAGE_NUM, label="页数")

    def perform_request(self, validated_request_data: OrderedDict):
        return DataPipelineDataSource.objects.filter_data_source(
            validated_request_data["data_pipeline_name"],
            page=validated_request_data["page"],
            page_size=validated_request_data["page_size"],
        )


class SpaceSerializer(serializers.Serializer):
    space_type = serializers.CharField(required=False, label="空间类型", default=SpaceTypes.ALL.value)
    space_id = serializers.CharField(required=False, label="空间 ID", default=None)


class CreateDataPipeline(Resource):
    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="链路名称")
        chinese_name = serializers.CharField(required=False, label="链路中文名称", default="")
        etl_configs = serializers.ListField(required=True, label="链路场景类型")
        spaces = serializers.ListField(child=SpaceSerializer(), required=True, label="空间范围")
        label = serializers.CharField(required=False, label="标签", default="", allow_blank=True)
        kafka_cluster_id = serializers.IntegerField(required=True, label="kafka 消息队列标识")
        transfer_cluster_id = serializers.CharField(required=True, label="transfer 集群标识")
        influxdb_storage_cluster_id = serializers.IntegerField(required=False, label="influxdb 存储集群标识", default=0)
        kafka_storage_cluster_id = serializers.IntegerField(required=False, label="kafka 存储集群标识", default=0)
        es_storage_cluster_id = serializers.IntegerField(required=False, label="es 存储集群标识", default=0)
        vm_storage_cluster_id = serializers.IntegerField(required=False, label="vm 存储集群标识", default=0)
        is_enable = serializers.BooleanField(required=False, label="是否开启", default=True)
        is_default = serializers.BooleanField(required=False, label="是否默认管道", default=False)
        description = serializers.CharField(required=False, label="链路描述", default="", allow_blank=True)
        creator = serializers.CharField(required=True, label="用户名")

        def validate(self, data: OrderedDict) -> OrderedDict:
            """校验数据"""
            # 校验存储必须存在，influxdb、kafka、es中的一个
            if not (
                data.get("influxdb_storage_cluster_id")
                or data.get("kafka_storage_cluster_id")
                or data.get("es_storage_cluster_id")
                or data.get("vm_storage_cluster_id")
            ):
                raise ValidationError(
                    _("参数[influxdb_storage_cluster_id]、[kafka_storage_cluster_id]、[es_storage_cluster_id]不能同时为空")
                )

            # 检测是否允许设置默认
            if data.get("is_default") and DataPipeline.check_exist_default(data.get("spaces"), data.get("etl_configs")):
                raise ValidationError("default pipeline has exist, please edit and retry!")
            return data

    def perform_request(self, validated_request_data: OrderedDict):
        return DataPipeline.create_record(**validated_request_data)


class UpdateDataPipeline(Resource):
    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, label="链路名称")
        etl_configs = serializers.ListField(required=False, label="链路场景类型")
        spaces = serializers.ListField(child=SpaceSerializer(), required=False, label="空间范围")
        is_enable = serializers.BooleanField(required=False, label="是否开启", default=None)
        is_default = serializers.BooleanField(required=False, label="是否默认管道", default=None)
        description = serializers.CharField(required=False, label="链路描述", default=None, allow_blank=True)
        updater = serializers.CharField(required=True, label="用户名")

    def perform_request(self, validated_request_data: OrderedDict):
        return DataPipeline.update_record(**validated_request_data)


class GetClusterInfo(Resource):
    """获取集群信息"""

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.IntegerField(required=False, label="集群 ID", allow_null=True)
        cluster_type = serializers.CharField(required=False, label="集群类型", allow_null=True, allow_blank=True)

    def perform_request(self, validated_request_data):
        return StorageCluster.get_cluster_id_cluster_name(
            cluster_id=validated_request_data.get("cluster_id"), cluster_type=validated_request_data.get("cluster_type")
        )


class GetEtlConfig(Resource):
    """获取数据类型"""

    def perform_request(self, validated_request_data: OrderedDict):
        return [etl_config[1] for etl_config in constants.ETLConfig._choices_labels.value]


class GetTransferList(Resource):
    """获取 transfer 集群列表"""

    def perform_request(self, validated_request_data: OrderedDict):
        return dp_utils.get_transfer_cluster()


class CheckClusterHealth(Resource):
    """检测集群连通性"""

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(label="集群 ID", required=False, allow_null=True)
        cluster_type = serializers.CharField(label="集群类型", required=False, default="")
        domain = serializers.CharField(label="集群域名", required=False, default="")
        port = serializers.IntegerField(label="集群端口", required=False, default=0)
        schema = serializers.CharField(label="协议", required=False, default="")
        is_ssl_verify = serializers.BooleanField(label="ssl 校验", required=False, default=False)
        username = serializers.CharField(label="用户名", required=False, default="")
        password = serializers.CharField(label="密码", required=False, default="")

    def perform_request(self, validated_request_data: OrderedDict):
        return ClusterHealthCheck.check(**validated_request_data)


class ListClusters(Resource):
    class RequestSerializer(serializers.Serializer):
        cluster_type = serializers.CharField(label="集群类型", required=False, default="all")
        page_size = serializers.IntegerField(default=constants.DEFAULT_PAGE_SIZE, label="每页的条数")
        page = serializers.IntegerField(default=constants.MIN_PAGE_NUM, min_value=constants.MIN_PAGE_NUM, label="页数")

    def perform_request(self, validated_request_data: OrderedDict):
        cluster_type = validated_request_data["cluster_type"]
        objs = ClusterInfo.objects.filter(
            cluster_type__in=[ClusterInfo.TYPE_ES, ClusterInfo.TYPE_INFLUXDB, ClusterInfo.TYPE_KAFKA]
        )
        if cluster_type != "all":
            objs = objs.filter(cluster_type=cluster_type)

        objs = objs.order_by("-last_modify_time")
        page, page_size = validated_request_data["page"], validated_request_data["page_size"]
        start, end = (page - 1) * page_size, page * page_size
        # 分页数据
        data = objs[start:end]
        cluster_ids = [d.cluster_id for d in data]
        cluster_id_pipeline_name = DataPipeline.objects.get_name_by_cluster_ids(cluster_ids)
        ret_data = []
        for obj in data:
            item = obj.to_dict()
            item["pipeline_name"] = cluster_id_pipeline_name.get(obj.cluster_id, "")
            ret_data.append(item)

        return {"total": objs.count(), "data": ret_data}


class GetStorageClusterDetail(Resource):
    """获取存储集群的详情"""

    class RequestSerializer(serializers.Serializer):
        cluster_id = serializers.CharField(label="集群 id", required=True)
        page_size = serializers.IntegerField(default=constants.DEFAULT_PAGE_SIZE, label="每页的条数")
        page = serializers.IntegerField(default=constants.MIN_PAGE_NUM, min_value=constants.MIN_PAGE_NUM, label="页数")

    def perform_request(self, validated_request_data: OrderedDict):
        return StorageClusterDetail.get_detail(validated_request_data["cluster_id"])


class RegisterCluster(Resource):
    """注册集群资源"""

    class RequestSerializer(serializers.Serializer):
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

    def validate_cluster_id(self, cluster_id: str):
        """集群是否存在"""
        if not ClusterInfo.objects.filter(cluster_id=cluster_id).exists():
            raise ValidationError("cluster_id: %s not found", cluster_id)
        return cluster_id

    def perform_request(self, validated_request_data: OrderedDict):
        cluster_id = validated_request_data.pop("cluster_id")
        try:
            cluster = ClusterInfo.objects.get(cluster_id=cluster_id)
        except ClusterInfo.DoesNotExist:
            raise ValidationError("cluster_id: %s not found", cluster_id)

        return cluster.modify(**validated_request_data)
