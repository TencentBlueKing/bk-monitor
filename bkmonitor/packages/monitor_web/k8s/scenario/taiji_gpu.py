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
k8s 太极 GPU指标
"""


# 每个场景需要配置一个 get_metrics函数 以返回指标列表
def get_metrics() -> list:
    return [
        Category(
            id="GPU",
            name="GPU",
            children=[
                Metric(
                    id="bcs_taiji_gpu:k8s_container_bs_cpu_core_used",
                    name=_lazy("太极GPU容器CPU使用核心"),
                    unit="core",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_bs_resource_request_cpu",
                    name=_lazy("太极GPU容器CPU申请核心"),
                    unit="core",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_bs_mem_usage_bytes",
                    name=_lazy("太极GPU容器内存使用量"),
                    unit="bytes",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_bs_resource_request_mem",
                    name=_lazy("太极GPU容器内存申请量"),
                    unit="bytes",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_gpu_used",
                    name=_lazy("太极GPU容器使用算力（卡数）"),
                    unit="none",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_resource_request_gpu",
                    name=_lazy("太极GPU容器申请算力（卡数）"),
                    unit="none",
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_vgpu_gpu_mem_usage",
                    name=_lazy("太极GPU容器使用显存（GB）"),
                    unit="gbytes",  # 原始数据为GB
                    unsupported_resource=[],
                    show_chart=True,
                ),
                Metric(
                    id="bcs_taiji_gpu:k8s_container_vgpu_gpu_mem_total",
                    name=_lazy("太极GPU容器总显存（GB）"),
                    unit="gbytes",  # 原始数据为GB
                    unsupported_resource=[],
                    show_chart=True,
                ),
            ],
        ),
    ]
