"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from constants.apm import CachedEnum


class LabelMixin:
    """
    标签映射混入类，提供统一的标签获取逻辑

    子类需要定义 _LABEL_MAPPING 类变量，包含 {枚举值: 标签} 的映射
    """

    @cached_property
    def label(self):
        """
        获取枚举成员的标签值

        从子类的 _LABEL_MAPPING 或 _get_label_mapping 方法中获取标签
        """
        # 首先尝试获取 _LABEL_MAPPING 类变量
        label_mapping = getattr(self.__class__, "_LABEL_MAPPING", None)

        # 如果没有 _LABEL_MAPPING，尝试调用 _get_label_mapping 方法
        if label_mapping is None:
            get_mapping_method = getattr(self.__class__, "_get_label_mapping", None)
            if get_mapping_method is not None:
                label_mapping = get_mapping_method()

        if label_mapping is not None:
            return str(label_mapping.get(self, self.value))
        return str(self.value)


class EntityType(LabelMixin, CachedEnum):
    """
    事件类型
    """

    BcsPod = "BcsPod"
    APMService = "APMService"
    BkNodeHost = "BkNodeHost"
    UnKnown = "Unknown"

    @classmethod
    def _get_label_mapping(cls):
        return {
            cls.BcsPod: _("BCS Pod"),
            cls.APMService: _("APM服务"),
            cls.BkNodeHost: _("主机节点"),
            cls.UnKnown: _("未知"),
        }

    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value


class MetricType(CachedEnum):
    """
    索引类型
    """

    NODE = "node"
    EBPF_CALL = "ebpf_call"
    DEPENDENCY = "dependency"

    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]


class IndexType(CachedEnum):
    """
    索引类型
    """

    ENTITY = "entity"
    EDGE = "edge"


class MetricDimension(LabelMixin, CachedEnum):
    TOTAL = "total"
    ACTIVE = "active"
    PASSIVE = "passive"

    AVG = "avg"
    P99 = "p99"
    P95 = "p95"
    P50 = "p50"

    DEFAULT = "default"

    @classmethod
    def _get_label_mapping(cls):
        return {
            cls.TOTAL: str(_("总数")),
            cls.ACTIVE: str(_("主调")),
            cls.PASSIVE: str(_("被调")),
            cls.AVG: str(_("平均")),
            cls.P99: str(_("p99")),
            cls.P95: str(_("p95")),
            cls.P50: str(_("p50")),
            cls.DEFAULT: "default",
        }


# 度量单位常量
class MetricUnit:
    BYTES = "bytes"
    PERCENT_UNIT = "percentunit"
    BPS = "Bps"
    NANOSECONDS = "ns"


# 指标类型前缀
class MetricTypePrefix:
    APM = "apm"
    BCS = "bcs"
    HOST = "host"


# APM指标名
class APMMetricName:
    REQUEST_COUNT = "request_count"
    TOTAL_REQUEST_COUNT = "total_request_count"
    ACTIVE_REQUEST_COUNT = "active_request_count"
    PASSIVE_REQUEST_COUNT = "passive_request_count"

    ERROR_COUNT = "error_count"
    ERROR_RATE = "error_rate"

    DURATION = "duration"
    DURATION_AVG = "duration_avg"
    DURATION_P99 = "duration_p99"
    DURATION_P95 = "duration_p95"
    DURATION_P50 = "duration_p50"


# BCS指标名
class BCSMetricName:
    PERFORMANCE_CPU_USAGE = "performance_cpu_usage"
    PERFORMANCE_CPU_REQUEST_USAGE_RATE = "performance_cpu_request_usage_rate"
    PERFORMANCE_CPU_LIMIT_USAGE_RATE = "performance_cpu_limit_usage_rate"

    PERFORMANCE_MEMORY_USAGE = "performance_memory_usage"
    PERFORMANCE_MEMORY_REQUEST_USAGE_RATE = "performance_memory_request_usage_rate"
    PERFORMANCE_MEMORY_LIMIT_USAGE_RATE = "performance_memory_limit_usage_rate"

    TRAFFIC_IN = "traffic_in"
    TRAFFIC_OUT = "traffic_out"


# 主机指标名
class HostMetricName:
    CPU_USAGE_RATE = "cpu_usage_rate"
    CPU_FIVE_MINUTE_AVERAGE_LOAD = "cpu_five_minute_average_load"

    MEM_PHYSICAL_FREE = "mem_physical_free"

    NIC_IN_RATE = "nic_in_rate"
    NIC_OUT_RATE = "nic_out_rate"

    DISK_USAGE_RATE = "disk_usage_rate"


