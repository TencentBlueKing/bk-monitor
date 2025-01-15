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


import arrow

from api.cmdb.define import Host, TopoNode

now = arrow.now()
utc_now = now.to("utc")
now_str = str(now.to("local").naive)
utc_now_str = str(now.to("utc").naive)
utc_timestamp = now.timestamp

AGENT_LOSE_DATA = {
    "utctime2": utc_now_str,
    "value": [
        {
            "event_raw_id": 29,
            "event_type": "gse_basic_alarm_type",
            "event_time": utc_now_str,
            "extra": {"count": 1, "host": [{"ip": "127.0.0.1", "cloudid": 0, "bizid": 0}], "type": 2},
            "event_title": "",
            "event_desc": "",
            "event_source_system": "",
        }
    ],
    "server": "127.0.0.1",
    "utctime": utc_now_str,
    "time": utc_now_str,
    "timezone": 8,
}

AGENT_LOSE_DATA2 = {
    "utctime2": utc_now_str,
    "value": [
        {
            "event_raw_id": 29,
            "event_type": "gse_basic_alarm_type",
            "event_time": utc_now_str,
            "extra": {"count": 1, "host": [{"cloudid": 0, "bizid": 0, "agent_id": "0:127.0.0.1"}], "type": 2},
            "event_title": "",
            "event_desc": "",
            "event_source_system": "",
        }
    ],
    "server": "127.0.0.1",
    "utctime": utc_now_str,
    "time": utc_now_str,
    "timezone": 8,
}

AGENT_LOSE_DATA3 = {
    "utctime2": utc_now_str,
    "value": [
        {
            "event_raw_id": 29,
            "event_type": "gse_basic_alarm_type",
            "event_time": utc_now_str,
            "extra": {
                "count": 1,
                "host": [{"cloudid": 0, "bizid": 0, "agent_id": "0100005254008ed86116666614661851"}],
                "type": 2,
            },
            "event_title": "",
            "event_desc": "",
            "event_source_system": "",
        }
    ],
    "server": "127.0.0.1",
    "utctime": utc_now_str,
    "time": utc_now_str,
    "timezone": 8,
}


AGENT_LOSE_DATA_CLEAN = {
    "data": {
        "record_id": "b3a0d98506ed48e358e9176dbe4d23c4.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
            "agent_version": "v1",
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id", "agent_version"],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        3: {
            "anomaly_message": "GSE AGENT \u5931\u8054",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "b3a0d98506ed48e358e9176dbe4d23c4.{}.31.54.3".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1572868513",
}

AGENT_LOSE_DATA_CLEAN2 = {
    "data": {
        "record_id": "8043faacbbd950898164a946faabe72c.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
            "agent_version": "v2",
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id", "agent_version"],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        3: {
            "anomaly_message": "GSE AGENT \u5931\u8054",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "8043faacbbd950898164a946faabe72c.{}.31.54.3".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1572868513",
}

AGENT_LOSE_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "update_time": 1572868513,
            "algorithms": [
                {
                    "config": "",
                    "level": 3,
                    "type": "",
                }
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "create_time": 1572868513,
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.agent-gse",
                    "result_table_id": "system.event",
                    "metric_field": "agent-gse",
                }
            ],
            "id": 54,
            "name": "Agent\u5fc3\u8df3\u4e22\u5931",
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.11", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.16", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.9", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.8", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.4", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.45", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.80", "bk_target_cloud_id": 0},
                        ],
                    }
                ]
            ],
        }
    ],
    "update_time": 1572868513,
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
            "id": 52,
            "notice_group_list": [],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "detects": [
        {
            "level": 3,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 10},
            "trigger_config": {"count": 1, "check_window": 10},
        }
    ],
    "source_type": "BASEALARM",
    "create_time": 1572868513,
    "id": 31,
    "name": "Agent\u5fc3\u8df3\u4e22\u5931-test",
}

PING_UNREACH_DATA = {
    "server": "127.0.0.1",
    "time": now,
    "value": [
        {
            "event_desc": "",
            "event_raw_id": 27422,
            "event_source_system": "",
            "event_time": utc_now_str,
            "event_timezone": 0,
            "event_title": "",
            "event_type": "gse_basic_alarm_type",
            "extra": {
                "bizid": 0,
                "cloudid": 0,
                "count": 30,
                "host": "127.0.0.11",
                "iplist": [
                    "127.0.0.1",
                    "127.0.0.16",
                ],
                "type": 8,
            },
        }
    ],
}

