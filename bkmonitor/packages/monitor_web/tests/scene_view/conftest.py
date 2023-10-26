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
from monitor_web.scene_view.builtin.kubernetes import KubernetesBuiltinProcessor
from monitor_web.scene_view.resources import GetKubernetesControlPlaneStatus
from monitor_web.strategies.resources import GetMetricListV2Resource

from api.cmdb.client import ListServiceInstanceDetail
from api.cmdb.default import GetHostByIP
from api.cmdb.define import Host
from bkmonitor.data_source import BkMonitorTimeSeriesDataSource

MOCK_SCENE_VIEW_GET_KUBERNETES_CONTROL_PLANIE_STATUS = [
    {'label': 'etcd', 'status': 'SUCCESS'},
    {'label': 'kube-apiserver', 'status': 'SUCCESS'},
    {'label': 'kube-controller-manager', 'status': 'SUCCESS'},
    {'label': 'kube-scheduler', 'status': 'SUCCESS'},
    {'label': 'kube-proxy', 'status': 'SUCCESS'},
    {'label': 'Kubelet', 'status': 'SUCCESS'},
]

MOCK_STRATEGIES_GET_METRIC_LIST_V2 = {
    "metric_list": [
        {
            'id': 281,
            'name': '重启次数',
            'bk_biz_id': 0,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'time_series',
            'dimensions': [
                {'id': 'pod', 'name': 'pod', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_monitor_type', 'name': 'bk_monitor_type', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_endpoint', 'name': 'bk_endpoint', 'is_dimension': True, 'type': 'string'},
                {'id': 'container', 'name': 'container', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_service', 'name': 'bk_service', 'is_dimension': True, 'type': 'string'},
                {'id': 'target', 'name': 'target', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_namespace', 'name': 'bk_namespace', 'is_dimension': True, 'type': 'string'},
                {'id': 'container_name', 'name': 'container_name', 'is_dimension': True, 'type': 'string'},
                {'id': 'pod_name', 'name': 'pod_name', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_job', 'name': 'bk_job', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_instance', 'name': 'bk_instance', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_biz_id', 'name': 'bk_biz_id', 'is_dimension': True, 'type': 'string'},
                {'id': 'bcs_cluster_id', 'name': 'bcs_cluster_id', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_container', 'name': 'bk_container', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_pod', 'name': 'bk_pod', 'is_dimension': True, 'type': 'string'},
                {'id': 'namespace', 'name': 'namespace', 'is_dimension': True, 'type': 'string'},
            ],
            'collect_interval': 1,
            'unit': '',
            'metric_field': 'kube_pod_container_status_restarts_total',
            'result_table_id': '',
            'time_field': 'time',
            'result_table_label': 'kubernetes',
            'result_table_label_name': 'kubernetes',
            'metric_field_name': '重启次数',
            'result_table_name': 'kube_pod',
            'description': '重启次数',
            'remarks': [],
            'default_condition': [],
            'default_dimensions': [],
            'default_trigger_config': {'check_window': 5, 'count': 1},
            'related_id': 'kube',
            'related_name': 'kube',
            'extend_fields': {},
            'use_frequency': 1,
            'disabled': False,
            'data_target': 'none_target',
            'metric_id': 'bk_monitor..kube_pod_container_status_restarts_total',
        },
        {
            'id': 274,
            'name': 'kube_pod_container_resource_limits',
            'bk_biz_id': 0,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'time_series',
            'dimensions': [
                {'id': 'pod', 'name': 'pod', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_monitor_type', 'name': 'bk_monitor_type', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_endpoint', 'name': 'bk_endpoint', 'is_dimension': True, 'type': 'string'},
                {'id': 'container', 'name': 'container', 'is_dimension': True, 'type': 'string'},
                {'id': 'node', 'name': 'node', 'is_dimension': True, 'type': 'string'},
                {'id': 'resource', 'name': 'resource', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_service', 'name': 'bk_service', 'is_dimension': True, 'type': 'string'},
                {'id': 'target', 'name': 'target', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_namespace', 'name': 'bk_namespace', 'is_dimension': True, 'type': 'string'},
                {'id': 'container_name', 'name': 'container_name', 'is_dimension': True, 'type': 'string'},
                {'id': 'pod_name', 'name': 'pod_name', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_job', 'name': 'bk_job', 'is_dimension': True, 'type': 'string'},
                {'id': 'unit', 'name': 'unit', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_instance', 'name': 'bk_instance', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_biz_id', 'name': 'bk_biz_id', 'is_dimension': True, 'type': 'string'},
                {'id': 'bcs_cluster_id', 'name': 'bcs_cluster_id', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_container', 'name': 'bk_container', 'is_dimension': True, 'type': 'string'},
                {'id': 'bk_pod', 'name': 'bk_pod', 'is_dimension': True, 'type': 'string'},
                {'id': 'namespace', 'name': 'namespace', 'is_dimension': True, 'type': 'string'},
            ],
            'collect_interval': 1,
            'unit': '',
            'metric_field': 'kube_pod_container_resource_limits',
            'result_table_id': '',
            'time_field': 'time',
            'result_table_label': 'kubernetes',
            'result_table_label_name': 'kubernetes',
            'metric_field_name': 'kube_pod_container_resource_limits',
            'result_table_name': 'kube_pod',
            'description': 'kube_pod_container_resource_limits',
            'remarks': [],
            'default_condition': [],
            'default_dimensions': [],
            'default_trigger_config': {'check_window': 5, 'count': 1},
            'related_id': 'kube',
            'related_name': 'kube',
            'extend_fields': {},
            'use_frequency': 0,
            'disabled': False,
            'data_target': 'none_target',
            'metric_id': 'bk_monitor..kube_pod_container_resource_limits',
        },
    ],
    "tag_list": [
        {'id': '__COMMON_USED__', 'name': '常用'},
        {'id': 'container', 'name': 'container'},
        {'id': 'kube', 'name': 'kube'},
        {'id': 'kubelet', 'name': 'kubelet'},
    ],
    "data_source_list": [
        {
            'count': 98,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'time_series',
            'id': 'bk_monitor_time_series',
            'name': '监控采集指标',
        },
        {
            'count': 0,
            'data_source_label': 'bk_log_search',
            'data_type_label': 'time_series',
            'id': 'log_time_series',
            'name': '日志平台指标',
        },
        {
            'count': 0,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'event',
            'id': 'bk_monitor_event',
            'name': '系统事件',
        },
        {
            'count': 0,
            'data_source_label': 'bk_data',
            'data_type_label': 'time_series',
            'id': 'bk_data_time_series',
            'name': '计算平台指标',
        },
        {'count': 0, 'data_source_label': 'custom', 'data_type_label': 'event', 'id': 'custom_event', 'name': '自定义事件'},
        {
            'count': 0,
            'data_source_label': 'custom',
            'data_type_label': 'time_series',
            'id': 'custom_time_series',
            'name': '自定义指标',
        },
        {
            'count': 0,
            'data_source_label': 'bk_log_search',
            'data_type_label': 'log',
            'id': 'bk_log_search_log',
            'name': '日志平台关键字',
        },
        {
            'count': 0,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'log',
            'id': 'bk_monitor_log',
            'name': '日志关键字事件',
        },
        {'count': 0, 'data_source_label': 'bk_fta', 'data_type_label': 'event', 'id': 'bk_fta_event', 'name': '第三方告警'},
        {'count': 0, 'data_source_label': 'bk_fta', 'data_type_label': 'alert', 'id': 'bk_fta_alert', 'name': '关联告警'},
        {
            'count': 0,
            'data_source_label': 'bk_monitor',
            'data_type_label': 'alert',
            'id': 'bk_monitor_alert',
            'name': '关联策略',
        },
    ],
    "scenario_list": [
        {'id': 'uptimecheck', 'name': '服务拨测', 'count': 0},
        {'id': 'application_check', 'name': '业务应用', 'count': 0},
        {'id': 'service_module', 'name': '服务模块', 'count': 0},
        {'id': 'component', 'name': '组件', 'count': 0},
        {'id': 'host_process', 'name': '进程', 'count': 0},
        {'id': 'os', 'name': '操作系统', 'count': 0},
        {'id': 'host_device', 'name': '主机设备', 'count': 0},
        {'id': 'kubernetes', 'name': 'kubernetes', 'count': 98},
        {'id': 'hardware_device', 'name': '硬件设备', 'count': 0},
        {'id': 'other_rt', 'name': '其他', 'count': 0},
    ],
}


@pytest.fixture
def monkeypatch_list_service_instance_detail(monkeypatch):
    mock_return_value = {
        "count": 1,
        "info": [
            {
                "bk_biz_id": 2,
                "process_instances": [
                    {
                        "process": {
                            "proc_num": None,
                            "bk_start_check_secs": None,
                            "bind_info": [
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 1,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 1,
                                    "port": "70",
                                },
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 2,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 2,
                                    "port": "7000-8000",
                                },
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 3,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 3,
                                    "port": "8800",
                                },
                            ],
                            "priority": None,
                            "pid_file": "",
                            "auto_start": None,
                            "stop_cmd": "",
                            "description": "",
                            "bk_process_id": 1,
                            "bk_process_name": "process_name",
                            "bk_start_param_regex": "",
                            "start_cmd": "",
                            "user": "",
                            "face_stop_cmd": "",
                            "bk_biz_id": 2,
                            "bk_func_name": "process_name",
                            "work_path": "",
                            "service_instance_id": 1,
                            "reload_cmd": "",
                            "timeout": None,
                            "bk_supplier_account": "tencent",
                            "restart_cmd": "",
                        },
                        "relation": {
                            "bk_biz_id": 2,
                            "process_template_id": 1,
                            "bk_host_id": 1,
                            "service_instance_id": 1,
                            "bk_process_id": 1,
                            "bk_supplier_account": "tencent",
                        },
                    }
                ],
                "bk_module_id": 1,
                "name": "1.1.1.1_process_name_80",
                "labels": None,
                "bk_host_id": 1,
                "bk_supplier_account": "tencent",
                "service_template_id": 1,
            }
        ],
    }
    monkeypatch.setattr(ListServiceInstanceDetail, "perform_request", lambda *args, **kwargs: mock_return_value)


@pytest.fixture
def monkeypatch_bk_monitor_time_series_data_source(monkeypatch):
    mock_return_value = [
        {
            "bind_ip": "0.0.0.0",
            "bk_biz_id": "2",
            "bk_cloud_id": "0",
            "bk_supplier_id": "0",
            "bk_target_cloud_id": "0",
            "bk_target_ip": "1.1.1.1",
            "display_name": "process_name",
            "hostname": None,
            "ip": "1.1.1.1",
            "listen": "[70,71,7000]",
            "nonlisten": "[90]",
            "not_accurate_listen": '["0.0.0.0:100"]',
            "param_regex": None,
            "port_health": 1,
            "proc_exists": 1,
            "proc_name": "process_name",
            "protocol": "tcp",
            "_time_": 1662360180000,
        },
        {
            "bind_ip": "0.0.0.0",
            "bk_biz_id": "2",
            "bk_cloud_id": "0",
            "bk_supplier_id": "0",
            "bk_target_cloud_id": "0",
            "bk_target_ip": "1.1.1.1",
            "display_name": "process_name",
            "hostname": None,
            "ip": "1.1.1.1",
            "listen": "[70,71]",
            "nonlisten": "[90]",
            "not_accurate_listen": '["0.0.0.0:100"]',
            "param_regex": None,
            "port_health": 1,
            "proc_exists": 1,
            "proc_name": "process_name",
            "protocol": "udp",
            "_time_": 1662360180000,
        },
    ]
    monkeypatch.setattr(BkMonitorTimeSeriesDataSource, "query_data", lambda *args, **kwargs: mock_return_value)


@pytest.fixture
def monkeypatch_cmdb_get_info_by_ip(monkeypatch):
    """返回主机信息 ."""
    mock_return_value = [
        Host(
            {
                "bk_biz_id": 2,
                "bk_host_innerip": "1.1.1.1",
                "ip": "1.1.1.1",
                "bk_host_id": 1,
                "bk_cloud_id": 0,
            }
        )
    ]
    monkeypatch.setattr(GetHostByIP, "perform_request", lambda self, params: mock_return_value)


@pytest.fixture
def monkeypatch_get_kubernetes_control_plane_status(monkeypatch):
    """返回一个集群的容器container usage信息 ."""
    monkeypatch.setattr(
        GetKubernetesControlPlaneStatus,
        "perform_request",
        lambda self, params: MOCK_SCENE_VIEW_GET_KUBERNETES_CONTROL_PLANIE_STATUS,
    )


@pytest.fixture
def monkeypatch_strategies_get_metric_list_v2(monkeypatch):
    """返回metrics指标数据 ."""
    monkeypatch.setattr(
        GetMetricListV2Resource, "perform_request", lambda self, params: MOCK_STRATEGIES_GET_METRIC_LIST_V2
    )


@pytest.fixture
def add_scene_view_model(monkeypatch):
    """添加视图order配置 ."""
    SceneViewModel.objects.all().delete()
    SceneViewModel.objects.create(
        **{
            'bk_biz_id': 2,
            'id': 'pod',
            'list': [],
            'mode': 'auto',
            'name': 'Pod',
            'options': {
                'detail_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesPod',
                            'data': {'bcs_cluster_id': '$bcs_cluster_id', 'pod_name': '$pod_name'},
                            'dataType': 'info',
                            'datasource': 'info',
                        }
                    ],
                    'title': 'Pod',
                    'type': 'info',
                },
                'enable_group': True,
                'panel_tool': {
                    'columns_toggle': True,
                    'compare_select': True,
                    'interval_select': False,
                    'method_select': False,
                    'need_compare_target': True,
                    'split_switcher': False,
                },
                'selector_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesPods',
                            'compare_fields': {
                                'bcs_cluster_id': 'bcs_cluster_id',
                                'namespace': 'namespace',
                                'pod_name': 'pod_name',
                            },
                            'data': {'bcs_cluster_id': '$bcs_cluster_id'},
                            'dataType': 'list',
                            'datasource': 'pod_list',
                            'fields': {
                                'bcs_cluster_id': 'bcs_cluster_id',
                                'namespace': 'namespace',
                                'pod_name': 'pod_name',
                            },
                        }
                    ],
                    'title': 'Pods',
                    'type': 'list',
                },
                'show_panel_count': True,
            },
            'order': [
                {
                    'id': 'custom_1675931839480',
                    'panels': [
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.pod.gpu_1',
                            'title': 'gpu_1',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.pod.gpu_2',
                            'title': 'gpu_2',
                        },
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
                        }
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
                    ],
                    'title': '其他',
                },
            ],
            'panels': [],
            'scene_id': 'kubernetes',
            'type': '',
            'unique_id': 10,
            'variables': [],
        }
    )
    SceneViewModel.objects.create(
        **{
            'bk_biz_id': 2,
            'id': 'node',
            'list': [],
            'mode': 'auto',
            'name': 'Node',
            'options': {
                'detail_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesNode',
                            'data': {'bcs_cluster_id': '$bcs_cluster_id', 'node_ip': '$bk_target_ip'},
                            'dataType': 'info',
                            'datasource': 'info',
                        }
                    ],
                    'title': 'node',
                    'type': 'info',
                },
                'enable_group': True,
                'panel_tool': {
                    'columns_toggle': True,
                    'compare_select': True,
                    'interval_select': False,
                    'method_select': False,
                    'need_compare_target': True,
                    'split_switcher': False,
                },
                'selector_panel': {
                    'targets': [
                        {
                            'api': 'scene_view.getKubernetesNodes',
                            'compare_fields': {'node_ip': 'bk_target_ip'},
                            'data': {
                                'bcs_cluster_id': '$bcs_cluster_id',
                                'node_ip': '$node_ip',
                                'node_name': 'node_name',
                            },
                            'dataType': 'list',
                            'datasource': 'node_list',
                            'fields': {
                                'bcs_cluster_id': 'bcs_cluster_id',
                                'node_ip': 'bk_target_ip',
                                'node_name': 'node_name',
                            },
                        }
                    ],
                    'title': 'nodes',
                    'type': 'list',
                },
                'show_panel_count': True,
            },
            'order': [
                {
                    'id': 'bk_monitor.time_series.k8s.node.custom_1676273173178',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.cpu_detail.usage',
                            'title': 'CPU单核使用率',
                        }
                    ],
                    'title': 'GPU',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.cpu',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.load.load5',
                            'title': 'load5',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.cpu_summary.usage',
                            'title': 'CPU使用率',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.system.cpu_detail.guest',
                            'title': 'guest',
                        },
                        {
                            'hidden': True,
                            'id': 'bk_monitor.time_series.k8s.node.system.cpu_detail.idle',
                            'title': 'idle',
                        },
                    ],
                    'title': 'CPU',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.memory',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.mem.free',
                            'title': '物理内存空闲量',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.swap.used',
                            'title': 'used',
                        },
                    ],
                    'title': '内存',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.network',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.net.speed_recv_bit',
                            'title': '网卡入流量比特速率',
                        },
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.net.speed_sent_bit',
                            'title': '网卡出流量比特速率',
                        },
                    ],
                    'title': '网络',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.disk',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.disk.in_use',
                            'title': '磁盘空间使用率',
                        },
                        {'hidden': False, 'id': 'bk_monitor.time_series.k8s.node.system.io.r_s', 'title': 'I/O读次数'},
                    ],
                    'title': '磁盘',
                },
                {
                    'id': 'bk_monitor.time_series.k8s.node.process',
                    'panels': [
                        {
                            'hidden': False,
                            'id': 'bk_monitor.time_series.k8s.node.system.env.procs',
                            'title': '系统总进程数',
                        }
                    ],
                    'title': '系统进程',
                },
                {'id': 'bk_monitor.time_series.k8s.node.__UNGROUP__', 'panels': [], 'title': '未分组的指标'},
            ],
            'panels': [],
            'scene_id': 'kubernetes',
            'type': '',
            'unique_id': 9,
            'variables': [],
        }
    )


