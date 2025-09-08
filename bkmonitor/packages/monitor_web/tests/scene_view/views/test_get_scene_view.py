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
import pytest

from core.drf_resource import resource


class TestGetSceneViewResource:
    @pytest.mark.django_db
    def test_perform_request_pod(self, add_bcs_pods, add_scene_view_model, monkeypatch_strategies_get_metric_list_v2):
        params = {"scene_id": "kubernetes", "type": "detail", "id": "pod", "bk_biz_id": 2}
        actual = resource.scene_view.get_scene_view(params)
        expect = {
            'id': 'pod',
            'mode': 'auto',
            'name': 'Pod',
            'options': {
                'alert_filterable': True,
                'detail_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesPod',
                            'data': {
                                'bcs_cluster_id': '$bcs_cluster_id',
                                'namespace': '$namespace',
                                'pod_name': '$pod_name',
                            },
                            'dataType': 'info',
                            'datasource': 'info',
                        }
                    ],
                    'title': 'Pod',
                    'type': 'info',
                },
                'enable_group': True,
                'enable_index_list': True,
                'panel_tool': {
                    'columns_toggle': True,
                    'compare_select': True,
                    'interval_select': True,
                    'method_select': True,
                    'split_switcher': False,
                },
                'selector_panel': {
                    'options': {
                        'selector_list': {
                            'default_sort_field': '-limit_cpu_usage_ratio',
                            'field_sort': True,
                            'query_update_url': True,
                            'status_filter': True,
                        }
                    },
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesPodList',
                            'data': {'bcs_cluster_id': '$bcs_cluster_id'},
                            'dataType': 'list',
                            'datasource': 'pod_list',
                            'fields': {
                                'bcs_cluster_id': 'bcs_cluster_id',
                                'namespace': 'namespace',
                                'pod_name': 'name',
                            },
                        }
                    ],
                    'title': 'Pods',
                    'type': 'table',
                },
                'show_panel_count': False,
            },
            'order': [
                {
                    'id': 'bk_monitor.time_series.k8s.pod.custom_1675931839480',
                    'panels': [
                        {'hidden': True, 'id': 'bk_monitor.time_series.k8s.pod.gpu_1', 'title': 'gpu_1'},
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.pod.gpu_2', 'title': 'gpu_2'},
                    ],
                    'title': 'GPU',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.pod.cpu',
                    'panels': [
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.container_cpu_cfs_periods_total',
                            'title': 'container_cpu_cfs_periods_total',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_cpu_usage_seconds_total',
                            'title': 'container_cpu_usage_seconds_total',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_limits_ratio',
                            'title': 'kube_pod_cpu_limits_ratio',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_requests_ratio',
                            'title': 'kube_pod_cpu_requests_ratio',
                        },
                    ],
                    'title': 'CPU',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.pod.memory',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_rss',
                            'title': 'container_memory_rss',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_working_set_bytes',
                            'title': 'container_memory_working_set_bytes',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_limits_ratio',
                            'title': 'kube_pod_memory_limits_ratio',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_requests_ratio',
                            'title': 'kube_pod_memory_requests_ratio',
                        },
                    ],
                    'title': '内存',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.pod.network',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_receive_bytes_total',
                            'title': 'container_network_receive_bytes_total',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_transmit_bytes_total',
                            'title': 'container_network_transmit_bytes_total',
                        },
                    ],
                    'title': '网络',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.pod.fs',
                    'panels': [
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.container_fs_inodes_free',
                            'title': 'container_fs_inodes_free',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.container_fs_usage_bytes',
                            'title': 'container_fs_usage_bytes',
                        },
                    ],
                    'title': '存储',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.pod.else',
                    'panels': [
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.container_spec_memory_limit_bytes',
                            'title': 'container_spec_memory_limit_bytes',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_container_resource_limits',
                            'title': 'kube_pod_container_resource_limits',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_container_status_restarts_total',
                            'title': 'kube_pod_container_status_restarts_total',
                        },
                    ],
                    'title': '其他',
                },
            ],
            'overview_panels': [
                {
                    'id': 'bk_monitor.time_series.k8s.pod.custom_1675931839480',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.gpu_2',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'gpu_2',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {'alias': 'A', 'field': 'gpu_2', 'method': '$method', 'table': ''}
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'gpu_2',
                            'type': 'graph',
                        }
                    ],
                    'title': 'GPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.cpu',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_cpu_usage_seconds_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_cpu_usage_seconds_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU使用量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_limits_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_cpu_limits_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_limits_cpu_cores',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU limit使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_requests_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_cpu_requests_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_requests_cpu_cores',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU request使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': 'CPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.memory',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_rss',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_memory_rss',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存使用量(rss)',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_working_set_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_memory_working_set_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_working_set_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存使用量(working_set)',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_limits_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_memory_limits_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_limits_memory_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存limit使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_requests_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_memory_requests_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_requests_memory_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存request使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': '内存',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.network',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_receive_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_network_receive_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_network_receive_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网络入带宽',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_transmit_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_network_transmit_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_network_transmit_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网络出带宽',
                            'type': 'graph',
                        },
                    ],
                    'title': '网络',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.fs',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_fs_usage_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_fs_usage_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_fs_usage_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '存储信息',
                            'type': 'graph',
                        }
                    ],
                    'title': '存储',
                    'type': 'row',
                },
            ],
            'panels': [
                {
                    'id': 'bk_monitor.time_series.k8s.pod.custom_1675931839480',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.gpu_2',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'gpu_2',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {'alias': 'A', 'field': 'gpu_2', 'method': '$method', 'table': ''}
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'gpu_2',
                            'type': 'graph',
                        }
                    ],
                    'title': 'GPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.cpu',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_cpu_usage_seconds_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_cpu_usage_seconds_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU使用量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_limits_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_cpu_limits_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_limits_cpu_cores',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU limit使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_cpu_requests_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_cpu_requests_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_cpu_usage_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_requests_cpu_cores',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU request使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': 'CPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.memory',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_rss',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_memory_rss',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存使用量(rss)',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_memory_working_set_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_memory_working_set_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_working_set_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存使用量(working_set)',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_limits_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_memory_limits_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_limits_memory_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存limit使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.kube_pod_memory_requests_ratio',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'kube_pod_memory_requests_ratio',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A/B*100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_memory_rss',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'kube_pod_container_resource_requests_memory_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '内存request使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': '内存',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.network',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_receive_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_network_receive_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_network_receive_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网络入带宽',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_network_transmit_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_network_transmit_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'rate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_network_transmit_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网络出带宽',
                            'type': 'graph',
                        },
                    ],
                    'title': '网络',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.pod.fs',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.pod.container_fs_usage_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'container_fs_usage_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'container_fs_usage_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'namespace', 'method': 'eq', 'value': ['$namespace']},
                                                    {'key': 'pod_name', 'method': 'eq', 'value': ['$pod_name']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '存储信息',
                            'type': 'graph',
                        }
                    ],
                    'title': '存储',
                    'type': 'row',
                },
                {
                    'hidden': False,
                    'id': 'bk_monitor.time_series.k8s.events',
                    'panels': [
                        {
                            'id': 'events',
                            'options': {'dashboard_common': {'static_width': True}},
                            'targets': [
                                {
                                    'api': 'scene_view.getKubernetesEvents',
                                    'data': {
                                        'bcs_cluster_id': '$bcs_cluster_id',
                                        'data_source_label': 'custom',
                                        'data_type': 'chart',
                                        'data_type_label': 'event',
                                        'kind': 'Pod',
                                        'name': '$pod_name',
                                        'namespace': '$namespace',
                                        'result_table_id': 'events',
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                },
                                {
                                    'api': 'scene_view.getKubernetesEvents',
                                    'data': {
                                        'bcs_cluster_id': '$bcs_cluster_id',
                                        'data_source_label': 'custom',
                                        'data_type_label': 'event',
                                        'kind': 'Pod',
                                        'name': '$pod_name',
                                        'namespace': '$namespace',
                                        'result_table_id': 'events',
                                    },
                                    'dataType': 'table',
                                    'datasource': 'event_list',
                                },
                            ],
                            'title': 'Events',
                            'type': 'event-log',
                        }
                    ],
                    'title': '事件',
                    'type': 'row',
                },
            ],
            'type': 'detail',
            'variables': [],
        }
        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_node(self, add_bcs_nodes, add_scene_view_model, monkeypatch_kubernetes_get_metrics_list):
        params = {"scene_id": "kubernetes", "type": "detail", "id": "node", "bk_biz_id": 2}
        actual = resource.scene_view.get_scene_view(params)
        expect = {
            'id': 'node',
            'mode': 'auto',
            'name': 'Node',
            'options': {
                'alert_filterable': True,
                'detail_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesNode',
                            'data': {'bcs_cluster_id': '$bcs_cluster_id', 'node_ip': '$node_ip'},
                            'dataType': 'info',
                            'datasource': 'info',
                        }
                    ],
                    'title': 'node',
                    'type': 'info',
                },
                'enable_group': True,
                'enable_index_list': True,
                'panel_tool': {
                    'columns_toggle': True,
                    'compare_select': True,
                    'interval_select': True,
                    'method_select': True,
                    'split_switcher': False,
                },
                'selector_panel': {
                    'options': {
                        'selector_list': {
                            'default_sort_field': '-system_cpu_summary_usage',
                            'field_sort': True,
                            'query_update_url': True,
                            'status_filter': True,
                        }
                    },
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesNodeList',
                            'data': {'bcs_cluster_id': '$bcs_cluster_id'},
                            'dataType': 'list',
                            'datasource': 'node_list',
                            'fields': {'bcs_cluster_id': 'bcs_cluster_id', 'node_ip': 'node_ip', 'node_name': 'name'},
                        }
                    ],
                    'title': 'nodes',
                    'type': 'table',
                },
                'show_panel_count': False,
            },
            'order': [
                {
                    'id': 'bk_monitor.time_series.k8s.node.cpu',
                    'panels': [
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.node_load15', 'title': '15分钟平均负载'},
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.cpu_summary.usage', 'title': 'CPU使用率'},
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.cpu_detail.usage',
                            'title': 'CPU单核使用率',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_cpu_seconds_total',
                            'title': 'node_cpu_seconds_total',
                        },
                    ],
                    'title': 'CPU',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.memory',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_MemFree_bytes',
                            'title': '物理内存空闲量',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_pct_used',
                            'title': '物理内存已用占比',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_used',
                            'title': '物理内存已用量',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.mem.pct_used',
                            'title': '应用程序内存使用占比',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.mem.used',
                            'title': '应用程序内存使用量',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_MemTotal_bytes',
                            'title': 'node_memory_MemTotal_bytes',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_Buffers_bytes',
                            'title': 'node_memory_Buffers_bytes',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_Cached_bytes',
                            'title': 'node_memory_Cached_bytes',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_Shmem_bytes',
                            'title': 'node_memory_Shmem_bytes',
                        },
                    ],
                    'title': '内存',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.network',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_receive_bytes_total',
                            'title': '网卡入流量',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_transmit_bytes_total',
                            'title': '网卡出流量',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_transmit_errs_total',
                            'title': 'node_network_transmit_errs_total',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_receive_errs_total',
                            'title': 'node_network_receive_errs_total',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_up',
                            'title': 'node_network_up',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_network_info',
                            'title': 'node_network_info',
                        },
                    ],
                    'title': '网络',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.disk',
                    'panels': [
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.disk.in_use', 'title': '磁盘空间使用率'},
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_reads_completed_total',
                            'title': 'I/O读次数',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_writes_completed_total',
                            'title': 'I/O写次数',
                        },
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.io.util', 'title': 'I/O使用率'},
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_io_time_seconds_total',
                            'title': 'node_disk_io_time_seconds_total',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_read_bytes_total',
                            'title': 'node_disk_read_bytes_total',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_written_bytes_total',
                            'title': 'node_disk_written_bytes_total',
                        },
                    ],
                    'title': '磁盘',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.else',
                    'panels': [
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.node_uname_info',
                            'title': 'node_uname_info',
                        }
                    ],
                    'title': 'else',
                },
            ],
            'overview_panels': [
                {
                    'id': 'bk_monitor.time_series.k8s.node.cpu',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_load15',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_load15',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_load15',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '15分钟平均负载',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.cpu_summary.usage',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'usage',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(1 - '
                                        'avg(irate(node_cpu_seconds_total{mode="idle",'
                                        'bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
                                        '* 100',
                                        'query_configs': [
                                            {
                                                'alias': 'A',
                                                'data_source_label': 'prometheus',
                                                'data_type_label': 'time_series',
                                                'interval': '$interval',
                                                'promql': '(1 '
                                                '- '
                                                'avg(irate(node_cpu_seconds_total{mode="idle",'
                                                'bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
                                                '* '
                                                '100',
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.cpu_detail.usage',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'usage',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(1 - '
                                        'avg '
                                        'by(cpu) '
                                        '(irate(node_cpu_seconds_total{mode="idle",'
                                        'bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
                                        '* 100',
                                        'query_configs': [
                                            {
                                                'alias': 'A',
                                                'data_source_label': 'prometheus',
                                                'data_type_label': 'time_series',
                                                'interval': '$interval',
                                                'promql': '(1 '
                                                '- '
                                                'avg '
                                                'by(cpu) '
                                                '(irate(node_cpu_seconds_total{mode="idle",'
                                                'bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
                                                '* '
                                                '100',
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU单核使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': 'CPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.memory',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_MemFree_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_memory_MemFree_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存空闲量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_pct_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'psc_pct_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B) ' '/ A * ' '100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存已用占比',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'psc_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A - B',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存已用量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.pct_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'pct_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B ' '- C - D ' '+ E) / ' 'A * 100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'C',
                                                        'field': 'node_memory_Cached_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'D',
                                                        'field': 'node_memory_Buffers_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'E',
                                                        'field': 'node_memory_Shmem_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '应用程序内存使用占比',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A - B - ' 'C - D + ' 'E',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'C',
                                                        'field': 'node_memory_Cached_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'D',
                                                        'field': 'node_memory_Buffers_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'E',
                                                        'field': 'node_memory_Shmem_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '应用程序内存使用量',
                            'type': 'graph',
                        },
                    ],
                    'title': '内存',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.network',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_network_receive_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_network_receive_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_network_receive_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网卡入流量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_network_transmit_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_network_transmit_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_network_transmit_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网卡出流量',
                            'type': 'graph',
                        },
                    ],
                    'title': '网络',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.disk',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.disk.in_use',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'in_use',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B) ' '/ A * ' '100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_filesystem_size_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'fstype',
                                                        'method': 'eq',
                                                        'value': ['ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'zfs'],
                                                    },
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    },
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_filesystem_free_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'fstype',
                                                        'method': 'eq',
                                                        'value': ['ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'zfs'],
                                                    },
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    },
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '磁盘空间使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_reads_completed_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_disk_reads_completed_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_reads_completed_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O读次数',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_writes_completed_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_disk_writes_completed_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_writes_completed_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O写次数',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.io.util',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'util',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A * 100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_io_time_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'in',
                                                        'value': ['BCS-K8S-00000', 'BCS-K8S-00001'],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': '磁盘',
                    'type': 'row',
                },
            ],
            'panels': [
                {
                    'id': 'bk_monitor.time_series.k8s.node.cpu',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_load15',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_load15',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_load15',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '15分钟平均负载',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.cpu_summary.usage',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'usage',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(1 - avg '
                                        'by(bcs_cluster_id, '
                                        'instance) '
                                        '(irate(node_cpu_seconds_total{mode="idle",'
                                        'instance=~"$node_ip:",'
                                        'bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) '
                                        '* 100',
                                        'query_configs': [
                                            {
                                                'alias': 'A',
                                                'data_source_label': 'prometheus',
                                                'data_type_label': 'time_series',
                                                'interval': '$interval',
                                                'promql': '(1 '
                                                '- '
                                                'avg '
                                                'by(bcs_cluster_id, '
                                                'instance) '
                                                '(irate(node_cpu_seconds_total{mode="idle",'
                                                'instance=~"$node_ip:",'
                                                'bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) '
                                                '* '
                                                '100',
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.cpu_detail.usage',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'usage',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(1 - avg by(cpu) '
                                        '(irate(node_cpu_seconds_total{mode="idle",'
                                        'instance=~"$node_ip:",bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) '
                                        '* 100',
                                        'query_configs': [
                                            {
                                                'alias': 'A',
                                                'data_source_label': 'prometheus',
                                                'data_type_label': 'time_series',
                                                'interval': '$interval',
                                                'promql': '(1 '
                                                '- '
                                                'avg '
                                                'by(cpu) '
                                                '(irate(node_cpu_seconds_total{mode="idle",'
                                                'instance=~"$node_ip:",bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) '
                                                '* '
                                                '100',
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'CPU单核使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': 'CPU',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.memory',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_memory_MemFree_bytes',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_memory_MemFree_bytes',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存空闲量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_pct_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'psc_pct_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B) / A * ' '100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存已用占比',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.psc_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'psc_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A - B',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '物理内存已用量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.pct_used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'pct_used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B - C - D + ' 'E) / A * 100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'C',
                                                        'field': 'node_memory_Cached_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'D',
                                                        'field': 'node_memory_Buffers_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'E',
                                                        'field': 'node_memory_Shmem_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '应用程序内存使用占比',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.mem.used',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'used',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A - B - C - D + ' 'E',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_memory_MemTotal_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_memory_MemFree_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'C',
                                                        'field': 'node_memory_Cached_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'D',
                                                        'field': 'node_memory_Buffers_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'E',
                                                        'field': 'node_memory_Shmem_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '应用程序内存使用量',
                            'type': 'graph',
                        },
                    ],
                    'title': '内存',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.network',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_network_receive_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_network_receive_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_network_receive_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网卡入流量',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_network_transmit_bytes_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_network_transmit_bytes_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_network_transmit_bytes_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '网卡出流量',
                            'type': 'graph',
                        },
                    ],
                    'title': '网络',
                    'type': 'row',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.disk',
                    'panels': [
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.disk.in_use',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'in_use',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': '(A - B) / A * ' '100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_filesystem_size_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'fstype',
                                                        'method': 'eq',
                                                        'value': ['ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'zfs'],
                                                    },
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    }
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'B',
                                                        'field': 'node_filesystem_free_bytes',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'fstype',
                                                        'method': 'eq',
                                                        'value': ['ext2', 'ext3', 'ext4', 'btrfs', 'xfs', 'zfs'],
                                                    },
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            },
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': '磁盘空间使用率',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_reads_completed_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_disk_reads_completed_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_reads_completed_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O读次数',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.node_disk_writes_completed_total',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': ''},
                            'subTitle': 'node_disk_writes_completed_total',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_writes_completed_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O写次数',
                            'type': 'graph',
                        },
                        {
                            'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                            'id': 'bk_monitor.time_series.k8s.node.io.util',
                            'options': {'legend': {'displayMode': 'list', 'placement': 'right'}, 'unit': 'percent'},
                            'subTitle': 'util',
                            'targets': [
                                {
                                    'api': 'grafana.graphUnifyQuery',
                                    'data': {
                                        'expression': 'A * 100',
                                        'query_configs': [
                                            {
                                                'data_source_label': 'bk_monitor',
                                                'data_type_label': 'time_series',
                                                'functions': [
                                                    {
                                                        'id': 'time_shift',
                                                        'params': [{'id': 'n', 'value': '$time_shift'}],
                                                    },
                                                    {'id': 'irate', 'params': [{'id': 'window', 'value': '2m'}]},
                                                ],
                                                'group_by': ['$group_by'],
                                                'interval': '$interval',
                                                'metrics': [
                                                    {
                                                        'alias': 'A',
                                                        'field': 'node_disk_io_time_seconds_total',
                                                        'method': '$method',
                                                        'table': '',
                                                    }
                                                ],
                                                'table': '',
                                                'where': [
                                                    {
                                                        'key': 'bcs_cluster_id',
                                                        'method': 'eq',
                                                        'value': ['$bcs_cluster_id'],
                                                    },
                                                    {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                                ],
                                            }
                                        ],
                                    },
                                    'data_type': 'time_series',
                                    'datasource': 'time_series',
                                }
                            ],
                            'title': 'I/O使用率',
                            'type': 'graph',
                        },
                    ],
                    'title': '磁盘',
                    'type': 'row',
                },
            ],
            'type': 'detail',
            'variables': [],
        }

        assert actual == expect

    @pytest.mark.django_db
    def test_perform_request_service_monitor__nodata(self, monkeypatch_cluster_management_fetch_clusters):
        params = {"scene_id": "kubernetes", "type": "", "id": "service_monitor", "bk_biz_id": 2}
        actual = resource.scene_view.get_scene_view(params)
        expect = {
            'id': 'service_monitor',
            'mode': 'auto',
            'name': 'ServiceMonitor',
            'options': {},
            'order': [],
            'overview_panels': [
                {
                    'gridPos': {'h': 24, 'w': 24, 'x': 0, 'y': 0},
                    'id': 1,
                    'targets': [
                        {
                            'data': {
                                'subTitle': '1. '
                                '确认集群中是否已经安装bkmonitor-operator\n'
                                '2. 确认ServiceMonitor '
                                'Yaml配置文件已经正确应用',
                                'title': '暂未发现任何ServiceMonitor',
                                'type': 'building',
                            }
                        }
                    ],
                    'title': '',
                    'type': 'exception-guide',
                }
            ],
            'panels': [],
            'type': 'detail',
            'variables': [
                {
                    'id': 0,
                    'options': {'variables': {'internal': True, 'multiple': False, 'required': False}},
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesServiceMonitorEndpoints',
                            'data': {
                                'bcs_cluster_id': '$bcs_cluster_id',
                                'metric_path': '$metric_path',
                                'name': '$bk_monitor_name',
                                'namespace': '$namespace',
                            },
                            'dataType': 'list',
                            'datasource': 'scene_view',
                            'fields': {'id': 'bk_bcs_monitor_endpoints_id'},
                        }
                    ],
                    'title': 'Endpoints',
                    'type': 'list',
                }
            ],
        }
        assert actual == expect
