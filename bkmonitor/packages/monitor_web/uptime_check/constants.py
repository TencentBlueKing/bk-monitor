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

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from bkmonitor.utils.i18n import TranslateDict

# 拨测数据类型和数据来源
UPTIME_DATA_SOURCE_LABEL = "bk_monitor"
UPTIME_DATA_TYPE_LABEL = "time_series"
UPTIME_CHECK_DB = "uptimecheck"


def get_dataid(type):
    """
    获取data_id
    """
    if type == "heartbeat":
        return 9979
    elif type == "tcp":
        return 9978
    elif type == "udp":
        return 10286
    elif type == "http":
        return 10287


# 拨测 配置模板
UPTIME_CHECK_CONFIG_TEMPLATE = {
    "logging.level": "error",
    "max_procs": 1,
    "output.console": None,
    "path.data": "/var/lib/gse",
    "path.logs": "/var/log/gse",
    "path.pid": "/var/run/gse",
    "uptimecheckbeat": {
        "ip": None,
        "clean_up_timeout": "1s",
        "event_buffer_size": 10,
        "mode": "daemon",
        "node_id": 0,
        "bk_biz_id": 0,
        "bk_cloud_id": 0,
        "heart_beat": {"dataid": settings.UPTIMECHECK_HEARTBEAT_DATAID, "period": "60s"},
    },
}

# 采集器状态码 与 错误信息对应关系
RESULT_MSG = TranslateDict(
    {
        "-1": _("初始化状态（-1）"),
        "0": _("已成功探测目标服务，保存任务中..."),
        "1": _("测试任务执行失败：未知错误（1）"),
        "2": _("采集器任务取消（2）"),
        "3": _("目标响应时间大于期望响应时间（3）"),
        "1000": _("请检查任务参数是否有误，或确认目标服务是否可访问（1000）"),
        "1001": _("请检查任务参数是否有误，或网络/目标服务是否可访问（1001）"),
        "1002": _("请检查代理是否配置正确，或网络是否可达（1002）"),
        "1004": _("DNS解析失败，请检查域名格式是否正确（1004）"),
        "2000": _("请检查任务参数是否有误，或网络/目标服务是否可访问（2000）"),
        "2001": _("请求超时，请确认网络/目标服务是否可访问（2001）"),
        "2002": _("目标服务请求超过超时设置（2002）"),
        "2003": _("拨测采集器配置异常，请联系管开发者（2003）"),
        "3000": _("目标服务无响应返回（3000）"),
        "3001": _("请确认网络/目标服务是否可访问（3001）"),
        "3002": _("请确认响应内容是否正确（3002）"),
        "3003": _("请确认返回码是否正确（3003）"),
        "3004": _("临时响应失败（3004）"),
        "3005": _("服务无响应（3005）"),
        "3006": _("响应处理失败（3006）"),
        "3007": _("响应失败，请确认端口是否存在（3007）"),
        "3008": _("响应读取失败（3008）"),
        "3009": _("响应头部为空（3009）"),
        "3010": _("响应头部不符合（3010）"),
        "3011": _("未解析出ipv4地址（3011）"),
        "3012": _("未解析出ipv6地址（3012）"),
        "3013": _("url解析失败（3013）"),
    }
)
UDP_RESULT_MSG = TranslateDict(
    {
        "-1": _("初始化状态（-1）"),
        "0": _("已成功探测目标服务，保存任务中..."),
        "1000": _("链接失败，host 或者端口非法（1000）"),
        "1001": _("请检查任务参数是否有误，或网络/目标服务是否可访问（1001）"),
        "2000": _("请求写失败，syscall.write 返回错误（2000）"),
        "2002": _("目标服务请求超过超时设置（2002）"),
        "2003": _("请求初始化失败，'request'/'request_format' 解析出错（2003）"),
        "3000": _("目标服务无响应返回（3000）"),
        "3001": _("响应读取超时，请确认网络/目标服务是否可访问（3001）"),
        "3002": _("响应内容匹配失败，请确认响应内容是否正确（3002）"),
        "3007": _("响应失败，ICMP unreachable（3007）"),
    }
)

