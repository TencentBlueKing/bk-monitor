from abc import ABC
from typing import Any, ClassVar, final

import requests
from rest_framework import serializers
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient
from bk_monitor_base.infras.third_party_api.errors import BkApiError


class GseApiClient(BkApiClient, ABC):
    """
    GSE API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "gse"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/gse"
    apigw_base_url: ClassVar[str] = "api/bk-gse/prod/api/v2"

    @override
    def handle_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理请求参数"""
        slz = getattr(self, "RequestSerializer", None)
        if slz:
            slz_instance = slz(data=params)
            try:
                slz_instance.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                raise BkApiError(
                    self.module_name, self.action, self.method, "", f"request params is not valid:{e.detail}"
                )
            params = slz_instance.validated_data
        return params

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


@final
class StorageAddressSerializer(serializers.Serializer):
    ip = serializers.CharField(required=True, label="接收端IP或域名")
    port = serializers.IntegerField(required=True, label="接收端PORT")


class AddRoute(GseApiClient):
    """
    注册路由配置
    """

    action: ClassVar[str] = "add_route"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_add_route"
    apigw_path: ClassVar[str] = "data/add_route"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class MetadataSerializer(serializers.Serializer):
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")
            channel_id = serializers.IntegerField(required=False, label="路由ID")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        @final
        class RouteInfoSerializer(serializers.Serializer):
            @final
            class StreamToSerializer(serializers.Serializer):
                @final
                class KafkaStorageSerializer(serializers.Serializer):
                    topic_name = serializers.CharField(required=True, label="kafka的Topic信息")
                    data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                    biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")
                    partition = serializers.IntegerField(required=False, label="Topic的分区信息")

                @final
                class RedisStorageSerializer(serializers.Serializer):
                    channel_name = serializers.CharField(required=True, label="发布订阅Key")
                    data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                    biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")

                @final
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

        @final
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


class AddStreamTo(GseApiClient):
    """
    新增数据接收端配置
    """

    action: ClassVar[str] = "add_stream_to"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_add_streamto"
    apigw_path: ClassVar[str] = "data/add_streamto"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class MetadataSerializer(serializers.Serializer):
            label = serializers.DictField(required=False, label="可选信息")
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        @final
        class StreamToSerializer(serializers.Serializer):
            @final
            class KafkaSerializer(serializers.Serializer):
                storage_address = serializers.ListField(
                    required=True, label="kafka的地址和端口配置", child=StorageAddressSerializer()
                )
                sasl_username = serializers.CharField(required=False, label="kafka的用户名", allow_blank=True)
                sasl_passwd = serializers.CharField(required=False, label="kafka的密码", allow_blank=True)
                sasl_mechanisms = serializers.CharField(required=False, label="kafka的SASL机制", allow_blank=True)
                security_protocol = serializers.CharField(required=False, label="kafka的SASL协议", allow_blank=True)

            @final
            class RedisSerializer(serializers.Serializer):
                storage_address = serializers.ListField(
                    required=True, label="redis的地址和端口配置", child=StorageAddressSerializer()
                )
                passwd = serializers.CharField(required=False, label="redis的密码")
                master_name = serializers.CharField(required=False, label="redis sentinel mode的master name")

            @final
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


class DeleteRoute(GseApiClient):
    """
    删除路由配置
    """

    action: ClassVar[str] = "delete_route"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_delete_route"
    apigw_path: ClassVar[str] = "data/delete_route"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")
            method = serializers.ChoiceField(required=True, label="指定删除方式", choices=["all", "specification"])

        @final
        class SpecificationSerializer(serializers.Serializer):
            route = serializers.ListField(required=False, label="路由名称列表", child=serializers.CharField())
            stream_filters = serializers.ListField(
                required=False, label="过滤条件名称列表", child=serializers.CharField()
            )

        condition = ConditionSerializer(required=True, label="条件信息")
        operation = OperationSerializer(required=True, label="操作配置")
        specification = SpecificationSerializer(required=False, label="指定待删除的配置名称")


class DispatchMessage(GseApiClient):
    action: ClassVar[str] = "dispatch_message"
    method: ClassVar[str] = "POST"
    esb_base_url: ClassVar[str] = ""
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "cluster/dispatch_message"

    @final
    class RequestSerializer(serializers.Serializer):
        message_id = serializers.CharField(label="消息ID", max_length=64)
        agent_id_list = serializers.ListField(label="Agent ID列表", child=serializers.CharField(), min_length=1)
        content = serializers.CharField(label="请求内容")


