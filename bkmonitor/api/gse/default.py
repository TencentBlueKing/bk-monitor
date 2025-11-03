"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from typing import Any

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource.contrib.api import APIResource


def get_base_url():
    """根据环境变量是否存在，返回指定的地址"""
    if settings.BKGSE_APIGW_BASE_URL:
        return f"{settings.BKGSE_APIGW_BASE_URL.rstrip('/')}/api/v2/"
    return f"{settings.BK_COMPONENT_API_URL}/api/bk-gse/prod/api/v2/"


class GseBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/gse/"
    # 如果开启通过 gse agent 2.0 访问 API，则通过 apigw 访问 gse 的服务
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        base_url = get_base_url()

    module_name = "gse"


class GseAPIBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url = get_base_url()
    module_name = "gse"


####################################
#           Stream to              #
####################################
class StorageAddressSerializer(serializers.Serializer):
    ip = serializers.CharField(required=True, label="接收端IP或域名")
    port = serializers.IntegerField(required=True, label="接收端PORT")


class AddStreamTo(GseBaseResource):
    """
    新增数据接收端配置
    """

    action = "config_add_streamto/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/add_streamto"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class MetadataSerializer(serializers.Serializer):
            label = serializers.DictField(required=False, label="可选信息")
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        class StreamToSerializer(serializers.Serializer):
            class KafkaSerializer(serializers.Serializer):
                storage_address = serializers.ListField(
                    required=True, label="kafka的地址和端口配置", child=StorageAddressSerializer()
                )
                sasl_username = serializers.CharField(required=False, label="kafka的用户名", allow_blank=True)
                sasl_passwd = serializers.CharField(required=False, label="kafka的密码", allow_blank=True)
                sasl_mechanisms = serializers.CharField(required=False, label="kafka的SASL机制", allow_blank=True)
                security_protocol = serializers.CharField(required=False, label="kafka的SASL协议", allow_blank=True)

            class RedisSerializer(serializers.Serializer):
                storage_address = serializers.ListField(
                    required=True, label="redis的地址和端口配置", child=StorageAddressSerializer()
                )
                passwd = serializers.CharField(required=False, label="redis的密码")
                master_name = serializers.CharField(required=False, label="redis sentinel mode的master name")

            class PulsarSerializer(serializers.Serializer):
                storage_address = serializers.ListField(
                    required=True, label="pulsar的地址和端口配置", child=StorageAddressSerializer()
                )
                token = serializers.CharField(required=False, label="pulsar的鉴权token")

            name = serializers.CharField(required=True, label="接收端名称")
            report_mode = serializers.ChoiceField(
                required=True, choices=["kafka", "redis", "pulsar", "file"], label="接收端类型"
            )
            # report_mode:file
            data_log_path = serializers.CharField(required=False, label="文件路径")
            # report_mode:kafka
            kafka = KafkaSerializer(required=False, label="kafka接收端配置")
            # report_mode:redis
            redis = RedisSerializer(required=False, label="redis接收端配置")
            # report_mode:pulsar
            pulsar = PulsarSerializer(required=False, label="pulsar接收端配置")

        metadata = MetadataSerializer(required=True, label="所属平台的源信息")
        operation = OperationSerializer(required=True, label="操作人配置")
        stream_to = StreamToSerializer(required=True, label="接收端详细配置")


class UpdateStreamTo(GseBaseResource):
    """
    修改数据接收端配置
    """

    action = "config_update_streamto/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/update_streamto"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            stream_to_id = serializers.IntegerField(required=True, label="接收端配置的ID")
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        class SpecificationSerializer(serializers.Serializer):
            class StreamToSerializer(serializers.Serializer):
                class KafkaSerializer(serializers.Serializer):
                    storage_address = serializers.ListField(
                        required=True, label="kafka的地址和端口配置", child=StorageAddressSerializer()
                    )
                    sasl_username = serializers.CharField(required=False, label="kafka的用户名", allow_blank=True)
                    sasl_passwd = serializers.CharField(required=False, label="kafka的密码", allow_blank=True)
                    sasl_mechanisms = serializers.CharField(required=False, label="kafka的SASL机制", allow_blank=True)
                    security_protocol = serializers.CharField(required=False, label="kafka的SASL协议", allow_blank=True)

                class RedisSerializer(serializers.Serializer):
                    storage_address = serializers.ListField(
                        required=True, label="redis的地址和端口配置", child=StorageAddressSerializer()
                    )
                    passwd = serializers.CharField(required=False, label="redis的密码")
                    master_name = serializers.CharField(required=False, label="redis sentinel mode的master name")

                class PulsarSerializer(serializers.Serializer):
                    storage_address = serializers.ListField(
                        required=True, label="pulsar的地址和端口配置", child=StorageAddressSerializer()
                    )
                    token = serializers.CharField(required=False, label="pulsar的鉴权token")

                name = serializers.CharField(required=True, label="接收端名称")
                report_mode = serializers.ChoiceField(
                    required=True, choices=["kafka", "redis", "pulsar", "file"], label="接收端类型"
                )
                # report_mode:file
                data_log_path = serializers.CharField(required=False, label="文件路径")
                # report_mode:kafka
                kafka = KafkaSerializer(required=False, label="kafka接收端配置")
                # report_mode:redis
                redis = RedisSerializer(required=False, label="redis接收端配置")
                # report_mode:pulsar
                pulsar = PulsarSerializer(required=False, label="pulsar接收端配置")

            stream_to = StreamToSerializer(required=True, label="接收端详细配置")

        condition = ConditionSerializer(required=True, label="修改接口端配置条件信息")
        operation = OperationSerializer(required=True, label="操作人配置")
        specification = SpecificationSerializer(required=True, label="接收端配置信息")