@pytest.fixture
def monkeypatch_kubernetes_get_metrics_list(monkeypatch):
    def mock_return(view, metric_prefixes):
        if metric_prefixes == ["node_"]:
            result = [
                'node_cpu_seconds_total',
                'node_timex_offset_seconds',
                'node_memory_MemTotal_bytes',
                'node_memory_Buffers_bytes',
                'node_memory_Cached_bytes',
                'node_memory_MemFree_bytes',
                'node_memory_Shmem_bytes',
                'node_disk_io_time_seconds_total',
                'node_filesystem_size_bytes',
                'node_filesystem_free_bytes',
                'node_load15',
                'node_filefd_allocated',
                'node_filefd_maximum',
                'node_filesystem_files',
                'node_filesystem_files_free',
                'node_network_transmit_errs_total',
                'node_network_receive_errs_total',
                'node_network_up',
                'node_nf_conntrack_entries',
                'node_nf_conntrack_entries_limit',
                'node_timex_sync_status',
                'node_network_receive_bytes_total',
                'node_filesystem_avail_bytes',
                'node_uname_info',
                'node_network_info',
                'node_network_transmit_bytes_total',
                'node_disk_reads_completed_total',
                'node_disk_read_bytes_total',
                'node_disk_writes_completed_total',
                'node_disk_written_bytes_total',
            ]
            return result

        return []

    monkeypatch.setattr(KubernetesBuiltinProcessor, "get_metrics_list", mock_return)