PING_UNREACH_DATA_CLEAN = {
    "data": {
        "record_id": "990d2ce882caacb380df66462c847d9a.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id"],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        1: {
            "anomaly_message": "Ping不可达",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "990d2ce882caacb380df66462c847d9a.{}.35.58.1".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.35.1572868637",
}

PING_UNREACH_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "update_time": 1572868637,
            "algorithms": [
                {
                    "config": "",
                    "level": 1,
                    "type": "",
                    "id": 94,
                }
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "create_time": 1572868637,
            "query_configs": [
                {
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.ping-gse",
                    "data_source_label": "bk_monitor",
                    "result_table_id": "system.event",
                    "metric_field": "ping-gse",
                }
            ],
            "id": 58,
            "name": "PING\u4e0d\u53ef\u8fbe\u544a\u8b66",
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.11", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.16", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.9", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.8", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.4", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.45", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.80", "bk_target_cloud_id": 0},
                        ],
                    }
                ]
            ],
        }
    ],
    "update_time": 1572868637,
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
            "id": 56,
            "notice_group_list": [],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "detects": [
        {
            "level": 2,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 3, "check_window": 5},
        }
    ],
    "source_type": "BASEALARM",
    "create_time": 1572868637,
    "id": 35,
    "name": "Ping\u4e0d\u53ef\u8fbe-test",
}

DISK_READ_ONLY_DATA = {
    "isdst": 0,
    "utctime2": utc_now_str,
    "value": [
        {
            "event_raw_id": 5853,
            "event_type": "gse_basic_alarm_type",
            "event_time": utc_now_str,
            "extra": {
                "cloudid": 0,
                "host": "127.0.0.1",
                "ro": [
                    {"position": r"\/sys\/fs\/cgroup", "fs": "tmpfs", "type": "tmpfs"},
                    {"position": r"\/readonly_disk", "fs": r"dev\/vdb", "type": "ext4"},
                ],
                "type": 3,
                "bizid": 0,
            },
            "event_title": "",
            "event_desc": "",
            "event_source_system": "",
        }
    ],
    "server": "127.0.0.1",
    "utctime": utc_now_str,
    "time": utc_now_str,
    "timezone": 8,
}

DISK_READ_ONLY_DATA_CLEAN = {
    "data": {
        "record_id": "990d2ce882caacb380df66462c847d9a.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
            "position": r"\/sys\/fs\/cgroup\/readonly_disk",
            "fs": r"tmpfsdev\/vdb",
            "type": "tmpfsext4",
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id"],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        2: {
            "anomaly_message": ("磁盘(tmpfs-tmpfs(\\/sys\\/fs\\/cgroup), dev\\/vdb-ext4(\\/readonly_disk))只读告警"),
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "990d2ce882caacb380df66462c847d9a.{}.31.55.2".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1572868543",
}

DISK_READ_ONLY_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "update_time": 1572868543,
            "algorithms": [
                {
                    "config": "",
                    "level": 2,
                    "type": "",
                    "id": 91,
                }
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "create_time": 1572868543,
            "query_configs": [
                {
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.disk-readonly-gse",
                    "data_source_label": "bk_monitor",
                    "result_table_id": "system.event",
                    "metric_field": "disk-readonly-gse",
                }
            ],
            "id": 55,
            "name": "\u78c1\u76d8\u53ea\u8bfb",
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.11", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.16", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.9", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.8", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.4", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.45", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.80", "bk_target_cloud_id": 0},
                        ],
                    }
                ]
            ],
        }
    ],
    "update_time": 1572868543,
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
            "id": 53,
            "notice_group_list": [],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "detects": [
        {
            "level": 2,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 10},
            "trigger_config": {"count": 1, "check_window": 10},
        }
    ],
    "source_type": "BASEALARM",
    "create_time": 1572868543,
    "id": 32,
    "name": "\u78c1\u76d8\u53ea\u8bfb-test",
}

