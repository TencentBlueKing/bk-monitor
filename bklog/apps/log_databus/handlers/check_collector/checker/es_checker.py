# -*- coding: utf-8 -*-
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
import datetime
from datetime import timedelta
from typing import Any, Dict, List

from django.utils.translation import gettext as _

from apps.api import TransferApi
from apps.log_databus.constants import (
    INDEX_READ_SUFFIX,
    INDEX_WRITE_PREFIX,
    RETRY_TIMES,
)
from apps.log_databus.handlers.check_collector.checker.base_checker import Checker
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_esquery.utils.es_client import get_es_client
from apps.log_esquery.utils.es_route import EsRoute
from apps.log_measure.exceptions import EsConnectFailException
from apps.log_search.models import Scenario


def get_next_date(date_str: str, interval: int) -> str:
    """
    获取索引最新的分片, 根据索引分片的时间戳, 如果下一个分片是未来时间, 则返回当前索引分片的时间
    :param date_str: 日期字符串, 格式: %Y%m%d, 例如: 20210101
    :param interval: 时间间隔, 例如: 1
    :return: 下一时间间隔的日期, 例如: 20210102
    """
    date_format = "%Y%m%d"
    date_obj = datetime.datetime.strptime(date_str, date_format)
    now = datetime.datetime.now()
    next_date_obj = date_obj + timedelta(days=interval)
    if next_date_obj > now:
        return date_str
    return next_date_obj.strftime(date_format)


class EsChecker(Checker):
    CHECKER_NAME = "es checker"

    def __init__(self, table_id: str, bk_data_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_id = table_id
        self.bk_data_name = bk_data_name
        self.result_table = {}
        self.cluster_config = {}
        self.cluster_id = 0
        self.retention: int = 0
        # 物理索引列表
        self.indices = []
        self.es_client = None
        self.index_pattern = table_id.replace(".", "_")
        self.latest_date: str = ""

    def pre_run(self):
        try:
            result = TransferApi.get_result_table_storage(
                {"result_table_list": self.table_id, "storage_type": "elasticsearch"}
            )
            self.result_table = result.get(self.table_id, {})
            self.cluster_config = self.result_table.get("cluster_config", {})
            self.cluster_id = self.cluster_config.get("cluster_id", 0)
            self.retention = self.result_table.get("storage_config", {}).get("retention", 0)
        except Exception as e:
            self.append_error_info(_("[TransferApi] [get_result_table_storage] 失败, err: {e}").format(e=e))

    def _run(self):
        self.pre_run()
        self.get_es_client()
        self.get_indices()
        self.get_index_alias()

    def get_indices(self):
        """
        获取物理索引的名称
        """
        # 查该采集项的物理索引而不是该采集项所在集群的所有物理索引
        result: List[Dict[str, Any]] = EsRoute(scenario_id=Scenario.LOG, indices=self.table_id).cat_indices()
        self.indices = StorageHandler.sort_indices(result)

        if not self.indices:
            self.append_error_info(_("获取物理索引为空"))
            return
        for i in self.indices:
            self.append_normal_info(_("物理索引: {}, 健康: {}, 状态: {}").format(i["index"], i["health"], i["status"]))

        hot_node_count = 0
        for node in StorageHandler(self.cluster_id).cluster_nodes():
            if node.get("tag") == "hot":
                hot_node_count += 1

        latest_indices = self.indices[0]
        self.latest_date = latest_indices["index"].split("_")[-2]
        query_body = {"size": 1}
        query_data = self.es_client.search(index=latest_indices["index"], body=query_body)
        latest_data = query_data.get("hits", {}).get("hits", [])
        latest_data = latest_data[0] if latest_data else None
        self.append_normal_info(_("最近物理索引:{} 最新一条数据为:{}").format(latest_indices["index"], latest_data))

        if int(latest_indices["pri"]) < hot_node_count:
            self.append_warning_info(
                _("最近物理索引分片数量小于热节点分片数量, 可能会造成性能问题, 当前索引分片数{}, 热节点分片数{}").format(latest_indices["pri"], hot_node_count)
            )

    def get_es_client(self):
        es_client = None
        auth_info = self.result_table.get("auth_info", {})
        username = auth_info.get("username")
        password = auth_info.get("password")
        for i in range(RETRY_TIMES):
            try:
                es_client = get_es_client(
                    version=self.cluster_config["version"],
                    hosts=[self.cluster_config["domain_name"]],
                    username=username,
                    password=password,
                    scheme=self.cluster_config["schema"],
                    port=self.cluster_config["port"],
                    sniffer_timeout=600,
                    verify_certs=False,
                )
                if es_client is not None:
                    break
            except Exception as e:
                self.append_warning_info(_("创建es_client失败第{cnt}次, err: {e}").format(cnt=i + 1, e=e))

        if es_client and not es_client.ping(params={"request_timeout": 10}):
            self.append_error_info(EsConnectFailException().message)
            return

        self.es_client = es_client

    def get_index_alias(self):
        """获取物理索引的alias情况"""
        if not self.es_client:
            self.append_error_info(_("es_client不存在, 跳过检查index_alias"))
            return
        index_alias_info_dict = self.es_client.indices.get_alias(index=[i["index"] for i in self.indices])

        now_datetime = get_next_date(date_str=self.latest_date, interval=self.retention)

        now_read_index_alias = "{}_{}{}".format(self.index_pattern, now_datetime, INDEX_READ_SUFFIX)
        now_write_index_alias = "{}{}_{}".format(INDEX_WRITE_PREFIX, now_datetime, self.index_pattern)

        for i in self.indices:
            # index 物理索引名
            physical_index = i["index"]
            aliases = index_alias_info_dict.get(physical_index, {}).get("aliases", {})
            if not aliases:
                self.append_error_info(_("物理索引: {physical_index} 不存在alias别名").format(physical_index=physical_index))
                continue

            if physical_index.startswith(INDEX_WRITE_PREFIX):
                self.append_warning_info(
                    _("集群存在 write_ 开头的索引: \n{physical_index}").format(physical_index=physical_index)
                )
                return

            if now_read_index_alias in aliases and now_write_index_alias in aliases:
                self.append_normal_info(
                    _("索引: [{index_pattern}] 当天[{now_datetime}]读写别名已成功创建").format(
                        index_pattern=self.index_pattern, now_datetime=now_datetime
                    )
                )
                return

        if self.index_pattern:
            self.append_error_info(
                _("索引: [{index_pattern}] 当天[{now_datetime}]读写别名未成功创建").format(
                    index_pattern=self.index_pattern, now_datetime=now_datetime
                )
            )
