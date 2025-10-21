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
import logging
from collections import defaultdict
from datetime import UTC, datetime

import pytz
from django.conf import settings
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from bkmonitor.utils.time_tools import time_interval_align
from constants.apm import TelemetryDataType
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import (
    DATA_LINK_V4_VERSION_NAME,
    DataSourceLabel,
    DataTypeLabel,
)
from core.drf_resource import api, resource

logger = logging.getLogger("apm")


def handler_name(handler_cls: type):
    return str(handler_cls.__name__).split("BackendHandler")[0].lower()


class BackendRegistry:
    """
    后端适配器注册表
    """

    def __init__(self):
        self.registry = {}

    def register(self, adapter_cls):
        adapter_name = handler_name(adapter_cls)
        if adapter_name:
            self.registry[adapter_name] = adapter_cls
            return self.registry[adapter_name]
        return None

    def __call__(self, adapter_name, **kwargs):
        adapter_cls = self.registry[adapter_name]
        return adapter_cls(**kwargs)


class TelemetryBackendHandler:
    """后台数据适配器"""

    CALL_BACK_PARAMS_FRAME = {
        "id": 1,
        "title": "title",
        "type": "graph",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
        "targets": [],
        "options": {"time_series": {}},
    }

    GRAIN_MAPPING = {
        "1m": 60,
        "1d": 60 * 60 * 24,
    }

    def __init__(self, app, *args, **kwargs):
        self.app = app
        self.telemetry: TelemetryDataType = TelemetryDataType(handler_name(self.__class__))

    @cached_property
    def bk_data_id(self):
        return self.app.fetch_datasource_info(self.telemetry.datasource_type, attr_name="bk_data_id")

    @cached_property
    def result_table_id(self):
        return self.app.fetch_datasource_info(self.telemetry.datasource_type, attr_name="result_table_id")

    @classmethod
    def build_call_back_target(cls, data_type_label, data_source_label, **kwargs) -> dict:
        table_name = kwargs.get("table_name", "__default__")
        metric_field = kwargs.get("metric_field", "bk_apm_count")
        method_method = kwargs.get("method_method", "COUNT")
        grain = kwargs.pop("grain", "1m")
        query_config_kwargs = kwargs.pop("query_config_kwargs", {})
        target = {
            "data_type": "time_series",
            "datasource": "time_series",
            "api": "grafana.graphUnifyQuery",
            "data": {
                "expression": "A",
                "query_configs": [
                    {
                        "data_source_label": data_source_label,
                        "data_type_label": data_type_label,
                        "table": table_name,
                        "metrics": [{"field": metric_field, "method": method_method, "alias": "A"}],
                        "group_by": [],
                        "display": True,
                        "where": [],
                        "interval": cls.GRAIN_MAPPING[grain],
                        "interval_unit": "s",
                        "time_field": "time",
                        "filter_dict": {},
                        "functions": [],
                    }
                ],
            },
        }
        if query_config_kwargs:
            for query_config in target["data"]["query_configs"]:
                query_config.update(query_config_kwargs)
        target["data"].update(kwargs)
        return target

    @classmethod
    def build_data_count_query(cls, **kwargs):
        templates = []
        for idx, grain_config in enumerate([(_("分钟数据量"), "1m", None, 0, 0), (_("日数据量"), "1d", "bar", 12, 0)]):
            title, grain, display_type, x_pos, y_pos = grain_config
            kwargs["grain"] = grain
            _id = idx + 1
            template = copy.deepcopy(cls.CALL_BACK_PARAMS_FRAME)
            template["id"] = _id
            template["title"] = title
            template["gridPos"]["x"] = x_pos
            template["gridPos"]["y"] = y_pos
            template["options"]["collect_interval_display"] = grain
            if display_type:
                template["options"]["time_series"]["type"] = display_type
            target = cls.build_call_back_target(**kwargs)
            template["targets"] = [target]
            templates.append(template)
        return templates