class MetricName(LabelMixin, CachedEnum):
    # APM指标
    APM_REQUEST_COUNT = f"{MetricTypePrefix.APM}.{APMMetricName.REQUEST_COUNT}"
    APM_TOTAL_REQUEST_COUNT = f"{MetricTypePrefix.APM}.{APMMetricName.TOTAL_REQUEST_COUNT}"
    APM_ACTIVE_REQUEST_COUNT = f"{MetricTypePrefix.APM}.{APMMetricName.ACTIVE_REQUEST_COUNT}"
    APM_PASSIVE_REQUEST_COUNT = f"{MetricTypePrefix.APM}.{APMMetricName.PASSIVE_REQUEST_COUNT}"

    APM_ERROR_COUNT = f"{MetricTypePrefix.APM}.{APMMetricName.ERROR_COUNT}"
    APM_ERROR_RATE = f"{MetricTypePrefix.APM}.{APMMetricName.ERROR_RATE}"

    APM_DURATION = f"{MetricTypePrefix.APM}.{APMMetricName.DURATION}"
    APM_DURATION_AVG = f"{MetricTypePrefix.APM}.{APMMetricName.DURATION_AVG}"
    APM_DURATION_P99 = f"{MetricTypePrefix.APM}.{APMMetricName.DURATION_P99}"
    APM_DURATION_P95 = f"{MetricTypePrefix.APM}.{APMMetricName.DURATION_P95}"
    APM_DURATION_P50 = f"{MetricTypePrefix.APM}.{APMMetricName.DURATION_P50}"

    # BCS指标
    BCS_PERFORMANCE_CPU_USAGE = f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_CPU_USAGE}"
    BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE = (
        f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_CPU_REQUEST_USAGE_RATE}"
    )
    BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE = f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_CPU_LIMIT_USAGE_RATE}"

    BCS_PERFORMANCE_MEMORY_USAGE = f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_MEMORY_USAGE}"
    BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE = (
        f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_MEMORY_REQUEST_USAGE_RATE}"
    )
    BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE = (
        f"{MetricTypePrefix.BCS}.{BCSMetricName.PERFORMANCE_MEMORY_LIMIT_USAGE_RATE}"
    )

    BCS_TRAFFIC_IN = f"{MetricTypePrefix.BCS}.{BCSMetricName.TRAFFIC_IN}"
    BCS_TRAFFIC_OUT = f"{MetricTypePrefix.BCS}.{BCSMetricName.TRAFFIC_OUT}"

    # 主机指标
    HOST_CPU_USAGE_RATE = f"{MetricTypePrefix.HOST}.{HostMetricName.CPU_USAGE_RATE}"
    HOST_CPU_FIVE_MINUTE_AVERAGE_LOAD = f"{MetricTypePrefix.HOST}.{HostMetricName.CPU_FIVE_MINUTE_AVERAGE_LOAD}"

    HOST_MEM_PHYSICAL_FREE = f"{MetricTypePrefix.HOST}.{HostMetricName.MEM_PHYSICAL_FREE}"

    HOST_NIC_IN_RATE = f"{MetricTypePrefix.HOST}.{HostMetricName.NIC_IN_RATE}"
    HOST_NIC_OUT_RATE = f"{MetricTypePrefix.HOST}.{HostMetricName.NIC_OUT_RATE}"

    HOST_DISK_USAGE_RATE = f"{MetricTypePrefix.HOST}.{HostMetricName.DISK_USAGE_RATE}"

    @classmethod
    def _get_label_mapping(cls):
        return {
            cls.APM_REQUEST_COUNT: _("请求数"),
            cls.APM_TOTAL_REQUEST_COUNT: _("请求总数"),
            cls.APM_ACTIVE_REQUEST_COUNT: _("主调请求数"),
            cls.APM_PASSIVE_REQUEST_COUNT: _("被调请求数"),
            cls.APM_ERROR_COUNT: _("错误请求数"),
            cls.APM_ERROR_RATE: _("错误率"),
            cls.APM_DURATION: _("耗时"),
            cls.APM_DURATION_AVG: _("平均耗时"),
            cls.APM_DURATION_P99: _("99% 耗时"),
            cls.APM_DURATION_P95: _("95% 耗时"),
            cls.APM_DURATION_P50: _("50% 耗时"),
            cls.BCS_PERFORMANCE_CPU_USAGE: _("CPU使用量"),
            cls.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE: _("CPU request使用率"),
            cls.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE: _("CPU limit使用率"),
            cls.BCS_PERFORMANCE_MEMORY_USAGE: _("内存使用量"),
            cls.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE: _("内存 request使用率"),
            cls.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE: _("内存 limit使用率"),
            cls.BCS_TRAFFIC_IN: _("网络入带宽"),
            cls.BCS_TRAFFIC_OUT: _("网络出带宽"),
            cls.HOST_CPU_USAGE_RATE: _("CPU使用率"),
            cls.HOST_CPU_FIVE_MINUTE_AVERAGE_LOAD: _("CPU五分钟平均负载"),
            cls.HOST_MEM_PHYSICAL_FREE: _("物理内存空闲量"),
            cls.HOST_NIC_IN_RATE: _("网卡入流量比特速率"),
            cls.HOST_NIC_OUT_RATE: _("网卡出流量比特速率"),
            cls.HOST_DISK_USAGE_RATE: _("磁盘空间使用率"),
        }
