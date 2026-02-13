"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _lazy


class LabelType:
    DataSourceLabel = "source_label"  # 数据源标签
    DataTypeLabel = "type_label "  # 数据类型标签
    ResultTableLabel = "result_table_label"  # 结果表分类标签


# 数据来源标签，例如：计算平台(bk_data)，监控采集器(bk_monitor_collector)
class DataSourceLabel:
    BK_MONITOR_COLLECTOR = "bk_monitor"
    BK_DATA = "bk_data"
    CUSTOM = "custom"
    BK_LOG_SEARCH = "bk_log_search"
    BK_FTA = "bk_fta"
    BK_APM = "bk_apm"
    PROMETHEUS = "prometheus"
    DASHBOARD = "dashboard"


DATA_SOURCE_LABEL_ALIAS = {
    DataSourceLabel.BK_MONITOR_COLLECTOR: _lazy("监控采集指标"),
    DataSourceLabel.BK_DATA: _lazy("计算平台指标"),
    DataSourceLabel.CUSTOM: _lazy("自定义指标"),
    DataSourceLabel.BK_LOG_SEARCH: _lazy("日志平台指标"),
    DataSourceLabel.BK_FTA: _lazy("关联告警"),
    DataSourceLabel.BK_APM: _lazy("Trace明细指标"),
    DataSourceLabel.PROMETHEUS: _lazy("Prometheus"),
    DataSourceLabel.DASHBOARD: _lazy("DASHBOARD"),
}


# 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
class DataTypeLabel:
    TIME_SERIES = "time_series"
    EVENT = "event"
    LOG = "log"
    ALERT = "alert"
    TRACE = "trace"


DATA_TYPE_LABEL_ALIAS = {
    DataTypeLabel.TIME_SERIES: _lazy("时序数据"),
    DataTypeLabel.EVENT: _lazy("事件数据"),
    DataTypeLabel.LOG: _lazy("日志数据"),
    DataTypeLabel.ALERT: _lazy("关联告警"),
    DataTypeLabel.TRACE: _lazy("Trace数据"),
}


DATA_SOURCE_LABEL_CHOICE = (
    (DataTypeLabel.TIME_SERIES, _lazy("时序数据")),
    (DataTypeLabel.EVENT, _lazy("事件")),
    (DataTypeLabel.LOG, _lazy("日志")),
)

# 数据分类
DATA_CATEGORY = [
    {
        "type": "bk_monitor_time_series",
        "name": _lazy("监控采集指标"),
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    },
    {
        "type": "prometheus_time_series",
        "name": "Prometheus",
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.PROMETHEUS,
    },
    {
        "type": "log_time_series",
        "name": _lazy("日志平台指标"),
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
    },
    {
        "type": "bk_monitor_event",
        "name": _lazy("系统事件"),
        "data_type_label": DataTypeLabel.EVENT,
        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    },
    {
        "type": "bk_data_time_series",
        "name": _lazy("计算平台指标"),
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.BK_DATA,
    },
    {
        "type": "custom_event",
        "name": _lazy("自定义事件"),
        "data_type_label": DataTypeLabel.EVENT,
        "data_source_label": DataSourceLabel.CUSTOM,
    },
    {
        "type": "custom_time_series",
        "name": _lazy("自定义指标"),
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.CUSTOM,
    },
    {
        "type": "bk_log_search_log",
        "name": _lazy("日志平台关键字"),
        "data_type_label": DataTypeLabel.LOG,
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
    },
    {
        "type": "bk_monitor_log",
        "name": _lazy("日志关键字事件"),
        "data_type_label": DataTypeLabel.LOG,
        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    },
    {
        "type": "bk_fta_event",
        "name": _lazy("第三方告警"),
        "data_type_label": DataTypeLabel.EVENT,
        "data_source_label": DataSourceLabel.BK_FTA,
    },
    {
        "type": "bk_fta_alert",
        "name": _lazy("关联告警"),
        "data_type_label": DataTypeLabel.ALERT,
        "data_source_label": DataSourceLabel.BK_FTA,
    },
    {
        "type": "bk_monitor_alert",
        "name": _lazy("关联策略"),
        "data_type_label": DataTypeLabel.ALERT,
        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    },
    {
        "type": "bk_apm_trace_timeseries",
        "name": _lazy("Trace明细指标"),
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_source_label": DataSourceLabel.BK_APM,
    },
    {
        "type": "bk_apm_trace",
        "name": "Trace",
        "data_type_label": DataTypeLabel.LOG,
        "data_source_label": DataSourceLabel.BK_APM,
    },
]


# 主机标签
class HostResultTableLabel:
    os = "os"
    host_process = "host_process"
    host_device = "host_device"


class KubernetesResultTableLabel:
    kubernetes = "kubernetes"


# 应用标签
class ApplicationsResultTableLabel:
    application_check = "application_check"
    uptimecheck = "uptimecheck"
    apm = "apm"


# 服务标签
class ServicesResultTableLabel:
    component = "component"
    service_module = "service_module"
    service_process = "service_process"


# 数据中心标签
class DataCenterResultTableLabel:
    hardware_device = "hardware_device"


# 其他标签
class OthersResultTableLabel:
    other_rt = "other_rt"


# 标签
class ResultTableLabelObj:
    HostObject = HostResultTableLabel
    KubernetesObject = KubernetesResultTableLabel
    ServicesObj = ServicesResultTableLabel
    ApplicationsObj = ApplicationsResultTableLabel
    OthersObj = OthersResultTableLabel
    DataCenterObj = DataCenterResultTableLabel


# 展示排序
LABEL_ORDER_LIST = [
    ResultTableLabelObj.HostObject.os,
    ResultTableLabelObj.HostObject.host_process,
    ResultTableLabelObj.HostObject.host_device,
    ResultTableLabelObj.ServicesObj.component,
    ResultTableLabelObj.ServicesObj.service_process,
    ResultTableLabelObj.ServicesObj.service_module,
    ResultTableLabelObj.ApplicationsObj.application_check,
    ResultTableLabelObj.ApplicationsObj.uptimecheck,
    ResultTableLabelObj.ApplicationsObj.apm,
    ResultTableLabelObj.DataCenterObj.hardware_device,
    ResultTableLabelObj.OthersObj.other_rt,
    ResultTableLabelObj.KubernetesObject.kubernetes,
]

METRIC_TYPE_CHOICES = (
    ("metric", "指标"),
    ("dimension", "维度"),
)


class MetricType:
    METRIC = "metric"
    DIMENSION = "dimension"


# 视图最大维度取值数
# 单图最大展示线条数
GRAPH_MAX_SLIMIT = 2000
# 查询最大时序（series）限制
TS_MAX_SLIMIT = 100

# 自定义事件恢复关键词
RECOVERY = "recovery"

# 统一查询模块支持的数据源类型
UnifyQueryDataSources = [
    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
    (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
    (DataSourceLabel.BK_APM, DataTypeLabel.EVENT),
]
# 灰度统一查询模块数据源
GrayUnifyQueryDataSources = [
    (DataSourceLabel.BK_APM, DataTypeLabel.LOG),
    (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
    (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
    (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
    (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG),
]

# V3链路版本
DATA_LINK_V3_VERSION_NAME = "V3"
# V4链路版本
DATA_LINK_V4_VERSION_NAME = "V4"
