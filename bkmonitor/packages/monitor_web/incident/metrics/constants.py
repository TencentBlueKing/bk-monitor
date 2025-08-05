"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from constants.apm import CachedEnum

class EntityType(CachedEnum):
    """
    事件类型
    """

    BcsPod = "BcsPod"
    APMService = "APMService"
    BkNodeHost = "BkNodeHost"
    UnKnown = "Unknown"
    
    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]

    @cached_property
    def label(self):
        return str(
            {
                EntityType.BcsPod: _("BCS Pod"),
                EntityType.APMService: _("APM服务"),
                EntityType.BkNodeHost: _("主机节点"),
                EntityType.UnKnown: _("未知"),
            }.get(self, self.value)
        )

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

    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]

class IndexType(CachedEnum):
    """
    索引类型
    """

    ENTITY = "entity"
    EDGE = "edge"

class MetricName(CachedEnum):
    # APM指标
    APM_TOTAL_REQUEST_COUNT = "apm.total_request_count"
    APM_ACTIVE_REQUEST_COUNT = "apm.active_request_count"
    APM_PASSIVE_REQUEST_COUNT = "apm.passive_request_count"
    APM_ERROR_COUNT = "apm.error_count"
    APM_ERROR_RATE = "apm.error_rate"
    APM_DURATION_AVG = "apm.duration_avg"
    APM_DURATION_P99 = "apm.duration_p99"
    APM_DURATION_P95 = "apm.duration_p95"
    APM_DURATION_P50 = "apm.duration_p50"
    
    # BCS指标
    BCS_PERFORMANCE_CPU_USAGE = "bcs.performance_cpu_usage"
    BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE = "bcs.performance_cpu_request_usage_rate"
    BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE = "bcs.performance_cpu_limit_usage_rate"
    
    BCS_PERFORMANCE_MEMORY_USAGE = "bcs.performance_memory_usage"
    BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE = "bcs.performance_memory_request_usage_rate"
    BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE = "bcs.performance_memory_limit_usage_rate"
    
    BCS_TRAFFIC_IN = "bcs.traffic_in"
    BCS_TRAFFIC_OUT = "bcs.traffic_out"
    
    # 主机指标
    HOST_CPU_USAGE_RATE = "host.cpu_usage_rate"
    HOST_CPU_FIVE_MINUTE_AVERAGE_LOAD = "host.cpu_five_minute_average_load"
    
    HOST_MEM_PHYSICAL_FREE = "host.mem_physical_free"
    
    HOST_NIC_IN_RATE = "host.nic_in_rate"
    HOST_NIC_OUT_RATE = "host.nic_out_rate"
    
    HOST_DISK_USAGE_RATE = "host.disk_usage_rate"
    
    @cached_property
    def label(self):
        return str(
            {
                MetricName.APM_TOTAL_REQUEST_COUNT: "请求总数",
                MetricName.APM_ACTIVE_REQUEST_COUNT: "主调请求数",
                MetricName.APM_PASSIVE_REQUEST_COUNT: "被调请求数",
                MetricName.APM_ERROR_COUNT: "错误请求数",
                MetricName.APM_ERROR_RATE: "错误率",
                MetricName.APM_DURATION_AVG: "平均耗时",
                MetricName.APM_DURATION_P99: "99% 耗时",
                MetricName.APM_DURATION_P95: "95% 耗时",
                MetricName.APM_DURATION_P50: "50% 耗时",
                
                MetricName.BCS_PERFORMANCE_CPU_USAGE: "CPU使用量",
                MetricName.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE: "CPU request使用率",
                MetricName.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE: "CPU limit使用率",
                
                MetricName.BCS_PERFORMANCE_MEMORY_USAGE: "内存使用量",
                MetricName.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE: "内存 request使用率",
                MetricName.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE: "内存 limit使用率",
                
                MetricName.BCS_TRAFFIC_IN: "网络入带宽",
                MetricName.BCS_TRAFFIC_OUT: "网络出带宽",
                
                MetricName.HOST_CPU_USAGE_RATE: "CPU使用率",
                MetricName.HOST_CPU_FIVE_MINUTE_AVERAGE_LOAD: "CPU五分钟平均负载",
                
                MetricName.HOST_MEM_PHYSICAL_FREE: "物理内存空闲量",
                
                MetricName.HOST_NIC_IN_RATE: "网卡入流量比特速率",
                MetricName.HOST_NIC_OUT_RATE: "网卡出流量比特速率",
                
                MetricName.HOST_DISK_USAGE_RATE: "磁盘空间使用率",
            }.get(self, self.value)
        )