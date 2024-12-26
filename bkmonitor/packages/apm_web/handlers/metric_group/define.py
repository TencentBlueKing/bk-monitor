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

from django.utils.translation import gettext_lazy as _


class GroupEnum:
    TRPC: str = "trpc"
    RESOURCE: str = "resource"

    @classmethod
    def choices(cls):
        return [(cls.TRPC, cls.TRPC), (cls.RESOURCE, cls.RESOURCE)]


class CalculationType:
    REQUEST_TOTAL = "request_total"
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
    def choices(cls):
        return [
            (cls.REQUEST_TOTAL, _("请求量")),
            (cls.SUCCESS_RATE, _("成功率")),
            (cls.TIMEOUT_RATE, _("超时率")),
            (cls.EXCEPTION_RATE, _("异常率")),
            (cls.AVG_DURATION, _("平均耗时")),
            (cls.P50_DURATION, _("P50 耗时")),
            (cls.P95_DURATION, _("P95 耗时")),
            (cls.P99_DURATION, _("P99 耗时")),
        ]
