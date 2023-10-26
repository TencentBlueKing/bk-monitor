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
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin.constants import DEFAULT_NODE_PANELS
from monitor_web.scene_view.builtin.kubernetes import KubernetesBuiltinProcessor

pytestmark = pytest.mark.django_db


NODE_ORDER = [
    {
        'id': 'bk_monitor.time_series.k8s.node.cpu',
        'panels': [
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.node_load15', 'title': '15分钟平均负载'},
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.cpu_summary.usage', 'title': 'CPU使用率'},
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.cpu_detail.usage', 'title': 'CPU单核使用率'},
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
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.mem.psc_pct_used', 'title': '物理内存已用占比'},
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.mem.psc_used', 'title': '物理内存已用量'},
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.mem.pct_used', 'title': '应用程序内存使用占比'},
            {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.mem.used', 'title': '应用程序内存使用量'},
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
]
NODE_PANELS = [
    {
        'id': 'bk_monitor.time_series.k8s.node.cpu',
        'panels': [
            {
                'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                'id': 'bk_monitor.time_series.k8s.node.node_load15',
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
                                    ],
                                    'group_by': ['$group_by'],
                                    'interval': '$interval',
                                    'metrics': [
                                        {'alias': 'A', 'field': 'node_load15', 'method': '$method', 'table': ''}
                                    ],
                                    'table': '',
                                    'where': [
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
                'subTitle': 'usage',
                'targets': [
                    {
                        'api': 'grafana.graphUnifyQuery',
                        'data': {
                            'expression': '(1 - avg '
                            'by(bcs_cluster_id, '
                            'instance) '
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
                                    'by(bcs_cluster_id, '
                                    'instance) '
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
                'title': 'CPU使用率',
                'type': 'graph',
            },
            {
                'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                'id': 'bk_monitor.time_series.k8s.node.cpu_detail.usage',
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
                'subTitle': 'usage',
                'targets': [
                    {
                        'api': 'grafana.graphUnifyQuery',
                        'data': {
                            'expression': '(1 - avg by(cpu) '
                            '(irate(node_cpu_seconds_total{'
                            'mode="idle",instance=~"$node_ip:",bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) '
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
                                    '(irate(node_cpu_seconds_total{'
                                    'mode="idle",'
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
                                        {'key': 'instance', 'method': 'reg', 'value': ['^$node_ip:']},
                                    ],
                                },
                                {
                                    'data_source_label': 'bk_monitor',
                                    'data_type_label': 'time_series',
                                    'functions': [
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                                        {'key': 'bcs_cluster_id', 'method': 'eq', 'value': ['$bcs_cluster_id']},
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
]
NODE_OVERVIEW_PANELS = [
    {
        'id': 'bk_monitor.time_series.k8s.node.cpu',
        'panels': [
            {
                'gridPos': {'h': 8, 'w': 24, 'x': 0, 'y': 0},
                'id': 'bk_monitor.time_series.k8s.node.node_load15',
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
                                    ],
                                    'group_by': ['$group_by'],
                                    'interval': '$interval',
                                    'metrics': [
                                        {'alias': 'A', 'field': 'node_load15', 'method': '$method', 'table': ''}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
                'subTitle': 'usage',
                'targets': [
                    {
                        'api': 'grafana.graphUnifyQuery',
                        'data': {
                            'expression': '(1 - '
                            'avg(irate(node_cpu_seconds_total{'
                            'mode="idle",bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
                            '* 100',
                            'query_configs': [
                                {
                                    'alias': 'A',
                                    'data_source_label': 'prometheus',
                                    'data_type_label': 'time_series',
                                    'interval': '$interval',
                                    'promql': '(1 '
                                    '- '
                                    'avg(irate(node_cpu_seconds_total{'
                                    'mode="idle",bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
                'subTitle': 'usage',
                'targets': [
                    {
                        'api': 'grafana.graphUnifyQuery',
                        'data': {
                            'expression': '(1 - '
                            'avg '
                            'by(cpu) '
                            '(irate(node_cpu_seconds_total{'
                            'mode="idle",bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
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
                                    '(irate(node_cpu_seconds_total{'
                                    'mode="idle",bcs_cluster_id=~"^(BCS-K8S-00000|BCS-K8S-00001)$"}[5m]))) '
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]}
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
                'options': {'legend': {'displayMode': 'list', 'placement': 'right'}},
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
                                        {'id': 'time_shift', 'params': [{'id': 'n', 'value': '$time_shift'}]},
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
]


class TestKubernetesBuiltinProcessor:
    def test_build_node_order(self, add_scene_view_model, monkeypatch_kubernetes_get_metrics_list):
        bk_biz_id = 2
        scene_id = "kubernetes"
        view_id = "node"
        scene_type = ""

        view = SceneViewModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type, id=view_id
        ).first()

        default_detail_config = DEFAULT_NODE_PANELS
        panel_group_map = KubernetesBuiltinProcessor.build_panel_group(view, default_detail_config)
        actual = KubernetesBuiltinProcessor.build_order(view, default_detail_config, panel_group_map)
        expect = NODE_ORDER

        assert actual == expect

    def test_build_node_panels(self, add_scene_view_model, monkeypatch_kubernetes_get_metrics_list):
        bk_biz_id = 2
        scene_id = "kubernetes"
        view_id = "node"
        scene_type = ""
        where = [
            {
                "key": "bcs_cluster_id",
                "method": "eq",
                "value": ["$bcs_cluster_id"],
            },
            {
                "key": "instance",
                "method": "reg",
                "value": ["^$node_ip:"],
            },
        ]

        view = SceneViewModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type, id=view_id
        ).first()

        default_detail_config = DEFAULT_NODE_PANELS
        panel_group_map = KubernetesBuiltinProcessor.build_panel_group(view, default_detail_config)
        order = KubernetesBuiltinProcessor.build_order(view, default_detail_config, panel_group_map)
        actual = KubernetesBuiltinProcessor.build_panels(order, panel_group_map, where)
        expect = NODE_PANELS

        assert actual == expect

    def test_get_node_view_config(self, add_bcs_nodes, add_scene_view_model, monkeypatch_kubernetes_get_metrics_list):
        bk_biz_id = 2
        scene_id = "kubernetes"
        view_id = "node"
        scene_type = ""

        view = SceneViewModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type, id=view_id
        ).first()

        view_config = {}
        KubernetesBuiltinProcessor.get_node_view_config(view, view_config)

        expect = {
            'order': NODE_ORDER,
            'overview_panels': NODE_OVERVIEW_PANELS,
            'panels': NODE_PANELS,
        }
        assert view_config == expect
