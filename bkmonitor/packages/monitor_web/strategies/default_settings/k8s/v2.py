# -*- coding: utf-8 -*-
from django.utils.translation import gettext as _

"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    nodata_recover_detects_config,
    remind_algorithms_config,
    remind_detects_config,
    warning_algorithms_config,
    warning_detects_config,
)

DEFAULT_K8S_STRATEGIES = [
    {
        "detects": warning_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 1),
                "expression": "a /b * 100",
                "functions": [],
                "name": "sum_without_time(rest_client_requests_total) "
                "/sum_without_time(rest_client_requests_total) * 100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"key": "code", "method": "eq", "value": ["^5[0-9][0-9]"]}],
                        "agg_dimension": ["bcs_cluster_id", "instance", "job"],
                        "agg_interval": 300,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "rate", "params": [{"id": "window", "value": "5m"}]}],
                        "metric_field": "rest_client_requests_total",
                        "metric_id": "bk_monitor..rest_client_requests_total",
                        "name": "rest_client_requests_total",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance", "job"],
                        "agg_interval": 300,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "rest_client_requests_total",
                        "metric_id": "bk_monitor..rest_client_requests_total",
                        "name": "rest_client_requests_total",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-master"],
        "name": _("[kube Master] 客户端访问 APIServer 出错 rest_client_requests_total_5xx"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": remind_algorithms_config("gte", 0),
                "expression": "a/b-(c-1)/c",
                "functions": [],
                "name": (
                    "sum_without_time(mem "
                    "requests)/sum_without_time(kube_node_status_allocatable_memory_bytes)-"
                    "(count_without_time(kube_node_status_allocatable_memory_bytes)-1)/"
                    "count_without_time(kube_node_status_allocatable_memory_bytes)"
                ),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "bcs_cluster_id", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "node", "method": "neq", "value": [""]},
                        ],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_container_resource_requests_memory_bytes",
                        "metric_id": "bk_monitor..kube_pod_container_resource_requests_memory_bytes",
                        "name": _("内存 requests"),
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "bcs_cluster_id", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "node", "method": "neq", "value": [""]},
                        ],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_status_allocatable_memory_bytes",
                        "metric_id": "bk_monitor..kube_node_status_allocatable_memory_bytes",
                        "name": "kube_node_status_allocatable_memory_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "bcs_cluster_id", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "node", "method": "neq", "value": [""]},
                        ],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "count_without_time",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_status_allocatable_memory_bytes",
                        "metric_id": "bk_monitor..kube_node_status_allocatable_memory_bytes",
                        "name": "kube_node_status_allocatable_memory_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), _("k8s_集群资源")],
        "name": _("[kube 集群资源] 集群的内存资源分配过载-KubeMemoryOvercommit"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a/b-(c-1)/c",
                "functions": [],
                "name": (
                    "sum_without_time(CPU "
                    "requests)/sum_without_time(kube_node_status_allocatable_cpu_cores)-"
                    "(count_without_time(kube_node_status_allocatable_cpu_cores)-1)/"
                    "count_without_time(kube_node_status_allocatable_cpu_cores)"
                ),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"condition": "and", "key": "node", "method": "neq", "value": [""]}],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_container_resource_requests_cpu_cores",
                        "metric_id": "bk_monitor..kube_pod_container_resource_requests_cpu_cores",
                        "name": "CPU requests",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [{"condition": "and", "key": "node", "method": "neq", "value": [""]}],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_status_allocatable_cpu_cores",
                        "metric_id": "bk_monitor..kube_node_status_allocatable_cpu_cores",
                        "name": "kube_node_status_allocatable_cpu_cores",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [{"condition": "and", "key": "node", "method": "neq", "value": [""]}],
                        "agg_dimension": ["bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "count_without_time",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_status_allocatable_cpu_cores",
                        "metric_id": "bk_monitor..kube_node_status_allocatable_cpu_cores",
                        "name": "kube_node_status_allocatable_cpu_cores",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), _("k8s_集群资源")],
        "name": _("[kube集群资源] 集群的CPU资源分配过载-KubeCPUOvercommit"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": remind_algorithms_config("gte", 25),
                "expression": "a/b * 100",
                "functions": [],
                "name": _("sum_without_time(CPU节流周期间隔数)/sum_without_time(CPU执行周期间隔时间数) " "* 100"),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {
                                "condition": "and",
                                "key": "container",
                                "method": "neq",
                                "value": ["tke-monitor-agent", "bscp-sidecar"],
                            },
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod", "container"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "5m"}]}],
                        "metric_field": "container_cpu_cfs_throttled_periods_total",
                        "metric_id": "bk_monitor..container_cpu_cfs_throttled_periods_total",
                        "name": _("CPU节流周期间隔数"),
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {
                                "condition": "and",
                                "key": "container",
                                "method": "neq",
                                "value": ["tke-monitor-agent", "bscp-sidecar"],
                            },
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod", "container"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "5m"}]}],
                        "metric_field": "container_cpu_cfs_periods_total",
                        "metric_id": "bk_monitor..container_cpu_cfs_periods_total",
                        "name": _("CPU执行周期间隔时间数"),
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] pod的CPU 执行周期受限占比高CPUThrottlingHigh"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(1, 5, 3),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a - b",
                "functions": [{"id": "abs", "params": []}],
                "name": "MAX(kube_job_spec_completions) - " "MAX(kube_job_status_succeeded)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "job_name"],
                        "agg_interval": 3600,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_job_spec_completions",
                        "metric_id": "bk_monitor..kube_job_spec_completions",
                        "name": "kube_job_spec_completions",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]}
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "job_name"],
                        "agg_interval": 3600,
                        "agg_method": "MAX",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_job_status_succeeded",
                        "metric_id": "bk_monitor..kube_job_status_succeeded",
                        "name": "kube_job_status_succeeded",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-job"],
        "name": _("[kube kubelet]  job运行太久"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": remind_algorithms_config("gte", 95),
                "expression": "a /  b * 100",
                "functions": [],
                "name": _("SUM(CPU使用量) /  sum_without_time(CPU limits) * 100"),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod", "container"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "rate", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "container_cpu_usage_seconds_total",
                        "metric_id": "bk_monitor..container_cpu_usage_seconds_total",
                        "name": _("CPU使用量"),
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod", "container"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_container_resource_limits_cpu_cores",
                        "metric_id": "bk_monitor..kube_pod_container_resource_limits_cpu_cores",
                        "name": "CPU limits",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] pod 的 CPU 使用率高"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": nodata_recover_detects_config(5, 5, 1, 3),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "MAX(kube_pod_container_status_terminated_reason)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "reason", "method": "eq", "value": ["OOMKilled"]},
                            {
                                "condition": "and",
                                "key": "namespace",
                                "method": "neq",
                                "value": ["", "bkmonitor-operator"],
                            },
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod_name"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "kube_pod_container_status_terminated_reason",
                        "metric_id": "bk_monitor..kube_pod_container_status_terminated_reason",
                        "name": "kube_pod_container_status_terminated_reason",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] pod 因OOM重启"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "max_without_time(kube_pod_container_status_waiting_reason)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                            {
                                "condition": "and",
                                "key": "namespace",
                                "method": "neq",
                                "value": ["", "bkmonitor-operator"],
                            },
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod", "container"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_container_status_waiting_reason",
                        "metric_id": "bk_monitor..kube_pod_container_status_waiting_reason",
                        "name": "kube_pod_container_status_waiting_reason",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] 容器状态异常"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a * b",
                "functions": [],
                "name": "max_without_time(kube_pod_status_phase) * " "max_without_time(kube_pod_owner)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "phase", "method": "eq", "value": ["Pending", "Unknown"]},
                            {
                                "condition": "and",
                                "key": "namespace",
                                "method": "neq",
                                "value": ["", "bkmonitor-operator"],
                            },
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod"],
                        "agg_interval": 600,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_status_phase",
                        "metric_id": "bk_monitor..kube_pod_status_phase",
                        "name": "kube_pod_status_phase",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "owner_kind", "method": "neq", "value": ["Job"]},
                            {
                                "condition": "and",
                                "key": "namespace",
                                "method": "neq",
                                "value": ["", "bkmonitor-operator"],
                            },
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "pod"],
                        "agg_interval": 600,
                        "agg_method": "max_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_pod_owner",
                        "metric_id": "bk_monitor..kube_pod_owner",
                        "name": "kube_pod_owner",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] pod 状态异常"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "(a - b) and(c == 0)",
                "functions": [{"id": "abs", "params": []}],
                "name": "(AVG(kube_hpa_status_desired_replicas) - "
                "AVG(kube_hpa_status_current_replicas)) "
                "AVG(kube_hpa_status_desired_replicas)nd(AVG(kube_hpa_status_current_replicas) "
                "== 0)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "hpa", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "hpa"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_hpa_status_desired_replicas",
                        "metric_id": "bk_monitor..kube_hpa_status_desired_replicas",
                        "name": "kube_hpa_status_desired_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "hpa", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "hpa"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_hpa_status_current_replicas",
                        "metric_id": "bk_monitor..kube_hpa_status_current_replicas",
                        "name": "kube_hpa_status_current_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "hpa", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "hpa"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "changes", "params": [{"id": "window", "value": "10m"}]}],
                        "metric_field": "kube_hpa_status_current_replicas",
                        "metric_id": "bk_monitor..kube_hpa_status_current_replicas",
                        "name": "kube_hpa_status_current_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-hpa"],
        "name": _("[kube hpa] 副本数和HPA不匹配"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("eq", 0),
                "expression": "a - b",
                "functions": [{"id": "abs", "params": []}],
                "name": "AVG(kube_hpa_status_current_replicas) - " "AVG(kube_hpa_spec_max_replicas)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "hpa", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "hpa"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_hpa_status_current_replicas",
                        "metric_id": "bk_monitor..kube_hpa_status_current_replicas",
                        "name": "kube_hpa_status_current_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "hpa", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "hpa"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_hpa_spec_max_replicas",
                        "metric_id": "bk_monitor..kube_hpa_spec_max_replicas",
                        "name": "kube_hpa_spec_max_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-hpa"],
        "name": _("[kube hpa] 副本数达到HPA最大值"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "(a-b) and (c ==0)",
                "functions": [{"id": "abs", "params": []}],
                "name": "(AVG(kube_deployment_spec_replicas)-AVG(kube_deployment_status_replicas_available)) "
                "AVG(kube_deployment_spec_replicas)nd "
                "(AVG(kube_deployment_status_replicas_updated) ==0)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "deployment", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "deployment"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_deployment_spec_replicas",
                        "metric_id": "bk_monitor..kube_deployment_spec_replicas",
                        "name": "kube_deployment_spec_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "deployment", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "deployment"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_deployment_status_replicas_available",
                        "metric_id": "bk_monitor..kube_deployment_status_replicas_available",
                        "name": "kube_deployment_status_replicas_available",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "deployment", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "deployment", "namespace"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "changes", "params": [{"id": "window", "value": "10m"}]}],
                        "metric_field": "kube_deployment_status_replicas_updated",
                        "metric_id": "bk_monitor..kube_deployment_status_replicas_updated",
                        "name": "kube_deployment_status_replicas_updated",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-deployment"],
        "name": _("[kube deployment] deployment 副本数不匹配"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a - b",
                "functions": [{"id": "abs", "params": []}],
                "name": "AVG(kube_deployment_status_observed_generation) - " "AVG(kube_deployment_metadata_generation)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "deployment", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "deployment"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_deployment_status_observed_generation",
                        "metric_id": "bk_monitor..kube_deployment_status_observed_generation",
                        "name": "kube_deployment_status_observed_generation",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "deployment", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "deployment"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_deployment_metadata_generation",
                        "metric_id": "bk_monitor..kube_deployment_metadata_generation",
                        "name": "kube_deployment_metadata_generation",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-deployment"],
        "name": _("[kube deployment] deployment 部署版本不匹配"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "(a - b) and   (c == 0)",
                "functions": [{"id": "abs", "params": []}],
                "name": "(max_without_time(kube_statefulset_status_replicas_ready) "
                "- max_without_time(kube_statefulset_status_replicas)) "
                "max_without_time(kube_statefulset_status_replicas_ready)nd   "
                "(max_without_time(kube_statefulset_status_replicas_updated) "
                "== 0)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "statefulset"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_statefulset_status_replicas_ready",
                        "metric_id": "bk_monitor..kube_statefulset_status_replicas_ready",
                        "name": "kube_statefulset_status_replicas_ready",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "statefulset"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_statefulset_status_replicas",
                        "metric_id": "bk_monitor..kube_statefulset_status_replicas",
                        "name": "kube_statefulset_status_replicas",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]}
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "statefulset"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "changes", "params": [{"id": "window", "value": "10m"}]}],
                        "metric_field": "kube_statefulset_status_replicas_updated",
                        "metric_id": "bk_monitor..kube_statefulset_status_replicas_updated",
                        "name": "kube_statefulset_status_replicas_updated",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-statefulset"],
        "name": _("[kube statefulset] statefulset 副本数不匹配"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a - b",
                "functions": [{"id": "abs", "params": []}],
                "name": "max_without_time(kube_statefulset_status_observed_generation) "
                "- max_without_time(kube_statefulset_metadata_generation)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "statefulset"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_statefulset_status_observed_generation",
                        "metric_id": "bk_monitor..kube_statefulset_status_observed_generation",
                        "name": "kube_statefulset_status_observed_generation",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "statefulset"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_statefulset_metadata_generation",
                        "metric_id": "bk_monitor..kube_statefulset_metadata_generation",
                        "name": "kube_statefulset_metadata_generation",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-statefulset"],
        "name": _("[kube statefulset] statefulset 部署版本不匹配"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "sum_without_time(node_network_up)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["node-exporter"]}
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "namespace", "pod"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "changes", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "node_network_up",
                        "metric_id": "bk_monitor..node_network_up",
                        "name": "node_network_up",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 网卡状态不稳定"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 10),
                "expression": "a",
                "functions": [],
                "name": "SUM(node_network_receive_errs_total)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance", "device"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "node_network_receive_errs_total",
                        "metric_id": "bk_monitor..node_network_receive_errs_total",
                        "name": "node_network_receive_errs_total",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 网卡接收出错"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 10),
                "expression": "a",
                "functions": [],
                "name": "SUM(node_network_transmit_errs_total)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance", "device"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "node_network_transmit_errs_total",
                        "metric_id": "bk_monitor..node_network_transmit_errs_total",
                        "name": "node_network_transmit_errs_total",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 网卡发送出错"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": [
                    {
                        "config": [[{"method": "gt", "threshold": 0.05}], [{"method": "lte", "threshold": -0.05}]],
                        "level": 3,
                        "type": "Threshold",
                        "unit_prefix": "",
                    }
                ],
                "expression": "a and b",
                "functions": [],
                "name": "MAX(node_timex_offset_seconds) "
                "MAX(node_timex_offset_seconds)nd "
                "AVG(node_timex_offset_seconds)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_timex_offset_seconds",
                        "metric_id": "bk_monitor..node_timex_offset_seconds",
                        "name": "node_timex_offset_seconds",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 300,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "deriv", "params": [{"id": "window", "value": "5m"}]}],
                        "metric_field": "node_timex_offset_seconds",
                        "metric_id": "bk_monitor..node_timex_offset_seconds",
                        "name": "node_timex_offset_seconds",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node]-机器时钟漂移"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": remind_algorithms_config("gte", 10),
                "expression": "a * b",
                "functions": [],
                "name": "SUM(kubelet_pleg_relist_duration_seconds_bucket) * " "AVG(kubelet_node_name)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]}
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "le", "node"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [
                            {"id": "rate", "params": [{"id": "window", "value": "5m"}]},
                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]},
                        ],
                        "metric_field": "kubelet_pleg_relist_duration_seconds_bucket",
                        "metric_id": "bk_monitor..kubelet_pleg_relist_duration_seconds_bucket",
                        "name": "kubelet_pleg_relist_duration_seconds_bucket",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kubelet"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["instance", "bcs_cluster_id", "node"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kubelet_node_name",
                        "metric_id": "bk_monitor..kubelet_node_name",
                        "name": "kubelet_node_name",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-kubelet"],
        "name": _("[kube kubelet] PLEG 耗时高 kubelet_pleg_relist"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 75),
                "expression": "a/b*100",
                "functions": [],
                "name": (
                    "max_without_time(node_nf_conntrack_entries)/"
                    "max_without_time(node_nf_conntrack_entries_limit)*100"
                ),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_nf_conntrack_entries",
                        "metric_id": "bk_monitor..node_nf_conntrack_entries",
                        "name": "node_nf_conntrack_entries",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_nf_conntrack_entries_limit",
                        "metric_id": "bk_monitor..node_nf_conntrack_entries_limit",
                        "name": "node_nf_conntrack_entries_limit",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 使用大量Conntrack条目"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("eq", 1),
                "expression": "a",
                "functions": [],
                "name": "MAX(kube_node_spec_taint)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {
                                "condition": "and",
                                "key": "key",
                                "method": "eq",
                                "value": ["node.kubernetes.io/unreachable"],
                            },
                            {"condition": "and", "key": "effect", "method": "eq", "value": ["NoSchedule"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "node"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_spec_taint",
                        "metric_id": "bk_monitor..kube_node_spec_taint",
                        "name": "kube_node_spec_taint",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube节点] node不可用 KubeNodeUnreachable"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 2),
                "expression": "a",
                "functions": [],
                "name": "SUM(kube_node_status_condition)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "condition", "method": "eq", "value": ["Ready"]},
                            {"condition": "and", "key": "status", "method": "eq", "value": ["true"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "node"],
                        "agg_interval": 600,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "changes", "params": [{"id": "window", "value": "20m"}]}],
                        "metric_field": "kube_node_status_condition",
                        "metric_id": "bk_monitor..kube_node_status_condition",
                        "name": "kube_node_status_condition",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube节点] node状态抖动 KubeNodeReadinessFlapping"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": remind_algorithms_config("gte", 60),
                "expression": "a * b",
                "functions": [],
                "name": "SUM(kubelet_pod_worker_duration_seconds_bucket) * " "AVG(kubelet_node_name)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kubelet"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "node", "le"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [
                            {"id": "rate", "params": [{"id": "window", "value": "5m"}]},
                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]},
                        ],
                        "metric_field": "kubelet_pod_worker_duration_seconds_bucket",
                        "metric_id": "bk_monitor..kubelet_pod_worker_duration_seconds_bucket",
                        "name": "kubelet_pod_worker_duration_seconds_bucket",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kubelet"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["instance", "bcs_cluster_id", "node"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kubelet_node_name",
                        "metric_id": "bk_monitor..kubelet_node_name",
                        "name": "kubelet_node_name",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube kubelet] pod 启动耗时高 kubelet_pod_worker_duration"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(5, 5, 1),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [{"id": "abs", "params": []}],
                "name": "AVG(kube_persistentvolume_status_phase)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "phase", "method": "eq", "value": ["Failed", "Pending"]},
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": [],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_persistentvolume_status_phase",
                        "metric_id": "bk_monitor..kube_persistentvolume_status_phase",
                        "name": "kube_persistentvolume_status_phase",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-volume"],
        "name": _("[kube volume] persistentVolume 处于 Failed 或 Pending状态"),
        "notice": DEFAULT_NOTICE,
    },
]
