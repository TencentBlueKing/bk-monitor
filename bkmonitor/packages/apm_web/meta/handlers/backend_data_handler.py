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

import datetime
import json

from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from api.bkdata.default import (
    GetDataBusSamplingData,
    GetDataBusStoragesInfo,
    GetDataManageMetricsDataCount,
)
from api.log_search.default import (
    DataBusCollectorsIndicesResource,
    DataBusCollectorsResource,
    LogSearchIndexSetResource,
)
from constants.apm import TelemetryDataType
from core.drf_resource import api


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
    def build_data_count_query(cls, data_type_label, data_source_label, table_name, **kwargs):
        template = [
            {
                "id": 1,
                "title": _("分钟数据量"),
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "datasource": "time_series",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": data_source_label,
                                    "data_type_label": data_type_label,
                                    "table": table_name,
                                    "metrics": [{"field": "bk_apm_count", "method": "COUNT", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [],
                                    "interval": 60,
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
            {
                "id": 2,
                "title": _("日数据量"),
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "datasource": "time_series",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": data_source_label,
                                    "data_type_label": data_type_label,
                                    "table": table_name,
                                    "metrics": [{"field": "bk_apm_count", "method": "COUNT", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [],
                                    "interval": 60 * 60 * 24,
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
        ]
        query_config_kwargs = kwargs.pop("query_config_kwargs", {})
        if kwargs or query_config_kwargs:
            for config in template:
                for target in config["targets"]:
                    for query_config in target["data"]["query_configs"]:
                        query_config.update(**query_config_kwargs)
                    target["data"].update(**kwargs)
        return template


"""
观测数据后端适配器注册表
"""
telemetry_handler_registry = BackendRegistry()


@telemetry_handler_registry.register
class TracingBackendHandler(TelemetryBackendHandler):
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
        return self.build_data_count_query(
            data_type_label="time_series", data_source_label="custom", table_name=self.metric_result_table_id, **kwargs
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        view_config = self.get_data_view_config(start_time=start_time, end_time=end_time, **kwargs)
        data = api.unify_query.query_data(**view_config[0])
        count = 0
        for line in data["series"]:
            for point in line["datapoints"]:
                count += point[0]
        return count


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
        return DataBusCollectorsResource().request(collector_config_id=self.collector_config_id)

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
        table_name = (self.result_table_id.replace(".", "_"),)
        return self.build_data_count_query(
            data_type_label="log",
            data_source_label="bk_apm",
            table_name=table_name,
            query_config_kwargs={"index_set_id": self.index_set_id},
            **kwargs,
        )

    def get_data_count(self, start_time: int, end_time: int, **kwargs):
        view_config = self.get_data_view_config(start_time=start_time, end_time=end_time, **kwargs)
        data = api.unify_query.query_data(**view_config[0])
        count = 0
        for line in data["series"]:
            for point in line["datapoints"]:
                count += point[0]
        return count


@telemetry_handler_registry.register
class MetricBackendHandler(TelemetryBackendHandler):
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
        return GetDataBusStoragesInfo().request(raw_data_id=self.bk_base_data_id) if self.bk_base_data_id else []

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
        return [
            {
                "id": 1,
                "title": _("分钟数据量"),
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "datasource": "time_series",
                        "api": "apm_meta.dataHistogram",
                        "data": {
                            "application_id": self.app.applicaiotn_id,
                            "telemetry_data_type": self.telemetry.value,
                            "data_view_config": {"view_type": "histogram", "grain": "1m"},
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
            {
                "id": 2,
                "title": _("日数据量"),
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "datasource": "time_series",
                        "api": "apm_meta.dataHistogram",
                        "data": {
                            "application_id": self.app.applicaiotn_id,
                            "telemetry_data_type": self.telemetry.value,
                            "data_view_config": {"view_type": "histogram", "grain": "1d"},
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
        ]

    def get_data_view(self, start_time: int, end_time: int, **kwargs):
        return GetDataManageMetricsDataCount().request(
            data_set_ids=self.bk_base_data_id, start_time=start_time, end_time=end_time, **kwargs
        )

    def get_data_count(self, start_time: int, end_time: int):
        resp = self.get_data_view(start_time, end_time)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point["rawdata_count"]:
                    count += point["rawdata_count"]
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self.get_data_view(start_time, end_time, time_grain=grain)
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
                    "datapoints": [
                        [view_series["rawdata_count"], view_series["time"] * 1000] for view_series in resp["series"]
                    ],
                }
            ],
        }
        return histograms


@telemetry_handler_registry.register
class ProfilingBackendHandler(TelemetryBackendHandler):
    """
    性能分析后端适配器
    """

    def storage_info(self):
        return GetDataBusStoragesInfo().request(raw_data_id=self.bk_data_id) if self.bk_data_id else []

    def data_sampling(self, **kwargs):
        resp_data = []
        if self.bk_data_id:
            resp = GetDataBusSamplingData().request(data_id=self.bk_data_id)
            for log in resp:
                log_content = json.loads(log["value"])
                time_str = datetime.datetime.fromtimestamp(
                    int(log_content["time"]) / 1000, timezone.get_current_timezone()
                ).strftime("%Y-%m-%d %H:%M:%S")
                resp_data.append({"raw_log": log_content, "sampling_time": time_str})
        return resp_data

    def get_data_view_config(self, **kwargs):
        return [
            {
                "id": 1,
                "title": _("分钟数据量"),
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "datasource": "time_series",
                        "api": "apm_meta.dataHistogram",
                        "data": {
                            "application_id": self.app.applicaiotn_id,
                            "telemetry_data_type": self.telemetry.value,
                            "data_view_config": {"view_type": "histogram", "grain": "1m"},
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
            {
                "id": 2,
                "title": _("日数据量"),
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "datasource": "time_series",
                        "api": "apm_meta.dataHistogram",
                        "data": {
                            "application_id": self.app.applicaiotn_id,
                            "telemetry_data_type": self.telemetry.value,
                            "data_view_config": {"view_type": "histogram", "grain": "1d"},
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
        ]

    def get_data_view(self, start_time: int, end_time: int, **kwargs):
        return GetDataManageMetricsDataCount().request(
            data_set_ids=self.bk_data_id, start_time=start_time, end_time=end_time, **kwargs
        )

    def get_data_count(self, start_time: int, end_time: int):
        resp = self.get_data_view(start_time, end_time)
        count = 0
        for data in resp:
            for point in data["series"]:
                if point["rawdata_count"]:
                    count += point["rawdata_count"]
        return count

    def get_data_histogram(self, start_time, end_time, grain="1d"):
        resp = self.get_data_view(start_time, end_time, time_grain=grain)
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
                    "datapoints": [
                        [view_series["rawdata_count"], view_series["time"] * 1000] for view_series in resp["series"]
                    ],
                }
            ],
        }
        return histograms
