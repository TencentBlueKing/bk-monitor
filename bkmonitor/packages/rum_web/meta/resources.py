"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
import uuid

from rest_framework import serializers

from core.drf_resource import Resource


def _mock_application(bk_biz_id, app_name, app_alias="", application_id=None, **kwargs):
    """构造一条 mock 应用数据"""
    now = time.strftime("%Y-%m-%d %H:%M:%S+0800")
    aid = application_id or abs(hash(f"{bk_biz_id}_{app_name}")) % 100000
    return {
        "application_id": aid,
        "bk_biz_id": bk_biz_id,
        "app_name": app_name,
        "app_alias": app_alias or app_name,
        "description": kwargs.get("description", ""),
        "client_type": kwargs.get("client_type", "web"),
        "is_enabled": True,
        "application_apdex_config": {"apdex_default": 200, "LCP": 2000, "INP": 2000},
        "application_qps_config": 500,
        "span_datasource_config": {
            "es_storage_cluster": 16,
            "es_retention": 7,
            "es_number_of_replicas": 0,
            "es_shards": 3,
            "es_slice_size": 500,
        },
        "span_result_table_id": f"{bk_biz_id}_bkrum_span_{app_name}",
        "metric_result_table_id": f"{bk_biz_id}_bkrum_metric_{app_name}.__default__",
        "time_series_group_id": 142,
        "data_status": "normal",
        "no_data_period": 10,
        "is_create_finished": True,
        "bk_tenant_id": "system",
        "create_user": "admin",
        "create_time": now,
        "update_user": "admin",
        "update_time": now,
        "permission": {
            "manage_rum_application": True,
            "view_rum_application": True,
        },
    }


class CreateApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"^[a-z0-9_.-]+$")
        app_alias = serializers.CharField(label="应用别名", max_length=255)
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        client_type = serializers.CharField(label="前端类型", required=False, default="web")

    def perform_request(self, validated_request_data):
        return _mock_application(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=validated_request_data["app_alias"],
            description=validated_request_data.get("description", ""),
            client_type=validated_request_data.get("client_type", "web"),
        )


class CheckDuplicateAppNameResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    def perform_request(self, validated_request_data):
        return {"exists": False}


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        return {"result": True}


class StartDataSourceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        return {"result": True}


class StopDataSourceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        return {"result": True}


class GetApplicationInfoByAppNameResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        is_get_detail = serializers.BooleanField(label="是否获取详情", required=False, default=True)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        is_get_detail = validated_request_data.get("is_get_detail", True)

        full = _mock_application(bk_biz_id, app_name, app_alias=app_name)

        if not is_get_detail:
            # 精简模式：只返回基础定位字段，不返回配置/存储/状态等详情
            return {
                "application_id": full["application_id"],
                "bk_biz_id": full["bk_biz_id"],
                "app_name": full["app_name"],
                "app_alias": full["app_alias"],
                "description": full["description"],
                "client_type": full["client_type"],
                "is_enabled": full["is_enabled"],
                "data_status": full["data_status"],
            }

        return full


class SetupApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class SpanDatasourceConfigSerializer(serializers.Serializer):
            es_storage_cluster = serializers.IntegerField(label="存储集群", required=False)
            es_retention = serializers.IntegerField(label="保留天数", required=False)
            es_number_of_replicas = serializers.IntegerField(label="副本数", required=False)
            es_shards = serializers.IntegerField(label="分片数", required=False)
            es_slice_size = serializers.IntegerField(label="切分大小", required=False)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        app_alias = serializers.CharField(label="展示名称", required=False, allow_blank=True)
        description = serializers.CharField(label="描述", required=False, allow_blank=True)
        span_datasource_config = SpanDatasourceConfigSerializer(required=False)
        application_apdex_config = serializers.DictField(label="Apdex配置", required=False)

    def perform_request(self, validated_request_data):
        # 配置页聚合保存入口，不返回数据
        return None


class GetMetaConfigInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_request_data):
        return {
            "client_type_options": ["web"],
            "setup": {
                "guide_url": {
                    "access_url": "www.example.com",
                    "best_practice": "",
                    "metric_description": "",
                },
                "index_prefix_name": f"{validated_request_data['bk_biz_id']}_bkrum_",
                "es_retention_days": {
                    "default": 7,
                    "default_es_max": 7,
                    "private_es_max": 30,
                },
                "es_number_of_replicas": {
                    "default": 1,
                    "default_es_max": 3,
                    "private_es_max": 10,
                },
            },
        }


class GetStorageInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        return {
            "es_number_of_replicas": 0,
            "es_retention": 7,
            "es_shards": 3,
            "es_slice_size": 30,
            "es_storage_cluster": 16,
        }


class GetIndicesInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        table_name = app_name.replace("-", "_")
        return [
            {
                "health": "green",
                "status": "open",
                "index": f"v2_{bk_biz_id}_bkrum_span_{table_name}",
                "uuid": uuid.uuid4().hex[:16],
                "pri": 3,
                "rep": 0,
                "docs_count": 49982610,
                "docs_deleted": 1162,
                "store_size": 19516475812,
                "pri_store_size": 19516475812,
            },
            {
                "health": "green",
                "status": "open",
                "index": f"v2_{bk_biz_id}_bkrum_span_{table_name}",
                "uuid": uuid.uuid4().hex[:16],
                "pri": 3,
                "rep": 0,
                "docs_count": 365476235,
                "docs_deleted": 0,
                "store_size": 138787848810,
                "pri_store_size": 138787848810,
            },
        ]


class GetDataSamplingResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        size = serializers.IntegerField(label="拉取条数", required=False, default=10)

    many_response_data = True

    def perform_request(self, validated_request_data):
        now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        return [
            {
                "raw_log": {
                    "trace_id": uuid.uuid4().hex,
                    "span_id": uuid.uuid4().hex[:16],
                    "span_name": "/api/v1/page/load",
                    "kind": 1,
                    "elapsed_time": 1250000,
                    "resource.service.name": validated_request_data["app_name"],
                    "status.code": 0,
                },
                "sampling_time": now,
            }
            for _ in range(min(validated_request_data.get("size", 10), 3))
        ]


class GetNoDataStrategyInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        strategy_id = abs(hash(f"{bk_biz_id}_{app_name}_nodata")) % 100000
        return {
            "id": strategy_id,
            "name": f"BKRUM-无数据告警-{app_name}-metric",
            "alert_status": 1,
            "alert_count": 0,
            "alert_graph": {
                "id": 1,
                "title": "告警数量",
                "type": "apdex-chart",
                "targets": [
                    {
                        "dataType": "event",
                        "datasource": "time_series",
                        "api": "rum_metric.alertQuery",
                        "data": {
                            "bk_biz_id": bk_biz_id,
                            "app_name": app_name,
                            "strategy_id": strategy_id,
                        },
                    }
                ],
            },
            "is_enabled": False,
            "notice_group": [{"id": 451, "name": "运维"}],
        }


class GetDataViewConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        table_name = app_name.replace("-", "_")
        metric_table = f"{bk_biz_id}_bkrum_metric_{table_name}.__default__"
        return [
            {
                "id": 1,
                "title": "分钟数据量",
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "datasource": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": metric_table,
                                    "metrics": [
                                        {
                                            "field": "bk_rum_count",
                                            "method": "SUM",
                                            "alias": "A",
                                        }
                                    ],
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
                            "table_name": metric_table,
                            "metric_field": "bk_rum_count",
                            "method_method": "SUM",
                        },
                    }
                ],
                "options": {
                    "time_series": {},
                    "collect_interval_display": "1m",
                },
            },
        ]


class GetDataHistogramResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        data_view_config = serializers.DictField(label="查询模板配置", required=False, default=dict)

    def perform_request(self, validated_request_data):
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        # 生成模拟的直方图数据点（每分钟一个点）
        interval = 60
        datapoints = []
        ts = start_time
        while ts <= end_time:
            datapoints.append([abs(hash(str(ts))) % 1000, ts * 1000])
            ts += interval
        return {
            "metrics": [],
            "series": [
                {
                    "target": "bk_rum_count",
                    "metric_field": "bk_rum_count",
                    "alias": "A",
                    "type": "bar",
                    "unit": "",
                    "dimensions": {},
                    "datapoints": datapoints,
                }
            ],
        }


class ListApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        mock_apps = [
            {
                "application_id": 101,
                "bk_biz_id": bk_biz_id,
                "app_name": "www.example.com",
                "app_alias": "示例官网",
                "description": "示例官网前端监控",
                "client_type": "web",
                "is_enabled": True,
                "span_data_status": "normal",
                "metric_data_status": "normal",
                "span_result_table_id": f"{bk_biz_id}_bkrum_span_www_example_com",
                "metric_result_table_id": f"{bk_biz_id}_bkrum_metric_www_example_com.__default__",
                "is_create_finished": True,
                "permission": {
                    "manage_rum_application": True,
                    "view_rum_application": True,
                },
            },
            {
                "application_id": 102,
                "bk_biz_id": bk_biz_id,
                "app_name": "www.bk-console.com",
                "app_alias": "蓝鲸管理台",
                "description": "蓝鲸管理台前端性能监控",
                "client_type": "web",
                "is_enabled": True,
                "span_data_status": "normal",
                "metric_data_status": "no_data",
                "span_result_table_id": f"{bk_biz_id}_bkrum_span",
                "metric_result_table_id": f"{bk_biz_id}_bkrum_metric.__default__",
                "is_create_finished": True,
                "permission": {
                    "manage_rum_application": True,
                    "view_rum_application": True,
                },
            },
        ]

        columns = [
            {
                "id": "app_name",
                "name": "应用名称",
                "disabled": True,
                "checked": True,
                "sortable": False,
                "type": "link",
                "width": None,
                "min_width": 200,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": "view_rum_application",
                "asyncable": False,
                "props": {},
                "showOverflowTooltip": True,
            },
            {
                "id": "app_alias",
                "name": "应用别名",
                "disabled": False,
                "checked": True,
                "sortable": False,
                "type": "string",
                "width": None,
                "min_width": 120,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": None,
                "asyncable": False,
                "props": {},
                "showOverflowTooltip": True,
            },
            {
                "id": "description",
                "name": "描述",
                "disabled": False,
                "checked": True,
                "sortable": False,
                "type": "string",
                "width": None,
                "min_width": 120,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": None,
                "asyncable": False,
                "props": {},
                "showOverflowTooltip": True,
            },
            {
                "id": "lcp_p75",
                "name": "LCP P75",
                "disabled": False,
                "checked": True,
                "sortable": "custom",
                "type": "string",
                "width": 130,
                "min_width": None,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": None,
                "asyncable": True,
                "props": {},
                "showOverflowTooltip": False,
            },
            {
                "id": "js_error_rate",
                "name": "JS 错误率",
                "disabled": False,
                "checked": True,
                "sortable": "custom",
                "type": "string",
                "width": 130,
                "min_width": None,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": None,
                "asyncable": True,
                "props": {},
                "showOverflowTooltip": False,
            },
            {
                "id": "api_fail_rate",
                "name": "API 失败率",
                "disabled": False,
                "checked": True,
                "sortable": "custom",
                "type": "string",
                "width": 130,
                "min_width": None,
                "max_width": None,
                "filterable": False,
                "filter_list": [],
                "actionId": None,
                "asyncable": True,
                "props": {},
                "showOverflowTooltip": False,
            },
        ]

        return {
            "columns": columns,
            "total": len(mock_apps),
            "data": mock_apps,
        }


class ListApplicationAsyncResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        column = serializers.ChoiceField(label="列名", choices=["lcp_p75", "js_error_rate", "api_fail_rate"])
        application_ids = serializers.ListField(label="应用ID列表", child=serializers.CharField())
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    many_response_data = True

    # 各列 mock 值的定义
    _COLUMN_MOCK_MAP = {
        "lcp_p75": {"id": "lcp_p75", "name": "LCP P75", "unit": "ms"},
        "js_error_rate": {"id": "js_error_rate", "name": "JS 错误率", "unit": "%"},
        "api_fail_rate": {"id": "api_fail_rate", "name": "API 失败率", "unit": "%"},
    }

    _MOCK_APPS = {
        "101": "www.example.com",
        "102": "www.bk-console.com",
    }

    def perform_request(self, validated_request_data):
        column = validated_request_data["column"]
        application_ids = validated_request_data["application_ids"]
        column_def = self._COLUMN_MOCK_MAP[column]

        # 根据 column 生成不同量级的 mock 值
        mock_values = {
            "lcp_p75": lambda aid: abs(hash(f"lcp_{aid}")) % 3000 + 500,
            "js_error_rate": lambda aid: round((abs(hash(f"js_{aid}")) % 500) / 100, 2),
            "api_fail_rate": lambda aid: round((abs(hash(f"api_{aid}")) % 300) / 100, 2),
        }

        result = []
        for aid in application_ids:
            app_name = self._MOCK_APPS.get(str(aid), f"app_{aid}")
            value = mock_values[column](aid)
            result.append(
                {
                    "application_id": int(aid) if str(aid).isdigit() else aid,
                    "app_name": app_name,
                    column: {
                        "id": column_def["id"],
                        "name": column_def["name"],
                        "value": value,
                        "unit": column_def["unit"],
                    },
                }
            )
        return result


class QueryRumTokenInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")

    def perform_request(self, validated_request_data):
        return {
            "token": f"mock_rum_token_{uuid.uuid4().hex[:12]}",
        }


class StorageFieldInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    many_response_data = True

    def perform_request(self, validated_request_data):
        return [
            {
                "field_name": "__parse_failure",
                "ch_field_name": "",
                "analysis_field": False,
                "field_type": "boolean",
                "time_field": False,
            },
            {
                "field_name": "attributes.apdex_type",
                "ch_field_name": "",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "attributes.enduser.id",
                "ch_field_name": "",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "span_name",
                "ch_field_name": "Span名称",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "trace_id",
                "ch_field_name": "Trace ID",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "span_id",
                "ch_field_name": "Span ID",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "elapsed_time",
                "ch_field_name": "耗时",
                "analysis_field": False,
                "field_type": "long",
                "time_field": False,
            },
            {
                "field_name": "sampling_time",
                "ch_field_name": "采样时间",
                "analysis_field": False,
                "field_type": "date",
                "time_field": True,
            },
            {
                "field_name": "resource.service.name",
                "ch_field_name": "服务名称",
                "analysis_field": False,
                "field_type": "keyword",
                "time_field": False,
            },
            {
                "field_name": "status.code",
                "ch_field_name": "状态码",
                "analysis_field": False,
                "field_type": "integer",
                "time_field": False,
            },
        ]
