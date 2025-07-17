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
from apps.utils.thread import MultiExecuteFunc


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
            result_table_id_bkbase = result_table_id.rsplit("_", maxsplit=1)[0]
            tokenizers_config = result_table_mappings.get(result_table_id_bkbase)
            if not tokenizers_config:
                continue
            result_table_id_es = result_table_id_bkbase.split("_", maxsplit=1)[-1]
            field_configs = result_table_config["mappings"][result_table_id_es]["properties"]
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
