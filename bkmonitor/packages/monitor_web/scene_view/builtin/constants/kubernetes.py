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

DEFAULT_HOST_DETAIL = {
    "overview_panels": [
        {
            "id": "cpu",
            "title": "CPU",
            "type": "row",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.load.load5",
                    "type": "graph",
                    "title": "5\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                    "subTitle": "system.load.load5",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "load5", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.load",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                    "matchDisplay": {"os_type": "linux"},
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.usage",
                    "type": "graph",
                    "title": "CPU\u4f7f\u7528\u7387",
                    "subTitle": "system.cpu_summary.usage",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "usage", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.cpu_summary",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.usage",
                    "type": "graph",
                    "title": "CPU\u5355\u6838\u4f7f\u7528\u7387",
                    "subTitle": "system.cpu_detail.usage",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "usage", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.cpu_detail",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
            ],
        },
        {
            "id": "memory",
            "title": "\u5185\u5b58",
            "type": "row",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.mem.free",
                    "type": "graph",
                    "title": "\u7269\u7406\u5185\u5b58\u7a7a\u95f2\u91cf",
                    "subTitle": "system.mem.free",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "free", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.mem",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.swap.used",
                    "type": "graph",
                    "title": "SWAP\u5df2\u7528\u91cf",
                    "subTitle": "system.swap.used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.swap",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.mem.psc_pct_used",
                    "type": "graph",
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u5360\u6bd4",
                    "subTitle": "system.mem.psc_pct_used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "psc_pct_used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.mem",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.mem.psc_used",
                    "type": "graph",
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u91cf",
                    "subTitle": "system.mem.psc_used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "psc_used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.mem",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.mem.used",
                    "type": "graph",
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u91cf",
                    "subTitle": "system.mem.used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.mem",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.mem.pct_used",
                    "type": "graph",
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u5360\u6bd4",
                    "subTitle": "system.mem.pct_used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "pct_used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.mem",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.swap.pct_used",
                    "type": "graph",
                    "title": "SWAP\u5df2\u7528\u5360\u6bd4",
                    "subTitle": "system.swap.pct_used",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "pct_used", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.swap",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
            ],
        },
        {
            "id": "network",
            "title": "\u7f51\u7edc",
            "type": "row",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.net.speed_recv_bit",
                    "type": "graph",
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf\u6bd4\u7279\u901f\u7387",
                    "subTitle": "system.net.speed_recv_bit",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_recv_bit", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_sent_bit",
                    "type": "graph",
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf\u6bd4\u7279\u901f\u7387 ",
                    "subTitle": "system.net.speed_sent_bit",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_sent_bit", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_recv",
                    "type": "graph",
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf",
                    "subTitle": "system.net.speed_recv",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_recv", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_sent",
                    "type": "graph",
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf",
                    "subTitle": "system.net.speed_sent",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_sent", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_packets_sent",
                    "type": "graph",
                    "title": "\u7f51\u5361\u51fa\u5305\u91cf",
                    "subTitle": "system.net.speed_packets_sent",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_packets_sent", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_packets_recv",
                    "type": "graph",
                    "title": "\u7f51\u5361\u5165\u5305\u91cf",
                    "subTitle": "system.net.speed_packets_recv",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "speed_packets_recv", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.net",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_estab",
                    "type": "graph",
                    "title": "estab\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_estab",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_estab", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_timewait",
                    "type": "graph",
                    "title": "timewait\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_timewait",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_timewait", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_listen",
                    "type": "graph",
                    "title": "listen\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_listen",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_listen", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_lastack",
                    "type": "graph",
                    "title": "lastact\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_lastack",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_lastack", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_recv",
                    "type": "graph",
                    "title": "synrecv\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_syn_recv",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_syn_recv", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_sent",
                    "type": "graph",
                    "title": "synsent\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_syn_sent",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_syn_sent", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait1",
                    "type": "graph",
                    "title": "finwait1\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_finwait1",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_finwait1", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait2",
                    "type": "graph",
                    "title": "finwait2\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_finwait2",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_finwait2", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closing",
                    "type": "graph",
                    "title": "closing\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_closing",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_closing", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closed",
                    "type": "graph",
                    "title": "closed\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_closed",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_closed", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_indatagrams",
                    "type": "graph",
                    "title": "udp\u63a5\u6536\u5305\u91cf",
                    "subTitle": "system.netstat.cur_udp_indatagrams",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [
                                            {"field": "cur_udp_indatagrams", "method": "$method", "alias": "A"}
                                        ],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_outdatagrams",
                    "type": "graph",
                    "title": "udp\u53d1\u9001\u5305\u91cf",
                    "subTitle": "system.netstat.cur_udp_outdatagrams",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [
                                            {"field": "cur_udp_outdatagrams", "method": "$method", "alias": "A"}
                                        ],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closewait",
                    "type": "graph",
                    "title": "closewait\u8fde\u63a5\u6570",
                    "subTitle": "system.netstat.cur_tcp_closewait",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "cur_tcp_closewait", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.netstat",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
            ],
        },
        {
            "id": "disk",
            "title": "\u78c1\u76d8",
            "type": "row",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.disk.in_use",
                    "type": "graph",
                    "title": "\u78c1\u76d8\u7a7a\u95f4\u4f7f\u7528\u7387",
                    "subTitle": "system.disk.in_use",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "in_use", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.disk",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "mount_point"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.io.r_s",
                    "type": "graph",
                    "title": "I/O\u8bfb\u6b21\u6570",
                    "subTitle": "system.io.r_s",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "r_s", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.io",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.io.w_s",
                    "type": "graph",
                    "title": "I/O\u5199\u6b21\u6570",
                    "subTitle": "system.io.w_s",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "w_s", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.io",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
                {
                    "id": "bk_monitor.time_series.system.io.util",
                    "type": "graph",
                    "title": "I/O\u4f7f\u7528\u7387",
                    "subTitle": "system.io.util",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "util", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.io",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by", "device_name"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                },
            ],
        },
        {
            "id": "process",
            "title": "\u7cfb\u7edf\u8fdb\u7a0b",
            "type": "row",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.env.procs",
                    "type": "graph",
                    "title": "\u7cfb\u7edf\u603b\u8fdb\u7a0b\u6570",
                    "subTitle": "system.env.procs",
                    "targets": [
                        {
                            "data": {
                                "expression": "A",
                                "query_configs": [
                                    {
                                        "metrics": [{"field": "procs", "method": "$method", "alias": "A"}],
                                        "interval": "$interval",
                                        "table": "system.env",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "group_by": ["$group_by"],
                                        "where": [],
                                        "functions": [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ],
                                        "filter_dict": {"targets": ["$current_target", "$compare_targets"]},
                                    }
                                ],
                            },
                            "ignore_group_by": ["bk_host_id"],
                            "alias": "",
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    ],
                }
            ],
        },
        {"id": "__UNGROUP__", "title": "\u672a\u5206\u7ec4\u7684\u6307\u6807", "type": "row", "panels": []},
    ],  # noqa
    "order": [
        {
            "id": "cpu",
            "title": "CPU",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.load.load5",
                    "hidden": False,
                    "title": "5\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.usage",
                    "hidden": False,
                    "title": "CPU\u4f7f\u7528\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.usage",
                    "hidden": False,
                    "title": "CPU\u5355\u6838\u4f7f\u7528\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.guest",
                    "hidden": True,
                    "title": "\u5185\u6838\u5728\u865a\u62df\u673a\u4e0a\u8fd0\u884c\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.idle",
                    "hidden": True,
                    "title": "CPU\u5355\u6838\u7a7a\u95f2\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.interrupt",
                    "hidden": True,
                    "title": "\u786c\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.iowait",
                    "hidden": True,
                    "title": "CPU\u5355\u6838\u7b49\u5f85IO\u7684\u65f6\u95f4\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.nice",
                    "hidden": True,
                    "title": "\u4f4e\u4f18\u5148\u7ea7\u7a0b\u5e8f\u5728\u7528\u6237\u6001\u6267\u884c\u7684CPU\u5360\u6bd4",  # noqa
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.softirq",
                    "hidden": True,
                    "title": "\u8f6f\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.stolen",
                    "hidden": True,
                    "title": "CPU\u5355\u6838\u5206\u914d\u7ed9\u865a\u62df\u673a\u7684\u65f6\u95f4\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.system",
                    "hidden": True,
                    "title": "CPU\u5355\u6838\u7cfb\u7edf\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_detail.user",
                    "hidden": True,
                    "title": "CPU\u5355\u6838\u7528\u6237\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.guest",
                    "hidden": True,
                    "title": "\u5185\u6838\u5728\u865a\u62df\u673a\u4e0a\u8fd0\u884c\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.idle",
                    "hidden": True,
                    "title": "CPU\u7a7a\u95f2\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.interrupt",
                    "hidden": True,
                    "title": "\u786c\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.iowait",
                    "hidden": True,
                    "title": "CPU\u7b49\u5f85IO\u7684\u65f6\u95f4\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.nice",
                    "hidden": True,
                    "title": "\u4f4e\u4f18\u5148\u7ea7\u7a0b\u5e8f\u5728\u7528\u6237\u6001\u6267\u884c\u7684CPU\u5360\u6bd4",  # noqa
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.softirq",
                    "hidden": True,
                    "title": "\u8f6f\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.stolen",
                    "hidden": True,
                    "title": "CPU\u5206\u914d\u7ed9\u865a\u62df\u673a\u7684\u65f6\u95f4\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.system",
                    "hidden": True,
                    "title": "CPU\u7cfb\u7edf\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.cpu_summary.user",
                    "hidden": True,
                    "title": "CPU\u7528\u6237\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.load.load1",
                    "hidden": True,
                    "title": "1\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                },
                {
                    "id": "bk_monitor.time_series.system.load.load15",
                    "hidden": True,
                    "title": "15\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                },
                {
                    "id": "bk_monitor.time_series.system.load.per_cpu_load",
                    "hidden": True,
                    "title": "\u5355\u6838CPU\u7684load",
                },
            ],
        },
        {
            "id": "memory",
            "title": "\u5185\u5b58",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.mem.free",
                    "hidden": False,
                    "title": "\u7269\u7406\u5185\u5b58\u7a7a\u95f2\u91cf",
                },
                {"id": "bk_monitor.time_series.system.swap.used", "hidden": False, "title": "SWAP\u5df2\u7528\u91cf"},
                {
                    "id": "bk_monitor.time_series.system.mem.psc_pct_used",
                    "hidden": False,
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.psc_used",
                    "hidden": False,
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.used",
                    "hidden": False,
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.pct_used",
                    "hidden": False,
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.swap.pct_used",
                    "hidden": False,
                    "title": "SWAP\u5df2\u7528\u5360\u6bd4",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.buffer",
                    "hidden": True,
                    "title": "\u5185\u5b58buffered\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.cached",
                    "hidden": True,
                    "title": "\u5185\u5b58cached\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.pct_usable",
                    "hidden": True,
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u53ef\u7528\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.shared",
                    "hidden": True,
                    "title": "\u5171\u4eab\u5185\u5b58\u4f7f\u7528\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.total",
                    "hidden": True,
                    "title": "\u7269\u7406\u5185\u5b58\u603b\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.mem.usable",
                    "hidden": True,
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u53ef\u7528\u91cf",
                },
                {"id": "bk_monitor.time_series.system.swap.free", "hidden": True, "title": "SWAP\u7a7a\u95f2\u91cf"},
                {
                    "id": "bk_monitor.time_series.system.swap.swap_in",
                    "hidden": True,
                    "title": "swap\u4ece\u786c\u76d8\u5230\u5185\u5b58",
                },
                {
                    "id": "bk_monitor.time_series.system.swap.swap_out",
                    "hidden": True,
                    "title": "swap\u4ece\u5185\u5b58\u5230\u786c\u76d8",
                },
                {"id": "bk_monitor.time_series.system.swap.total", "hidden": True, "title": "SWAP\u603b\u91cf"},
            ],
        },
        {
            "id": "network",
            "title": "\u7f51\u7edc",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.net.speed_recv_bit",
                    "hidden": False,
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf\u6bd4\u7279\u901f\u7387",
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_sent_bit",
                    "hidden": False,
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf\u6bd4\u7279\u901f\u7387 ",
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_recv",
                    "hidden": False,
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_sent",
                    "hidden": False,
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_packets_sent",
                    "hidden": False,
                    "title": "\u7f51\u5361\u51fa\u5305\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.net.speed_packets_recv",
                    "hidden": False,
                    "title": "\u7f51\u5361\u5165\u5305\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_estab",
                    "hidden": False,
                    "title": "estab\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_timewait",
                    "hidden": False,
                    "title": "timewait\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_listen",
                    "hidden": False,
                    "title": "listen\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_lastack",
                    "hidden": False,
                    "title": "lastact\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_recv",
                    "hidden": False,
                    "title": "synrecv\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_sent",
                    "hidden": False,
                    "title": "synsent\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait1",
                    "hidden": False,
                    "title": "finwait1\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait2",
                    "hidden": False,
                    "title": "finwait2\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closing",
                    "hidden": False,
                    "title": "closing\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closed",
                    "hidden": False,
                    "title": "closed\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_indatagrams",
                    "hidden": False,
                    "title": "udp\u63a5\u6536\u5305\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_outdatagrams",
                    "hidden": False,
                    "title": "udp\u53d1\u9001\u5305\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closewait",
                    "hidden": False,
                    "title": "closewait\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.net.carrier",
                    "hidden": True,
                    "title": "\u8bbe\u5907\u9a71\u52a8\u7a0b\u5e8f\u68c0\u6d4b\u5230\u7684\u8f7d\u6ce2\u4e22\u5931\u6570",  # noqa
                },
                {
                    "id": "bk_monitor.time_series.system.net.collisions",
                    "hidden": True,
                    "title": "\u7f51\u5361\u51b2\u7a81\u5305",
                },
                {
                    "id": "bk_monitor.time_series.system.net.dropped",
                    "hidden": True,
                    "title": "\u7f51\u5361\u4e22\u5f03\u5305",
                },
                {
                    "id": "bk_monitor.time_series.system.net.errors",
                    "hidden": True,
                    "title": "\u7f51\u5361\u9519\u8bef\u5305",
                },
                {
                    "id": "bk_monitor.time_series.system.net.overruns",
                    "hidden": True,
                    "title": "\u7f51\u5361\u7269\u7406\u5c42\u4e22\u5f03",
                },
            ],
        },
        {
            "id": "disk",
            "title": "\u78c1\u76d8",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.disk.in_use",
                    "hidden": False,
                    "title": "\u78c1\u76d8\u7a7a\u95f4\u4f7f\u7528\u7387",
                },
                {"id": "bk_monitor.time_series.system.io.r_s", "hidden": False, "title": "I/O\u8bfb\u6b21\u6570"},
                {"id": "bk_monitor.time_series.system.io.w_s", "hidden": False, "title": "I/O\u5199\u6b21\u6570"},
                {"id": "bk_monitor.time_series.system.io.util", "hidden": False, "title": "I/O\u4f7f\u7528\u7387"},
                {
                    "id": "bk_monitor.time_series.system.disk.free",
                    "hidden": True,
                    "title": "\u78c1\u76d8\u53ef\u7528\u7a7a\u95f4\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.disk.total",
                    "hidden": True,
                    "title": "\u78c1\u76d8\u603b\u7a7a\u95f4\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.disk.used",
                    "hidden": True,
                    "title": "\u78c1\u76d8\u5df2\u7528\u7a7a\u95f4\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.io.avgqu_sz",
                    "hidden": True,
                    "title": "\u5e73\u5747I/O\u961f\u5217\u957f\u5ea6",
                },
                {
                    "id": "bk_monitor.time_series.system.io.avgrq_sz",
                    "hidden": True,
                    "title": "\u8bbe\u5907\u6bcf\u6b21I/O\u5e73\u5747\u6570\u636e\u5927\u5c0f",
                },
                {
                    "id": "bk_monitor.time_series.system.io.await",
                    "hidden": True,
                    "title": "I/O\u5e73\u5747\u7b49\u5f85\u65f6\u957f",
                },
                {"id": "bk_monitor.time_series.system.io.rkb_s", "hidden": True, "title": "I/O\u8bfb\u901f\u7387"},
                {
                    "id": "bk_monitor.time_series.system.io.svctm",
                    "hidden": True,
                    "title": "I/O\u5e73\u5747\u670d\u52a1\u65f6\u957f",
                },
                {"id": "bk_monitor.time_series.system.io.wkb_s", "hidden": True, "title": "I/O\u5199\u901f\u7387"},
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closed",
                    "hidden": True,
                    "title": "closed\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closewait",
                    "hidden": True,
                    "title": "closewait\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_closing",
                    "hidden": True,
                    "title": "closing\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_estab",
                    "hidden": True,
                    "title": "estab\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait1",
                    "hidden": True,
                    "title": "finwait1\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_finwait2",
                    "hidden": True,
                    "title": "finwait2\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_lastack",
                    "hidden": True,
                    "title": "lastact\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_listen",
                    "hidden": True,
                    "title": "listen\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_recv",
                    "hidden": True,
                    "title": "synrecv\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_syn_sent",
                    "hidden": True,
                    "title": "synsent\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_tcp_timewait",
                    "hidden": True,
                    "title": "timewait\u8fde\u63a5\u6570",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_indatagrams",
                    "hidden": True,
                    "title": "udp\u63a5\u6536\u5305\u91cf",
                },
                {
                    "id": "bk_monitor.time_series.system.netstat.cur_udp_outdatagrams",
                    "hidden": True,
                    "title": "udp\u53d1\u9001\u5305\u91cf",
                },
            ],
        },
        {
            "id": "process",
            "title": "\u7cfb\u7edf\u8fdb\u7a0b",
            "panels": [
                {
                    "id": "bk_monitor.time_series.system.env.procs",
                    "hidden": False,
                    "title": "\u7cfb\u7edf\u603b\u8fdb\u7a0b\u6570",
                }
            ],
        },
        {
            "id": "__UNGROUP__",
            "title": "\u672a\u5206\u7ec4\u7684\u6307\u6807",
            "panels": [
                {
                    "title": "\u4e22\u5305\u7387",
                    "id": "bk_monitor.time_series.pingserver.base.loss_percent",
                    "hidden": True,
                },
                {
                    "title": "\u6700\u5927\u65f6\u5ef6",
                    "id": "bk_monitor.time_series.pingserver.base.max_rtt",
                    "hidden": True,
                },
                {
                    "title": "\u6700\u5c0f\u65f6\u5ef6",
                    "id": "bk_monitor.time_series.pingserver.base.min_rtt",
                    "hidden": True,
                },
                {
                    "title": "\u5e73\u5747\u65f6\u5ef6",
                    "id": "bk_monitor.time_series.pingserver.base.avg_rtt",
                    "hidden": True,
                },
                {
                    "title": "\u767b\u5f55\u7684\u7528\u6237\u6570",
                    "id": "bk_monitor.time_series.system.env.login_user",
                    "hidden": True,
                },
                {
                    "title": "\u6700\u5927\u6587\u4ef6\u63cf\u8ff0\u7b26",
                    "id": "bk_monitor.time_series.system.env.maxfiles",
                    "hidden": True,
                },
                {
                    "title": "\u5904\u4e8e\u7b49\u5f85I/O\u5b8c\u6210\u7684\u8fdb\u7a0b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.system.env.procs_blocked_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u4e0a\u4e0b\u6587\u5207\u6362\u6b21\u6570",
                    "id": "bk_monitor.time_series.system.env.procs_ctxt_total",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u540e\u6240\u521b\u5efa\u8fc7\u7684\u8fdb\u7a0b\u6570\u91cf",
                    "id": "bk_monitor.time_series.system.env.procs_processes_total",
                    "hidden": True,
                },
                {
                    "title": "\u6b63\u5728\u8fd0\u884c\u7684\u8fdb\u7a0b\u603b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.system.env.proc_running_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u65f6\u95f4",
                    "id": "bk_monitor.time_series.system.env.uptime",
                    "hidden": True,
                },
                {
                    "title": "\u53ef\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.system.inode.free",
                    "hidden": True,
                },
                {
                    "title": "\u5df2\u7528inode\u5360\u6bd4",
                    "id": "bk_monitor.time_series.system.inode.in_use",
                    "hidden": True,
                },
                {"title": "\u603binode\u6570\u91cf", "id": "bk_monitor.time_series.system.inode.total", "hidden": True},
                {
                    "title": "\u5df2\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.system.inode.used",
                    "hidden": True,
                },
                {
                    "title": "fs_state",
                    "id": "bk_monitor.time_series.script_check_fstab_mount.base.fs_state",
                    "hidden": True,
                },
                {
                    "title": "corosync_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.corosync_status",
                    "hidden": True,
                },
                {
                    "title": "crm_nodes_flag",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.crm_nodes_flag",
                    "hidden": True,
                },
                {
                    "title": "crm_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.crm_status",
                    "hidden": True,
                },
                {
                    "title": "crmd_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.crmd_status",
                    "hidden": True,
                },
                {
                    "title": "double_if_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.double_if_status",
                    "hidden": True,
                },
                {
                    "title": "exporter_version",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.exporter_version",
                    "hidden": True,
                },
                {
                    "title": "file_size",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.file_size",
                    "hidden": True,
                },
                {
                    "title": "innode_usage",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.innode_usage",
                    "hidden": True,
                },
                {
                    "title": "mount_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.mount_status",
                    "hidden": True,
                },
                {
                    "title": "network_interface_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.network_interface_status",
                    "hidden": True,
                },
                {
                    "title": "ntp_offset",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.ntp_offset",
                    "hidden": True,
                },
                {
                    "title": "ntp_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.ntp_status",
                    "hidden": True,
                },
                {
                    "title": "port_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.port_status",
                    "hidden": True,
                },
                {
                    "title": "process_status",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.process_status",
                    "hidden": True,
                },
                {
                    "title": "system_uptime",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.system_uptime",
                    "hidden": True,
                },
                {
                    "title": "thread_count",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.thread_count",
                    "hidden": True,
                },
                {
                    "title": "vcs_group_state",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.vcs_group_state",
                    "hidden": True,
                },
                {
                    "title": "vcs_heart_beat",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.vcs_heart_beat",
                    "hidden": True,
                },
                {
                    "title": "vcs_heart_net",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.vcs_heart_net",
                    "hidden": True,
                },
                {
                    "title": "vcs_system_state",
                    "id": "bk_monitor.time_series.exporter_linux_willtest.base.vcs_system_state",
                    "hidden": True,
                },
                {"title": "disk_usage", "id": "bk_monitor.time_series.script_xx.base.disk_usage", "hidden": True},
                {
                    "title": "conntrack_found",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_found",
                    "hidden": True,
                },
                {
                    "title": "conntrack_insert_failed",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_insert_failed",
                    "hidden": True,
                },
                {
                    "title": "conntrack_ignore",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_ignore",
                    "hidden": True,
                },
                {
                    "title": "conntrack_error",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_error",
                    "hidden": True,
                },
                {
                    "title": "conntrack_early_drop",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_early_drop",
                    "hidden": True,
                },
                {
                    "title": "conntrack_insert",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_insert",
                    "hidden": True,
                },
                {
                    "title": "conntrack_drop",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_drop",
                    "hidden": True,
                },
                {
                    "title": "conntrack_invalid",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_invalid",
                    "hidden": True,
                },
                {
                    "title": "conntrack_search_restart",
                    "id": "bk_monitor.time_series.script_conntrack_stats.group1.conntrack_search_restart",
                    "hidden": True,
                },
                {
                    "title": "datahub_databus_task_created",
                    "id": "bk_monitor.time_series.pushgateway_bkbase_databus_metrics.datahub_databus_task.datahub_databus_task_created",  # noqa
                    "hidden": True,
                },
                {
                    "title": "datahub_databus_task_total",
                    "id": "bk_monitor.time_series.pushgateway_bkbase_databus_metrics.datahub_databus_task.datahub_databus_task_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "Recv_Q",
                    "id": "bk_monitor.time_series.script_check_tcp_recv_send_queue_size.tcp.kafka_tcp_recv_queue_size",
                    "hidden": True,
                },
                {
                    "title": "kafka_broker_numbers",
                    "id": "bk_monitor.time_series.script_kafka_broker_numbers.base.kafka_broker_numbers",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u603b\u7a7a\u95f4\u5927\u5c0f",
                    "id": "bk_monitor.time_series.dbm_system.disk.total",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u5df2\u7528\u7a7a\u95f4\u5927\u5c0f",
                    "id": "bk_monitor.time_series.dbm_system.disk.used",
                    "hidden": True,
                },
                {
                    "title": "\u767b\u5f55\u7684\u7528\u6237\u6570",
                    "id": "bk_monitor.time_series.dbm_system.env.login_user",
                    "hidden": True,
                },
                {
                    "title": "\u6700\u5927\u6587\u4ef6\u63cf\u8ff0\u7b26",
                    "id": "bk_monitor.time_series.dbm_system.env.maxfiles",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u603b\u8fdb\u7a0b\u6570",
                    "id": "bk_monitor.time_series.dbm_system.env.procs",
                    "hidden": True,
                },
                {
                    "title": "\u5904\u4e8e\u7b49\u5f85I/O\u5b8c\u6210\u7684\u8fdb\u7a0b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.dbm_system.env.procs_blocked_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u4e0a\u4e0b\u6587\u5207\u6362\u6b21\u6570",
                    "id": "bk_monitor.time_series.dbm_system.env.procs_ctxt_total",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u540e\u6240\u521b\u5efa\u8fc7\u7684\u8fdb\u7a0b\u6570\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.env.procs_processes_total",
                    "hidden": True,
                },
                {
                    "title": "\u6b63\u5728\u8fd0\u884c\u7684\u8fdb\u7a0b\u603b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.dbm_system.env.proc_running_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u65f6\u95f4",
                    "id": "bk_monitor.time_series.dbm_system.env.uptime",
                    "hidden": True,
                },
                {
                    "title": "\u53ef\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.inode.free",
                    "hidden": True,
                },
                {
                    "title": "\u5df2\u7528inode\u5360\u6bd4",
                    "id": "bk_monitor.time_series.dbm_system.inode.in_use",
                    "hidden": True,
                },
                {
                    "title": "\u603binode\u6570\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.inode.total",
                    "hidden": True,
                },
                {
                    "title": "\u5df2\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.inode.used",
                    "hidden": True,
                },
                {"title": "I/O\u4f7f\u7528\u7387", "id": "bk_monitor.time_series.dbm_system.io.util", "hidden": True},
                {"title": "I/O\u5199\u901f\u7387", "id": "bk_monitor.time_series.dbm_system.io.wkb_s", "hidden": True},
                {"title": "I/O\u5199\u6b21\u6570", "id": "bk_monitor.time_series.dbm_system.io.w_s", "hidden": True},
                {
                    "title": "\u7269\u7406\u5185\u5b58\u603b\u5927\u5c0f",
                    "id": "bk_monitor.time_series.dbm_system.mem.total",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.mem.used",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u5305\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.net.speed_packets_recv",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.net.speed_recv",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.net.speed_sent",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf\u6bd4\u7279\u901f\u7387 ",
                    "id": "bk_monitor.time_series.dbm_system.net.speed_sent_bit",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u7a7a\u95f2\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.swap.free",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u5df2\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.dbm_system.swap.pct_used",
                    "hidden": True,
                },
                {
                    "title": "swap\u4ece\u786c\u76d8\u5230\u5185\u5b58",
                    "id": "bk_monitor.time_series.dbm_system.swap.swap_in",
                    "hidden": True,
                },
                {
                    "title": "swap\u4ece\u5185\u5b58\u5230\u786c\u76d8",
                    "id": "bk_monitor.time_series.dbm_system.swap.swap_out",
                    "hidden": True,
                },
                {"title": "SWAP\u603b\u91cf", "id": "bk_monitor.time_series.dbm_system.swap.total", "hidden": True},
                {
                    "title": "SWAP\u5df2\u7528\u91cf",
                    "id": "bk_monitor.time_series.dbm_system.swap.used",
                    "hidden": True,
                },
                {
                    "title": "\u5185\u6838\u5728\u865a\u62df\u673a\u4e0a\u8fd0\u884c\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.guest",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u7a7a\u95f2\u7387",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.idle",
                    "hidden": True,
                },
                {
                    "title": "\u786c\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.interrupt",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u7b49\u5f85IO\u7684\u65f6\u95f4\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.iowait",
                    "hidden": True,
                },
                {
                    "title": "\u4f4e\u4f18\u5148\u7ea7\u7a0b\u5e8f\u5728\u7528\u6237\u6001\u6267\u884c\u7684CPU\u5360\u6bd4",  # noqa
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.nice",
                    "hidden": True,
                },
                {
                    "title": "\u8f6f\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.softirq",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u5206\u914d\u7ed9\u865a\u62df\u673a\u7684\u65f6\u95f4\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.stolen",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u7cfb\u7edf\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.system",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.usage",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u7528\u6237\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_detail.user",
                    "hidden": True,
                },
                {
                    "title": "\u5185\u6838\u5728\u865a\u62df\u673a\u4e0a\u8fd0\u884c\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.guest",
                    "hidden": True,
                },
                {
                    "title": "CPU\u7a7a\u95f2\u7387",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.idle",
                    "hidden": True,
                },
                {
                    "title": "\u786c\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.interrupt",
                    "hidden": True,
                },
                {
                    "title": "CPU\u7b49\u5f85IO\u7684\u65f6\u95f4\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.iowait",
                    "hidden": True,
                },
                {
                    "title": "\u4f4e\u4f18\u5148\u7ea7\u7a0b\u5e8f\u5728\u7528\u6237\u6001\u6267\u884c\u7684CPU\u5360\u6bd4",  # noqa
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.nice",
                    "hidden": True,
                },
                {
                    "title": "\u8f6f\u4ef6\u4e2d\u65ad\u6570\u7684CPU\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.softirq",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5206\u914d\u7ed9\u865a\u62df\u673a\u7684\u65f6\u95f4\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.stolen",
                    "hidden": True,
                },
                {
                    "title": "CPU\u7cfb\u7edf\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.system",
                    "hidden": True,
                },
                {
                    "title": "CPU\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.usage",
                    "hidden": True,
                },
                {
                    "title": "CPU\u7528\u6237\u7a0b\u5e8f\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.cpu_summary.user",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u53ef\u7528\u7a7a\u95f4\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.disk.free",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u7a7a\u95f4\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.perforce_system.disk.in_use",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u603b\u7a7a\u95f4\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.disk.total",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u5df2\u7528\u7a7a\u95f4\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.disk.used",
                    "hidden": True,
                },
                {
                    "title": "\u767b\u5f55\u7684\u7528\u6237\u6570",
                    "id": "bk_monitor.time_series.perforce_system.env.login_user",
                    "hidden": True,
                },
                {
                    "title": "\u6700\u5927\u6587\u4ef6\u63cf\u8ff0\u7b26",
                    "id": "bk_monitor.time_series.perforce_system.env.maxfiles",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u603b\u8fdb\u7a0b\u6570",
                    "id": "bk_monitor.time_series.perforce_system.env.procs",
                    "hidden": True,
                },
                {
                    "title": "\u5904\u4e8e\u7b49\u5f85I/O\u5b8c\u6210\u7684\u8fdb\u7a0b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.perforce_system.env.procs_blocked_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u4e0a\u4e0b\u6587\u5207\u6362\u6b21\u6570",
                    "id": "bk_monitor.time_series.perforce_system.env.procs_ctxt_total",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u540e\u6240\u521b\u5efa\u8fc7\u7684\u8fdb\u7a0b\u6570\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.env.procs_processes_total",
                    "hidden": True,
                },
                {
                    "title": "\u6b63\u5728\u8fd0\u884c\u7684\u8fdb\u7a0b\u603b\u4e2a\u6570",
                    "id": "bk_monitor.time_series.perforce_system.env.proc_running_current",
                    "hidden": True,
                },
                {
                    "title": "\u7cfb\u7edf\u542f\u52a8\u65f6\u95f4",
                    "id": "bk_monitor.time_series.perforce_system.env.uptime",
                    "hidden": True,
                },
                {
                    "title": "\u53ef\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.inode.free",
                    "hidden": True,
                },
                {
                    "title": "\u5df2\u7528inode\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.inode.in_use",
                    "hidden": True,
                },
                {
                    "title": "\u603binode\u6570\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.inode.total",
                    "hidden": True,
                },
                {
                    "title": "\u5df2\u7528inode\u6570\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.inode.used",
                    "hidden": True,
                },
                {
                    "title": "\u5e73\u5747I/O\u961f\u5217\u957f\u5ea6",
                    "id": "bk_monitor.time_series.perforce_system.io.avgqu_sz",
                    "hidden": True,
                },
                {
                    "title": "\u8bbe\u5907\u6bcf\u6b21I/O\u5e73\u5747\u6570\u636e\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.io.avgrq_sz",
                    "hidden": True,
                },
                {
                    "title": "I/O\u5e73\u5747\u7b49\u5f85\u65f6\u957f",
                    "id": "bk_monitor.time_series.perforce_system.io.await",
                    "hidden": True,
                },
                {
                    "title": "I/O\u8bfb\u901f\u7387",
                    "id": "bk_monitor.time_series.perforce_system.io.rkb_s",
                    "hidden": True,
                },
                {
                    "title": "I/O\u8bfb\u6b21\u6570",
                    "id": "bk_monitor.time_series.perforce_system.io.r_s",
                    "hidden": True,
                },
                {
                    "title": "I/O\u5e73\u5747\u670d\u52a1\u65f6\u957f",
                    "id": "bk_monitor.time_series.perforce_system.io.svctm",
                    "hidden": True,
                },
                {
                    "title": "I/O\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.perforce_system.io.util",
                    "hidden": True,
                },
                {
                    "title": "I/O\u5199\u901f\u7387",
                    "id": "bk_monitor.time_series.perforce_system.io.wkb_s",
                    "hidden": True,
                },
                {
                    "title": "I/O\u5199\u6b21\u6570",
                    "id": "bk_monitor.time_series.perforce_system.io.w_s",
                    "hidden": True,
                },
                {
                    "title": "1\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                    "id": "bk_monitor.time_series.perforce_system.load.load1",
                    "hidden": True,
                },
                {
                    "title": "15\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                    "id": "bk_monitor.time_series.perforce_system.load.load15",
                    "hidden": True,
                },
                {
                    "title": "5\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                    "id": "bk_monitor.time_series.perforce_system.load.load5",
                    "hidden": True,
                },
                {
                    "title": "\u5355\u6838CPU\u7684load",
                    "id": "bk_monitor.time_series.perforce_system.load.per_cpu_load",
                    "hidden": True,
                },
                {
                    "title": "\u5185\u5b58buffered\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.mem.buffer",
                    "hidden": True,
                },
                {
                    "title": "\u5185\u5b58cached\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.mem.cached",
                    "hidden": True,
                },
                {
                    "title": "\u7269\u7406\u5185\u5b58\u7a7a\u95f2\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.mem.free",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u53ef\u7528\u7387",
                    "id": "bk_monitor.time_series.perforce_system.mem.pct_usable",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.mem.pct_used",
                    "hidden": True,
                },
                {
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.mem.psc_pct_used",
                    "hidden": True,
                },
                {
                    "title": "\u7269\u7406\u5185\u5b58\u5df2\u7528\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.mem.psc_used",
                    "hidden": True,
                },
                {
                    "title": "\u5171\u4eab\u5185\u5b58\u4f7f\u7528\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.mem.shared",
                    "hidden": True,
                },
                {
                    "title": "\u7269\u7406\u5185\u5b58\u603b\u5927\u5c0f",
                    "id": "bk_monitor.time_series.perforce_system.mem.total",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u53ef\u7528\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.mem.usable",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.mem.used",
                    "hidden": True,
                },
                {
                    "title": "\u8bbe\u5907\u9a71\u52a8\u7a0b\u5e8f\u68c0\u6d4b\u5230\u7684\u8f7d\u6ce2\u4e22\u5931\u6570",  # noqa
                    "id": "bk_monitor.time_series.perforce_system.net.carrier",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51b2\u7a81\u5305",
                    "id": "bk_monitor.time_series.perforce_system.net.collisions",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u4e22\u5f03\u5305",
                    "id": "bk_monitor.time_series.perforce_system.net.dropped",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u9519\u8bef\u5305",
                    "id": "bk_monitor.time_series.perforce_system.net.errors",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u7269\u7406\u5c42\u4e22\u5f03",
                    "id": "bk_monitor.time_series.perforce_system.net.overruns",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u5305\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_packets_recv",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51fa\u5305\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_packets_sent",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_recv",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf\u6bd4\u7279\u901f\u7387",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_recv_bit",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_sent",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u51fa\u6d41\u91cf\u6bd4\u7279\u901f\u7387 ",
                    "id": "bk_monitor.time_series.perforce_system.net.speed_sent_bit",
                    "hidden": True,
                },
                {
                    "title": "closed\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_closed",
                    "hidden": True,
                },
                {
                    "title": "closewait\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_closewait",
                    "hidden": True,
                },
                {
                    "title": "closing\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_closing",
                    "hidden": True,
                },
                {
                    "title": "estab\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_estab",
                    "hidden": True,
                },
                {
                    "title": "finwait1\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_finwait1",
                    "hidden": True,
                },
                {
                    "title": "finwait2\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_finwait2",
                    "hidden": True,
                },
                {
                    "title": "lastact\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_lastack",
                    "hidden": True,
                },
                {
                    "title": "listen\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_listen",
                    "hidden": True,
                },
                {
                    "title": "synrecv\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_syn_recv",
                    "hidden": True,
                },
                {
                    "title": "synsent\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_syn_sent",
                    "hidden": True,
                },
                {
                    "title": "timewait\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_tcp_timewait",
                    "hidden": True,
                },
                {
                    "title": "udp\u63a5\u6536\u5305\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_udp_indatagrams",
                    "hidden": True,
                },
                {
                    "title": "udp\u53d1\u9001\u5305\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.netstat.cur_udp_outdatagrams",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u7a7a\u95f2\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.swap.free",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u5df2\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.perforce_system.swap.pct_used",
                    "hidden": True,
                },
                {
                    "title": "swap\u4ece\u786c\u76d8\u5230\u5185\u5b58",
                    "id": "bk_monitor.time_series.perforce_system.swap.swap_in",
                    "hidden": True,
                },
                {
                    "title": "swap\u4ece\u5185\u5b58\u5230\u786c\u76d8",
                    "id": "bk_monitor.time_series.perforce_system.swap.swap_out",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u603b\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.swap.total",
                    "hidden": True,
                },
                {
                    "title": "SWAP\u5df2\u7528\u91cf",
                    "id": "bk_monitor.time_series.perforce_system.swap.used",
                    "hidden": True,
                },
                {
                    "title": "CPU\u5355\u6838\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.dbm_system.cpu_detail.usage",
                    "hidden": True,
                },
                {
                    "title": "\u78c1\u76d8\u7a7a\u95f4\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.dbm_system.disk.in_use",
                    "hidden": True,
                },
                {"title": "I/O\u8bfb\u901f\u7387", "id": "bk_monitor.time_series.dbm_system.io.rkb_s", "hidden": True},
                {
                    "title": "1\u5206\u949f\u5e73\u5747\u8d1f\u8f7d",
                    "id": "bk_monitor.time_series.dbm_system.load.load1",
                    "hidden": True,
                },
                {
                    "title": "\u5e94\u7528\u7a0b\u5e8f\u5185\u5b58\u4f7f\u7528\u5360\u6bd4",
                    "id": "bk_monitor.time_series.dbm_system.mem.pct_used",
                    "hidden": True,
                },
                {
                    "title": "\u7f51\u5361\u5165\u6d41\u91cf\u6bd4\u7279\u901f\u7387",
                    "id": "bk_monitor.time_series.dbm_system.net.speed_recv_bit",
                    "hidden": True,
                },
                {
                    "title": "estab\u8fde\u63a5\u6570",
                    "id": "bk_monitor.time_series.dbm_system.netstat.cur_tcp_estab",
                    "hidden": True,
                },
                {
                    "title": "CPU\u4f7f\u7528\u7387",
                    "id": "bk_monitor.time_series.dbm_system.cpu_summary.usage",
                    "hidden": True,
                },
                {
                    "title": "disk_usage",
                    "id": "bk_monitor.time_series.script_test_metric_cache.__default__.disk_usage",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_gc_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_accumulator_gc_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_gc_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_accumulator_gc_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_published_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_accumulator_published_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_published_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_accumulator_published_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_beat_sent_bytes_size_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_beat_sent_bytes_size_sum",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_beat_sent_bytes_size_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_beat_sent_bytes_size_count",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_beat_sent_bytes_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_beat_sent_bytes_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_cluster_dropped_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_cluster_dropped_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_controller_reload_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_controller_reload_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_controller_reload_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_controller_reload_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_controller_reload_failed_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_controller_reload_failed_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_controller_reload_success_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_controller_reload_success_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_engine_load_config_failed_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_engine_load_config_failed_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_engine_load_config_success_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_engine_load_config_success_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_sent_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_exporter_sent_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_sent_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_exporter_sent_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_sent_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_exporter_sent_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_panic_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_panic_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_internal_error_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_proxy_internal_error_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_uptime",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.bk_collector_uptime",
                    "hidden": True,
                },
                {
                    "title": "go_gc_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_gc_duration_seconds_sum",
                    "hidden": True,
                },
                {
                    "title": "go_gc_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_gc_duration_seconds_count",
                    "hidden": True,
                },
                {
                    "title": "go_goroutines",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_goroutines",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_alloc_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_alloc_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_alloc_bytes_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_alloc_bytes_total",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_buck_hash_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_buck_hash_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_frees_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_frees_total",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_gc_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_gc_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_alloc_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_alloc_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_idle_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_idle_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_inuse_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_inuse_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_objects",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_objects",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_released_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_released_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_heap_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_heap_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_last_gc_time_seconds",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_last_gc_time_seconds",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_lookups_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_lookups_total",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_mallocs_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_mallocs_total",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_mcache_inuse_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_mcache_inuse_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_mcache_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_mcache_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_mspan_inuse_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_mspan_inuse_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_mspan_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_mspan_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_next_gc_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_next_gc_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_other_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_other_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_stack_inuse_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_stack_inuse_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_stack_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_stack_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_memstats_sys_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_memstats_sys_bytes",
                    "hidden": True,
                },
                {
                    "title": "go_threads",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.go_threads",
                    "hidden": True,
                },
                {
                    "title": "process_cpu_seconds_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_cpu_seconds_total",
                    "hidden": True,
                },
                {
                    "title": "process_max_fds",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_max_fds",
                    "hidden": True,
                },
                {
                    "title": "process_open_fds",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_open_fds",
                    "hidden": True,
                },
                {
                    "title": "process_resident_memory_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_resident_memory_bytes",
                    "hidden": True,
                },
                {
                    "title": "process_start_time_seconds",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_start_time_seconds",
                    "hidden": True,
                },
                {
                    "title": "process_virtual_memory_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_virtual_memory_bytes",
                    "hidden": True,
                },
                {
                    "title": "process_virtual_memory_max_bytes",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.process_virtual_memory_max_bytes",
                    "hidden": True,
                },
                {
                    "title": "promhttp_metric_handler_requests_in_flight",
                    "id": "bk_monitor.time_series.pushgateway_collector.group1.promhttp_metric_handler_requests_in_flight",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_precheck_failed_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_precheck_failed_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_handled_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_handled_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_handled_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_handled_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_handled_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_handled_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_received_bytes_size_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_received_bytes_size_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_received_bytes_size_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_received_bytes_size_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_received_bytes_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_receiver_received_bytes_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_precheck_failed_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bk_collector_proxy_precheck_failed_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bkm_metricbeat_endpoint_up",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.bkm_metricbeat_endpoint_up",
                    "hidden": True,
                },
                {
                    "title": "promhttp_metric_handler_requests_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group2.promhttp_metric_handler_requests_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_token_info",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_receiver_token_info",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_queue_full_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_exporter_queue_full_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_queue_tick_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_exporter_queue_tick_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_ping_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_pingserver_ping_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_ping_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_pingserver_ping_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_ping_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_pingserver_ping_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_rollping_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_pingserver_rollping_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_targets_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_pingserver_targets_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_handled_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_handled_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_handled_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_handled_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_handled_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_handled_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_received_bytes_size_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_received_bytes_size_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_received_bytes_size_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_received_bytes_size_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_received_bytes_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_proxy_received_bytes_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_semaphore_acquired_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_semaphore_acquired_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_semaphore_acquired_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_semaphore_acquired_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_semaphore_acquired_num",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_semaphore_acquired_num",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_semaphore_acquired_success",
                    "id": "bk_monitor.time_series.pushgateway_collector.group3.bk_collector_semaphore_acquired_success",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_handled_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_receiver_handled_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_receiver_received_bytes_size_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_receiver_received_bytes_size_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_gc_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_accumulator_gc_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_published_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_accumulator_published_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_beat_sent_bytes_size_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_beat_sent_bytes_size_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_controller_reload_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_controller_reload_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_sent_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group4.bk_collector_exporter_sent_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_exported_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_exported_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_handled_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_handled_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_queue_pop_batch_size_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_exporter_queue_pop_batch_size_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_exported_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_exported_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_exported_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_exported_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_handled_duration_seconds_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_handled_duration_seconds_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_handled_duration_seconds_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_handled_duration_seconds_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_added_series_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_accumulator_added_series_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_accumulator_series_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_accumulator_series_count",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_converter_failed_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_converter_failed_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_handled_event_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_exporter_handled_event_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_queue_pop_batch_size_sum",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_exporter_queue_pop_batch_size_sum",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_exporter_queue_pop_batch_size_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_exporter_queue_pop_batch_size_count",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pingserver_ping_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pingserver_ping_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_built_success_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_pipeline_built_success_total",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_handled_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_proxy_handled_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_proxy_received_bytes_size_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_proxy_received_bytes_size_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "bk_collector_series_limiter_added_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_series_limiter_added_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_series_limiter_count",
                    "id": "bk_monitor.time_series.pushgateway_collector.group5.bk_collector_series_limiter_count",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_pipeline_handled_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group6.bk_collector_pipeline_handled_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_app_build_info",
                    "id": "bk_monitor.time_series.pushgateway_collector.group7.bk_collector_app_build_info",
                    "hidden": True,
                },
                {
                    "title": "go_info",
                    "id": "bk_monitor.time_series.pushgateway_collector.group7.go_info",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_converter_span_kind_total",
                    "id": "bk_monitor.time_series.pushgateway_collector.group8.bk_collector_converter_span_kind_total",
                    "hidden": True,
                },
                {
                    "title": "bk_collector_semaphore_acquired_duration_seconds_bucket",
                    "id": "bk_monitor.time_series.pushgateway_collector.group9.bk_collector_semaphore_acquired_duration_seconds_bucket",  # noqa
                    "hidden": True,
                },
                {
                    "title": "go_gc_duration_seconds",
                    "id": "bk_monitor.time_series.pushgateway_collector.group10.go_gc_duration_seconds",
                    "hidden": True,
                },
                {
                    "title": "disk_usage",
                    "id": "bk_monitor.time_series.script_test_group.__default__.disk_usage",
                    "hidden": True,
                },
                {
                    "title": "disk_usage",
                    "id": "bk_monitor.time_series.script_gwh_test.__default__.disk_usage",
                    "hidden": True,
                },
                {
                    "title": "disk_usage",
                    "id": "bk_monitor.time_series.script_liang_test_dynamic_group.__default__.disk_usage",
                    "hidden": True,
                },
                {
                    "title": "disk_usage",
                    "id": "bk_monitor.time_series.script_liang_test_008.__default__.disk_usage",
                    "hidden": True,
                },
            ],
        },
    ],
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
