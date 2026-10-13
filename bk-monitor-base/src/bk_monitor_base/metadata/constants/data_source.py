from typing import final


# 数据来源标签，例如：计算平台(bk_data)，监控采集器(bk_monitor_collector)
@final
class DataSourceLabel:
    BK_MONITOR_COLLECTOR = "bk_monitor"
    BK_DATA = "bk_data"
    CUSTOM = "custom"
    BK_LOG_SEARCH = "bk_log_search"
    BK_FTA = "bk_fta"
    BK_APM = "bk_apm"
    PROMETHEUS = "prometheus"
    DASHBOARD = "dashboard"


# 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
@final
class DataTypeLabel:
    TIME_SERIES = "time_series"
    EVENT = "event"
    LOG = "log"
    ALERT = "alert"
    TRACE = "trace"


# V3链路版本
DATA_LINK_V3_VERSION_NAME = "V3"
# V4链路版本
DATA_LINK_V4_VERSION_NAME = "V4"
