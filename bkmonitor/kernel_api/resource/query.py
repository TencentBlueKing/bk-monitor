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
import re
from typing import Any, Dict, List, Set

from rest_framework.exceptions import NotFound

from bkmonitor.views import serializers
from core.drf_resource import Resource
from metadata import models
from query_api.resources import GetEsDataResource

logger = logging.getLogger(__name__)


class QueryEsResource(Resource):
    _INDEX_PATTERN = re.compile(r"^(?P<prefix>.+)_(?P<date>\d{8})_\d+$")

    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        query_body = serializers.DictField(required=True, label="查询内容")
        use_full_index_names = serializers.BooleanField(required=False, label="是否使用索引全名进行检索", default=False)

    @classmethod
    def _process_index_names(cls, index_names: List[str]) -> List[str]:
        processed_index_names: Set[str] = set()
        for index_name in index_names:
            match = cls._INDEX_PATTERN.match(index_name)
            if not match:
                # 不满足合并条件也要进行检索
                processed_index_names.add(index_name)
            else:
                processed_index_names.add(
                    "{prefix}_{date}_*".format(prefix=match.group("prefix"), date=match.group("date"))
                )
        return list(processed_index_names)

    def perform_request(self, validated_request_data):
        table_id = validated_request_data["table_id"]
        result_table = self.get_result_table(table_id)

        storage: models.ESStorage = self.get_storage(result_table)
        storage_info: Dict[str, Any] = storage.consul_config
        data_source_info = {
            "domain_name": storage_info["cluster_config"]["domain_name"],
            "port": storage_info["cluster_config"]["port"],
            "is_ssl_verify": storage_info["cluster_config"]["is_ssl_verify"],
            "auth_info": storage_info["auth_info"],
        }

        extra: Dict[str, Any] = {}
        if validated_request_data["use_full_index_names"]:
            data_source_info.update(
                {
                    "schema": storage_info["cluster_config"]["schema"],
                    "version": storage_info["cluster_config"]["version"],
                }
            )
            extra["index_names"] = self._process_index_names(storage.get_index_names())

        data = GetEsDataResource().request(
            index_name=validated_request_data["table_id"],
            doc_type="_doc",
            query_body=validated_request_data["query_body"],
            datasource_info=data_source_info,
            **extra
        )
        return data

    @staticmethod
    def get_result_table(table_id: str) -> models.ResultTable:
        try:
            result_table = models.ResultTable.get_result_table(table_id=table_id)
        except models.ResultTable.DoesNotExist:
            raise NotFound("result_table({}) not exists.".format(table_id))
        except Exception as err:
            logger.exception("get result_table({}) failed, error message is {}".format(table_id, err))
            raise Exception("get result_table({}) failed, error message is {}".format(table_id, err))
        return result_table

    @staticmethod
    def get_storage(result_table: models.ResultTable) -> models.ESStorage:
        try:
            storage: models.ESStorage = result_table.get_storage(models.ClusterInfo.TYPE_ES)
        except models.storage.ESStorage.DoesNotExist:
            raise NotFound("result table({}) storage info not exists.".format(result_table.table_id))
        except Exception as err:
            logger.exception(
                "get result table({}) storage failed, error message is {}".format(result_table.table_id, err)
            )
            raise Exception(
                "get result table({}) storage failed, error message is {}".format(result_table.table_id, err)
            )
        return storage
