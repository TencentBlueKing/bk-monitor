# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework import serializers


class DatasourceOptionSerializer(serializers.Serializer):
    """
    APM 存储配置
    用于:
    1. CreateDataHub 接口 (CreateApplicationHub)
    """

    es_storage_cluster = serializers.IntegerField(label="es存储集群", required=False)
    es_retention = serializers.IntegerField(label="es存储周期", min_value=1, required=False)
    es_number_of_replicas = serializers.IntegerField(label="es副本数量", min_value=0, required=False)
    es_shards = serializers.IntegerField(label="es索引分片数量", min_value=1, required=False)
    es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500, required=False)


class PluginConfigSerializer(serializers.Serializer):
    """
    APM Log-Trace 配置
    用于:
    1. CreateDataHub 接口 (CreateApplicationHub)
    """

    target_node_type = serializers.CharField(label="节点类型", max_length=255)
    target_nodes = serializers.ListField(
        label="目标节点",
        required=False,
    )
    target_object_type = serializers.CharField(label="目标类型", max_length=255)
    data_encoding = serializers.CharField(label="日志字符集", max_length=255)
    paths = serializers.ListSerializer(
        label="语言",
        child=serializers.CharField(max_length=255),
        required=False,
    )


class ApplicationHubSerializer(serializers.Serializer):
    """
    APM 创建/更新参数
    用于:
    1. CreateDataHub 接口 (CreateApplicationHub)
    """

    app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"^[a-z0-9_-]+$", required=False)
    app_alias = serializers.CharField(label="应用别名", max_length=255, required=False)
    description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
    plugin_id = serializers.CharField(label="插件ID", max_length=255, required=False, default="opentelemetry")
    deployment_ids = serializers.ListField(
        label="环境", child=serializers.CharField(max_length=255), required=False, default=["centos"]
    )
    language_ids = serializers.ListField(
        label="语言", child=serializers.CharField(max_length=255), required=False, default=["python"]
    )
    datasource_option = DatasourceOptionSerializer(required=False)
    plugin_config = PluginConfigSerializer(required=False)
    enable_profiling = serializers.BooleanField(label="是否开启 Profiling 功能", required=False, default=False)
    enable_tracing = serializers.BooleanField(label="是否开启 Tracing 功能", required=False, default=True)


class CustomReportHubSerializer(serializers.Serializer):
    """
    日志平台自定义上报 创建/更新参数
    用于:
    1. CreateDataHub 接口 (CreateApplicationHub)
    """

    name = serializers.RegexField(label="日志自定义上报名称", max_length=50, regex=r"^[a-z0-9_-]+$", required=False)


class EsStorageOptionSerializer(serializers.Serializer):
    """
    ES 存储配置参数
    用于:
    1. CreateDataHub 接口 (CreateApplicationHub)
    """

    es_storage_cluster = serializers.IntegerField(label="es存储集群", required=False)
    es_retention = serializers.IntegerField(label="es存储周期", min_value=1, required=False)
    es_number_of_replicas = serializers.IntegerField(label="es副本数量", min_value=0, required=False)
    es_shards = serializers.IntegerField(label="es索引分片数量", min_value=1, required=False)
    es_slice_size = serializers.IntegerField(label="es索引切分大小", required=False)