DISK_FULL_DATA = {
    "isdst": 0,
    "utctime2": utc_now_str,
    "value": [
        {
            "event_raw_id": 7795,
            "event_type": "gse_basic_alarm_type",
            "event_time": utc_now_str,
            "extra": {
                "used_percent": 93,
                "used": 45330684,
                "cloudid": 0,
                "free": 7,
                "fstype": "ext4",
                "host": "127.0.0.1",
                "disk": "/",
                "file_system": "/dev/vda1",
                "size": 51473888,
                "bizid": 0,
                "avail": 3505456,
                "type": 6,
            },
            "event_title": "",
            "event_desc": "",
            "event_source_system": "",
        }
    ],
    "server": "127.0.0.1",
    "utctime": utc_now_str,
    "time": utc_now_str,
    "timezone": 8,
}

DISK_FULL_DATA_CLEAN = {
    "data": {
        "record_id": "990d2ce882caacb380df66462c847d9a.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
            "disk": "/",
            "file_system": "/dev/vda1",
            "fstype": "ext4",
        },
        "dimension_fields": ['bk_target_ip', 'bk_target_cloud_id', 'file_system', 'fstype', 'disk'],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        3: {
            "anomaly_message": "磁盘(/)剩余空间只有7%",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "990d2ce882caacb380df66462c847d9a.{}.31.64.3".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1573030943",
}

DISK_FULL_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "update_time": 1573030943,
            "algorithms": [
                {
                    "config": "",
                    "level": 3,
                    "type": "",
                    "id": 113,
                }
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "create_time": 1573030943,
            "item_id": 64,
            "query_configs": [
                {
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.disk-full-gse",
                    "data_source_label": "bk_monitor",
                    "result_table_id": "system.event",
                    "metric_field": "disk-full-gse",
                }
            ],
            "id": 64,
            "name": "\u78c1\u76d8\u5199\u6ee1",
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.80", "bk_target_cloud_id": 0},
                        ],
                    }
                ]
            ],
        }
    ],
    "update_time": 1573030943,
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
            "id": 54,
            "notice_group_list": [],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 118,
            },
        }
    ],
    "detects": [
        {
            "level": 3,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 1, "check_window": 3},
        }
    ],
    "source_type": "BASEALARM",
    "strategy_name": "\u78c1\u76d8\u5199\u6ee1-test",
    "create_time": 1572868571,
    "id": 33,
    "name": "\u78c1\u76d8\u5199\u6ee1-test",
}

COREFILE_DATA = {
    "isdst": 0,
    "server": "127.0.0.1",
    "time": now,
    "timezone": 8,
    "utctime": now,
    "utctime2": utc_now_str,
    "value": [
        {
            "event_desc": "",
            "event_raw_id": 11,
            "event_source_system": "",
            "event_time": utc_now_str,
            "event_title": "",
            "event_type": "gse_basic_alarm_type",
            "extra": {
                "bizid": 0,
                "cloudid": 0,
                "corefile": "/data/corefile/core_101041_2019-11-04",
                "filesize": "0",
                "host": "127.0.0.1",
                "type": 7,
            },
        }
    ],
}

COREFILE_DATA_CLEAN = {
    "data": {
        "record_id": "990d2ce882caacb380df66462c847d9a.{}".format(utc_timestamp),
        "values": {"value": "", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
        },
        "dimension_fields": ['bk_target_ip', 'bk_target_cloud_id', 'executable_path', 'executable', 'signal'],
        "value": "",
        "time": utc_timestamp,
    },
    "anomaly": {
        1: {
            "anomaly_message": "产生corefile：/data/corefile/core_101041_2019-11-04",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "990d2ce882caacb380df66462c847d9a.{}.31.57.1".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1572868604",
}

COREFILE_STRATEGY = {
    "bk_biz_id": 2,
    "items": [
        {
            "algorithms": [
                {
                    "config": "",
                    "level": 1,
                    "type": "",
                    "id": 93,
                }
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "query_configs": [
                {
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.corefile-gse",
                    "data_source_label": "bk_monitor",
                    "result_table_id": "system.event",
                    "metric_field": "corefile-gse",
                }
            ],
            "id": 57,
            "name": "Corefile\u4ea7\u751f",
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.11", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.16", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.9", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.8", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.4", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.45", "bk_target_cloud_id": 0},
                            {"bk_target_ip": "127.0.0.80", "bk_target_cloud_id": 0},
                        ],
                    }
                ]
            ],
        }
    ],
    "update_time": 1572868604,
    "scenario": "os",
    "actions": [
        {
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
            "id": 55,
            "notice_group_list": [],
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 120,
            },
        }
    ],
    "detects": [
        {
            "level": 1,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 1, "check_window": 5},
        }
    ],
    "source_type": "BASEALARM",
    "create_time": 1572868604,
    "id": 34,
    "name": "corefile\u4ea7\u751f-test",
}

