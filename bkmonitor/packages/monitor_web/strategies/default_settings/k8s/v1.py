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
from django.utils.translation import gettext as _

from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    fatal_algorithms_config,
    fatal_detects_config,
    nodata_recover_detects_config,
    remind_algorithms_config,
    remind_detects_config,
    warning_algorithms_config,
    warning_detects_config,
)

DEFAULT_K8S_STRATEGIES = [
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 0),
                "expression": "a -  b",
                "functions": [],
                "name": "sum_without_time(kube_daemonset_status_desired_number_scheduled) "
                "-  "
                "sum_without_time(kube_daemonset_status_current_number_scheduled)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "daemonset"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_daemonset_status_desired_number_scheduled",
                        "metric_id": "bk_monitor..kube_daemonset_status_desired_number_scheduled",
                        "name": "kube_daemonset_status_desired_number_scheduled",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "daemonset"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_daemonset_status_current_number_scheduled",
                        "metric_id": "bk_monitor..kube_daemonset_status_current_number_scheduled",
                        "name": "kube_daemonset_status_current_number_scheduled",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-daemonset"],
        "name": _("[kube daemonset] daemonset 部分 node 未调度 KubeDaemonSetNotScheduled"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": nodata_recover_detects_config(5, 5, 4, 2),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 5),
                "expression": "a",
                "functions": [],
                "name": _("SUM(重启次数)"),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "container_name", "pod_name"],
                        "agg_interval": 900,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "30m"}]}],
                        "metric_field": "kube_pod_container_status_restarts_total",
                        "metric_id": "bk_monitor..kube_pod_container_status_restarts_total",
                        "name": _("重启次数"),
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube pod] pod近30分钟重启次数过多 KubePodCrashLooping"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 85),
                "expression": "(a - b) / a *100",
                "functions": [],
                "name": "(MAX(node_filesystem_size_bytes) - "
                "MAX(node_filesystem_free_bytes)) / "
                "MAX(node_filesystem_size_bytes) *100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "fstype", "method": "reg", "value": ["ext[234]|btrfs|xfs|zfs"]}
                        ],
                        "agg_dimension": ["mountpoint", "bcs_cluster_id", "instance", "fstype", "device"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filesystem_size_bytes",
                        "metric_id": "bk_monitor..node_filesystem_size_bytes",
                        "name": "node_filesystem_size_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "fstype", "method": "reg", "value": ["ext[234]|btrfs|xfs|zfs"]}
                        ],
                        "agg_dimension": ["mountpoint", "bcs_cluster_id", "instance", "fstype", "device"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filesystem_free_bytes",
                        "metric_id": "bk_monitor..node_filesystem_free_bytes",
                        "name": "node_filesystem_free_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node]-磁盘使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": fatal_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": fatal_algorithms_config("eq", 0),
                "expression": "a",
                "functions": [],
                "name": "max_without_time(kube_node_status_condition)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "condition", "method": "eq", "value": ["Ready"]},
                            {"condition": "and", "key": "status", "method": "eq", "value": ["true"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "node"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
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
        "name": _("[kube node] node 状态异常 KubeNodeNotReady"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 90),
                "expression": "(a -b - c - d + e)/a * 100",
                "functions": [],
                "name": "(max_without_time(node_memory_MemTotal_bytes) "
                "-max_without_time(node_memory_MemFree_bytes) - "
                "max_without_time(node_memory_Cached_bytes) - "
                "max_without_time(node_memory_Buffers_bytes) + "
                "max_without_time(node_memory_Shmem_bytes))/max_without_time(node_memory_",
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
                        "metric_field": "node_memory_MemTotal_bytes",
                        "metric_id": "bk_monitor..node_memory_MemTotal_bytes",
                        "name": "node_memory_MemTotal_bytes",
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
                        "metric_field": "node_memory_MemFree_bytes",
                        "metric_id": "bk_monitor..node_memory_MemFree_bytes",
                        "name": "node_memory_MemFree_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_memory_Cached_bytes",
                        "metric_id": "bk_monitor..node_memory_Cached_bytes",
                        "name": "node_memory_Cached_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "d",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_memory_Buffers_bytes",
                        "metric_id": "bk_monitor..node_memory_Buffers_bytes",
                        "name": "node_memory_Buffers_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "e",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_memory_Shmem_bytes",
                        "metric_id": "bk_monitor..node_memory_Shmem_bytes",
                        "name": "node_memory_Shmem_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 内存使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 10, 5),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "AVG(kube_daemonset_status_number_misscheduled)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "daemonset"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "kube_daemonset_status_number_misscheduled",
                        "metric_id": "bk_monitor..kube_daemonset_status_number_misscheduled",
                        "name": "kube_daemonset_status_number_misscheduled",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-daemonset"],
        "name": _("[kube daemonset] daemonset 部分 node 被错误调度 KubeDaemonSetMisScheduled"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(10, 10, 8),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 90),
                "expression": "(a - b) / a*100",
                "functions": [],
                "name": "(sum_without_time(node_filesystem_files) - "
                "sum_without_time(node_filesystem_files_free)) / "
                "sum_without_time(node_filesystem_files)*100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "fstype", "method": "reg", "value": ["ext[234]|btrfs|xfs|zfs"]}
                        ],
                        "agg_dimension": ["fstype", "bcs_cluster_id", "device", "instance"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filesystem_files",
                        "metric_id": "bk_monitor..node_filesystem_files",
                        "name": "node_filesystem_files",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "fstype", "method": "reg", "value": ["ext[234]|btrfs|xfs|zfs"]}
                        ],
                        "agg_dimension": ["fstype", "bcs_cluster_id", "device", "instance"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filesystem_files_free",
                        "metric_id": "bk_monitor..node_filesystem_files_free",
                        "name": "node_filesystem_files_free",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 磁盘inode使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 1),
                "expression": "a /  b",
                "functions": [],
                "name": "sum_without_time(node_load15) /  " "count_without_time(node_cpu_seconds_total)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_load15",
                        "metric_id": "bk_monitor..node_load15",
                        "name": "node_load15",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["node-exporter"]},
                            {"condition": "and", "key": "mode", "method": "eq", "value": ["idle"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "count_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_cpu_seconds_total",
                        "metric_id": "bk_monitor..node_cpu_seconds_total",
                        "name": "node_cpu_seconds_total",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 服务器负载告警(load average 15min)"),
        "notice": DEFAULT_NOTICE,
    },
    # 这是连接apiserver客户端证书过期监控， 并不监控api server的证书， 因此禁用
    # {
    #     "detects": fatal_detects_config(5, 5, 4),
    #     "items": [
    #         {
    #             "name": _("[kube master] apiserver证书过期监控 KubeClientCertificateExpiration"),
    #             "no_data_config": NO_DATA_CONFIG,
    #             "target": [[]],
    #             "expression": "b>0 and a",
    #             "functions": [],
    #             "origin_sql": (
    #                 "histogram_quantile(0.01, sum by (bcs_cluster_id, le) "
    #                 "(rate(bkmonitor:apiserver_client_certificate_expiration_seconds_bucket"
    #                 "{job=\"apiserver\"}[5m])))"
    #             ),
    #             "query_configs": [
    #                 {
    #                     "data_source_label": "prometheus",
    #                     "data_type_label": "time_series",
    #                     "alias": "a",
    #                     "metric_id": (
    #                         "histogram_quantile(0.01, sum by (bcs_cluster_id, le) "
    #                         "(rate(bkmonitor:apiserver_client_certificate_expiration_seconds_bucket{j..."
    #                     ),
    #                     "functions": [],
    #                     "promql": (
    #                         "histogram_quantile(0.01, sum by (bcs_cluster_id, le) "
    #                         "(rate(bkmonitor:apiserver_client_certificate_expiration_seconds_bucket"
    #                         "{job=\"apiserver\"}[5m])))"
    #                     ),
    #                     "agg_interval": 60,
    #                 }
    #             ],
    #             "algorithms": fatal_algorithms_config("lt", 86400),
    #             "metric_type": "time_series",
    #         }
    #     ],
    #     "labels": [_("k8s_系统内置"), "kube-master"],
    #     "name": _("[kube master] apiserver证书过期监控 KubeClientCertificateExpiration"),
    #     "notice": {
    #         "config": {"interval_notify_mode": "standard", "need_poll": True, "notify_interval": 7200},
    #         "options": {
    #             "converge_config": {"need_biz_converge": True},
    #             "end_time": "23:59:59",
    #             "start_time": "00:00:00",
    #         },
    #         "signal": ["abnormal", "no_data"],
    #     },
    # },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 90),
                "expression": "a / b *100",
                "functions": [],
                "name": "MAX(node_filefd_allocated) / MAX(node_filefd_maximum) " "*100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [],
                        "agg_dimension": ["instance", "bcs_cluster_id"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filefd_allocated",
                        "metric_id": "bk_monitor..node_filefd_allocated",
                        "name": "node_filefd_allocated",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "MAX",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filefd_maximum",
                        "metric_id": "bk_monitor..node_filefd_maximum",
                        "name": "node_filefd_maximum",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] FD使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(15, 10, 8),
        "items": [
            {
                "algorithms": warning_algorithms_config("lt", 100),
                "expression": "a /  b * 100",
                "functions": [],
                "name": "sum_without_time(kube_daemonset_status_number_ready) /  "
                "sum_without_time(kube_daemonset_status_desired_number_scheduled) "
                "* 100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "daemonset"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_daemonset_status_number_ready",
                        "metric_id": "bk_monitor..kube_daemonset_status_number_ready",
                        "name": "kube_daemonset_status_number_ready",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "daemonset"],
                        "agg_interval": 60,
                        "agg_method": "sum_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_daemonset_status_desired_number_scheduled",
                        "metric_id": "bk_monitor..kube_daemonset_status_desired_number_scheduled",
                        "name": "kube_daemonset_status_desired_number_scheduled",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-daemonset"],
        "name": _("[kube daemonset] daemonSet处于就绪状态的百分比 KubeDaemonSetRolloutStuck"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": remind_detects_config(1, 10, 8),
        "items": [
            {
                "algorithms": remind_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "SUM(kube_job_status_failed)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "namespace", "job_name"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_job_status_failed",
                        "metric_id": "bk_monitor..kube_job_status_failed",
                        "name": "kube_job_status_failed",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-job"],
        "name": _("[kube kubelet] job执行失败的数量KubeJobFailed"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": fatal_detects_config(5, 1, 1),
        "items": [
            {
                "algorithms": fatal_algorithms_config("gt", 0),
                "expression": "a",
                "functions": [],
                "name": "SUM(node_filesystem_readonly)",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "fstype", "method": "reg", "value": ["ext[234]|btrfs|xfs|zfs"]}
                        ],
                        "agg_dimension": ["fstype", "bcs_cluster_id", "device", "instance"],
                        "agg_interval": 60,
                        "agg_method": "SUM",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "node_filesystem_readonly",
                        "metric_id": "bk_monitor..node_filesystem_readonly",
                        "name": "node_filesystem_readonly",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 磁盘只读告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 90),
                "expression": "(1- a)*100",
                "functions": [],
                "name": "(1- AVG(node_cpu_seconds_total))*100",
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [{"condition": "and", "key": "mode", "method": "eq", "value": ["idle"]}],
                        "agg_dimension": ["bcs_cluster_id", "instance"],
                        "agg_interval": 60,
                        "agg_method": "AVG",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [{"id": "irate", "params": [{"id": "window", "value": "5m"}]}],
                        "metric_field": "node_cpu_seconds_total",
                        "metric_id": "bk_monitor..node_cpu_seconds_total",
                        "name": "node_cpu_seconds_total",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] CPU使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 90),
                "expression": "a*100",
                "functions": [],
                "name": "SUM(node_disk_io_time_seconds_total)*100",
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
                        "functions": [{"id": "rate", "params": [{"id": "window", "value": "2m"}]}],
                        "metric_field": "node_disk_io_time_seconds_total",
                        "metric_id": "bk_monitor..node_disk_io_time_seconds_total",
                        "name": "node_disk_io_time_seconds_total",
                        "result_table_id": "",
                        "unit": "",
                    }
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-node"],
        "name": _("[kube node] 磁盘IO使用率告警"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 5, 4),
        "items": [
            {
                "algorithms": warning_algorithms_config("gte", 95),
                "expression": "a/b*100",
                "functions": [],
                "name": _("max_without_time(内存使用量(rss))/max_without_time(container_spec_memory_limit_bytes)*100"),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "pod_name", "namespace", "container_name"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "container_memory_rss",
                        "metric_id": "bk_monitor..container_memory_rss",
                        "name": _("内存使用量(rss)"),
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                            {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                            {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "pod_name", "namespace", "container_name"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "b",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "container_spec_memory_limit_bytes",
                        "metric_id": "bk_monitor..container_spec_memory_limit_bytes",
                        "name": "container_spec_memory_limit_bytes",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube资源] pod的内存使用率高"),
        "notice": DEFAULT_NOTICE,
    },
    {
        "detects": warning_detects_config(5, 10, 8),
        "items": [
            {
                "algorithms": warning_algorithms_config("gt", 95),
                "expression": "a*b/c*100",
                "functions": [],
                "name": (
                    "max_without_time(kubelet_running_pods)*max_without_time(kubelet_node_name)/"
                    "max_without_time(kube_node_status_capacity_pods)*100"
                ),
                "no_data_config": NO_DATA_CONFIG,
                "query_configs": [
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kubelet"]},
                            {"condition": "and", "key": "metrics_path", "method": "eq", "value": ["/metrics"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "node"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "a",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kubelet_running_pods",
                        "metric_id": "bk_monitor..kubelet_running_pods",
                        "name": "kubelet_running_pods",
                        "result_table_id": "",
                        "unit": "",
                    },
                    {
                        "agg_condition": [
                            {"key": "job", "method": "eq", "value": ["kubelet"]},
                            {"condition": "and", "key": "metrics_path", "method": "eq", "value": ["/metrics"]},
                        ],
                        "agg_dimension": ["bcs_cluster_id", "instance", "node"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
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
                    {
                        "agg_condition": [{"key": "job", "method": "eq", "value": ["kube-state-metrics"]}],
                        "agg_dimension": ["bcs_cluster_id", "instance", "node"],
                        "agg_interval": 60,
                        "agg_method": "max_without_time",
                        "alias": "c",
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "functions": [],
                        "metric_field": "kube_node_status_capacity_pods",
                        "metric_id": "bk_monitor..kube_node_status_capacity_pods",
                        "name": "kube_node_status_capacity_pods",
                        "result_table_id": "",
                        "unit": "",
                    },
                ],
                "target": [[]],
            }
        ],
        "labels": [_("k8s_系统内置"), "kube-pod"],
        "name": _("[kube kubelet] 运行的pod过多 KubeletTooManyPods"),
        "notice": DEFAULT_NOTICE,
    },
]
