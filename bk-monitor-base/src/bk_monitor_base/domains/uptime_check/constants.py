"""
拨测模块常量定义
"""

from enum import Enum
from typing import final

from django.utils.translation import gettext_lazy as _


@final
class CollectStatus:
    """采集状态常量"""

    SUCCESS = "SUCCESS"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    NODATA = "NODATA"


class UptimeCheckProtocol(str, Enum):
    """拨测协议类型"""

    HTTP = "HTTP"
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"


class CollectorInstallWay(int, Enum):
    """采集器安装方式"""

    BUILD_IN = 0  # 内置
    ZIP_FILE = 1  # ZIP文件
    EXE_FILE = 2  # 可执行文件


# 拨测任务最小周期(秒)
TASK_MIN_PERIOD = 10

# 默认最大超时时间(毫秒)
DEFAULT_MAX_TIMEOUT = 15000

# 默认输出字段
DEFAULT_UPTIMECHECK_OUTPUT_FIELDS = ["bk_host_innerip", "bk_host_innerip_v6"]

# 采集器名称
COLLECTOR_NAME = "uptimecheckbeat"

# 数据库名称
UPTIME_CHECK_DB = "uptimecheck"

# 数据标签
UPTIME_DATA_TYPE_LABEL = "time_series"

# 数据来源
UPTIME_DATA_SOURCE_LABEL = "bk_monitor"

# 节点状态
BEAT_STATUS = {"RUNNING": "0", "DOWN": "-1", "NEED_UPGRADE": "2", "INVALID": "-2"}

# 针对error_code进行监控的过滤模板
ERROR_CODE_TEMPLATE = '[[{"field": "error_code", "method": "eq", "value": "%s"}]]'

# 监控指标为响应内容时的过滤条件
UPTIME_CHECK_MONIT_RESPONSE = ERROR_CODE_TEMPLATE % 3002

# 监控指标为状态码时的过滤条件
UPTIME_CHECK_MONIT_RESPONSE_CODE = ERROR_CODE_TEMPLATE % 3003

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

# 可用率监控 默认阈值
UPTIME_CHECK_AVAILABLE_DEFAULT_VALUE = 100

# 拨测 概览页面 默认每个任务展示可用率曲线的时间范围(单位：小时)
UPTIME_CHECK_SUMMARY_TIME_RANGE = 1

# 拨测 任务详情页面 可用率曲线group_by minute1的时间范围(单位：小时)
UPTIME_CHECK_TASK_DETAIL_GROUP_BY_MINUTE1_TIME_RANGE = 12

# 拨测 任务详情页面 默认每个任务展示可用率曲线的时间范围(单位：小时)
UPTIME_CHECK_TASK_DETAIL_TIME_RANGE = 24

# 采集器状态码与错误信息对应关系
RESULT_MSG = {
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

UDP_RESULT_MSG = {
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