class DeleteStreamTo(GseBaseResource):
    """
    删除数据接收端配置
    """

    action = "config_delete_streamto/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/delete_streamto"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            stream_to_id = serializers.IntegerField(required=True, label="接收端配置的ID")
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        condition = ConditionSerializer(required=True, label="修改接口端配置条件信息")
        operation = OperationSerializer(required=True, label="操作人配置")


class QueryStreamTo(GseBaseResource):
    """
    查询数据接收端配置
    """

    action = "config_query_streamto/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/query_streamto"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")
            stream_to_id = serializers.IntegerField(required=False, label="接收端配置的ID")
            label = serializers.DictField(required=False, label="可选信息")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        condition = ConditionSerializer(required=True, label="修改接口端配置条件信息")
        operation = OperationSerializer(required=True, label="操作人配置")


####################################
#           Route Info             #
####################################
class AddRoute(GseBaseResource):
    """
    注册路由配置
    """

    action = "config_add_route/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/add_route"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class MetadataSerializer(serializers.Serializer):
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")
            channel_id = serializers.IntegerField(required=False, label="路由ID")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        class RouteInfoSerializer(serializers.Serializer):
            class StreamToSerializer(serializers.Serializer):
                class KafkaStorageSerializer(serializers.Serializer):
                    topic_name = serializers.CharField(required=True, label="kafka的Topic信息")
                    data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                    biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")
                    partition = serializers.IntegerField(required=False, label="Topic的分区信息")

                class RedisStorageSerializer(serializers.Serializer):
                    channel_name = serializers.CharField(required=True, label="发布订阅Key")
                    data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                    biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")

                class PulsarStorageSerializer(serializers.Serializer):
                    name = serializers.CharField(required=True, label="Pulsar的Topic")
                    tenant = serializers.CharField(required=False, label="tenant名称")
                    namespace = serializers.CharField(required=False, label="Pulsar的namespace名称")

                stream_to_id = serializers.IntegerField(required=True, label="数据接收端配置ID")
                kafka = KafkaStorageSerializer(required=False, label="Kafka存储信息")
                redis = RedisStorageSerializer(required=False, label="Redis存储信息")
                pulsar = PulsarStorageSerializer(required=False, label="Pulsar存储信息")

            name = serializers.CharField(required=True, label="路由名称")
            stream_to = StreamToSerializer(required=True, label="数据接收端配置信息")
            filter_name_and = serializers.ListField(required=False, label="与条件", child=serializers.CharField())
            filter_name_or = serializers.ListField(required=False, label="或条件", child=serializers.CharField())

        class StreamFilterInfoSerializer(serializers.Serializer):
            name = serializers.CharField(required=True, label="filter名字")
            field_index = serializers.IntegerField(required=True, label="字段索引")
            field_data_type = serializers.ChoiceField(
                required=True, label="数据类型", choices=["int", "string", "bytes"]
            )
            field_data_value = serializers.CharField(required=True, label="数据值")
            field_separator = serializers.CharField(required=False, label="分隔符")
            field_in = serializers.ChoiceField(
                required=False, default="protocol", label="数据来源协议还是原始数据", choices=["protocol", "data"]
            )

        metadata = MetadataSerializer(required=True, label="所属平台的源信息")
        operation = OperationSerializer(required=True, label="操作人配置")
        route = serializers.ListField(required=False, label="路由入库配置", child=RouteInfoSerializer())
        stream_filters = serializers.ListField(required=False, label="过滤规则配置")