CUSTOM_STR_DATA = {
    "_bizid_": 0,
    "_cloudid_": 0,
    "_server_": "127.0.0.1",
    "_time_": now,
    "_utctime_": utc_now_str,
    "_value_": ["This service is offline"],
}

GSE_PROCESS_EVENT_DATA = {
    "data": [
        {
            "dimension": {
                "bk_target_cloud_id": "0",
                "bk_target_ip": "127.0.0.1",
                "process_group_id": "nodeman",
                "process_index": "nodeman:bkmonitorbeat",
                "process_name": "bkmonitorbeat",
            },
            "event": {"content": "check bkmonitorbeat not running, and restart it success"},
            "event_name": "process_restart_success",
            "target": "10.0.1.10|0",
            "timestamp": 1619171000,
        }
    ],
    "data_id": 1100008,
}
GSE_PROCESS_EVENT_DATA_CLEAN = {
    "data": {
        "time": 1619171,
        "value": "事件类型: 进程重启成功, 事件内容: check bkmonitorbeat not running, and restart it success",
        "values": {
            "time": 1619171,
            "value": "事件类型: 进程重启成功, 事件内容: check bkmonitorbeat not running, and restart it success",
        },
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "process_group_id": "nodeman",
            "process_index": "nodeman:bkmonitorbeat",
            "process_name": "bkmonitorbeat",
            "event_name": "process_restart_success",
            "bk_topo_node": ["biz|2", "module|9", "set|5", "test|2"],
            "agent_version": "v1",
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id", "agent_version"],
        "record_id": "53125324982b76cb0553900830ee940a.{}".format(1619171),
    },
    "anomaly": {
        2: {
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "53125324982b76cb0553900830ee940a.{}.31.449.2".format(1619171),
            "anomaly_message": "事件类型: 进程重启成功, 事件内容: check bkmonitorbeat not running, and restart it success",
        }
    },
    "strategy_snapshot_key": "bk_bkmonitorv3.ee.cache.strategy.snapshot.209.1617956776",
}
CUSTOM_STR_DATA_CLEAN = {
    "data": {
        "record_id": "990d2ce882caacb380df66462c847d9a.{}".format(utc_timestamp),
        "values": {"value": "This service is offline", "time": utc_timestamp},
        "dimensions": {
            "bk_host_id": 2,
            "bk_target_cloud_id": 0,
            "bk_target_ip": "127.0.0.1",
            "bk_topo_node": sorted({"biz|2", "test|2", "set|5", "module|9"}),
        },
        "dimension_fields": ["bk_target_ip", "bk_target_cloud_id"],
        "value": "This service is offline",
        "time": utc_timestamp,
    },
    "anomaly": {
        2: {
            "anomaly_message": "This service is offline",
            "anomaly_time": arrow.get(utc_timestamp).format("YYYY-MM-DD HH:mm:ss"),
            "anomaly_id": "990d2ce882caacb380df66462c847d9a.{}.31.53.2".format(utc_timestamp),
        }
    },
    "strategy_snapshot_key": "bk_monitor.ee[development].cache.strategy.snapshot.31.1572868423",
}

CUSTOM_STR_STRATEGY = {
    "actions": [
        {
            "type": "notice",
            "config": {
                "alarm_end_time": "23:59:59",
                "alarm_interval": 120,
                "alarm_start_time": "00:00:00",
                "send_recovery_alarm": False,
            },
            "id": 51,
            "notice_group_list": [],
            "notice_template": {"anomaly_template": "", "id": 0, "recovery_template": ""},
        }
    ],
    "bk_biz_id": 2,
    "create_time": 1572868423,
    "id": 30,
    "items": [
        {
            "algorithms": [
                {
                    "config": "",
                    "type": "",
                    "id": 89,
                    "level": 2,
                }
            ],
            "create_time": 1572868423,
            "id": 53,
            "name": "\u81ea\u5b9a\u4e49\u5b57\u7b26\u578b\u544a\u8b66",
            "no_data_config": {"continuous": 5, "is_enabled": False},
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "event",
                    "metric_id": "bk_monitor.gse_custom_event",
                    "result_table_id": "system.event",
                    "metric_field": "gse_custom_event",
                }
            ],
            "update_time": 1572868423,
            "target": [
                [
                    {
                        "field": "bk_target_ip",
                        "method": "eq",
                        "value": [
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.10"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.11"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.16"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.9"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.8"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.4"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.45"},
                            {"bk_target_cloud_id": 0, "bk_target_ip": "10.0.1.80"},
                        ],
                    }
                ]
            ],
        }
    ],
    "detects": [
        {
            "level": 2,
            "expression": "",
            "connector": "and",
            "recovery_config": {"check_window": 5},
            "trigger_config": {"count": 1, "check_window": 5},
        }
    ],
    "name": "\u81ea\u5b9a\u4e49\u5b57\u7b26\u578b-bond",
    "scenario": "os",
    "source_type": "BASEALARM",
    "update_time": 1572868423,
}

