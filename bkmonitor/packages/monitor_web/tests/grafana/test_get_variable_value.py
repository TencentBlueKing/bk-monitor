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

import pytest
from django.conf import settings
from monitor_web.grafana.resources import GetVariableValue

from api.kubernetes.default import FetchK8sClusterListResource
from constants.data_source import DataSourceLabel, DataTypeLabel

pytestmark = pytest.mark.django_db


class TestGetVariableValue:
    """
    测试拉取Grafana变量
    """

    resource_name = "resource.grafana.get_variable_value"

    def test_dimensions_with_bkmonitor_timeseries(self, mocker):
        """监控时序数据，维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "field": "device_name",
                "metric_field": "usage",
                "result_table_id": "system.cpu_summary",
                "where": [],
            },
        }
        get_dimension_data_return = {"values": {"device_name": ["cpu-total"]}}
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        data = GetVariableValue().request(params)

        assert data == [{"label": "cpu-total", "value": "cpu-total"}]

    def test_dimensions_with_bkmonitor_log(self, mocker):
        """监控日志关键词，维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": "bk_monitor",
                "data_type_label": "log",
                "field": "event_name",
                "metric_field": "event.count",
                "result_table_id": "2_bkmonitor_event_1500137",
                "where": [],
            },
        }
        get_es_data_return = {
            "hits": {
                "hits": [
                    {
                        "sort": [1630743307000000000],
                        "_type": "_doc",
                        "_source": {
                            "event_name": "login_count",
                            "time": "1630743307000",
                            "target": "0:10.0.0.1",
                            "dimensions": {
                                "bk_biz_id": "2",
                                "bk_module_id": "39",
                                "bk_collect_config_id": "40",
                                "bk_target_topo_id": "",
                                "bk_target_topo_level": "",
                                "file_path": "/data/bkee/logs/open_paas/login_uwsgi.log",
                                "bk_target_service_category_id": "",
                                "bk_target_ip": "10.0.0.1",
                                "bk_set_id": "7",
                                "bk_target_service_instance_id": "",
                                "bk_target_cloud_id": "0",
                            },
                            "event": {"content": "xxxx", "count": 75},
                        },
                        "_score": None,
                        "_index": "v2_2_bkmonitor_event_1500137_20210903_0",
                        "_id": "9e8e2d4c22fadc58dfaa0c59843a43f1",
                    }
                ],
                "total": {"relation": "eq", "value": 90},
                "max_score": None,
            },
            "_shards": {"successful": 4, "failed": 0, "skipped": 0, "total": 4},
            "took": 16,
            "aggregations": {
                "event_name": {
                    "buckets": [
                        {
                            "time": {
                                "buckets": [
                                    {
                                        "event.count": {"value": 3},
                                        "key_as_string": "1630741560000",
                                        "key": 1630741560000,
                                        "doc_count": 3,
                                    },
                                    {
                                        "event.count": {"value": 3},
                                        "key_as_string": "1630743300000",
                                        "key": 1630743300000,
                                        "doc_count": 3,
                                    },
                                ]
                            },
                            "key": "login_count",
                            "doc_count": 90,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }
        mocker.patch("api.metadata.default.GetEsDataResource.perform_request", return_value=get_es_data_return)
        data = GetVariableValue().request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [
            {"label": "login_count", "value": "login_count"},
        ]

    def test_dimensions_with_custom_timeseries(self, mocker):
        """自定义指标（时序数据），维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": "custom",
                "data_type_label": "time_series",
                "field": "pod",
                "metric_field": "kube_node_status_capacity",
                "result_table_id": "2_bkmonitor_time_series_1500080.base",
                "where": [],
            },
        }
        get_dimension_data_return = {"values": {"pod": ["pod1", "pod2"]}}
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        data = GetVariableValue().request(params)
        data.sort(key=lambda x: x["value"])
        assert data == [{"label": "pod1", "value": "pod1"}, {"label": "pod2", "value": "pod2"}]

    def test_dimensions_with_custom_event(self, mocker):
        """自定义事件，维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": "custom",
                "data_type_label": "event",
                "field": "namespace",
                "metric_field": "BackOff",
                "result_table_id": "2_bkmonitor_event_1500114",
                "where": [],
            },
        }
        get_es_data_return = {
            "hits": {
                "hits": [
                    {
                        "sort": [1630743992000000000],
                        "_type": "_doc",
                        "_source": {
                            "event_name": "BackOff",
                            "time": "1630743992000",
                            "target": "kubelet",
                            "dimensions": {
                                "kind": "Pod",
                                "namespace": "bk-monitoring",
                                "name": "bkmonitorbeat-267ks",
                                "uid": "33ae0afb-03e5-11ec-b225-5254004edcb5",
                            },
                            "event": {"content": "Back-off restarting failed container", "count": 1},
                        },
                        "_score": None,
                        "_index": "v2_2_bkmonitor_event_1500114_20210819_0",
                        "_id": "c1038d9948e0532eb9bcd6965fadc635",
                    }
                ],
                "total": {"relation": "eq", "value": 5},
                "max_score": None,
            },
            "_shards": {"successful": 4, "failed": 0, "skipped": 1, "total": 4},
            "took": 16,
            "aggregations": {
                "dimensions.namespace": {
                    "buckets": [
                        {
                            "time": {
                                "buckets": [
                                    {
                                        "_index": {"value": 1.0},
                                        "key_as_string": "1630742460000",
                                        "key": 1630742460000,
                                        "doc_count": 1,
                                    },
                                    {
                                        "_index": {"value": 1.0},
                                        "key_as_string": "1630743960000",
                                        "key": 1630743960000,
                                        "doc_count": 1,
                                    },
                                ]
                            },
                            "key": "bk-monitoring",
                            "doc_count": 5,
                        }
                    ],
                    "sum_other_doc_count": 0,
                    "doc_count_error_upper_bound": 0,
                }
            },
            "timed_out": False,
        }
        mocker.patch("api.metadata.default.GetEsDataResource.perform_request", return_value=get_es_data_return)
        data = GetVariableValue().request(params)
        assert data == [
            {"label": "bk-monitoring", "value": "bk-monitoring"},
        ]

    def test_dimensions_with_log_search_log(self, mocker):
        """日志平台日志关键字，维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": "bk_log_search",
                "data_type_label": "log",
                "field": "path",
                "metric_field": "_index",
                "result_table_id": "2_bklog.dillon_test",
                "where": [],
                "index_set_id": "104",
            },
        }
        es_query_search_return = {
            "_shards": {"failed": 0, "skipped": 0, "successful": 3, "total": 3},
            "aggregations": {
                "path": {
                    "buckets": [
                        {
                            "doc_count": 139,
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "_index": {"value": 2},
                                        "doc_count": 2,
                                        "key": 1630719660000,
                                        "key_as_string": "1630719660000",
                                    },
                                    {
                                        "_index": {"value": 2},
                                        "doc_count": 2,
                                        "key": 1630723200000,
                                        "key_as_string": "1630723200000",
                                    },
                                ]
                            },
                            "key": "/var/log/messages",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                }
            },
            "hits": {
                "hits": [
                    {
                        "_id": "6a425a1ca64f1f4e526f147fd1a39aba",
                        "_index": "v2_2_bklog_dillon_test_20210831_0",
                        "_score": 0.0,
                        "_source": {
                            "cloudId": 0,
                            "dtEventTimeStamp": "1630719736000",
                            "gseIndex": 412144,
                            "iterationIndex": 2,
                            "log": "Sep  4 09:42:15 VM-1-56-centos ssm: [GIN] 2021/09/04 - "
                            "09:42:15 | 200 |    1.285774ms |       10.0.0.1 | POST   "
                            '  "/api/v1/auth/access-tokens/verify"',
                            "path": "/var/log/messages",
                            "serverIp": "10.0.0.1",
                            "time": "1630719736000",
                        },
                        "_type": "_doc",
                    }
                ],
                "max_score": 0.0,
                "total": 139,
            },
            "timed_out": False,
            "took": 15,
        }
        mocker.patch(
            "api.log_search.default.ESQuerySearchResource.perform_request", return_value=es_query_search_return
        )
        data = GetVariableValue().request(params)
        assert data == [{"label": "/var/log/messages", "value": "/var/log/messages"}]

    def test_dimensions_with_log_search_timeseries(self, mocker):
        """日志平台时序数据（指标），维度查询"""
        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": "bk_log_search",
                "data_type_label": "time_series",
                "field": "span_name",
                "metric_field": "elapsed_time",
                "result_table_id": "2_bklog.bkmonitor_otlp",
                "where": [],
                "index_set_id": "72",
            },
        }

        es_query_search_return = {
            "_shards": {"failed": 0, "skipped": 0, "successful": 3, "total": 3},
            "aggregations": {
                "span_name": {
                    "buckets": [
                        {
                            "doc_count": 1025,
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "elapsed_time": {"value": 2808.74358974359},
                                        "doc_count": 39,
                                        "key": 1630724520000,
                                        "key_as_string": "1630724520000",
                                    },
                                    {
                                        "elapsed_time": {"value": 2004.3939393939395},
                                        "doc_count": 33,
                                        "key": 1630726080000,
                                        "key_as_string": "1630726080000",
                                    },
                                ]
                            },
                            "key": "influxdb-client-query",
                        },
                        {
                            "doc_count": 1025,
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "elapsed_time": {"value": 2993.7179487179487},
                                        "doc_count": 39,
                                        "key": 1630724520000,
                                        "key_as_string": "1630724520000",
                                    },
                                    {
                                        "elapsed_time": {"value": 2242.818181818182},
                                        "doc_count": 33,
                                        "key": 1630726080000,
                                        "key_as_string": "1630726080000",
                                    },
                                ]
                            },
                            "key": "influxdb-query-select",
                        },
                        {
                            "doc_count": 971,
                            "dtEventTimeStamp": {
                                "buckets": [
                                    {
                                        "elapsed_time": {"value": 246.14705882352942},
                                        "doc_count": 34,
                                        "key": 1630724520000,
                                        "key_as_string": "1630724520000",
                                    },
                                    {
                                        "elapsed_time": {"value": 305.35483870967744},
                                        "doc_count": 31,
                                        "key": 1630726080000,
                                        "key_as_string": "1630726080000",
                                    },
                                ]
                            },
                            "key": "handle-ts-query",
                        },
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
            },
            "hits": {
                "hits": [
                    {
                        "_id": "2092de7866a41f26e7edf2f147e0bb0d",
                        "_index": "v2_2_bklog_bkmonitor_otlp_20210902_0",
                        "_score": 0.0,
                        "_source": {
                            "attributes": {
                                "promql_stmt": "avg by(bk_target_ip, bk_target_cloud_id) (avg_over_time(a[1m] "
                                "offset -59s999ms)) + on(bk_target_ip, bk_target_cloud_id) "
                                "group_right() avg by(bk_target_ip, bk_target_cloud_id) "
                                "(avg_over_time(b[1m] offset -59s999ms))"
                            },
                            "cloudId": 0,
                            "dtEventTimeStamp": "1630724613000",
                            "elapsed_time": 368,
                            "end_time": 1630724613411993,
                            "events": [],
                            "gseIndex": 490469,
                            "iterationIndex": 0,
                            "kind": 1,
                            "links": [],
                            "parent_span_id": "b8387415713cca21",
                            "path": "",
                            "resource": {"bk_data_id": 1500096, "service.name": "test-service"},
                            "serverIp": "10.0.0.1",
                            "span_id": "990f5a2181ca54f1",
                            "span_name": "handle-ts-query",
                            "start_time": 1630724613411625,
                            "status": {"code": 1},
                            "time": "1630724613000",
                            "trace_id": "a3314795fdf896b8356303c367aa4e0e",
                            "trace_state": "",
                        },
                        "_type": "_doc",
                    }
                ],
                "max_score": 0.0,
                "total": 8051,
            },
            "timed_out": False,
            "took": 13,
        }
        mocker.patch(
            "api.log_search.default.ESQuerySearchResource.perform_request", return_value=es_query_search_return
        )
        data = GetVariableValue().request(params)
        assert {item["value"] for item in data} == {"influxdb-query-select", "handle-ts-query", "influxdb-client-query"}
        assert sorted(data, key=lambda x: x["value"]) == sorted(
            [
                {"label": "influxdb-query-select", "value": "influxdb-query-select"},
                {"label": "handle-ts-query", "value": "handle-ts-query"},
                {"label": "influxdb-client-query", "value": "influxdb-client-query"},
            ],
            key=lambda x: x["value"],
        )

    def test_bcs_cluster_id_dimension(self, mocker, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        """bcs集群维度查询"""
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        params = {
            "bk_biz_id": 2,
            "type": "dimension",
            "params": {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "field": "bcs_cluster_id",
                "metric_field": "usage",
                "result_table_id": "kubernetes",
                "where": [],
            },
        }
        get_dimension_data_return = {"values": {"bcs_cluster_id": ["BCS-K8S-00000", "BCS-K8S-00001"]}}
        mocker.patch(
            "api.unify_query.default.GetDimensionDataResource.perform_request", return_value=get_dimension_data_return
        )
        actual = GetVariableValue().request(params)
        expect = [
            {'label': 'BCS-K8S-00000(蓝鲸社区版7.0)', 'value': 'BCS-K8S-00000'},
            {'label': 'BCS-K8S-00001', 'value': 'BCS-K8S-00001'},
        ]
        assert actual == expect

    def test_scenario_os_type_is_host(self, monkeypatch_api_cmdb_get_host_by_topo_node):
        params = {
            "type": "host",
            "params": {
                "label_field": "bk_host_name",
                "value_field": "bk_host_innerip",
                "where": [{"key": "bk_host_innerip", "method": "include", "value": ["10.0.0.1", "10.0.0.2"]}],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'bk_host_name-a', 'value': '10.0.0.1'}, {'label': 'bk_host_name-b', 'value': '10.0.0.2'}]
        assert actual == expect

    def test_scenario_kubernetes_type_is_cluster(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "cluster",
            "params": {
                "label_field": "name",
                "value_field": "bcs_cluster_id",
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [
            {'label': 'BCS-K8S-00000(蓝鲸社区版7.0)', 'value': 'BCS-K8S-00000'},
            {'label': 'BCS-K8S-00001(蓝鲸社区版7.0)', 'value': 'BCS-K8S-00001'},
        ]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "cluster",
            "params": {
                "label_field": "name",
                "value_field": "bcs_cluster_id",
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = [
            {'label': 'BCS-K8S-00000(蓝鲸社区版7.0)', 'value': 'BCS-K8S-00000'},
            {'label': 'BCS-K8S-00002(蓝鲸社区版7.0)', 'value': 'BCS-K8S-00002'},
        ]
        assert actual == expect

    def test_scenario_kubernetes_type_is_namespace(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_workloads,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "namespace",
            "params": {
                "label_field": "namespace",
                "value_field": "namespace",
                "where": [{"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00000"]}],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'bcs-system', 'value': 'bcs-system'}]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "namespace",
            "params": {
                "label_field": "namespace",
                "value_field": "namespace",
                "where": [{"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00002"]}],
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'namespace_a', 'value': 'namespace_a'}]
        assert actual == expect

    def test_scenario_kubernetes_type_is_pod(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_pods,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "pod",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [{"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00000"]}],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [
            {'label': 'api-gateway-0', 'value': 'api-gateway-0'},
            {'label': 'api-gateway-1', 'value': 'api-gateway-1'},
        ]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "pod",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [{"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00002"]}],
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'api-gateway-2', 'value': 'api-gateway-2'}]
        assert actual == expect

    def test_scenario_kubernetes_type_is_container(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_containers,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "container",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00000"]},
                    {"key": "pod_name", "method": "eq", "value": ["api-gateway-etcd-0"]},
                ],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'etcd', 'value': 'etcd'}]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "container",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00002"]},
                ],
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'etcd', 'value': 'etcd'}]
        assert actual == expect

    def test_scenario_kubernetes_type_is_node(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_nodes,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "node",
            "params": {
                "label_field": "name",
                "value_field": "ip",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00000"]},
                ],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'master-1-1-1-1', 'value': '1.1.1.1'}]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "node",
            "params": {
                "label_field": "name",
                "value_field": "ip",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00002"]},
                ],
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = []
        assert actual == expect

    def test_scenario_kubernetes_type_is_service(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
        add_bcs_service,
    ):
        params = {
            "scenario": "kubernetes",
            "type": "service",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00000"]},
                ],
            },
            "bk_biz_id": "2",
        }
        actual = GetVariableValue().request(params)
        expect = [
            {'label': 'api-gateway', 'value': 'api-gateway'},
            {'label': 'api-gateway-etcd', 'value': 'api-gateway-etcd'},
            {'label': 'elasticsearch-data', 'value': 'elasticsearch-data'},
        ]
        assert actual == expect

        params = {
            "scenario": "kubernetes",
            "type": "service",
            "params": {
                "label_field": "name",
                "value_field": "name",
                "where": [
                    {"key": "bcs_cluster_id", "method": "eq", "value": ["BCS-K8S-00002"]},
                ],
            },
            "bk_biz_id": "-3",
        }
        actual = GetVariableValue().request(params)
        expect = [{'label': 'elasticsearch-data', 'value': 'elasticsearch-data'}]
        assert actual == expect
