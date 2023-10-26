# -*- coding: utf-8 -*-
from rest_framework import serializers

from bkm_ipchooser import constants, mock_data
from bkm_ipchooser.serializers import base


class TreesRequestSer(base.ScopeSelectorBaseSer):
    count_instance_type = serializers.ChoiceField(
        help_text="统计实例类型", choices=constants.InstanceType.list_choices(), default=constants.InstanceType.HOST.value
    )

    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_TREES_REQUEST}


class TreesResponseSer(serializers.Serializer):
    class Meta:
        swagger_schema_fields = {"example": mock_data.API_TOPO_TREES_RESPONSE}


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