PROCESS_EVENT_STRATEGY = {
    "id": 441,
    "name": "Gse\u8fdb\u7a0b\u6258\u7ba1\u4e8b\u4ef6\u544a\u8b66(\u5e73\u53f0\u4fa7)",
    "bk_biz_id": 18,
    "scenario": "host_process",
    "is_enabled": True,
    "update_time": "2021-04-21 21:35:06+0800",
    "update_user": "system",
    "create_time": "2021-04-21 21:35:06+0800",
    "create_user": "system",
    "actions": [
        {
            "id": 432,
            "config": {
                "alarm_start_time": "00:00:00",
                "alarm_end_time": "23:59:59",
                "alarm_interval": 1440,
                "send_recovery_alarm": False,
            },
            "type": "notice",
            "notice_group_list": [
                {
                    "id": 63,
                    "display_name": "\u3010\u84dd\u9cb8\u3011\u5b98\u65b9\u63d2\u4ef6\u7ba1\u7406\u5458",
                }
            ],
            "notice_group_id_list": [63],
        }
    ],
    "detects": [
        {
            "level": 2,
            "expression": "",
            "connector": "and",
            "trigger_config": {"count": 1, "check_window": 5},
            "recovery_config": {"check_window": 5},
        }
    ],
    "items": [
        {
            "id": 449,
            "name": "Gse\u8fdb\u7a0b\u6258\u7ba1\u4e8b\u4ef6\u544a\u8b66(\u5e73\u53f0\u4fa7)",
            "update_time": "2021-04-21 21:35:06+0800",
            "create_time": "2021-04-21 21:35:06+0800",
            "target": [
                [
                    {
                        "field": "host_topo_node",
                        "value": [
                            {
                                "bk_obj_id": "biz",
                                "bk_inst_id": 18,
                            }
                        ],
                        "method": "eq",
                    }
                ]
            ],
            "algorithms": [
                {
                    "id": 395,
                    "type": "",
                    "config": [],
                    "level": 2,
                }
            ],
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "event",
                    "result_table_id": "system.event",
                    "metric_field": "gse_process_event",
                    "metric_id": "bk_monitor.gse_process_event",
                    "agg_condition": [
                        {
                            "key": "process_name",
                            "value": [
                                "basereport",
                                "processbeat",
                                "exceptionbeat",
                                "bkmonitorbeat",
                                "bkmonitorproxy",
                                "bkunifylogbeat",
                            ],
                            "method": "include",
                        }
                    ],
                }
            ],
        }
    ],
}


HOST_OBJECT = Host(
    bk_host_innerip="127.0.0.1",
    bk_cloud_id=0,
    bk_host_id=2,
    bk_biz_id=2,
    bk_cloud_name="default area",
    bk_host_outerip="",
    bk_host_name="VM_1_11_centos",
    bk_os_name="linux centos",
    bk_os_version="7.4.1708",
    bk_os_type="1",
    bk_set_ids="",
    bk_module_ids=[1],
    bk_bak_operator="test",
    operator="test",
    topo_link={
        "module|9": [
            {"bk_obj_id": "module", "bk_inst_id": 9, "bk_obj_name": "Module", "bk_inst_name": "测试模块"},
            {"bk_obj_id": "set", "bk_inst_id": 5, "bk_obj_name": "Set", "bk_inst_name": "测试集群"},
            {"bk_obj_id": "test", "bk_inst_id": 2, "bk_obj_name": "Test", "bk_inst_name": "测试"},
            {"bk_obj_id": "biz", "bk_inst_id": 2, "bk_obj_name": "Biz", "bk_inst_name": "测试业务"},
        ]
    },
)
