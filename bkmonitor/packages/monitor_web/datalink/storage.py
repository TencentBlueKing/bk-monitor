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

import copy
import json
import time
from typing import Dict, List, Optional, Tuple

import humanize
from django.utils.translation import gettext_lazy as _
from typing_extensions import TypedDict

from common.log import logger
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.errors.datalink import ResultTableMetaError


def get_storager(table_id):
    """构建函数，返回结果表对应的存储对象"""
    details = api.metadata.query_result_table_storage_detail(table_id=table_id)
    if len(details) == 0:
        raise ResultTableMetaError("No table({}) metadata".format(table_id))

    detail = details[0]
    # 自动判定主入库存储信息
    if "victoria_metrics" in detail and detail["victoria_metrics"]:
        return VictoriaMetricsStorage(detail=detail)
    elif "influxdb" in detail and detail["influxdb"]:
        return InfluxdbStorager(detail=detail)
    elif "elasticsearch" in detail and detail["elasticsearch"]:
        return EsStorage(detail=detail)

    raise ResultTableMetaError("No valid storage in table: {}".format(table_id))


InfoElement = TypedDict("InfoElement", {"key": str, "name": str, "value": str})

StatusContentKey = TypedDict("StatusContentKey", {"key": str, "name": str})
StatusContentVal = Dict[str, str]
StatusContent = TypedDict("StatusContent", {"keys": List, "values": List})
StatusElement = TypedDict("StatusElement", {"key": str, "name": str, "content": StatusContent})


class Storager:
    INFO_TMP: List[InfoElement] = []
    STATUS_TMP: List[StatusElement] = []

    def __init__(self, detail: Dict):
        self.detail = detail

    def get_info(self) -> List[InfoElement]:
        """读取存储基本元信息"""
        info = copy.deepcopy(self.INFO_TMP)
        for item in info:
            custom_handler = f"handle_info_{item['key']}"
            if not hasattr(self, custom_handler):
                continue
            item["value"] = getattr(self, custom_handler)()
        return info

    def get_status(self) -> List[StatusContent]:
        """读取存储状态"""
        status = copy.deepcopy(self.STATUS_TMP)
        for s in status:
            custom_handler = f"handle_status_{s['key']}"
            if not hasattr(self, custom_handler):
                continue
            s["content"] = getattr(self, custom_handler)(s["content"])
        return status