"""
观测数据后端适配器注册表
"""
telemetry_handler_registry = BackendRegistry()


@telemetry_handler_registry.register
class TraceBackendHandler(TelemetryBackendHandler):
    """
    跟踪后端适配器
    """

    TIME_FORMAT_LEN = 11

    @cached_property
    def metric_result_table_id(self):
        return self.app.fetch_datasource_info("metric", attr_name="result_table_id")

    def storage_info(self):
        datasource_config = self.app.get_config_by_key(self.app.APPLICATION_DATASOURCE_CONFIG_KEY).config_value
        if "es_shards" not in datasource_config:
            indices_data = self.indices_info()
            if indices_data:
                shards_count = indices_data[0]["pri"]
                datasource_config = {**datasource_config, "es_shards": shards_count}
        return datasource_config

    def storage_field_info(self):
        # 获取字段信息
        field_data = api.apm_api.query_fields({"bk_biz_id": self.app.bk_biz_id, "app_name": self.app.app_name})
        # 获取字段描述信息
        table_data = api.metadata.get_result_table({"table_id": self.app.trace_result_table_id}).get("field_list", [])
        field_desc_data = {field_info["field_name"]: field_info["description"] for field_info in table_data}
        # 构造响应信息
        return [
            {
                "field_name": key,
                "ch_field_name": field_desc_data.get(key, ""),
                "analysis_field": value == "text",
                "field_type": value,
                "time_field": value == "date",
            }
            for key, value in field_data.items()
        ]

    @property
    def storage_status(self):
        indices = self.indices_info() or [{}]
        return all([idx.get("health") == "green" for idx in indices])

    def indices_info(self):
        es_index_name = self.result_table_id.replace(".", "_")
        data = api.metadata.es_route(
            {
                "es_storage_cluster": self.app.es_storage_cluster,
                "url": f"_cat/indices/{es_index_name}_*_*?bytes=b&format=json",
            }
        )
        result = []
        for item in data:
            __, index_name = item["index"].split("v2_", 1)
            __, index_name_time = index_name.split(es_index_name)
            if len(index_name_time) != self.TIME_FORMAT_LEN:
                continue
            result.append({k.replace(".", "_"): v for k, v in item.items()})
        return result

    def data_sampling(self, size: int = 10, **kwargs):
        resp = api.metadata.kafka_tail({"table_id": self.result_table_id, "size": size}) if self.result_table_id else []
        return [{"raw_log": log, "sampling_time": log.get("datetime", "")} for log in resp]

    def get_data_view_config(self, **kwargs):
        view_params = {
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "data_source_label": DataSourceLabel.CUSTOM,
            "table_name": self.metric_result_table_id,
            "metric_field": "bk_apm_count",
            "method_method": "SUM",
        }
        kwargs.update(view_params)
        return self.build_data_count_query(
            **kwargs,
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        view_config = self.get_data_view_config(
            start_time=start_time, end_time=end_time, bk_biz_id=self.app.bk_biz_id, **kwargs
        )
        data = resource.grafana.graph_unify_query(view_config[0]["targets"][0]["data"])
        count = 0
        for line in data["series"]:
            for point in line["datapoints"]:
                point_count = point[0] if isinstance(point[0], int) else 0
                count += point_count
        return count

    def get_no_data_strategy_config(self, **kwargs):
        promql = (
            f'sum(sum_over_time({{__name__="custom:{self.metric_result_table_id}:bk_apm_count"}}[1m])) or vector(0)'
        )
        return {
            "result_table_id": self.result_table_id,
            "metric_id": promql,
            "metric_field": "bk_apm_count",
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "promql": promql,
                    "agg_interval": 60,
                    "alias": "a",
                }
            ],
        }


