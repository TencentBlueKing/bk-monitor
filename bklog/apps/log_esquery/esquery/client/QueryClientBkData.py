# pylint: disable=invalid-name
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json
import re
from copy import deepcopy
from typing import Any

from django.conf import settings
from elasticsearch.client import _make_path
from opentelemetry import trace

from apps.api import BkDataMetaApi, BkDataQueryApi, BkDataStorekitApi
from apps.exceptions import ApiResultError
from apps.log_esquery.constants import BKDATA_NOT_HAVE_INDEX
from apps.log_esquery.esquery.client.QueryClientTemplate import QueryClientTemplate
from apps.log_esquery.exceptions import EsClientSearchException
from apps.log_esquery.type_constants import type_mapping_dict
from apps.log_esquery.utils.es_client import adapt_es_query_body, needs_es_query_body_adaptation, parse_es_version
from apps.utils.cache import cache_five_minute
from apps.utils.local import get_request_tenant_id
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc

BKDATA_ES_VERSION_QUERY_TIMEOUT = 3


class QueryClientBkData(QueryClientTemplate):  # pylint: disable=invalid-name
    def __init__(self, bkdata_authentication_method: str = "", bkdata_data_token: str = ""):
        super().__init__()
        self._client = BkDataQueryApi
        self.bkdata_authentication_method = bkdata_authentication_method
        self.bkdata_data_token = bkdata_data_token

    def query(self, index: str, body: dict[str, Any], scroll=None, track_total_hits=False):
        try:
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("bkdata_es_query") as span:
                body = self.adapt_query_body(index, body)
                # bkdata情景下,当且仅当用户主动传了 track_total_hits: true 时，才允许往 body 中注入该参数
                if track_total_hits:
                    body.update({"track_total_hits": True})
                sql = json.dumps({"index": index, "body": body})
                params = {"prefer_storage": "es", "sql": sql}
                span.set_attribute("db.statement", sql)
                span.set_attribute("db.system", "elasticsearch")

                if self.bkdata_authentication_method:
                    params["bkdata_authentication_method"] = self.bkdata_authentication_method
                if self.bkdata_data_token:
                    params["bkdata_data_token"] = self.bkdata_data_token

                result = self._client.query(params, timeout=settings.ES_QUERY_TIMEOUT)
                result = result["list"]
                if not result:
                    result = {"hits": {"hits": [], "total": 0}}
                return result
        except ApiResultError as e:
            if str(e.code) == BKDATA_NOT_HAVE_INDEX:
                return {"hits": {"hits": [], "total": 0}}
            raise EsClientSearchException(e.message, code=e.code)
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise EsClientSearchException(
                EsClientSearchException.MESSAGE.format(error=e),
                code=getattr(e, "code", EsClientSearchException.ERROR_CODE),
            )

    def adapt_query_body(self, index: str, body: dict, default_es_version: str | None = None) -> dict:
        if not needs_es_query_body_adaptation(body):
            return deepcopy(body)
        version = self.get_es_version(index) or default_es_version
        if version is None:
            return deepcopy(body)
        return adapt_es_query_body(body, version)

    def get_es_version(self, index: str) -> str | None:
        # 有限支持：整份 DSL 按首个结果表的集群版本适配，不拆分跨版本集群查询。
        result_table_id = index.split(",", 1)[0].strip().removesuffix("_*")
        result_table_id = re.sub(r"_\d{4}(?:\d{2}){0,3}\*$", "", result_table_id)
        if not result_table_id or "*" in result_table_id or "?" in result_table_id:
            return None
        try:
            info = self._get_cached_es_version(result_table_id=result_table_id, bk_tenant_id=get_request_tenant_id())
            return info["version"]
        except Exception:  # pylint: disable=broad-except
            logger.warning("[bkdata] read ES version cache failed, result_table_id=%s", result_table_id, exc_info=True)
            return None

    @staticmethod
    @cache_five_minute("bkdata_es_version_{bk_tenant_id}_{result_table_id}", need_md5=True)
    def _get_cached_es_version(result_table_id: str, bk_tenant_id: str) -> dict:
        version = None
        try:
            storages = BkDataMetaApi.result_tables.storages(
                {"result_table_id": result_table_id},
                bk_tenant_id=bk_tenant_id,
                timeout=BKDATA_ES_VERSION_QUERY_TIMEOUT,
            )
            cluster_name = (storages.get("es", {}).get("storage_cluster") or {}).get("cluster_name")
            if cluster_name:
                response = BkDataStorekitApi.storekit_es_route(
                    {"cluster_name": cluster_name, "uri": "/"},
                    bk_tenant_id=bk_tenant_id,
                    timeout=BKDATA_ES_VERSION_QUERY_TIMEOUT,
                )
                info = json.loads(response) if isinstance(response, str) else response
                candidate = info.get("version", {}).get("number")
                if isinstance(candidate, str) and parse_es_version(candidate) is not None:
                    version = candidate
        except Exception:  # pylint: disable=broad-except
            logger.warning("[bkdata] query ES version failed, result_table_id=%s", result_table_id, exc_info=True)
        # 缓存探测失败结果，避免异常期间每次聚合查询都重复探测。
        return {"version": version}

    def mapping(self, index: str, add_settings_details: bool = False) -> dict:
        index_list: list = index.split(",")
        new_index_list: list = []
        has_wildcard = False
        result_table_ids = []
        for _index in index_list:
            if not _index.endswith("*"):
                _index = _index + "_*"
            else:
                has_wildcard = True
            new_index_list.append(_index)
            result_table_ids.append(_index.rsplit("_", maxsplit=1)[0])
        index = ",".join(new_index_list)

        params = {
            "prefer_storage": "es",
            "sql": json.dumps({"index": index, "mapping": True}),
        }

        if self.bkdata_authentication_method:
            params["bkdata_authentication_method"] = self.bkdata_authentication_method
        if self.bkdata_data_token:
            params["bkdata_data_token"] = self.bkdata_data_token

        mapping_dict: type_mapping_dict = self._client.query(params)
        result_dict: dict = mapping_dict.get("list", {})
        data = self.filter_mapping(index_list, result_dict) if not has_wildcard else result_dict
        if add_settings_details:
            # 添加自定义分词信息
            data = self.add_analyzer_details(result_table_ids, data)
        return data

    @staticmethod
    def add_analyzer_details(result_table_ids, mapping):
        """
        为bkdata的索引集添加自定义分词
        """
        result_tables = BkDataMetaApi.result_tables.list(
            {"result_table_ids": result_table_ids, "related": ["storages"]}
        )
        result_table_mappings = {}
        for item in result_tables:
            tokenizers = json.loads(item.get("storages", {}).get("es", {}).get("storage_config", "{}")).get(
                "tokenizers", {}
            )
            if not tokenizers:
                continue
            result_table_mappings[item["result_table_id"]] = tokenizers
        if not result_table_mappings:
            return mapping

        for result_table_id, result_table_config in mapping.items():
            if not result_table_config["mappings"]:
                continue

            result_table_id_bkbase = result_table_id.rsplit("_", maxsplit=1)[0]
            tokenizers_config = result_table_mappings.get(result_table_id_bkbase)
            if not tokenizers_config:
                continue

            if "properties" in result_table_config["mappings"]:
                field_configs = result_table_config["mappings"]["properties"]
            else:
                # ES 5.X 的情况
                field_configs = list(result_table_config["mappings"].values())[0].get("properties", [])
            for field_name, field_config in field_configs.items():
                if field_name in tokenizers_config:
                    field_config.update(
                        {
                            "analyzer": "bkbase_custom",
                            "analyzer_details": {
                                "tokenizer_details": {"tokenize_on_chars": tokenizers_config[field_name]}
                            },
                        }
                    )
        return mapping

    @staticmethod
    def filter_mapping(indices: list, indices_mapping: dict):
        if not indices_mapping:
            return {}
        indices = [item.lower() for item in indices]
        result = {}
        for index, mapping in indices_mapping.items():
            if len(index) <= 11:
                continue
            rt_name = index[0:-11]
            if rt_name in indices:
                result[index] = mapping
        return result

    @classmethod
    def indices(cls, bk_biz_id, result_table_id=None, with_storage=False):
        """
        查询索引列表
        :param bk_biz_id:
        :param result_table_id:
        :param with_storage:
        :return:
        """
        related_filter_params = json.dumps(
            {"type": "storages", "attr_name": "common_cluster.cluster_type", "attr_value": "es"}
        )
        index_results = BkDataMetaApi.result_tables.list(
            {"bk_biz_id": bk_biz_id, "related_filter": related_filter_params}
        )
        index_list = [
            {"result_table_id": item["result_table_id"], "result_table_name_alias": item["result_table_name_alias"]}
            for item in index_results
        ]

        if with_storage and index_list:
            multi_execute_func = MultiExecuteFunc()
            for _index in index_list:
                result_table_id = _index["result_table_id"]
                multi_execute_func.append(result_table_id, QueryClientBkData.get_cluster_info, result_table_id)
            result = multi_execute_func.run()
            for _index in index_list:
                _index.update(result.get(_index["result_table_id"], {}))
        return index_list

    def get_cluster_info(self, result_table_id=None):
        result_table_ids: list = result_table_id.split(",")
        storage_cluster_ids = []
        storage_cluster_names = []
        storage_cluster_domains = []
        storage_cluster_ports = []
        for rt_id in result_table_ids:
            cluster_info = BkDataMetaApi.result_tables.storages({"result_table_id": rt_id})
            es_info = cluster_info.get("es")
            if not es_info:
                continue
            storage_cluster_ids.append(str(es_info["storage_cluster"]["id"]))
            storage_cluster_names.append(es_info["storage_cluster"]["cluster_name"])
            cluster_connection_info = json.loads(es_info["storage_cluster"]["connection_info"])
            storage_cluster_domains.append(cluster_connection_info["host"])
            storage_cluster_ports.append(str(cluster_connection_info["port"]))
        return {
            "storage_cluster_id": ",".join(storage_cluster_ids),
            "storage_cluster_name": ",".join(storage_cluster_names),
            "storage_cluster_port": ",".join(storage_cluster_ports),
            "storage_cluster_domain_name": ",".join(storage_cluster_domains),
        }

    def _get_cluster_name(self, index):
        return self.get_cluster_info(index)["storage_cluster_name"]

    def cluster_stats(self, index=None):
        uri = "_cluster/stats"
        params = {"cluster_name": self._get_cluster_name(index), "uri": uri}
        return json.loads(BkDataStorekitApi.storekit_es_route(params))

    def cat_indices(self, index=None, bytes="mb", format="json", params=None):
        index_list = index.split(",")
        ret = []
        for _index in index_list:
            target_index = self._get_index_target(_index)
            uri: str = _make_path("_cat", "indices", target_index)
            uri = uri.lstrip("//")
            params = {"cluster_name": self._get_cluster_name(_index), "uri": f"{uri}?bytes={bytes}&format={format}"}
            ret.extend(json.loads(BkDataStorekitApi.storekit_es_route(params)))
        return ret

    def cluster_nodes_stats(self, index=None):
        uri = "_nodes/stats"
        params = self._build_es_route_param(uri, index)
        return json.loads(BkDataStorekitApi.storekit_es_route(params))

    def es_route(self, url: str, index=None):
        index_list = index.split(",")
        return {_index: self._get_bkdata_es_route(self._build_es_route_param(url, _index)) for _index in index_list}

    def _get_bkdata_es_route(self, params):
        return json.loads(BkDataStorekitApi.storekit_es_route(params))

    def _build_es_route_param(self, uri: str, index: str):
        return {"cluster_name": self._get_cluster_name(index), "uri": uri}

    def _get_index_target(self, index: str):
        index_list: list = index.split(",")
        new_index_list: list = []
        for _index in index_list:
            if not _index.endswith("*"):
                _index = _index + "_*"
            new_index_list.append(_index)
        return ",".join(new_index_list)
