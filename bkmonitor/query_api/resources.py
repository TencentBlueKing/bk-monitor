# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import List

from elasticsearch5.exceptions import ConnectionError
from rest_framework.exceptions import APIException

from bkmonitor.views import serializers
from core.drf_resource import Resource
from metadata.utils.es_tools import get_client_by_datasource_info
from query_api.drivers import load_driver_by_sql


class GetTSDataResource(Resource):
    class RequestSerializer(serializers.Serializer):
        sql = serializers.CharField(required=True, label="SQL查询语句")

    def perform_request(self, validated_request_data):
        sql = validated_request_data["sql"]
        # load driver
        query_driver = load_driver_by_sql(sql)
        return query_driver.query()


class GetEsDataResource(Resource):
    class RequestSerializer(serializers.Serializer):
        index_name = serializers.CharField(required=True, label="索引名")
        # 可以是具体的索引名，也可以包含通配符号，以下都是符合预期的：
        # - 具体索引名：2_bkapm_trace_testapp_20240820_0
        # - 包含通配符：2_bkapm_trace_testapp_*_*
        index_names = serializers.ListSerializer(
            required=False, label="索引名列表（不为空优先使用）", child=serializers.CharField(required=True, label="索引名")
        )
        doc_type = serializers.CharField(required=True, label="文档类型")
        query_body = serializers.DictField(required=True, label="查询内容")
        datasource_info = serializers.DictField(required=True, label="链接信息")

    def perform_request(self, validated_request_data):
        try:
            index_names: List[str] = validated_request_data.get("index_names") or []
            if index_names:
                index: str = ",".join(index_names)
            else:
                index: str = f"{validated_request_data['index_name']}*"

            es_client = get_client_by_datasource_info(validated_request_data["datasource_info"])
            data = es_client.search(
                index=index, doc_type=validated_request_data["doc_type"], body=validated_request_data["query_body"]
            )
            return data
        except ConnectionError as conn_err:
            domain_name = validated_request_data["datasource_info"]["domain_name"]
            port = validated_request_data["datasource_info"]["port"]
            raise APIException("connect hosts:{}:{} error, message is {}.".format(domain_name, port, conn_err))
        except Exception as err:
            raise Exception("call get_es_data api failed, error message is {}".format(err))