@telemetry_handler_registry.register
class LogBackendHandler(TelemetryBackendHandler):
    """
    日志后端适配器
    """

    @cached_property
    def collector_config_id(self):
        return self.app.fetch_datasource_info(self.telemetry.datasource_type, attr_name="collector_config_id")

    @cached_property
    def index_set_id(self):
        return self.app.fetch_datasource_info(self.telemetry.datasource_type, attr_name="index_set_id")

    def storage_info(self):
        resp = api.log_search.data_bus_collectors(collector_config_id=self.collector_config_id)
        return {
            "es_number_of_replicas": resp["storage_replies"],
            "es_retention": resp["retention"],
            "es_shards": resp["storage_shards_nums"],
            "es_slice_size": resp["storage_shards_size"],
            "es_storage_cluster": resp["storage_cluster_id"],
            "display_storage_cluster_name": resp["storage_cluster_name"],
            "display_es_storage_index_name": f"{resp['table_id_prefix']}{resp['table_id']}",
            "display_index_split_rule": resp["index_split_rule"],
        }

    def storage_field_info(self):
        res_data = api.log_search.log_search_index_set(index_set_id=self.index_set_id)
        fields = []
        for field in res_data.get("fields"):
            fields.append(
                {
                    "field_name": field["field_name"],
                    "ch_field_name": field["field_alias"],
                    "analysis_field": field["is_analyzed"],
                    "field_type": field["field_type"],
                    "time_field": True if field["field_name"] == res_data.get("time_field") else False,
                }
            )
        return fields

    @property
    def storage_status(self):
        indices = self.indices_info() or [{}]
        return all([idx.get("health") == "green" for idx in indices])

    def indices_info(self):
        data = api.log_search.data_bus_collectors_indices(collector_config_id=self.collector_config_id)
        result = []
        for item in data:
            result.append({key.replace(".", "_"): value for key, value in item.items()})
        return result

    def data_sampling(self, size: int = 10, **kwargs):
        resp = api.metadata.kafka_tail({"table_id": self.result_table_id, "size": size}) if self.result_table_id else []
        return [{"raw_log": log, "sampling_time": log.get("datetime", "")} for log in resp]

    def get_data_view_config(self, **kwargs):
        view_params = {
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
            "table_name": self.result_table_id,
            "metric_field": "_index",
            "method_method": "COUNT",
            "query_config_kwargs": {"index_set_id": self.index_set_id},
        }
        kwargs.update(view_params)
        return self.build_data_count_query(
            **kwargs,
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        view_config = self.get_data_view_config(
            start_time=start_time, end_time=end_time, bk_biz_id=self.app.bk_biz_id, **kwargs
        )
        data = resource.grafana.graph_unify_query(view_config[0]["targets"][0]["data"])
        count = 0
        for line in data["series"]:
            for point in line["datapoints"]:
                point_count = point[0] if isinstance(point[0], int) else 0
                count += point_count
        return count

    def get_no_data_strategy_config(self, **kwargs):
        table_id = self.result_table_id.replace(".", ":")
        promql = f'sum(count_over_time({{__name__="bklog:{table_id}:_index"}}[1m])) or vector(0)'
        return {
            "result_table_id": self.result_table_id,
            "metric_id": promql,
            "metric_field": "_index",
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "promql": promql,
                    "agg_interval": 60,
                    "alias": "a",
                }
            ],
        }


