# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import datetime
import json

from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from api.bkdata.default import (
    GetDataBusSamplingData,
    GetRawDataStoragesInfo,
    GetStorageMetricsDataCount,
)
from api.log_search.default import (
    DataBusCollectorsIndicesResource,
    DataBusCollectorsResource,
    LogSearchIndexSetResource,
)
from constants.apm import TelemetryDataType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource


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
        "options": {"time_series": {"type": "bar"}},
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
    def build_call_back_target(cls, data_type_label, data_source_label, table_name, metric_field, **kwargs) -> dict:
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
                        "metrics": [{"field": metric_field, "method": "COUNT", "alias": "A"}],
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
                query_config.update(**query_config_kwargs)
        return target

    @classmethod
    def build_data_count_query(cls, **kwargs):
        templates = []
        for idx, grain_config in enumerate([(_("分钟数据量"), "1m", 0, 0), (_("日数据量"), "1d", 12, 0)]):
            title, grain, x_pos, y_pos = grain_config
            kwargs["grain"] = grain
            _id = idx + 1
            template = copy.deepcopy(cls.CALL_BACK_PARAMS_FRAME)
            template["id"] = _id
            template["title"] = title
            template["gridPos"]["x"] = x_pos
            template["gridPos"]["y"] = y_pos
            target = cls.build_call_back_target(**kwargs)
            if isinstance(target.get("data"), dict):
                target["data"].update(**kwargs)
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
        return all([idx.get("health") == "green" for idx in self.indices_info()])

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
            "data_type_label": "time_series",
            "data_source_label": DataSourceLabel.CUSTOM,
            "table_name": self.metric_result_table_id,
            "metric_field": "bk_apm_count",
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
                count += point[0]
        return count

    def get_no_data_strategy_config(self, **kwargs):
        return {
            "result_table_id": self.metric_result_table_id,
            "metric_id": f"custom.{self.metric_result_table_id}.bk_apm_count",
            "metric_field": "bk_apm_count",
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.CUSTOM,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "alias": "a",
                    "result_table_id": f"{self.metric_result_table_id}",
                    "agg_method": "COUNT",
                    "agg_interval": 60,
                    "agg_dimension": [],
                    "agg_condition": [],
                    "metric_field": "bk_apm_count",
                    "unit": "ns",
                    "metric_id": f"custom.{self.metric_result_table_id}.bk_apm_count",
                    "index_set_id": "",
                    "query_string": "*",
                    "custom_event_name": "bk_apm_count",
                    "functions": [],
                    "time_field": "time",
                    "bkmonitor_strategy_id": "bk_apm_count",
                    "alert_name": "bk_apm_count",
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
        resp = DataBusCollectorsResource().request(collector_config_id=self.collector_config_id)
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
        res_data = LogSearchIndexSetResource().request(index_set_id=self.index_set_id)
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
        return all([idx.get("health") == "green" for idx in self.indices_info()])

    def indices_info(self):
        data = DataBusCollectorsIndicesResource().request(collector_config_id=self.collector_config_id)
        result = []
        for item in data:
            result.append({key.replace(".", "_"): value for key, value in item.items()})
        return result

    def data_sampling(self, size: int = 10, **kwargs):
        resp = api.metadata.kafka_tail({"table_id": self.result_table_id, "size": size}) if self.result_table_id else []
        return [{"raw_log": log, "sampling_time": log.get("datetime", "")} for log in resp]

    def get_data_view_config(self, **kwargs):
        view_params = {
            "data_type_label": "time_series",
            "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
            "table_name": self.result_table_id,
            "metric_field": "_index",
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
                count += point[0]
        return count

    def get_no_data_strategy_config(self, **kwargs):
        return {
            "result_table_id": self.result_table_id,
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "metric_id": f"{self.result_table_id}._index",
            "metric_field": "_index",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "index_set_id": self.index_set_id,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "index_set_id": self.index_set_id,
                    "result_table_id": self.result_table_id,
                    "agg_method": "COUNT",
                    "agg_interval": 60,
                    "agg_dimension": [],
                    "agg_condition": [],
                    "alias": "a",
                    "metric_field": "_index",
                    "metric_id": f"{self.result_table_id}._index",
                    "query_string": "*",
                    "group_by": [],
                    "display": True,
                    "where": [],
                    "interval": 60,
                    "interval_unit": "s",
                    "time_field": "dtEventTimeStamp",
                    "filter_dict": {},
                    "functions": [],
                }
            ],
        }


