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

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.dataflow.node.processor import RealTimeNode
from bkmonitor.dataflow.node.source import StreamSourceNode
from bkmonitor.dataflow.node.storage import TSpiderStorageNode
from bkmonitor.dataflow.task.base import BaseTask


class APMMetricAggregateFullNode(RealTimeNode):
    def __init__(self, from_result_table_id, bk_biz_id, app_name, parent):
        self.app_name = app_name
        self.from_result_table_id = from_result_table_id
        self.bk_biz_id = bk_biz_id
        self.parent_list = [parent]

    @property
    def name(self):
        return _("聚合指标计算")

    @property
    def table_name(self):
        """
        输出表名（不带业务ID前缀）
        """
        return f"bkapm_metric_{self.app_name}_agg"

    @property
    def config(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "sql": self._sql,
            "table_name": self.table_name,
            "name": self.name,
            "count_freq": 60,
            "waiting_time": 10,
            "window_type": "scroll",
            "counter": None,
            "output_name": self.table_name,
            "from_result_table_ids": [self.from_result_table_id],
        }

    @property
    def _sql(self):
        return f"""SELECT count(*) as bk_apm_count,
max(bk_apm_duration) as bk_apm_max_duration,
sum(bk_apm_duration) as bk_apm_sum_duration,
sum(IF(status_code='2', 1, 0)) as bk_apm_error_count,
sum(IF(apdex_type='frustrated', 1, 0)) as bk_apm_frustrated_count,
sum(IF(apdex_type='satisfied', 1, 0)) as bk_apm_satisfied_count,
sum(IF(apdex_type='tolerating', 1, 0)) as bk_apm_tolerating_count,
sum(IF(kind='2' OR kind='4', 1, 0)) as bk_apm_call_count,
sum(IF(kind='3' OR kind='5', 1, 0)) as bk_apm_request_count,
apdex_type,
bk_instance_id,
kind,
service_name,
span_name,
status_code,
telemetry_sdk_language,
telemetry_sdk_name,
telemetry_sdk_version,
target,
peer_service,
http_server_name,
http_method,
http_scheme,
http_flavor,
http_status_code,
rpc_method,
rpc_service,
rpc_system,
rpc_grpc_status_code,
db_name,
db_operation,
db_system,
messaging_system,
messaging_destination,
messaging_destination_kind,
celery_action,
celery_task_name
from {self.from_result_table_id}
GROUP BY
apdex_type,
bk_instance_id,
kind,
service_name,
span_name,
status_code,
telemetry_sdk_language,
telemetry_sdk_name,
telemetry_sdk_version,
target,
peer_service,
http_server_name,
http_method,
http_scheme,
http_flavor,
http_status_code,
rpc_method,
rpc_service,
rpc_system,
rpc_grpc_status_code,
db_name,
db_operation,
db_system,
messaging_system,
messaging_destination,
messaging_destination_kind,
celery_action,
celery_task_name"""


class APMMetricAvgAggFullNode(RealTimeNode):
    def __init__(self, from_result_table_id, bk_biz_id, app_name, parent):
        self.from_result_table_id = from_result_table_id
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.parent_list = [parent]

    @property
    def name(self):
        return _("平均值指标计算")

    @property
    def table_name(self):
        """
        输出表名（不带业务ID前缀）
        """
        return f"bkapm_metric_{self.app_name}_avg_agg"

    @property
    def config(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "sql": self._sql,
            "table_name": self.table_name,
            "name": self.name,
            "count_freq": 60,
            "waiting_time": 10,
            "window_type": "scroll",
            "counter": None,
            "output_name": self.table_name,
            "from_result_table_ids": [self.from_table_id],
        }

    @property
    def from_table_id(self):
        return f"{self.bk_biz_id}_{self.from_result_table_id}"

    @property
    def _sql(self):
        return f"""SELECT
(sum(bk_apm_sum_duration) / sum(bk_apm_count)) as bk_apm_avg_duration,
(sum(bk_apm_error_count) / sum(bk_apm_count)) as bk_apm_error_rate,
(cast((sum(bk_apm_satisfied_count)+sum(bk_apm_tolerating_count) * 0.5) AS DOUBLE)/sum(bk_apm_count)) as bk_apm_apdex,
apdex_type,
bk_instance_id,
kind,
service_name,
span_name,
status_code,
telemetry_sdk_language,
telemetry_sdk_name,
telemetry_sdk_version,
target,
peer_service,
http_server_name,
http_method,
http_scheme,
http_flavor,
http_status_code,
rpc_method,
rpc_service,
rpc_system,
rpc_grpc_status_code,
db_name,
db_operation,
db_system,
messaging_system,
messaging_destination,
messaging_destination_kind,
celery_action,
celery_task_name
from {self.from_table_id}
GROUP BY
apdex_type,
bk_instance_id,
kind,
service_name,
span_name,
status_code,
telemetry_sdk_language,
telemetry_sdk_name,
telemetry_sdk_version,
target,
peer_service,
http_server_name,
http_method,
http_scheme,
http_flavor,
http_status_code,
rpc_method,
rpc_service,
rpc_system,
rpc_grpc_status_code,
db_name,
db_operation,
db_system,
messaging_system,
messaging_destination,
messaging_destination_kind,
celery_action,
celery_task_name"""