# RT表字段模板
RT_FIELDS = [
    {"name": "available", "description": _("可用率"), "type": "double", "is_dimension": False},
    {"name": "version", "description": _("采集器版本"), "type": "string", "is_dimension": True},
    {"name": "bk_biz_id", "description": _("业务ID"), "type": "int", "is_dimension": True},
    {"name": "dataid", "description": "dataid", "type": "int", "is_dimension": True},
    {"name": "duration", "description": _("响应时长"), "type": "int", "is_dimension": False},
    {"name": "error_code", "description": _("错误码"), "type": "int", "is_dimension": True},
    {"name": "ip", "description": _("本机IP"), "type": "string", "is_dimension": True},
    {"name": "node_id", "description": _("拨测节点ID"), "type": "int", "is_dimension": True},
    {"name": "status", "description": _("检测结果"), "type": "", "is_dimension": True},
    {"name": "target_host", "description": _("目标ip或域名"), "type": "string", "is_dimension": True},
    {"name": "target_port", "description": _("目标端口号"), "type": "int", "is_dimension": True},
    {"name": "task_id", "description": _("拨测任务ID"), "type": "int", "is_dimension": True},
    {"name": "task_type", "description": _("拨测任务类型"), "type": "string", "is_dimension": True},
    {"name": "type", "description": _("检测类型"), "type": "string", "is_dimension": True},
]

# 拨测 概览页面 默认每个任务展示可用率曲线的时间范围(单位：小时)
UPTIME_CHECK_SUMMARY_TIME_RANGE = 1

# 拨测 任务详情页面 默认每个任务展示可用率曲线的时间范围(单位：小时)
UPTIME_CHECK_TASK_DETAIL_TIME_RANGE = 24

# 拨测 任务详情页面 可用率曲线group_by minute1的时间范围(单位：小时)
UPTIME_CHECK_TASK_DETAIL_GROUP_BY_MINUTE1_TIME_RANGE = 12

# 拨测 获取采集器心跳、版本信息时，取计算平台最近多少分钟内的数据
UPTIME_CHECK_BEAT_DATA_TIME_RANGE = 3

# 监控指标与监控字段对应关系
METRIC_TO_MONITOR_TARGET = {
    "available": "available",
    "task_duration": "task_duration",
    "response_code": "available",
    "response": "available",
}

# METRIC模板
UPTIME_CHECK_METRIC_TEMPLATE = {
    "bk_biz_id": "",
    "metric": "",
    "where_field_list": [],
    "method": "",
    "metric_field": "",
    "alis": "",
    "group_field_list": [],
    "rt_id": "",
    "graph_type": "time",
}

# 针对error_code进行监控的过滤模板
ERROR_CODE_TEMPLATE = '[[{"field": "error_code", "method": "eq", "value": "%s"}]]'

# 监控指标为响应内容时的过滤条件
UPTIME_CHECK_MONIT_RESPONSE = ERROR_CODE_TEMPLATE % 3002

# 监控指标为状态码时的过滤条件
UPTIME_CHECK_MONIT_RESPONSE_CODE = ERROR_CODE_TEMPLATE % 3003

# 新建拨测任务，默认生成告警策略模板
UPTIME_CHECK_DEFAULT_STRATEGY_TEMPLATE = {
    # variable
    "task_id": 0,
    "scenario": "uptimecheck",
    "monitor_target": "",
    "display_name": "",
    "condition": [[]],
    "node_count": 0,
    # static value
    "bk_biz_id": 0,
    "monitor_id": 0,
    "alarm_strategy_id": 0,
    "nodata_alarm": 0,
    "rules": {"alarm_window": 1440, "check_window": 5, "count": 3},
    "solution_notice": [],
    "solution_type": "",
    "solution_task_id": "",
    "solution_is_enable": False,
    "solution_params_replace": "",
    "is_recovery": False,
    "is_classify_notice": False,
    "alarm_level_config": {
        2: {
            "alarm_end_time": "23:59",
            "alarm_start_time": "00:00",
            "phone_receiver": [],
            "notify_way": ["mail", "wechat"],
            "responsible": [],
            "role_list": ["Maintainers"],
            "monitor_level": 2,
            "detect_algorithm": [{"config": {"threshold": 0, "method": "", "message": ""}, "algorithm_id": 1000}],
        }
    },
}

