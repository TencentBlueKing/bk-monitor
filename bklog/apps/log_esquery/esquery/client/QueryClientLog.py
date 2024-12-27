# -*- coding: utf-8 -*-
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
import re
from typing import Any, Dict

from django.conf import settings
from django.utils.translation import gettext as _
from elasticsearch import Elasticsearch as Elasticsearch
from elasticsearch5 import Elasticsearch as Elasticsearch5

from apps.api import TransferApi
from apps.log_databus.models import CollectorConfig
from apps.log_esquery.constants import DEFAULT_SCHEMA
from apps.log_esquery.esquery.client.QueryClientTemplate import QueryClientTemplate
from apps.log_esquery.exceptions import (
    BaseSearchFieldsException,
    BaseSearchIndexSettingsException,
    EsClientConnectInfoException,
    EsClientMetaInfoException,
    EsClientScrollException,
    EsClientSearchException,
    EsException,
)
from apps.log_esquery.type_constants import type_mapping_dict
from apps.log_esquery.utils.es_client import es_socket_ping, get_es_client
from apps.log_search.exceptions import IndexResultTableApiException
from apps.utils.cache import cache_five_minute
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc

DATE_RE = re.compile("[0-9]{6,8}$")


class QueryClientLog(QueryClientTemplate):  # pylint: disable=invalid-name
    def __init__(self, storage_cluster_id: int = None):
        super(QueryClientLog, self).__init__()
        self._client: Elasticsearch
        self.storage_cluster_id = storage_cluster_id

    def query(self, index: str, body: Dict[str, Any], scroll=None, track_total_hits=False):
        # query前没有必要检查ping
        self._build_connection(index=index, check_ping=False)

        # 如果版本不是5.0且track_total_hits为True时
        if track_total_hits and not isinstance(self._client, Elasticsearch5):
            body.update({"track_total_hits": True})

        try:
            params = {"request_timeout": settings.ES_QUERY_TIMEOUT}
            return self._client.search(index=index, body=body, scroll=scroll, params=params)
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise EsClientSearchException(EsClientSearchException.MESSAGE.format(error=e))

    def mapping(self, index: str, add_settings_details: bool = False) -> Dict:
        index_target = self._get_index_target(index=index, check_ping=False)
        try:
            logger.info("mapping for index=>{}, index_target=>{}".format(index, index_target))
            mapping_dict: type_mapping_dict = self._client.indices.get_mapping(index=index_target)
            if add_settings_details:
                settings_dict: Dict = self.get_settings(index=index)
                return self.add_analyzer_details(_mappings=mapping_dict, _settings=settings_dict)
            return mapping_dict
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise BaseSearchFieldsException(BaseSearchFieldsException.MESSAGE.format(error=e))

    def get_settings(self, index: str) -> Dict:
        index_target = self._get_index_target(index=index, check_ping=False)
        try:
            return self._client.indices.get_settings(index=index_target)
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise BaseSearchIndexSettingsException(BaseSearchIndexSettingsException.MESSAGE.format(error=e))

    def _get_index_target(self, index: str, check_ping: bool = True):
        index_list: list = index.split(",")
        new_index_list: list = []
        for _index in index_list:
            if not _index.endswith("*"):
                _index = _index + "_*"
            new_index_list.append(_index)
        index = ",".join(new_index_list)
        self._build_connection(index=index, check_ping=check_ping)
        # log的index转换逻辑
        return index.replace(".", "_")

    def scroll(self, index, scroll_id: str, scroll: str) -> Dict:
        self._build_connection(index, check_ping=False)
        try:
            return self._client.scroll(scroll_id=scroll_id, scroll=scroll)
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise EsClientScrollException(EsClientScrollException.MESSAGE.format(error=e))

    def cat_indices(self, index=None, bytes="mb", format="json", params=None):
        if params is None:
            params = {"request_timeout": 10}
        index_target = self._get_index_target(index)
        return self._client.cat.indices(index=index_target, bytes=bytes, format=format, params=params)

    def cluster_nodes_stats(self, index=None):
        self._get_index_target(index)
        return self._client.nodes.stats()

    def cluster_stats(self, index=None):
        self._get_index_target(index)
        try:
            return self._client.cluster.stats()
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise EsException

    def es_route(self, url: str, index=None):
        self._get_index_target(index)
        if not url.startswith("/"):
            url = "/" + url
        try:
            return self._client.transport.perform_request("GET", url)
        except Exception as e:  # pylint: disable=broad-except
            self.catch_timeout_raise(e)
            raise

    def _build_connection(self, index: str, check_ping: bool = True):
        index: str = self._get_meta_index(index=index)
        if not self._active:
            self._get_connection(index=index, check_ping=check_ping)
            if check_ping and not self._active:
                raise EsClientSearchException(EsClientSearchException.MESSAGE.format(error=_("EsClient链接失败")))

    @staticmethod
    def _get_meta_index(index: str):
        index_list: list = index.split(",")
        new_index_list = []
        for _index in index_list:
            # _index的格式兼容这些
            # 2_bklog.bkesb_container_20211207*
            # 2_bklog_bkesb_container_20211207*
            # 2_bklog.bkesb_container*
            # 2_bklog_bkesb_container*
            # 2_bklog.bkesb_container_*
            # 2_bklog_bkesb_container_*
            # 2_bklog_test_bklog_277*
            # 2_bklog.test_bklog_277*
            if "_%s." % settings.TABLE_ID_PREFIX in _index:
                tmp_index = _index
            else:
                tmp_index: str = _index.replace("_%s_" % settings.TABLE_ID_PREFIX, "_%s." % settings.TABLE_ID_PREFIX, 1)
            tmp_index = tmp_index.rstrip("_*")
            # 如果suffix是个日期，需要去掉后缀
            new_index, no_use, suffix = tmp_index.rpartition("_")  # pylint: disable=unused-variable
            if DATE_RE.match(suffix):
                new_index_list.append(new_index)
            else:
                new_index_list.append(tmp_index)
        return new_index_list[-1]

    def _get_connection(self, index: str, check_ping: bool = True):
        if not self.storage_cluster_id or self.storage_cluster_id == -1:
            _connect_info: tuple = self._connect_info(index=index)
        else:
            _connect_info: tuple = self._connect_info_by_storage_cluster_id(storage_cluster_id=self.storage_cluster_id)
        self.host, self.port, self.username, self.password, self.version, self.schema = _connect_info
        self._active: bool = False

        if not self.host or not self.port:
            raise EsClientConnectInfoException()

        es_socket_ping(host=self.host, port=self.port)

        logger.info(f"[esquery]get connection with {self.host}:{self.port} by {self.username}")

        self._client: Elasticsearch = get_es_client(
            version=self.version,
            hosts=[self.host],
            username=self.username,
            password=self.password,
            scheme=self.schema,
            port=self.port,
            sniffer_timeout=600,
            verify_certs=False,
        )
        # check_ping为False时，不检查ping
        if not check_ping or self._client.ping():
            self._active = True

    @cache_five_minute("_connect_info_{index}", need_md5=True)
    def _connect_info(self, index: str = "") -> tuple:
        transfer_api_response: dict = TransferApi.get_result_table_storage(
            {"result_table_list": index, "storage_type": "elasticsearch"}
        )

        if not transfer_api_response:
            raise EsClientMetaInfoException(
                EsClientMetaInfoException.MESSAGE.format(message=transfer_api_response.get("message"))
            )

        data: dict = transfer_api_response.get(index)
        return self._get_cluster_config(cluster_config=data.get("cluster_config"), auth_info=data.get("auth_info"))

    @cache_five_minute("_connect_info_{storage_cluster_id}", need_md5=True)
    def _connect_info_by_storage_cluster_id(self, storage_cluster_id: int) -> tuple:
        transfer_api_response: list = TransferApi.get_cluster_info({"cluster_id": storage_cluster_id})

        if not transfer_api_response:
            raise EsClientMetaInfoException(EsClientMetaInfoException.MESSAGE.format(message="meta_api_response error"))

        cluster_config: dict = transfer_api_response[0].get("cluster_config")
        return self._get_cluster_config(
            cluster_config=cluster_config, auth_info=transfer_api_response[0].get("auth_info")
        )

    @staticmethod
    def _get_cluster_config(cluster_config: dict, auth_info: dict):
        """
        提取存储集群配置信息
        """
        domain_name: str = cluster_config.get("domain_name")
        port: int = cluster_config.get("port")
        version: str = cluster_config.get("version")
        username: str = auth_info.get("username")
        password: str = auth_info.get("password")
        # 添加协议字段 由于是后添加的 所以放置在这个地方
        schema: str = cluster_config.get("schema") or DEFAULT_SCHEMA

        _es_password = password
        _es_host = domain_name
        _es_port = port
        _es_user = username
        _es_version = version
        _es_schema = schema

        return _es_host, _es_port, _es_user, _es_password, _es_version, _es_schema

    @classmethod
    def indices(cls, bk_biz_id, result_table_id=None, with_storage=False):
        """
        获取索引列表
        :param bk_biz_id:
        :param result_table_id:
        :param with_storage
        :return:
        """
        collect_obj = CollectorConfig.objects.filter(bk_biz_id=bk_biz_id).exclude(table_id=None)
        if result_table_id:
            collect_obj = collect_obj.filter(table_id=result_table_id)

        index_list = [
            {
                "bk_biz_id": _collect.bk_biz_id,
                "collector_config_id": _collect.collector_config_id,
                "result_table_id": _collect.table_id,
                "result_table_name_alias": _collect.collector_config_name,
            }
            for _collect in collect_obj
        ]

        # 补充索引集群信息
        if with_storage and index_list:
            indices = [_collect.table_id for _collect in collect_obj]
            storage_info = cls.bulk_cluster_infos(result_table_list=indices)
            for _index in index_list:
                cluster_config = storage_info.get(_index["result_table_id"], {}).get("cluster_config", {})
                _index.update(
                    {
                        "storage_cluster_id": cluster_config.get("cluster_id"),
                        "storage_cluster_name": cluster_config.get("cluster_name"),
                    }
                )
        return index_list

    @staticmethod
    @cache_five_minute("bulk_cluster_info_{result_table_list}", need_md5=True)
    def bulk_cluster_infos(result_table_list: list = None):
        multi_execute_func = MultiExecuteFunc()
        for rt in result_table_list:
            multi_execute_func.append(
                rt, TransferApi.get_result_table_storage, {"result_table_list": rt, "storage_type": "elasticsearch"}
            )
        result = multi_execute_func.run()
        cluster_infos = {}
        for _, cluster_info in result.items():  # noqa
            cluster_infos.update(cluster_info)
        return cluster_infos

    @cache_five_minute("get_cluster_info_{result_table_id}", need_md5=True)
    def get_cluster_info(self, result_table_id=None):
        result_table_id = result_table_id.split(",")[0]
        # 并发查询所需的配置
        multi_execute_func = MultiExecuteFunc()

        multi_execute_func.append(
            "result_table_config", TransferApi.get_result_table, params={"table_id": result_table_id}
        )
        multi_execute_func.append(
            "result_table_storage",
            TransferApi.get_result_table_storage,
            params={"result_table_list": result_table_id, "storage_type": "elasticsearch"},
        )

        result = multi_execute_func.run()
        if "result_table_config" not in result or "result_table_storage" not in result:
            raise IndexResultTableApiException()

        if result_table_id not in result["result_table_storage"]:
            raise IndexResultTableApiException(_("结果表不存在"))

        cluster_config = result["result_table_storage"][result_table_id].get("cluster_config")
        return {
            "bk_biz_id": result["result_table_config"]["bk_biz_id"],
            "storage_cluster_id": cluster_config.get("cluster_id"),
            "storage_cluster_name": cluster_config.get("cluster_name"),
        }
