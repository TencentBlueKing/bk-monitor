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

from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import NotFound

from bkmonitor.views import serializers
from core.drf_resource import Resource
from metadata import models
from query_api.resources import GetEsDataResource

logger = logging.getLogger(__name__)


class QueryEsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        query_body = serializers.DictField(required=True, label="查询内容")

    def perform_request(self, validated_request_data):
        table_id = validated_request_data["table_id"]
        result_table = self.get_result_table(table_id)
        storage_info = self.get_storage_info(result_table)
        data_source_info = {
            "domain_name": storage_info["cluster_config"]["domain_name"],
            "port": storage_info["cluster_config"]["port"],
            "is_ssl_verify": storage_info["cluster_config"]["is_ssl_verify"],
            "auth_info": storage_info["auth_info"],
        }
        data = GetEsDataResource().request(
            index_name=validated_request_data["table_id"],
            doc_type="_doc",
            query_body=validated_request_data["query_body"],
            datasource_info=data_source_info,
        )
        return data

    @staticmethod
    def get_result_table(table_id):
        try:
            result_table = models.ResultTable.get_result_table(table_id=table_id)
        except models.ResultTable.DoesNotExist:
            raise NotFound("result_table({}) not exists.".format(table_id))
        except Exception as err:
            logger.exception("get result_table({}) failed, error message is {}".format(table_id, err))
            raise Exception("get result_table({}) failed, error message is {}".format(table_id, err))
        return result_table

    @staticmethod
    def get_storage_info(result_table):
        try:
            consul_config = result_table.get_storage_info(models.ClusterInfo.TYPE_ES)
        except models.storage.ESStorage.DoesNotExist:
            raise NotFound("result table({}) storage info not exists.".format(result_table.table_id))
        except Exception as err:
            logger.exception(
                "get result table({}) storage info failed, error message is {}".format(result_table.table_id, err)
            )
            raise Exception(
                "get result table({}) storage info failed, error message is {}".format(result_table.table_id, err)
            )
        return consul_config
