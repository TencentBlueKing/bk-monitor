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
from enum import Enum

from django.utils.translation import gettext_lazy as _lazy

DEFAULT_PANEL_GROUP_ID_PREFIX = "bk_monitor.time_series.k8s.{view_id}."

GROUP_TITLE_MAP_KEY = {
    "CPU": "cpu",
    "内存": "memory",
    "网络": "network",
    "存储": "fs",
    "其他": "else",
}

VIEW_FILENAMES = [
    "kubernetes-cluster",
    "kubernetes-pod",
    "kubernetes-service",
    "kubernetes-container",
    "kubernetes-workload",
    "kubernetes-node",
    "kubernetes-service_monitor",
    "kubernetes-pod_monitor",
    "kubernetes-event",
]


class KubernetesSceneType(Enum):
    CLUSTER = "cluster"
    EVENT = "event"
    WORKLOAD = "workload"
    SERVICE = "service"
    POD = "pod"
    CONTAINER = "container"
    NODE = "node"
    SERVICE_MONITOR = "service_monitor"
    POD_MONITOR = "pod_monitor"


DEFAULT_GRAPH_UNIFY_QUERY_QUERY_CONFIG = {
    "metrics": [
        {
            "alias": "A",
            "table": "",
            "field": "",
            "method": "$method",
        }
    ],
    "interval": "$interval",
    "table": "",
    "data_source_label": "bk_monitor",
    "data_type_label": "time_series",
    "group_by": ["$group_by"],
    "where": [],
    "functions": [
        {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]},
        {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
    ],
}

DEFAULT_GRAPH_PROMQL_QUERY_CONFIG = {
    "interval": "$interval",
    "alias": "A",
    "data_source_label": "prometheus",
    "data_type_label": "time_series",
}

