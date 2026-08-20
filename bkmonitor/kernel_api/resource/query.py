"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import re
from typing import Any

from rest_framework.exceptions import NotFound

from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.views import serializers
from core.drf_resource import Resource
from metadata import models
from query_api.resources import GetEsDataResource

logger = logging.getLogger(__name__)


class QueryEsResource(Resource):
    _INDEX_PATTERN = re.compile(r"^(?P<prefix>.+)_(?P<date>\d{8})_\d+$")

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        query_body = serializers.DictField(required=True, label="查询内容")
        use_full_index_names = serializers.BooleanField(required=False, label="是否使用索引全名进行检索", default=False)
        is_index_prefix = serializers.BooleanField(
            required=False, label="table_id 是否为索引前缀（跨集群检索同前缀索引）", default=False
        )

    @classmethod
    def _process_index_names(cls, index_names: list[str]) -> list[str]:
        processed_index_names: set[str] = set()
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

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]

        if validated_request_data["is_index_prefix"]:
            return self._query_by_index_prefix(bk_tenant_id, table_id, validated_request_data["query_body"])

        try:
            result_table = models.ResultTable.get_result_table(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except models.ResultTable.DoesNotExist:
            logger.warning(f"query_es_data result_table({table_id}) not exists, return empty data")
            return {"hits": {"total": 0, "hits": []}}

        storage: models.ESStorage = self.get_storage(result_table)
        storage_info: dict[str, Any] = storage.consul_config
        data_source_info = {
            "domain_name": storage_info["cluster_config"]["domain_name"],
            "port": storage_info["cluster_config"]["port"],
            "is_ssl_verify": storage_info["cluster_config"]["is_ssl_verify"],
            "auth_info": storage_info["auth_info"],
        }

        extra: dict[str, Any] = {}
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
            **extra,
        )
        return data

    @classmethod
    def _query_by_index_prefix(cls, bk_tenant_id: str, index_prefix: str, query_body: dict[str, Any]) -> dict[str, Any]:
        """按索引前缀检索"""

        cluster_ids: set[int] = set(
            models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__startswith=index_prefix).values_list(
                "storage_cluster_id", flat=True
            )
        )
        if not cluster_ids:
            logger.warning(f"query_es_data index prefix({index_prefix}) has no storage, return empty data")
            return {"hits": {"total": 0, "hits": []}}

        clusters: list[models.ClusterInfo] = list(
            models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=cluster_ids)
        )

        responses: list[Any] = ThreadPool().map_ignore_exception(
            cls._query_cluster_by_index_prefix,
            [(cluster, index_prefix, query_body) for cluster in clusters],
            return_exception=True,
        )
        for response in responses:
            # 部分集群失败会返回残缺的 Trace，不如直接失败交由调用方决策
            if isinstance(response, Exception):
                raise response

        return cls._merge_responses(responses)

    @staticmethod
    def _query_cluster_by_index_prefix(
        cluster: models.ClusterInfo, index_prefix: str, query_body: dict[str, Any]
    ) -> dict[str, Any]:
        return GetEsDataResource().request(
            # 索引名由结果表 ID 将 . 替换为 _ 得到，GetEsDataResource 会补上 * 以命中同前缀索引
            index_name=index_prefix.replace(".", "_"),
            doc_type="_doc",
            query_body=query_body,
            datasource_info={
                "domain_name": cluster.domain_name,
                "port": cluster.port,
                "is_ssl_verify": cluster.is_ssl_verify,
                "schema": cluster.schema,
                "version": cluster.version,
                "auth_info": {"username": cluster.username, "password": cluster.password},
            },
        )

    @classmethod
    def _merge_responses(cls, responses: list[dict[str, Any]]) -> dict[str, Any]:
        total: int = 0
        hits: list[dict[str, Any]] = []
        for response in responses:
            hits_info: dict[str, Any] = response.get("hits") or {}
            hits_total: Any = hits_info.get("total") or 0
            total += hits_total["value"] if isinstance(hits_total, dict) else hits_total
            hits.extend(hits_info.get("hits") or [])

        return {"hits": {"total": total, "hits": hits}}

    @staticmethod
    def get_storage(result_table: models.ResultTable) -> models.ESStorage:
        try:
            storage: models.ESStorage = result_table.get_storage(models.ClusterInfo.TYPE_ES)
        except models.storage.ESStorage.DoesNotExist:
            raise NotFound(f"result table({result_table.table_id}) storage info not exists.")
        except Exception as err:
            logger.exception(f"get result table({result_table.table_id}) storage failed, error message is {err}")
            raise Exception(f"get result table({result_table.table_id}) storage failed, error message is {err}")
        return storage