class UpdateRoute(GseBaseResource):
    """
    修改路由配置
    """

    action = "config_update_route/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/update_route"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        class SpecificationSerializer(serializers.Serializer):
            class RouteInfoSerializer(serializers.Serializer):
                class StreamToSerializer(serializers.Serializer):
                    class KafkaStorageSerializer(serializers.Serializer):
                        topic_name = serializers.CharField(required=True, label="kafka的Topic信息")
                        data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                        biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")
                        partition = serializers.IntegerField(required=False, label="Topic的分区信息")

                    class RedisStorageSerializer(serializers.Serializer):
                        channel_name = serializers.CharField(required=True, label="发布订阅Key")
                        data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                        biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")

                    class PulsarStorageSerializer(serializers.Serializer):
                        name = serializers.CharField(required=True, label="Pulsar的Topic")
                        tenant = serializers.CharField(required=False, label="tenant名称")
                        namespace = serializers.CharField(required=False, label="Pulsar的namespace名称")

                    stream_to_id = serializers.IntegerField(required=True, label="数据接收端配置ID")
                    kafka = KafkaStorageSerializer(required=False, label="Kafka存储信息")
                    redis = RedisStorageSerializer(required=False, label="Redis存储信息")
                    pulsar = PulsarStorageSerializer(required=False, label="Pulsar存储信息")

                name = serializers.CharField(required=True, label="路由名称")
                stream_to = StreamToSerializer(required=True, label="数据接收端配置信息")
                filter_name_and = serializers.ListField(required=False, label="与条件", child=serializers.CharField())
                filter_name_or = serializers.ListField(required=False, label="或条件", child=serializers.CharField())

            class StreamFilterInfoSerializer(serializers.Serializer):
                name = serializers.CharField(required=True, label="filter名字")
                field_index = serializers.IntegerField(required=True, label="字段索引")
                field_data_type = serializers.ChoiceField(
                    required=True, label="数据类型", choices=["int", "string", "bytes"]
                )
                field_data_value = serializers.CharField(required=True, label="数据值")
                field_separator = serializers.CharField(required=False, label="分隔符")
                field_in = serializers.ChoiceField(
                    required=False, default="protocol", label="数据来源协议还是原始数据", choices=["protocol", "data"]
                )

            route = serializers.ListField(required=False, label="路由入库配置", child=RouteInfoSerializer())
            stream_filters = serializers.ListField(required=False, label="过滤规则配置")

        condition = ConditionSerializer(required=True, label="修改路由条件信息")
        operation = OperationSerializer(required=True, label="操作人配置")
        specification = SpecificationSerializer(required=True, label="路由信息")


class DeleteRoute(GseBaseResource):
    """
    删除路由配置
    """

    action = "config_delete_route/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/delete_route"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")
            method = serializers.ChoiceField(required=True, label="指定删除方式", choices=["all", "specification"])

        class SpecificationSerializer(serializers.Serializer):
            route = serializers.ListField(required=False, label="路由名称列表", child=serializers.CharField())
            stream_filters = serializers.ListField(
                required=False, label="过滤条件名称列表", child=serializers.CharField()
            )

        condition = ConditionSerializer(required=True, label="条件信息")
        operation = OperationSerializer(required=True, label="操作配置")
        specification = SpecificationSerializer(required=False, label="指定待删除的配置名称")


class QueryRoute(GseBaseResource):
    """
    查询路由配置
    """

    action = "config_query_route/"
    if getattr(settings, "USE_GSE_AGENT_STATUS_NEW_API", False):
        action = "data/query_route"

    method = "POST"

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=False, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        condition = ConditionSerializer(required=True, label="条件信息")
        operation = OperationSerializer(required=True, label="操作配置")


class GetAgentStatus(GseBaseResource):
    """
    主机查询接口
    """

    action = "get_agent_status"
    method = "POST"
    base_url = f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/gse/"
    backend_cache_type = CacheType.GSE

    class RequestSerializer(serializers.Serializer):
        class HostSerializer(serializers.Serializer):
            ip = serializers.IPAddressField(label="IP地址")
            bk_cloud_id = serializers.IntegerField(label="云区域ID")

        hosts = HostSerializer(label="主机列表", many=True)
        bk_supplier_account = serializers.IntegerField(label="开发商账号", default="0")


class GetProcStatus(GseBaseResource):
    """
    主机查询接口
    NOTE: 暂时没有使用，可以不调整
    """

    action = "get_proc_status"
    method = "POST"
    backend_cache_type = CacheType.GSE

    class RequestSerializer(serializers.Serializer):
        class HostSerializer(serializers.Serializer):
            ip = serializers.IPAddressField(label="IP地址")
            bk_cloud_id = serializers.IntegerField(label="云区域ID")

        class MetaSerializer(serializers.Serializer):
            class LabelSerializer(serializers.Serializer):
                proc_name = serializers.CharField(label="进程名称")

            namespace = serializers.CharField(label="命名空间")
            name = serializers.CharField(label="进程名")
            labels = LabelSerializer(label="标签信息")

        namespace = serializers.CharField(label="命名空间")
        hosts = HostSerializer(label="主机列表", many=True, required=False)
        agent_id_list = serializers.ListField(label="Agent ID列表", child=serializers.CharField(), required=False)
        meta = MetaSerializer(label="元信息")


class ListAgentState(GseAPIBaseResource):
    action = "cluster/list_agent_state"
    method = "POST"
    backend_cache_type = CacheType.GSE

    class RequestSerializer(serializers.Serializer):
        agent_id_list = serializers.ListField(child=serializers.CharField())


class DispatchMessage(GseAPIBaseResource):
    action = "cluster/dispatch_message"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        message_id = serializers.CharField(label="消息ID", max_length=64)
        agent_id_list = serializers.ListField(label="Agent ID列表", child=serializers.CharField(), min_length=1)
        content = serializers.CharField(label="请求内容")

    def perform_request(self, validated_request_data: dict[str, Any]):
        validated_request_data["slot_id"] = settings.GSE_SLOT_ID
        validated_request_data["token"] = settings.GSE_SLOT_TOKEN
        return super().perform_request(validated_request_data)