class InfluxdbStorager(Storager):
    INFO_TMP: List[InfoElement] = [
        {"key": "storage_type", "name": _("存储类型"), "value": "InfluxDB"},
        {"key": "cluster_name", "name": _("Proxy集群"), "value": ""},
        {"key": "instance_cluster_name", "name": _("实例集群"), "value": ""},
        {"key": "cluster_instance_num", "name": _("存储实例数"), "value": ""},
    ]

    STATUS_TMP: List[StatusElement] = [
        {
            "key": "instance",
            "name": _("存储实例"),
            "content": {
                "keys": [
                    {"key": "host_name", "name": _("主机实例")},
                    {"key": "influxdb_httpd_req_1h_increase", "name": _("服务端请求数(近1小时)")},
                    {"key": "influxdb_httpd_server_error_1h_increase", "name": _("服务端错误数(近1小时)")},
                    {"key": "influxdb_runtime_sys", "name": _("内存占用量")},
                ],
                "values": [],
            },
        },
        {
            "key": "database",
            "name": _("数据库"),
            "content": {
                "keys": [
                    {"key": "database", "name": _("库名")},
                    {"key": "influxdb_shard_write_points_ok_1h_increase", "name": _("写入成功点数(近1小时)")},
                    {"key": "influxdb_shard_write_point_err_1h_increase", "name": _("写入失败点数(近1小时)")},
                    {"key": "influxdb_shard_disk_bytes", "name": _("磁盘占用量")},
                    {"key": "influxdb_database_num_series", "name": _("Series数量")},
                ],
                "values": [],
            },
        },
    ]

    def __init__(self, detail: Dict):
        super().__init__(detail=detail)

    def handle_info_cluster_name(self) -> str:
        return self.detail["influxdb"]["cluster_config"]["cluster_name"]

    def handle_info_instance_cluster_name(self) -> str:
        return self.detail["influxdb"]["cluster_config"]["instance_cluster_name"]

    def handle_info_cluster_instance_num(self) -> str:
        return str(len(self.detail["influxdb_instance_cluster"]))

    def handle_info_is_default_cluster(self) -> str:
        return _("是") if self.detail["influxdb"]["cluster_config"]["is_default_cluster"] else _("否")

    def handle_status_instance(self, content: StatusContent) -> StatusContent:
        keys = content["keys"]
        hosts = self.detail["influxdb_instance_cluster"]
        values: List[StatusContentVal] = []
        for host in hosts:
            host_name = host["host_name"]
            val: StatusContentVal = {}
            for key in keys:
                key_name = key["key"]
                if key_name == "host_name":
                    val["host_name"] = host_name
                    continue
                custom_handler = f"handle_status_instance_{key_name}"
                val[key_name] = getattr(self, custom_handler)(host_name) if hasattr(self, custom_handler) else ""
            values.append(val)
        content["values"] = values
        return content

    def handle_status_instance_influxdb_httpd_req_1h_increase(self, host_name: str) -> str:
        ret = self._query_cluster_metric(
            "influxdb_httpd_req_1h_increase",
            bkm_cluster=self.handle_info_instance_cluster_name(),
            bkm_hostname=host_name,
        )
        return humanize.intcomma(ret[1]) if ret is not None else "-"

    def handle_status_instance_influxdb_httpd_server_error_1h_increase(self, host_name: str) -> str:
        ret = self._query_cluster_metric(
            "influxdb_httpd_server_error_1h_increase",
            bkm_cluster=self.handle_info_instance_cluster_name(),
            bkm_hostname=host_name,
        )
        return humanize.intcomma(ret[1]) if ret is not None else "-"

    def handle_status_instance_influxdb_runtime_sys(self, host_name: str) -> str:
        ret = self._query_cluster_metric(
            "influxdb_runtime_sys", bkm_cluster=self.handle_info_instance_cluster_name(), bkm_hostname=host_name
        )
        return humanize.naturalsize(ret[1]) if ret is not None else "-"

    def handle_status_database(self, content: StatusContent) -> StatusContent:
        keys = content["keys"]
        database = self.detail["influxdb"]["storage_config"]["database"]
        val: StatusContentVal = {}
        for key in keys:
            key_name = key["key"]
            if key_name == "database":
                val["database"] = database
                continue
            custom_handler = f"handle_status_database_{key_name}"
            val[key_name] = getattr(self, custom_handler)(database) if hasattr(self, custom_handler) else ""
        content["values"] = [val]
        return content

    def handle_status_database_influxdb_shard_write_points_ok_1h_increase(self, database: str):
        ret = self._query_cluster_metric(
            "influxdb_shard_write_points_ok_1h_increase",
            bkm_cluster=self.handle_info_instance_cluster_name(),
            database=database,
        )
        return humanize.intcomma(ret[1]) if ret is not None else "-"

    def handle_status_database_influxdb_shard_write_point_err_1h_increase(self, database: str):
        ret = self._query_cluster_metric(
            "influxdb_shard_write_points_err_1h_increase",
            bkm_cluster=self.handle_info_instance_cluster_name(),
            database=database,
        )
        return humanize.intcomma(ret[1]) if ret is not None else "-"

    def handle_status_database_influxdb_shard_disk_bytes(self, database: str):
        ret = self._query_cluster_metric(
            "influxdb_shard_disk_bytes", bkm_cluster=self.handle_info_instance_cluster_name(), database=database
        )
        return humanize.naturalsize(ret[1]) if ret is not None else "-"

    def handle_status_database_influxdb_database_num_series(self, database: str):
        ret = self._query_cluster_metric(
            "influxdb_database_num_series", bkm_cluster=self.handle_info_instance_cluster_name(), database=database
        )
        return humanize.intcomma(ret[1]) if ret is not None else "-"

    def _query_cluster_metric(self, metric_name: str, **conditions) -> Optional[Tuple[int, int]]:
        """查询集群指标"""
        body = {
            "query_list": [
                {
                    "data_source": "",
                    "table_id": "",
                    "field_name": metric_name,
                    "field_list": None,
                    "function": [
                        {
                            "method": "sum",
                            "without": False,
                            "dimensions": [],
                            "position": 0,
                            "args_list": None,
                            "vargs_list": None,
                        }
                    ],
                    "time_aggregation": {
                        "function": "sum_over_time",
                        "window": "60s",
                        "position": 0,
                        "vargs_list": None,
                    },
                    "reference_name": "a",
                    "dimensions": [],
                    "limit": 0,
                    "timestamp": None,
                    "start_or_end": 0,
                    "vector_offset": 0,
                    "offset": "",
                    "offset_forward": False,
                    "slimit": 0,
                    "soffset": 0,
                    "conditions": {},
                    "keep_columns": ["_time", "a"],
                }
            ],
            "metric_merge": "a",
            "result_columns": None,
            "end_time": int(time.time()),
            "instant": True,
        }
        field_list = [{"field_name": cond[0], "value": [cond[1]], "op": "eq"} for cond in conditions.items()]
        condition_list = ["and"] * (len(conditions) - 1)
        body["query_list"][0]["conditions"]["field_list"] = field_list
        body["query_list"][0]["conditions"]["condition_list"] = condition_list
        try:
            logger.info("Query cluster metrics, body = {}".format(json.dumps(body)))
            ret = api.unify_query.query_cluster_metrics_data(**body)
        except BKAPIError as err:
            logger.exception("Fail to query cluster metrics, body={}, err={}".format(body, err))
            return None
        if len(ret["series"]) > 0:
            return ret["series"][0]["values"][0]
        return None


class VictoriaMetricsStorage(Storager):
    INFO_TMP: List[InfoElement] = [
        {"key": "storage_type", "name": _("存储类型"), "value": "VictoriaMetrics"},
        {"key": "vm_result_table_id", "name": _("计算平台结果表"), "value": ""},
    ]

    def handle_info_vm_result_table_id(self):
        return self.detail["victoria_metrics"]["vm_result_table_id"]


class EsStorage(Storager):
    INFO_TMP: List[InfoElement] = [
        {"key": "storage_type", "name": _("存储类型"), "value": "ElasticSearch"},
        {"key": "cluster_name", "name": _("集群名"), "value": ""},
        {"key": "result_table", "name": _("结果表"), "value": ""},
    ]

    def handle_info_cluster_name(self):
        return "{}({})".format(
            self.detail["elasticsearch"]["cluster_config"]["cluster_name"],
            self.detail["elasticsearch"]["cluster_config"]["domain_name"],
        )

    def handle_info_result_table(self):
        return self.detail["result_table"]["table_id"]
