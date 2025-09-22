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

DEFAULT_APM_HOST_DETAIL = {
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
    ],
}
