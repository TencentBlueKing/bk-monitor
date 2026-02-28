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

from monitor_web.k8s.scenario import Category, Metric

"""
k8s TKE GPU指标
"""


# 每个场景需要配置一个 get_metrics函数 以返回指标列表
def get_metrics() -> list:
    return [
        Category(
            id="GPU",
            name="GPU",
            children=[
                Metric(
                    id="container_gpu_utilization",
                    name=_lazy("容器实际使用的算力"),
                    unit="percent",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="container_gpu_memory_total",
                    name=_lazy("容器实际使用的显存"),
                    unit="mbytes",  # 原始数据为MB
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="container_core_utilization_percentage",
                    name=_lazy("容器实际使用的算力占申请算力的百分比"),
                    unit="percent",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="container_mem_utilization_percentage",
                    name=_lazy("容器实际使用的显存占申请显存的百分比"),
                    unit="percent",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="container_request_gpu_memory",
                    name=_lazy("容器申请的显存"),
                    unit="mbytes",  # 原始数据为MB
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="container_request_gpu_utilization",
                    name=_lazy("容器申请的算力"),
                    unit="percent",
                    unsupported_resource=[],
                    show_chart=True,
                ),
            ],
        ),
    ]