DEFAULT_POD_DETAIL = [
    {
        "id": "bk_monitor.time_series.k8s.pod.cpu",
        "title": "CPU",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.pod.container_cpu_usage_seconds_total",
                "title": "CPU使用量",
                "target": {"query_configs": [{"field": "container_cpu_usage_seconds_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.kube_pod_cpu_requests_ratio",
                "title": "CPU request使用率",
                "target": {
                    "expression": "A/B*100",
                    "query_configs": [
                        {"alias": "A", "field": "container_cpu_usage_seconds_total"},
                        {"alias": "B", "field": "kube_pod_container_resource_requests_cpu_cores"},
                    ],
                },
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.kube_pod_cpu_limits_ratio",
                "title": "CPU limit使用率",
                "target": {
                    "expression": "A/B*100",
                    "query_configs": [
                        {"alias": "A", "field": "container_cpu_usage_seconds_total"},
                        {"alias": "B", "field": "kube_pod_container_resource_limits_cpu_cores"},
                    ],
                },
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.pod.memory",
        "title": "内存",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.pod.container_memory_rss",
                "title": "内存使用量(rss)",
                "target": {"query_configs": [{"field": "container_memory_rss"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.container_memory_working_set_bytes",
                "title": "内存使用量(working_set)",
                "target": {"query_configs": [{"field": "container_memory_working_set_bytes"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.kube_pod_memory_requests_ratio",
                "title": "内存request使用率",
                "target": {
                    "expression": "A/B*100",
                    "query_configs": [
                        {"alias": "A", "field": "container_memory_rss"},
                        {"alias": "B", "field": "kube_pod_container_resource_requests_memory_bytes"},
                    ],
                },
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.kube_pod_memory_limits_ratio",
                "title": "内存limit使用率",
                "target": {
                    "expression": "A/B*100",
                    "query_configs": [
                        {"alias": "A", "field": "container_memory_rss"},
                        {"alias": "B", "field": "kube_pod_container_resource_limits_memory_bytes"},
                    ],
                },
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.pod.network",
        "title": "网络",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.pod.container_network_receive_bytes_total",
                "title": "网络入带宽",
                "target": {"query_configs": [{"field": "container_network_receive_bytes_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.pod.container_network_transmit_bytes_total",
                "title": "网络出带宽",
                "target": {"query_configs": [{"field": "container_network_transmit_bytes_total"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.pod.fs",
        "title": "存储",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.pod.container_fs_usage_bytes",
                "title": "存储信息",
                "target": {"query_configs": [{"field": "container_fs_usage_bytes"}]},
            }
        ],
    },
]

DEFAULT_CONTAINER_DETAIL = [
    {
        "id": "bk_monitor.time_series.k8s.container.cpu",
        "title": "CPU",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.container.container_cpu_system_seconds_total",
                "title": "container_cpu_system_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_system_seconds_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.container.container_cpu_usage_seconds_total",
                "title": "container_cpu_usage_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_usage_seconds_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.container.container_cpu_user_seconds_total",
                "title": "container_cpu_user_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_user_seconds_total"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.container.memory",
        "title": "内存",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.container.container_memory_rss",
                "title": "内存实际使用量",
                "target": {"query_configs": [{"field": "container_memory_rss"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.container.network",
        "title": "网络",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.container.container_network_receive_bytes_total",
                "title": "网络入带宽",
                "target": {"query_configs": [{"field": "container_network_receive_bytes_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.container.container_network_transmit_bytes_total",
                "title": "网络出带宽",
                "target": {"query_configs": [{"field": "container_network_transmit_bytes_total"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.container.disk",
        "title": "存储",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.container.container_fs_usage_bytes",
                "title": "存储信息",
                "target": {"query_configs": [{"field": "container_fs_usage_bytes"}]},
            }
        ],
    },
]

DEFAULT_WORKLOAD_DETAIL = [
    {
        "id": "bk_monitor.time_series.k8s.workload.cpu",
        "title": "CPU",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.workload.container_cpu_system_seconds_total",
                "title": "container_cpu_system_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_system_seconds_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.workload.container_cpu_usage_seconds_total",
                "title": "container_cpu_usage_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_usage_seconds_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.workload.container_cpu_user_seconds_total",
                "title": "container_cpu_user_seconds_total",
                "target": {"query_configs": [{"field": "container_cpu_user_seconds_total"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.workload.memory",
        "title": "内存",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.workload.container_memory_rss",
                "title": "内存实际使用量",
                "target": {"query_configs": [{"field": "container_memory_rss"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.workload.network",
        "title": "网络",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.workload.container_network_receive_bytes_total",
                "title": "网络入带宽",
                "target": {"query_configs": [{"field": "container_network_receive_bytes_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.workload.container_network_transmit_bytes_total",
                "title": "网络出带宽",
                "target": {"query_configs": [{"field": "container_network_transmit_bytes_total"}]},
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.workload.disk",
        "title": "存储",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.workload.container_fs_usage_bytes",
                "title": "存储信息",
                "target": {"query_configs": [{"field": "container_fs_usage_bytes"}]},
            }
        ],
    },
]

DEFAULT_SERVICE_DETAIL = [
    {
        "id": "bk_monitor.time_series.k8s.service.network",
        "title": "网络",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.service.container_network_receive_bytes_total",
                "title": "网络入带宽",
                "target": {"query_configs": [{"field": "container_network_receive_bytes_total"}]},
            },
            {
                "id": "bk_monitor.time_series.k8s.service.container_network_transmit_bytes_total",
                "title": "网络出带宽",
                "target": {"query_configs": [{"field": "container_network_transmit_bytes_total"}]},
            },
        ],
    },
]

DEFAULT_NODE_PANELS = [
    {
        "id": "bk_monitor.time_series.k8s.node.cpu",
        "title": "CPU",
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.node.node_load15",
                "title": _lazy("15分钟平均负载"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_load15",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.cpu_summary.usage",
                "title": _lazy("CPU使用率"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "promql": (
                                        '(1 - avg by(bcs_cluster_id, instance) (irate(node_cpu_seconds_total{'
                                        'mode="idle",instance=~"$node_ip:",'
                                        'bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) * 100'
                                    ),
                                    "overview_promql": (
                                        '(1 - avg(irate(node_cpu_seconds_total{mode="idle",'
                                        'bcs_cluster_id=~"^(%(bcs_cluster_ids)s)$"}[5m]))) * 100'
                                    ),
                                }
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.cpu_detail.usage",
                "title": _lazy("CPU单核使用率"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "promql": (
                                        '(1 - avg by(cpu) (irate(node_cpu_seconds_total{'
                                        'mode="idle",instance=~"$node_ip:",'
                                        'bcs_cluster_id=~"^($bcs_cluster_id)$"}[5m]))) * 100'
                                    ),
                                    "overview_promql": (
                                        '(1 - avg by(cpu) (irate(node_cpu_seconds_total{mode="idle",'
                                        'bcs_cluster_id=~"^(%(bcs_cluster_ids)s)$"}[5m]))) * 100'
                                    ),
                                }
                            ],
                        }
                    }
                ],
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.node.memory",
        "title": _lazy("内存"),
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.node.node_memory_MemFree_bytes",
                "title": _lazy("物理内存空闲量"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemFree_bytes",
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.mem.psc_pct_used",
                "title": _lazy("物理内存已用占比"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "(A - B) / A * 100",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemTotal_bytes",
                                            "alias": "A",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemFree_bytes",
                                            "alias": "B",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.mem.psc_used",
                "title": _lazy("物理内存已用量"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "expression": "A - B",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemTotal_bytes",
                                            "alias": "A",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemFree_bytes",
                                            "alias": "B",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.mem.pct_used",
                "title": _lazy("应用程序内存使用占比"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "(A - B - C - D + E) / A * 100",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemTotal_bytes",
                                            "alias": "A",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemFree_bytes",
                                            "alias": "B",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Cached_bytes",
                                            "alias": "C",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Buffers_bytes",
                                            "alias": "D",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Shmem_bytes",
                                            "alias": "E",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.mem.used",
                "title": _lazy("应用程序内存使用量"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "expression": "A - B - C - D + E",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemTotal_bytes",
                                            "alias": "A",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_MemFree_bytes",
                                            "alias": "B",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Cached_bytes",
                                            "alias": "C",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Buffers_bytes",
                                            "alias": "D",
                                        }
                                    ]
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_memory_Shmem_bytes",
                                            "alias": "E",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.node.network",
        "title": _lazy("网络"),
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.node.node_network_receive_bytes_total",
                "title": _lazy("网卡入流量"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_network_receive_bytes_total",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.node_network_transmit_bytes_total",
                "title": _lazy("网卡出流量"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_network_transmit_bytes_total",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
        ],
    },
    {
        "id": "bk_monitor.time_series.k8s.node.disk",
        "title": _lazy("磁盘"),
        "panels": [
            {
                "id": "bk_monitor.time_series.k8s.node.disk.in_use",
                "title": _lazy("磁盘空间使用率"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "(A - B) / A * 100",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_filesystem_size_bytes",
                                            "alias": "A",
                                        }
                                    ],
                                    "where": [
                                        {
                                            "key": "fstype",
                                            "method": "eq",
                                            "value": ["ext2", "ext3", "ext4", "btrfs", "xfs", "zfs"],
                                        }
                                    ],
                                    "overview_where": [
                                        {
                                            "key": "fstype",
                                            "method": "eq",
                                            "value": ["ext2", "ext3", "ext4", "btrfs", "xfs", "zfs"],
                                        },
                                    ],
                                },
                                {
                                    "metrics": [
                                        {
                                            "field": "node_filesystem_free_bytes",
                                            "alias": "B",
                                        }
                                    ],
                                    "where": [
                                        {
                                            "key": "fstype",
                                            "method": "eq",
                                            "value": ["ext2", "ext3", "ext4", "btrfs", "xfs", "zfs"],
                                        }
                                    ],
                                    "overview_where": [
                                        {
                                            "key": "fstype",
                                            "method": "eq",
                                            "value": ["ext2", "ext3", "ext4", "btrfs", "xfs", "zfs"],
                                        },
                                    ],
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.node_disk_reads_completed_total",
                "title": _lazy("I/O读次数"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_disk_reads_completed_total",
                                        }
                                    ],
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.node_disk_writes_completed_total",
                "title": _lazy("I/O写次数"),
                "hidden": False,
                "targets": [
                    {
                        "data": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_disk_writes_completed_total",
                                        }
                                    ],
                                },
                            ],
                        }
                    }
                ],
            },
            {
                "id": "bk_monitor.time_series.k8s.node.io.util",
                "title": _lazy("I/O使用率"),
                "hidden": False,
                "unit": "percent",
                "targets": [
                    {
                        "data": {
                            "expression": "A * 100",
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": "node_disk_io_time_seconds_total",
                                            "alias": "A",
                                        }
                                    ]
                                },
                            ],
                        }
                    }
                ],
            },
        ],
    },
]