@telemetry_handler_registry.register
class MetricBackendHandler(TelemetryBackendHandler):
    """
    指标后端适配器
    """

    @cached_property
    def bk_base_data_info(self) -> dict:
        # Todo: APM_APPLY 临时方案，待接口支持
        from metadata import models

        ret = {}
        vm_record = models.AccessVMRecord.objects.filter(result_table_id=self.result_table_id).first()
        if vm_record:
            ret["data_id"] = vm_record.bk_base_data_id
            ret["vm_result_table_id"] = vm_record.vm_result_table_id
            ret["vm_cluster_id"] = vm_record.vm_cluster_id
        return ret

    @cached_property
    def datalink_version(self):
        from metadata import models

        result_table = models.ResultTable.objects.filter(table_id=self.result_table_id).first()
        return result_table.data_source.datalink_version if result_table else DATA_LINK_V4_VERSION_NAME

    @cached_property
    def data_status_config(self):
        return settings.APM_V4_METRIC_DATA_STATUS_CONFIG or {}

    @property
    def bk_base_data_id(self):
        bk_base_data_id = self.bk_base_data_info.get("data_id")
        return bk_base_data_id if isinstance(bk_base_data_id, int) and bk_base_data_id > 0 else None

    @property
    def bk_vm_result_table_id(self):
        return self.bk_base_data_info.get("vm_result_table_id")

    def storage_info(self):
        vm_cluster_id = self.bk_base_data_info.get("vm_cluster_id")
        if settings.ENABLE_MULTI_TENANT_MODE and vm_cluster_id:
            from metadata import models

            cluster_name = ""
            cluster_obj = models.ClusterInfo.objects.filter(cluster_id=vm_cluster_id).first()
            if cluster_obj:
                cluster_name = cluster_obj.cluster_name
            return [
                {
                    "raw_data_id": self.bk_base_data_id,
                    "bk_biz_id": self.app.bk_biz_id,
                    "result_table_id": self.bk_vm_result_table_id,
                    "storage_type": "vm",
                    "storage_type_alias": "",
                    "storage_cluster": vm_cluster_id,
                    "storage_cluster_alias": cluster_name,
                    "expire_time": "30d",
                    "expire_time_alias": _("30天"),
                    "status": "running",
                    "status_display": _("运行中"),
                    "created_at": "system",
                    "created_by": "system",
                }
            ]

        storage_info = []
        result_table = api.bkdata.get_result_table(result_table_id=self.bk_vm_result_table_id)
        storage = result_table.get("storages", {}).get("vm")
        if storage:
            try:
                expire_info = json.loads(storage.get("storage_cluster", {}).get("expires", "{}"))
                list_expire = expire_info.get("list_expire", [])
            except Exception:  # pylint: disable=broad-except
                list_expire = []
            expire = list_expire[0] if list_expire else {}
            ret_storage = {
                "raw_data_id": self.bk_base_data_id,
                "bk_biz_id": self.app.bk_biz_id,
                "result_table_id": self.bk_vm_result_table_id,
                "storage_type": "vm",
                "storage_type_alias": "",
                "storage_cluster": storage.get("storage_cluster", {}).get("storage_cluster_config_id"),
                "storage_cluster_alias": storage.get("storage_cluster", {}).get("cluster_name"),
                "expire_time": expire.get("value", "30d"),
                "expire_time_alias": expire.get("name", _("30天")),
                "status": "running",
                "status_display": _("运行中"),
                "created_at": storage["created_at"],
                "created_by": storage["created_by"],
            }
            storage_info.append(ret_storage)
        return storage_info

    @property
    def storage_status(self):
        storages = self.storage_info() or [{}]
        return all([storage.get("status") == "running" for storage in storages])

    def data_sampling(self, size: int = 10, **kwargs):
        # 指定时区
        target_timezone = pytz.timezone(settings.TIME_ZONE)
        resp = api.metadata.kafka_tail({"table_id": self.result_table_id, "size": size}) if self.result_table_id else []
        sampling_log_response = []
        for log in resp:
            log_data = log.get("data", [])
            formatted_time_with_colon = None
            for log_record in log_data:
                if "timestamp" not in log_record:
                    continue
                timestamp_s = log_record["timestamp"] / 1000
                localized_dt = datetime.fromtimestamp(timestamp_s, UTC).astimezone(target_timezone)
                # 格式化为指定的字符串格式
                formatted_time = localized_dt.strftime("%Y-%m-%d %H:%M:%S%z")
                formatted_time_with_colon = f"{formatted_time[:-2]}:{formatted_time[-2:]}"
                if formatted_time_with_colon:
                    break
            sampling_log_response.append({"raw_log": log, "sampling_time": formatted_time_with_colon})
        return sampling_log_response

    def get_data_view_config(self, **kwargs):
        view_params = {
            "application_id": self.app.application_id,
            "telemetry_data_type": self.telemetry.value,
        }
        kwargs.update(view_params)
        return self.build_data_count_query(
            **kwargs,
        )

    @classmethod
    def build_call_back_target(cls, application_id, telemetry_data_type, **kwargs) -> dict:
        grain = kwargs.pop("grain", "1m")
        target = {
            "data_type": "data_type_label",
            "datasource": "data_source_label",
            "api": "apm_meta.dataHistogram",
            "primary_key": application_id,
            "data": {
                "telemetry_data_type": telemetry_data_type,
                "data_view_config": {"grain": grain},
            },
        }
        if kwargs:
            data_view_config = target["data"]["data_view_config"]
            data_view_config.update(kwargs)
        return target

    def _get_data_view(self, start_time: int, end_time: int, **kwargs):
        if self.datalink_version == DATA_LINK_V4_VERSION_NAME:
            namespace = self.data_status_config.get("namespace", "bkmonitor-vm")
            metric_biz_id = self.data_status_config.get("metric_biz_id")
            if not metric_biz_id:
                return []

            if not self.bk_vm_result_table_id:
                return []

            # 多租户适配
            tenant_prefix = "" if self.app.bk_tenant_id == DEFAULT_TENANT_ID else f"{self.app.bk_tenant_id}-"

            # v3迁移到v4链路的规则
            component_id_prefix = f"{namespace}_{self.bk_vm_result_table_id}-"

            # 监控自建v4链路规则
            databus_name = "_".join(self.bk_vm_result_table_id.split("_")[1:])
            v4_component_id_prefix = f"bkmonitor-{databus_name}-"

            grain = kwargs.get("time_grain", "1m")

            # 时间对齐
            start_time = time_interval_align(timestamp=start_time, interval=self.GRAIN_MAPPING[grain])
            end_time = time_interval_align(timestamp=end_time, interval=self.GRAIN_MAPPING[grain])

            request_params = dict(
                # 数据存储在运营租户下
                bk_tenant_id=DEFAULT_TENANT_ID,
                promql=f'sum(increase(bkmonitor:record_count{{component_id=~"^{tenant_prefix}({component_id_prefix}|{v4_component_id_prefix})"}}[{grain}]))',
                start=start_time,
                end=end_time,
                step=grain,
                bk_biz_ids=[metric_biz_id],
                timezone=timezone.get_current_timezone_name(),
            )

            series = api.unify_query.query_data_by_promql(**request_params)["series"]

            # 讲同一个timestamp的count相加
            timestamp_to_count = defaultdict(int)
            for serie in series:
                for datapoint in serie["values"]:
                    timestamp_to_count[datapoint[0]] += datapoint[1]

            resp = [
                {
                    "series": [
                        {"output_count": count, "time": int(timestamp / 1000)}
                        for timestamp, count in timestamp_to_count.items()
                    ]
                }
            ]
        else:
            storages = self.storage_info()
            storage_result_table_id = None
            for storage in storages:
                if storage["storage_type"] == "vm":
                    storage_result_table_id = storage["result_table_id"]
                    break
            resp = (
                api.bkdata.get_storage_metrics_data_count(
                    data_set_ids=[storage_result_table_id],
                    storages=["vm"],
                    start_time=start_time,
                    end_time=end_time,
                    **kwargs,
                )
                if storage_result_table_id
                else []
            )
        return resp

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        resp = self._get_data_view(start_time, end_time, **kwargs)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point.get("output_count"):
                    point_count = point["output_count"] if isinstance(point["output_count"], int) else 0
                    count += point_count
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self._get_data_view(start_time, end_time, time_grain=grain)
        datapoints = (
            [[view_series["output_count"], view_series["time"] * 1000] for view_series in resp[0]["series"]]
            if resp
            else []
        )
        histograms = {
            "metrics": [],
            "series": [
                {
                    "target": "COUNT(rawdata)",
                    "metric_field": "_result",
                    "alias": "_result_",
                    "type": "bar",
                    "unit": "",
                    "dimensions": {},
                    "dimensions_translation": {},
                    "datapoints": datapoints,
                }
            ]
            if datapoints
            else [],
        }
        return histograms

    def get_no_data_strategy_config(self, **kwargs):
        promql = f'count({{__name__=~"custom:{self.result_table_id}:.*",__name__!~"^(apm|bk_apm).*"}}) or vector(0)'
        return {
            "result_table_id": self.result_table_id,
            "metric_id": promql,
            "metric_field": None,
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "promql": promql,
                    "agg_interval": 60,
                    "alias": "a",
                }
            ],
        }


