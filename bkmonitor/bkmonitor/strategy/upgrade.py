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

from core.unit import load_unit

UPDATE_METRICS = [
    {"table_id": "system.cpu_summary", "field_name": "usage", "unit": "percent", "description": "CPU使用率"},
    {"table_id": "system.cpu_summary", "field_name": "idle", "unit": "percentunit", "description": "CPU空闲率"},
    {"table_id": "system.cpu_summary", "field_name": "iowait", "unit": "percentunit", "description": "CPU等待IO的时间占比"},
    {"table_id": "system.cpu_summary", "field_name": "stolen", "unit": "percentunit", "description": "CPU分配给虚拟机的时间占比"},
    {"table_id": "system.cpu_summary", "field_name": "system", "unit": "percentunit", "description": "CPU系统程序使用占比"},
    {"table_id": "system.cpu_summary", "field_name": "user", "unit": "percentunit", "description": "CPU用户程序使用占比"},
    {"table_id": "system.io", "field_name": "await", "unit": "ms", "description": "I/O平均等待时长"},
    {"table_id": "system.io", "field_name": "svctm", "unit": "ms", "description": "I/O平均服务时长"},
    {"table_id": "system.io", "field_name": "r_s", "unit": "rps", "description": "I/O读次数"},
    {"table_id": "system.io", "field_name": "rkb_s", "unit": "KBs", "description": "I/O读速率"},
    {"table_id": "system.io", "field_name": "w_s", "unit": "wps", "description": "I/O写次数"},
    {"table_id": "system.io", "field_name": "wkb_s", "unit": "KBs", "description": "I/O写速率"},
    {"table_id": "system.io", "field_name": "util", "unit": "percentunit", "description": "I/O使用率", "suffix": "%"},
    {"table_id": "system.io", "field_name": "avgrq_sz", "unit": "Sectors/IORequest", "description": "设备每次I/O平均数据大小"},
    {"table_id": "system.io", "field_name": "avgqu_sz", "unit": "Sectors", "description": "平均I/O队列长度"},
    {"table_id": "system.env", "field_name": "uptime", "unit": "s", "description": "系统启动时间"},
    {"table_id": "system.env", "field_name": "procs", "unit": "short", "description": "系统总进程数"},
    {"table_id": "system.cpu_detail", "field_name": "usage", "unit": "percent", "description": "CPU单核使用率"},
    {"table_id": "system.cpu_detail", "field_name": "idle", "unit": "percentunit", "description": "CPU单核空闲率"},
    {"table_id": "system.cpu_detail", "field_name": "iowait", "unit": "percentunit", "description": "CPU单核等待IO的时间占比"},
    {"table_id": "system.cpu_detail", "field_name": "stolen", "unit": "percentunit", "description": "CPU单核分配给虚拟机的时间占比"},
    {"table_id": "system.cpu_detail", "field_name": "system", "unit": "percentunit", "description": "CPU单核系统程序使用占比"},
    {"table_id": "system.cpu_detail", "field_name": "user", "unit": "percentunit", "description": "CPU单核用户程序使用占比"},
    {
        "table_id": "system.mem",
        "field_name": "buffer",
        "unit": "decbytes",
        "description": "内存buffered大小",
        "suffix": "M",
    },
    {"table_id": "system.mem", "field_name": "cached", "unit": "decbytes", "description": "内存cached大小", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "free", "unit": "decbytes", "description": "物理内存空闲量", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "total", "unit": "decbytes", "description": "物理内存总大小", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "usable", "unit": "decbytes", "description": "应用程序内存可用量", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "pct_usable", "unit": "percent", "description": "应用程序内存可用率"},
    {"table_id": "system.mem", "field_name": "used", "unit": "decbytes", "description": "应用程序内存使用量", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "pct_used", "unit": "percent", "description": "应用程序内存使用占比"},
    {"table_id": "system.mem", "field_name": "psc_used", "unit": "decbytes", "description": "物理内存已用量", "suffix": "M"},
    {"table_id": "system.mem", "field_name": "psc_pct_used", "unit": "percent", "description": "物理内存已用占比"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_closewait", "unit": "short", "description": "closewait连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_timewait", "unit": "short", "description": "timewait连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_closed", "unit": "short", "description": "closed连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_closing", "unit": "short", "description": "closing连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_estab", "unit": "short", "description": "estab连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_finwait1", "unit": "short", "description": "finwait1连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_finwait2", "unit": "short", "description": "finwait2连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_lastack", "unit": "short", "description": "lastact连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_listen", "unit": "short", "description": "listen连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_syn_recv", "unit": "short", "description": "synrecv连接数"},
    {"table_id": "system.netstat", "field_name": "cur_tcp_syn_sent", "unit": "short", "description": "synsent连接数"},
    {"table_id": "system.netstat", "field_name": "cur_udp_indatagrams", "unit": "short", "description": "udp接收包量"},
    {"table_id": "system.netstat", "field_name": "cur_udp_outdatagrams", "unit": "short", "description": "udp发送包量"},
    {"table_id": "system.disk", "field_name": "free", "unit": "decbytes", "description": "磁盘可用空间大小", "suffix": "M"},
    {"table_id": "system.disk", "field_name": "total", "unit": "decbytes", "description": "磁盘总空间大小", "suffix": "M"},
    {"table_id": "system.disk", "field_name": "used", "unit": "decbytes", "description": "磁盘已用空间大小", "suffix": "M"},
    {"table_id": "system.disk", "field_name": "in_use", "unit": "percent", "description": "磁盘空间使用率"},
    {"table_id": "system.net", "field_name": "speed_packets_recv", "unit": "pps", "description": "网卡入包量"},
    {"table_id": "system.net", "field_name": "speed_packets_sent", "unit": "pps", "description": "网卡出包量"},
    {"table_id": "system.net", "field_name": "speed_recv", "unit": "Bps", "description": "网卡入流量", "suffix": "k"},
    {"table_id": "system.net", "field_name": "speed_sent", "unit": "Bps", "description": "网卡出流量", "suffix": "k"},
    {
        "table_id": "system.proc",
        "field_name": "cpu_usage_pct",
        "unit": "percentunit",
        "description": "进程CPU使用率",
        "suffix": "%",
    },
    {
        "table_id": "system.proc",
        "field_name": "mem_usage_pct",
        "unit": "percentunit",
        "description": "进程内存使用率",
        "suffix": "%",
    },
    {"table_id": "system.proc", "field_name": "fd_num", "unit": "short", "description": "进程文件句柄数"},
    {"table_id": "system.proc", "field_name": "mem_res", "unit": "decbytes", "description": "进程使用物理内存", "suffix": "M"},
    {"table_id": "system.proc", "field_name": "mem_virt", "unit": "decbytes", "description": "进程使用虚拟内存", "suffix": "M"},
    {"table_id": "system.inode", "field_name": "free", "unit": "short", "description": "可用inode数量"},
    {"table_id": "system.inode", "field_name": "total", "unit": "short", "description": "总inode数量"},
    {"table_id": "system.inode", "field_name": "used", "unit": "short", "description": "已用inode数量"},
    {"table_id": "system.inode", "field_name": "in_use", "unit": "percent", "description": "已用inode占比"},
    {"table_id": "system.swap", "field_name": "free", "unit": "decbytes", "description": "SWAP空闲量", "suffix": "M"},
    {"table_id": "system.swap", "field_name": "total", "unit": "decbytes", "description": "SWAP总量", "suffix": "M"},
    {"table_id": "system.swap", "field_name": "used", "unit": "decbytes", "description": "SWAP已用量", "suffix": "M"},
    {"table_id": "system.swap", "field_name": "pct_used", "unit": "percent", "description": "SWAP已用占比"},
    {"table_id": "system.proc_port", "field_name": "proc_exists", "unit": "none", "description": "进程存活状态"},
    {"table_id": "system.proc_port", "field_name": "port_health", "unit": "none", "description": "进程端口状态"},
    {"table_id": "uptimecheck.tcp", "field_name": "task_duration", "unit": "ms", "description": "耗时"},
    {
        "table_id": "uptimecheck.tcp",
        "field_name": "available",
        "unit": "percentunit",
        "description": "单点可用率",
        "suffix": "%",
    },
    {"table_id": "uptimecheck.udp", "field_name": "task_duration", "unit": "ms", "description": "耗时"},
    {
        "table_id": "uptimecheck.udp",
        "field_name": "available",
        "unit": "percentunit",
        "description": "单点可用率",
        "suffix": "%",
    },
    {"table_id": "uptimecheck.udp", "field_name": "times", "unit": "short", "description": "重试次数"},
    {"table_id": "uptimecheck.http", "field_name": "task_duration", "unit": "ms", "description": "耗时"},
    {
        "table_id": "uptimecheck.http",
        "field_name": "available",
        "unit": "percentunit",
        "description": "单点可用率",
        "suffix": "%",
    },
    {"table_id": "uptimecheck.http", "field_name": "content_length", "unit": "decbytes", "description": "响应长度"},
    {"table_id": "uptimecheck.http", "field_name": "steps", "unit": "short", "description": "请求步骤数"},
    {
        "table_id": "uptimecheck.icmp",
        "field_name": "available",
        "unit": "percentunit",
        "description": "单点可用率",
        "suffix": "%",
    },
    {
        "table_id": "uptimecheck.icmp",
        "field_name": "loss_percent",
        "unit": "percentunit",
        "description": "丢包率",
        "suffix": "%",
    },
    {"table_id": "uptimecheck.heartbeat", "field_name": "reload", "unit": "short", "description": "重载次数"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "running_tasks", "unit": "short", "description": "运行任务数"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "success", "unit": "short", "description": "成功事件数"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "uptime", "unit": "ms", "description": "启动时间"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "fail", "unit": "short", "description": "失败事件数"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "error", "unit": "short", "description": "错误事件数"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "reload_timestamp", "unit": "ms", "description": "重载时间"},
    {"table_id": "uptimecheck.heartbeat", "field_name": "loaded_tasks", "unit": "short", "description": "历史载入任务数"},
    {"table_id": "system.load", "field_name": "load1", "unit": "none", "description": "1分钟平均负载"},
    {"table_id": "system.load", "field_name": "load5", "unit": "none", "description": "5分钟平均负载"},
    {"table_id": "system.load", "field_name": "load15", "unit": "none", "description": "15分钟平均负载"},
    {
        "table_id": "beat_monitor.heartbeat_total",
        "field_name": "config_error_code",
        "unit": "none",
        "description": "整体配置错误码",
    },
    {"table_id": "beat_monitor.heartbeat_total", "field_name": "uptime", "unit": "s", "description": "运行秒数"},
    {"table_id": "beat_monitor.heartbeat_total", "field_name": "tasks", "unit": "short", "description": "采集任务数"},
    {
        "table_id": "beat_monitor.heartbeat_total",
        "field_name": "config_load_at",
        "unit": "none",
        "description": "配置加载时间",
    },
    {"table_id": "beat_monitor.heartbeat_total", "field_name": "published", "unit": "short", "description": "数据上报数"},
    {"table_id": "beat_monitor.heartbeat_total", "field_name": "errors", "unit": "short", "description": "采集错误数"},
    {"table_id": "beat_monitor.heartbeat_total", "field_name": "error_tasks", "unit": "short", "description": "错误子任务数"},
    {
        "table_id": "beat_monitor.heartbeat_child",
        "field_name": "config_error_code",
        "unit": "none",
        "description": "子配置错误码",
    },
]


def get_metric_suffix_mapping():
    """
    获取 metric_id 及对应单位后缀的映射关系
    :return:
    """
    metric_suffix = {}
    for metric in UPDATE_METRICS:
        metric_id = f"{metric['table_id']}.{metric['field_name']}"
        if metric.get("suffix"):
            metric_suffix[metric_id] = metric["suffix"]
        else:
            unit = load_unit(metric["unit"])
            if not unit.suffix_list or unit.suffix_idx >= len(unit.suffix_list):
                continue
            metric_suffix[metric_id] = unit.suffix_list[unit.suffix_idx]
    return metric_suffix


def get_metric_unit_mapping():
    """
    获取 metric_id 及对应单位的映射关系
    :return:
    """
    metric_unit = {}
    for metric in UPDATE_METRICS:
        metric_id = f"{metric['table_id']}.{metric['field_name']}"
        metric_unit[metric_id] = metric["unit"]
    return metric_unit
