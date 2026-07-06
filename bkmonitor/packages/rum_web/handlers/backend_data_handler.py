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
import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from rum_web.models.application import Application, RumAppConfig

logger = logging.getLogger("rum")


def handler_name(handler_cls: type):
    return str(handler_cls.__name__).split("BackendHandler")[0].lower()


class BackendRegistry:
    """后端适配器注册表"""

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
    """后台数据适配器基类，对齐 apm_web TelemetryBackendHandler"""

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

    @classmethod
    def build_call_back_target(cls, data_type_label, data_source_label, **kwargs) -> dict:
        """构建 unify_query 查询 target"""
        table_name = kwargs.get("table_name", "__default__")
        metric_field = kwargs.get("metric_field", "bk_rum_count")
        method_method = kwargs.get("method_method", "SUM")
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
        """构建数据量查询面板配置（分钟 + 日两个面板）"""
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
RUM 观测数据后端适配器注册表
"""
telemetry_handler_registry = BackendRegistry()


@telemetry_handler_registry.register
class RumBackendHandler(TelemetryBackendHandler):
    """
    RUM Span 数据后端适配器，对齐 apm_web RumBackendHandler。
    操作 span 数据源（ES），对应 Application.span_result_table_id。
    """

    TIME_FORMAT_LEN = 11

    def storage_info(self):
        """查询存储配置信息"""
        config = RumAppConfig.get_application_config_value(
            self.app.application_id, Application.APPLICATION_DATASOURCE_CONFIG_KEY
        )
        if config and config.config_value:
            datasource_config = config.config_value
            # 若配置中无 es_shards，从索引信息补充
            if "es_shards" not in datasource_config:
                try:
                    indices_data = self.indices_info()
                    if indices_data:
                        datasource_config = {**datasource_config, "es_shards": indices_data[0]["pri"]}
                except Exception:
                    pass
            return datasource_config

        # 无配置时返回默认值
        return {
            "es_number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
            "es_retention": settings.RUM_APP_DEFAULT_ES_RETENTION,
            "es_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
            "es_slice_size": settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT,
            "es_storage_cluster": settings.RUM_APP_DEFAULT_ES_STORAGE_CLUSTER,
        }

    def _get_es_storage_cluster(self) -> int:
        """获取 ES 存储集群 ID"""
        config = RumAppConfig.get_application_config_value(
            self.app.application_id, Application.APPLICATION_DATASOURCE_CONFIG_KEY
        )
        if config and config.config_value:
            cluster_id = config.config_value.get("es_storage_cluster")
            if cluster_id and cluster_id != -1:
                return cluster_id
        return settings.RUM_APP_DEFAULT_ES_STORAGE_CLUSTER

    def indices_info(self):
        """
        查询 ES 索引信息。
        参考 apm_web RumBackendHandler.indices_info()
        """
        if not self.app.span_result_table_id:
            return []

        es_index_name = self.app.span_result_table_id.replace(".", "_")
        es_storage_cluster = self._get_es_storage_cluster()
        try:
            data = api.metadata.es_route(
                {
                    "es_storage_cluster": es_storage_cluster,
                    "url": f"_cat/indices/{es_index_name}_*_*?bytes=b&format=json",
                }
            )
        except Exception as e:
            logger.warning(f"[RumBackendHandler] indices_info failed: {e}")
            return []

        result = []
        for item in data:
            index_name = item.get("index", "")
            # 提取时间后缀部分，过滤非标准索引
            parts = index_name.split(es_index_name)
            if len(parts) > 1 and len(parts[-1]) == self.TIME_FORMAT_LEN:
                result.append({k.replace(".", "_"): v for k, v in item.items()})
        return result

    def data_sampling(self, size: int = 10, **kwargs):
        """
        获取采样数据。
        参考 apm_web RumBackendHandler.data_sampling()
        """
        if not self.app.span_result_table_id:
            return []

        try:
            resp = api.metadata.kafka_tail({"table_id": self.app.span_result_table_id, "size": size})
        except Exception as e:
            logger.warning(f"[RumBackendHandler] data_sampling failed: {e}")
            return []
        return [{"raw_log": log, "sampling_time": log.get("datetime", "")} for log in resp]

    def storage_field_info(self):
        """
        获取存储字段信息。
        参考 apm_web TraceBackendHandler.storage_field_info()（简化版）
        """
        if not self.app.span_result_table_id:
            return []

        try:
            table_data = api.metadata.get_result_table({"table_id": self.app.span_result_table_id})
            field_list = table_data.get("field_list", [])
        except Exception as e:
            logger.warning(f"[RumBackendHandler] storage_field_info failed: {e}")
            return []

        return [
            {
                "field_name": field["field_name"],
                "ch_field_name": field.get("description", ""),
                "analysis_field": field.get("type") == "text",
                "field_type": field.get("type", ""),
                "time_field": field.get("type") == "date",
            }
            for field in field_list
        ]

    def get_data_view_config(self, **kwargs):
        """
        获取数据视图查询配置（分钟 + 日两个面板）。
        参考 apm_web RumBackendHandler.get_data_view_config()
        """
        metric_table = self.app.metric_result_table_id
        if not metric_table:
            return []

        view_params = {
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "data_source_label": DataSourceLabel.CUSTOM,
            "table_name": metric_table,
            "metric_field": "browser_web_vital_duration_bucket",  # TODO: 实际还是要用另一个代表数量的指标
            "method_method": "SUM",
        }
        kwargs.update(view_params)
        return self.build_data_count_query(**kwargs)

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
        promql = f'sum(sum_over_time({{__name__="custom:{self.app.metric_result_table_id}:browser_web_vital_duration_bucket"}}[1m])) or vector(0)'
        return {
            "result_table_id": self.app.span_result_table_id,
            "metric_id": promql,
            "metric_field": "browser_web_vital_duration_bucket",
            "name": f"BKRUM-{_('无数据告警')}-{self.app.app_name}",
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