class APMTspiderStorageNode(TSpiderStorageNode):
    def __init__(self, stuffix, bk_biz_id, app_name, indexed_fields, from_result_table_id, parent):
        self.indexed_fields = indexed_fields
        self.from_result_table_id = from_result_table_id
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.parent_list = [parent]
        self.suffix = stuffix
        self.storage = settings.APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE
        self.storage_expire = settings.APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE_EXPIRE

    @property
    def result_table_id(self):
        return f"{self.bk_biz_id}_bkapm_metric_{self.app_name}_{self.suffix}"

    @property
    def config(self):
        return {
            "name": f"{self.from_result_table_id}(tspider_storage)",
            "result_table_id": self.result_table_id,
            "bk_biz_id": self.bk_biz_id,
            "indexed_fields": self.indexed_fields,
            "cluster": self.storage,
            "expires": self.storage_expire,
            "from_result_table_ids": [self.result_table_id],
        }

    @property
    def name(self):
        return f"{self.from_result_table_id}(storage)"

    @property
    def output_table_name(self):
        return self.from_result_table_id


class APMVirtualMetricTask(BaseTask):
    """
    APM虚拟指标计算Flow
    """

    def __init__(self, result_table_id, bk_biz_id, app_name):
        super(APMVirtualMetricTask, self).__init__()
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.rt_id = result_table_id

        stream_source_node = StreamSourceNode(result_table_id)
        agg_calc_node = APMMetricAggregateFullNode(
            result_table_id, self.bk_biz_id, self.app_name, parent=stream_source_node
        )

        agg_storage = APMTspiderStorageNode(
            "agg",
            self.bk_biz_id,
            self.app_name,
            indexed_fields=[
                "apdex_type",
                "bk_instance_id",
                "kind",
                "service_name",
                "span_name",
                "status_code",
                "telemetry_sdk_language",
                "telemetry_sdk_name",
                "telemetry_sdk_version",
                "target",
                "peer_service",
                "http_server_name",
                "http_method",
                "http_scheme",
                "http_flavor",
                "http_status_code",
                "rpc_method",
                "rpc_service",
                "rpc_system",
                "rpc_grpc_status_code",
                "db_name",
                "db_operation",
                "db_system",
                "messaging_system",
                "messaging_destination",
                "messaging_destination_kind",
                "celery_action",
                "celery_task_name",
            ],
            from_result_table_id=agg_calc_node.table_name,
            parent=agg_calc_node,
        )

        agg_avg_calc_node = APMMetricAvgAggFullNode(
            agg_calc_node.table_name, self.bk_biz_id, self.app_name, parent=agg_calc_node
        )

        agg_avg_storage = APMTspiderStorageNode(
            "avg_agg",
            self.bk_biz_id,
            self.app_name,
            indexed_fields=[
                "apdex_type",
                "bk_instance_id",
                "kind",
                "service_name",
                "span_name",
                "status_code",
                "telemetry_sdk_language",
                "telemetry_sdk_name",
                "telemetry_sdk_version",
                "target",
                "peer_service",
                "http_server_name",
                "http_method",
                "http_scheme",
                "http_flavor",
                "http_status_code",
                "rpc_method",
                "rpc_service",
                "rpc_system",
                "rpc_grpc_status_code",
                "db_name",
                "db_operation",
                "db_system",
                "messaging_system",
                "messaging_destination",
                "messaging_destination_kind",
                "celery_action",
                "celery_task_name",
            ],
            from_result_table_id=agg_avg_calc_node.table_name,
            parent=agg_avg_calc_node,
        )

        self.node_list = [
            stream_source_node,
            agg_calc_node,
            agg_storage,
            agg_avg_calc_node,
            agg_avg_storage,
        ]

    @property
    def flow_name(self):
        return f"bkapm_metrics_{self.bk_biz_id}_{self.app_name}"