# 可用率监控 默认阈值
UPTIME_CHECK_AVAILABLE_DEFAULT_VALUE = 100

# 响应时间监控 默认阈值(ms) 默认使用用户在建立拨测任务时填写的时间
UPTIME_CHECK_DURATION_DEFAULT_VALUE = 1000

# HTTP任务允许设置的headers列表
UPTIME_CHECK_ALLOWED_HEADERS = [
    "Accept",
    "Accept-Charsets",
    "Accept-Encoding",
    "Accept-Language",
    "Cookie",
    "Cache-Control",
    "Content-Type",
    "Host",
    "Referer",
]

UPTIME_CHECK_METRICS = [
    {
        "items": [
            {
                "index": 1,
                "display": _("运行任务数"),
                "id": "uptimecheck.heartbeat.running_tasks",
                "item": "running_tasks",
                "description": _("运行任务数"),
            },
            {
                "index": 2,
                "display": _("成功事件数"),
                "id": "uptimecheck.heartbeat.success",
                "item": "success",
                "description": _("成功事件数"),
            },
            {
                "index": 3,
                "display": _("启动时间"),
                "id": "uptimecheck.heartbeat.uptime",
                "item": "uptime",
                "description": _("启动时间"),
            },
            {
                "index": 4,
                "display": _("采集器版本"),
                "id": "uptimecheck.heartbeat.version",
                "item": "version",
                "description": _("采集器版本"),
            },
            {
                "index": 5,
                "display": _("失败事件数"),
                "id": "uptimecheck.heartbeat.fail",
                "item": "fail",
                "description": _("失败事件数"),
            },
            {
                "index": 6,
                "display": _("运行错误数"),
                "id": "uptimecheck.heartbeat.error",
                "item": "error",
                "description": _("运行错误数"),
            },
            {
                "index": 7,
                "display": _("重载时间"),
                "id": "uptimecheck.heartbeat.reload_timestamp",
                "item": "reload_timestamp",
                "description": _("重载时间"),
            },
            {
                "index": 8,
                "display": _("历史载入任务数"),
                "id": "uptimecheck.heartbeat.loaded_tasks",
                "item": "loaded_tasks",
                "description": _("历史载入任务数"),
            },
        ],
        "table_name": "uptimecheck_heartbeat",
        "table_name_display": "heartbeat",
    },
    {
        "items": [
            {
                "index": 9,
                "display": _("耗时"),
                "id": "uptimecheck.http.task_duration",
                "item": "task_duration",
                "description": _("耗时"),
            },
            {
                "index": 10,
                "display": _("响应长度"),
                "id": "uptimecheck.http.content_length",
                "item": "content_length",
                "description": _("响应长度"),
            },
            {
                "index": 11,
                "display": _("响应消息"),
                "id": "uptimecheck.http.message",
                "item": "message",
                "description": _("响应消息"),
            },
            {
                "index": 12,
                "display": _("请求方法"),
                "id": "uptimecheck.http.method",
                "item": "method",
                "description": _("请求方法"),
            },
            {
                "index": 13,
                "display": _("响应状态码"),
                "id": "uptimecheck.http.response_code",
                "item": "response_code",
                "description": _("响应状态码"),
            },
            {
                "index": 14,
                "display": _("请求步骤数"),
                "id": "uptimecheck.http.steps",
                "item": "steps",
                "description": _("请求步骤数"),
            },
            {"index": 15, "display": _("请求网址"), "id": "uptimecheck.http.url", "item": "url", "description": _("请求网址")},
            {
                "index": 16,
                "display": _("单点可用率"),
                "id": "uptimecheck.http.available",
                "item": "available",
                "description": _("单点可用率"),
            },
        ],
        "table_name": "uptimecheck_http",
        "table_name_display": "http",
    },
    {
        "items": [
            {
                "index": 17,
                "display": _("耗时"),
                "id": "uptimecheck.tcp.task_duration",
                "item": "task_duration",
                "description": _("耗时"),
            },
            {
                "index": 18,
                "display": _("错误码"),
                "id": "uptimecheck.tcp.error_code",
                "item": "error_code",
                "description": _("错误码"),
            },
            {
                "index": 19,
                "display": _("任务id"),
                "id": "uptimecheck.tcp.task_type",
                "item": "task_type",
                "description": _("任务id"),
            },
            {
                "index": 20,
                "display": _("单点可用率"),
                "id": "uptimecheck.tcp.available",
                "item": "available",
                "description": _("单点可用率"),
            },
        ],
        "table_name": "uptimecheck_tcp",
        "table_name_display": "tcp",
    },
    {
        "items": [
            {
                "index": 21,
                "display": _("耗时"),
                "id": "uptimecheck.udp.task_duration",
                "item": "task_duration",
                "description": _("耗时"),
            },
            {
                "index": 22,
                "display": _("错误码"),
                "id": "uptimecheck.udp.error_code",
                "item": "error_code",
                "description": _("错误码"),
            },
            {
                "index": 23,
                "display": _("任务id"),
                "id": "uptimecheck.udp.task_type",
                "item": "task_type",
                "description": _("任务id"),
            },
            {
                "index": 24,
                "display": _("重试次数"),
                "id": "uptimecheck.udp.times",
                "item": "times",
                "description": _("重试次数"),
            },
            {
                "index": 25,
                "display": _("单点可用率"),
                "id": "uptimecheck.udp.available",
                "item": "available",
                "description": _("单点可用率"),
            },
        ],
        "table_name": "uptimecheck_udp",
        "table_name_display": "udp",
    },
    {
        "items": [
            {
                "index": 26,
                "display": _("耗时"),
                "id": "uptimecheck.icmp.task_duration",
                "item": "task_duration",
                "description": _("耗时"),
            },
            {
                "index": 27,
                "display": _("单点可用率"),
                "id": "uptimecheck.icmp.available",
                "item": "available",
                "description": _("单点可用率"),
            },
            {
                "index": 28,
                "display": _("目标地址"),
                "id": "uptimecheck.icmp.target",
                "item": "target",
                "description": _("目标地址"),
            },
        ],
        "table_name": "uptimecheck_icmp",
        "table_name_display": "icmp",
    },
]