@telemetry_handler_registry.register
class ProfilingBackendHandler(TelemetryBackendHandler):
    """
    性能分析后端适配器
    """

    def storage_info(self):
        return api.bkdata.get_raw_data_storages_info(raw_data_id=self.bk_data_id) if self.bk_data_id else []

    @property
    def storage_status(self):
        storages = self.storage_info() or [{}]
        return all([storage.get("status") == "running" for storage in storages])

    def data_sampling(self, **kwargs):
        resp_data = []
        if self.bk_data_id:
            resp = api.bkdata.get_data_bus_sampling_data(data_id=self.bk_data_id)
            for log in resp:
                log_content = json.loads(log["value"])
                resp_data.append({"raw_log": log_content, "sampling_time": ""})
        return resp_data

    def get_data_view_config(self, **kwargs):
        view_params = {
            "application_id": self.app.application_id,
            "telemetry_data_type": self.telemetry.value,
        }
        kwargs.update(view_params)
        return self.build_data_count_query(
            **kwargs,
        )

    @classmethod
    def build_call_back_target(cls, application_id, telemetry_data_type, **kwargs) -> dict:
        grain = kwargs.pop("grain", "1m")
        target = {
            "data_type": "data_type_label",
            "datasource": "data_source_label",
            "api": "apm_meta.dataHistogram",
            "primary_key": application_id,
            "data": {
                "telemetry_data_type": telemetry_data_type,
                "data_view_config": {"grain": grain},
            },
        }
        if kwargs:
            data_view_config = target["data"]["data_view_config"]
            data_view_config.update(kwargs)
        return target

    def _get_data_view(self, start_time: int, end_time: int, **kwargs):
        storages = self.storage_info()
        storage_result_table_id = None
        for storage in storages:
            if storage["storage_type"] == "doris":
                storage_result_table_id = storage["result_table_id"]
                break
        return (
            api.bkdata.get_storage_metrics_data_count(
                data_set_ids=[storage_result_table_id],
                storages=["doris"],
                start_time=start_time,
                end_time=end_time,
                **kwargs,
            )
            if storage_result_table_id
            else []
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        resp = self._get_data_view(start_time, end_time, **kwargs)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point.get("output_count"):
                    point_count = point["output_count"] if isinstance(point["output_count"], int) else 0
                    count += point_count
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self._get_data_view(start_time, end_time, time_grain=grain)
        datapoints = (
            [[view_series["output_count"], view_series["time"] * 1000] for view_series in resp[0]["series"]]
            if resp
            else []
        )
        histograms = {
            "metrics": [],
            "series": [
                {
                    "target": "COUNT(rawdata)",
                    "metric_field": "_result",
                    "alias": "_result_",
                    "type": "bar",
                    "unit": "",
                    "dimensions": {},
                    "dimensions_translation": {},
                    "datapoints": datapoints,
                }
            ]
            if datapoints
            else [],
        }
        return histograms

    def get_no_data_strategy_config(self):
        return None
