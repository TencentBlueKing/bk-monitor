# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from bkm_ipchooser import constants, exceptions, mock_data
from bkm_ipchooser.serializers import base
from bkm_space.api import SpaceApi
from bkm_space.define import SpaceTypeEnum


class TreesRequestSer(base.ScopeSelectorBaseSer):
    count_instance_type = serializers.ChoiceField(
        help_text="统计实例类型", choices=constants.InstanceType.list_choices(), default=constants.InstanceType.HOST.value
    )

    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_TREES_REQUEST}


class TreesResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_TREES_RESPONSE}


class QueryBusinessRequestSer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(help_text="业务 ID", required=True)

    def validate(self, attrs):
        space_info = SpaceApi.get_space_detail(bk_biz_id=attrs["bk_biz_id"])
        if space_info.space_type_id != SpaceTypeEnum.BKCC_SET.value:
            raise exceptions.SerValidationError(_("参数校验失败：请输入正确的业务集 bk_biz_id"))
        return attrs


class QueryBusinessResponseSer(serializers.Serializer):
    """查询业务集下业务返回"""


class QueryPathRequestSer(base.ScopeSelectorBaseSer):
    node_list = serializers.ListField(child=base.TreeNodeSer())
    count_instance_type = serializers.ChoiceField(
        help_text="统计实例类型", choices=constants.InstanceType.list_choices(), default=constants.InstanceType.HOST.value
    )

    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_PATH_REQUEST}


class QueryPathResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_PATH_RESPONSE}


class QueryHostsRequestSer(base.QueryHostsBaseSer):
    node_list = serializers.ListField(child=base.TreeNodeSer())

    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_HOSTS_REQUEST}


class QueryHostsResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_HOSTS_RESPONSE}


class QueryServiceInstancesRequestSer(base.ScopeSelectorBaseSer, base.PaginationSer):
    node_list = serializers.ListField(child=base.TreeNodeSer(), default=[])
    service_instance_id_list = serializers.ListField(child=serializers.IntegerField(), required=False)

    # 模糊查询字段
    search_content = serializers.CharField(label="模糊搜索内容", required=False, allow_blank=True)

    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_SERVICE_INSTANCE_REQUEST}


class QueryServiceInstancesResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_SERVICE_INSTANCE_RESPONSE}


class QueryHostIdInfosRequestSer(QueryHostsRequestSer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_HOST_ID_INFOS_REQUEST}


class QueryHostIdInfosResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_HOST_ID_INFOS_RESPONSE}


class AgentStatisticsRequestSer(QueryHostsRequestSer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_QUERY_HOST_ID_INFOS_REQUEST}


class ServiceInstanceCountRequestSer(AgentStatisticsRequestSer):
    """服务实例统计请求"""