class QueryRoute(GseApiClient):
    """
    查询路由配置
    """

    action: ClassVar[str] = "query_route"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_query_route"
    apigw_path: ClassVar[str] = "data/query_route"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=False, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        condition = ConditionSerializer(required=True, label="条件信息")
        operation = OperationSerializer(required=True, label="操作配置")


class QueryStreamTo(GseApiClient):
    """
    查询数据接收端配置
    """

    action: ClassVar[str] = "query_stream_to"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_query_streamto"
    apigw_path: ClassVar[str] = "data/query_streamto"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class ConditionSerializer(serializers.Serializer):
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")
            stream_to_id = serializers.IntegerField(required=False, label="接收端配置的ID")
            label = serializers.DictField(required=False, label="可选信息")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        condition = ConditionSerializer(required=True, label="修改接口端配置条件信息")
        operation = OperationSerializer(required=True, label="操作人配置")


class UpdateRoute(GseApiClient):
    """
    修改路由配置
    """

    action: ClassVar[str] = "update_route"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_update_route"
    apigw_path: ClassVar[str] = "data/update_route"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class ConditionSerializer(serializers.Serializer):
            channel_id = serializers.IntegerField(required=True, label="路由ID")
            plat_name = serializers.CharField(required=True, label="路由所属的平台")
            label = serializers.DictField(required=False, label="可选信息")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        @final
        class SpecificationSerializer(serializers.Serializer):
            @final
            class RouteInfoSerializer(serializers.Serializer):
                @final
                class StreamToSerializer(serializers.Serializer):
                    @final
                    class KafkaStorageSerializer(serializers.Serializer):
                        topic_name = serializers.CharField(required=True, label="kafka的Topic信息")
                        data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                        biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")
                        partition = serializers.IntegerField(required=False, label="Topic的分区信息")

                    @final
                    class RedisStorageSerializer(serializers.Serializer):
                        channel_name = serializers.CharField(required=True, label="发布订阅Key")
                        data_set = serializers.CharField(required=False, label="兼容字段，数据集名称")
                        biz_id = serializers.IntegerField(required=False, label="兼容字段，业务ID")

                    @final
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

            @final
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


class UpdateStreamTo(GseApiClient):
    """
    修改数据接收端配置
    """

    action: ClassVar[str] = "update_stream_to"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "config_update_streamto"
    apigw_path: ClassVar[str] = "data/update_streamto"

    @final
    class RequestSerializer(serializers.Serializer):
        @final
        class ConditionSerializer(serializers.Serializer):
            stream_to_id = serializers.IntegerField(required=True, label="接收端配置的ID")
            plat_name = serializers.CharField(required=True, label="接收端配置所属的平台")

        @final
        class OperationSerializer(serializers.Serializer):
            operator_name = serializers.CharField(required=True, label="API调用者")

        @final
        class SpecificationSerializer(serializers.Serializer):
            @final
            class StreamToSerializer(serializers.Serializer):
                @final
                class KafkaSerializer(serializers.Serializer):
                    storage_address = serializers.ListField(
                        required=True, label="kafka的地址和端口配置", child=StorageAddressSerializer()
                    )
                    sasl_username = serializers.CharField(required=False, label="kafka的用户名", allow_blank=True)
                    sasl_passwd = serializers.CharField(required=False, label="kafka的密码", allow_blank=True)
                    sasl_mechanisms = serializers.CharField(required=False, label="kafka的SASL机制", allow_blank=True)
                    security_protocol = serializers.CharField(required=False, label="kafka的SASL协议", allow_blank=True)

                @final
                class RedisSerializer(serializers.Serializer):
                    storage_address = serializers.ListField(
                        required=True, label="redis的地址和端口配置", child=StorageAddressSerializer()
                    )
                    passwd = serializers.CharField(required=False, label="redis的密码")
                    master_name = serializers.CharField(required=False, label="redis sentinel mode的master name")

                @final
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


add_route_client: AddRoute = AddRoute()
add_stream_to_client: AddStreamTo = AddStreamTo()
delete_route_client: DeleteRoute = DeleteRoute()
dispatch_message_client: DispatchMessage = DispatchMessage()
query_route_client: QueryRoute = QueryRoute()
query_stream_to_client: QueryStreamTo = QueryStreamTo()
update_route_client: UpdateRoute = UpdateRoute()
update_stream_to_client: UpdateStreamTo = UpdateStreamTo()
