"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property

from constants.apm import CachedEnum
from django.utils.translation import gettext_lazy as _


class GroupEnum(CachedEnum):
    TRPC = "trpc"
    RESOURCE = "resource"
    SPAN = "span"

    @cached_property
    def label(self) -> str:
        return self.value

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class CalculationType(CachedEnum):
    REQUEST_TOTAL = "request_total"
    ERROR_COUNT = "error_count"
    AVG_DURATION = "avg_duration"
    EXCEPTION_RATE = "exception_rate"
    TIMEOUT_RATE = "timeout_rate"
    SUCCESS_RATE = "success_rate"
    P50_DURATION = "p50_duration"
    P95_DURATION = "p95_duration"
    P99_DURATION = "p99_duration"
    PANIC = "panic"
    TOP_N = "top_n"
    BOTTOM_N = "bottom_n"

    # Resource
    # 内存使用率
    KUBE_MEMORY_USAGE = "kube_memory_usage"
    # CPU 使用率
    KUBE_CPU_USAGE = "kube_cpu_usage"
    # OOM 异常退出
    KUBE_OOM_KILLED = "kube_oom_killed"
    # 异常重启
    KUBE_ABNORMAL_RESTART = "kube_abnormal_restart"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        labels = {
            self.REQUEST_TOTAL: _("请求量"),
            self.SUCCESS_RATE: _("成功率"),
            self.TIMEOUT_RATE: _("超时率"),
            self.EXCEPTION_RATE: _("异常率"),
            self.AVG_DURATION: _("平均耗时"),
            self.P50_DURATION: _("P50 耗时"),
            self.P95_DURATION: _("P95 耗时"),
            self.P99_DURATION: _("P99 耗时"),
            self.ERROR_COUNT: _("错误数"),
        }
        return labels.get(self) or self.value