UPTIME_CHECK_RT = {
    "heartbeat": {
        "description": "",
        "fields": [
            {"field": "bk_cloud_id", "is_dimension": True, "description": _("云区域id")},
            {"field": "reload", "is_dimension": False, "description": _("重载次数")},
            {"field": "running_tasks", "is_dimension": False, "description": _("运行任务数")},
            {"field": "status", "is_dimension": True, "description": _("任务状态")},
            {"field": "success", "is_dimension": False, "description": _("成功事件数")},
            {"field": "uptime", "is_dimension": False, "description": _("启动时间")},
            {"field": "version", "is_dimension": True, "description": _("采集器版本")},
            {"field": "fail", "is_dimension": False, "description": _("失败事件数")},
            {"field": "error", "is_dimension": False, "description": _("运行错误数")},
            {"field": "reload_timestamp", "is_dimension": False, "description": _("重载时间")},
            {"field": "loaded_tasks", "is_dimension": False, "description": _("历史载入任务数")},
            {"field": "node_id", "is_dimension": True, "description": _("节点ID")},
            {"field": "biz_id", "is_dimension": False, "description": "biz_id"},
            {"field": "timestamp", "is_dimension": False, "description": "timestamp"},
        ],
    },
    "http": {
        "description": "",
        "fields": [
            {"field": "bk_cloud_id", "is_dimension": True, "description": _("云区域ID")},
            {"field": "task_duration", "is_dimension": False, "description": _("耗时")},
            {"field": "error_code", "is_dimension": True, "description": _("错误码")},
            {"field": "status", "is_dimension": True, "description": _("任务状态")},
            {"field": "task_id", "is_dimension": True, "description": _("任务id")},
            {"field": "node_id", "is_dimension": True, "description": _("节点ID")},
            {"field": "task_type", "is_dimension": True, "description": _("任务类型")},
            {"field": "charset", "is_dimension": True, "description": _("编码类型")},
            {"field": "content_length", "is_dimension": False, "description": _("响应长度")},
            {"field": "media_type", "is_dimension": True, "description": _("媒体类型")},
            {"field": "message", "is_dimension": True, "description": _("响应消息")},
            {"field": "method", "is_dimension": True, "description": _("请求方法")},
            {"field": "response_code", "is_dimension": True, "description": _("响应状态码")},
            {"field": "steps", "is_dimension": False, "description": _("请求步骤数")},
            {"field": "url", "is_dimension": True, "description": _("请求网址")},
            {"field": "available", "is_dimension": False, "description": _("单点可用率")},
            {"field": "biz_id", "is_dimension": False, "description": "biz_id"},
            {"field": "timestamp", "is_dimension": False, "description": "timestamp"},
        ],
    },
    "tcp": {
        "description": "",
        "fields": [
            {"field": "bk_cloud_id", "is_dimension": True, "description": _("云区域ID")},
            {"field": "task_duration", "is_dimension": False, "description": _("耗时")},
            {"field": "error_code", "is_dimension": True, "description": _("错误码")},
            {"field": "status", "is_dimension": True, "description": _("任务状态")},
            {"field": "target_host", "is_dimension": True, "description": _("目标主机")},
            {"field": "target_port", "is_dimension": True, "description": _("目标端口")},
            {"field": "task_id", "is_dimension": True, "description": _("任务id")},
            {"field": "task_type", "is_dimension": True, "description": _("任务id")},
            {"field": "node_id", "is_dimension": True, "description": _("节点ID")},
            {"field": "available", "is_dimension": False, "description": _("单点可用率")},
            {"field": "biz_id", "is_dimension": False, "description": "biz_id"},
            {"field": "timestamp", "is_dimension": False, "description": "timestamp"},
        ],
    },
    "udp": {
        "description": "",
        "fields": [
            {"field": "bk_cloud_id", "is_dimension": True, "description": _("云区域ID")},
            {"field": "task_duration", "is_dimension": False, "description": _("耗时")},
            {"field": "error_code", "is_dimension": True, "description": _("错误码")},
            {"field": "status", "is_dimension": True, "description": _("任务状态")},
            {"field": "target_host", "is_dimension": True, "description": _("目标主机")},
            {"field": "target_port", "is_dimension": True, "description": _("目标端口")},
            {"field": "task_id", "is_dimension": True, "description": _("任务id")},
            {"field": "task_type", "is_dimension": True, "description": _("任务id")},
            {"field": "node_id", "is_dimension": True, "description": _("节点ID")},
            {"field": "times", "is_dimension": False, "description": _("重试次数")},
            {"field": "available", "is_dimension": False, "description": _("单点可用率")},
            {"field": "timestamp", "is_dimension": False, "description": "timestamp"},
            {"field": "biz_id", "is_dimension": False, "description": "biz_id"},
        ],
    },
    "icmp": {
        "description": "",
        "fields": [
            {"field": "bk_cloud_id", "is_dimension": True, "description": _("云区域ID")},
            {"field": "task_duration", "is_dimension": False, "description": _("耗时")},
            {"field": "error_code", "is_dimension": True, "description": _("错误码")},
            {"field": "target", "is_dimension": True, "description": _("目标主机")},
            {"field": "target_type", "is_dimension": True, "description": _("目标类型")},
            {"field": "task_id", "is_dimension": True, "description": _("任务id")},
            {"field": "available", "is_dimension": False, "description": _("单点可用率")},
            {"field": "timestamp", "is_dimension": False, "description": "timestamp"},
            {"field": "bk_biz_id", "is_dimension": False, "description": "bk_biz_id"},
            {"field": "node_id", "is_dimension": True, "description": _("节点ID")},
        ],
    },
}
# ICMP协议拨测补充节点id维度
NODE_ID_FIELD = {
    "table_id": "uptimecheck.icmp",
    "unit": "",
    "is_config_by_user": True,
    "creator": "system",
    "field_name": "node_id",
    "field_type": "string",
    "tag": "dimension",
    "description": _("节点ID"),
}

# 节点状态
BEAT_STATUS = {"RUNNING": "0", "DOWN": "-1", "NEED_UPGRADE": "2", "INVALID": "-2"}

# 首页拨测概览视图中展示的任务个数
FRONT_PAGE_TASK_NUMBER = 5

# 直连区域ID
DEFAULT_CLOUD_ID = 0
# 拨测周期最小值(与页面可选最小值保持一致，避免查询不到数据的情况)
TASK_MIN_PERIOD = 10