class BkdataCountMixIn:
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
            data_view_config.update(**kwargs)
        return target


@telemetry_handler_registry.register
class MetricBackendHandler(BkdataCountMixIn, TelemetryBackendHandler):
    """
    指标后端适配器
    """

    @cached_property
    def bk_base_data_id(self):
        # Todo: APM_APPLY 临时方案，待接口支持
        from metadata import models

        vm_record = models.AccessVMRecord.objects.filter(result_table_id=self.result_table_id).first()
        return vm_record.bk_base_data_id if vm_record else None

    def storage_info(self):
        return GetRawDataStoragesInfo().request(raw_data_id=self.bk_base_data_id) if self.bk_base_data_id else []

    @property
    def storage_status(self):
        return all([storage.get("status") == "running" for storage in self.storage_info()])

    def data_sampling(self, **kwargs):
        resp_data = []
        if self.bk_base_data_id:
            resp = GetDataBusSamplingData().request(data_id=self.bk_base_data_id)
            for log in resp:
                log_content = json.loads(log["value"])
                time_str = datetime.datetime.fromtimestamp(
                    int(log_content["time"]) / 1000, timezone.get_current_timezone()
                ).strftime("%Y-%m-%d %H:%M:%S")
                resp_data.append({"raw_log": log_content, "sampling_time": time_str})
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

    def get_data_view(self, start_time: int, end_time: int, **kwargs):
        storages = self.storage_info()
        storage_result_table_id = None
        for storage in storages:
            if storage["storage_type"] == "vm":
                storage_result_table_id = storage["result_table_id"]
                break
        return (
            GetStorageMetricsDataCount().request(
                data_set_ids=[storage_result_table_id],
                storages=["vm"],
                start_time=start_time,
                end_time=end_time,
                **kwargs,
            )
            if storage_result_table_id
            else []
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        resp = self.get_data_view(start_time, end_time, **kwargs)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point["output_count"]:
                    count += point["output_count"]
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self.get_data_view(start_time, end_time, time_grain=grain)
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
            ],
        }
        return histograms

    def get_no_data_strategy_config(self, **kwargs):
        return {
            "result_table_id": self.result_table_id,
            "metric_id": f"sum(count_over_time(custom.{self.result_table_id}[1m]))",
            "metric_field": None,
            "name": f"BKAPM-{_('无数据告警')}-{self.app.app_name}-{self.telemetry.value}",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "table": self.result_table_id,
                    "promql": f"sum(count_over_time(custom.{self.result_table_id}[1m]))",
                    "agg_interval": 60,
                    "alias": "a",
                }
            ],
        }


@telemetry_handler_registry.register
class ProfilingBackendHandler(BkdataCountMixIn, TelemetryBackendHandler):
    """
    性能分析后端适配器
    """

    def storage_info(self):
        return GetRawDataStoragesInfo().request(raw_data_id=self.bk_data_id) if self.bk_data_id else []

    @property
    def storage_status(self):
        return all([storage.get("status") == "running" for storage in self.storage_info()])

    def data_sampling(self, **kwargs):
        resp_data = []
        if self.bk_data_id:
            resp = GetDataBusSamplingData().request(data_id=self.bk_data_id)
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

    def get_data_view(self, start_time: int, end_time: int, **kwargs):
        storages = self.storage_info()
        storage_result_table_id = None
        for storage in storages:
            if storage["storage_type"] == "doris":
                storage_result_table_id = storage["result_table_id"]
                break
        return (
            GetStorageMetricsDataCount().request(
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
        resp = self.get_data_view(start_time, end_time, **kwargs)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point["output_count"]:
                    count += point["output_count"]
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self.get_data_view(start_time, end_time, time_grain=grain)
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
            ],
        }
        return histograms

    def get_no_data_strategy_config(self):
        return None
