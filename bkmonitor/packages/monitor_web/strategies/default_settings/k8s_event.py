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

DEFAULT_K8S_EVENT_NAME = [
    # 调度和资源问题
    "FailedScheduling",  # Pod无法调度到节点上，可能由于资源不足或调度限制。
    "NodeNotReady",  # 节点未准备好，可能由于节点故障或网络问题。
    "NodeOutOfDisk",  # 节点磁盘空间不足，可能导致Pod无法调度。
    "NodeMemoryPressure",  # 节点内存压力过大，可能导致Pod被驱逐或OOM。
    "NodeDiskPressure",  # 节点磁盘压力过大，可能影响Pod调度和性能。
    "NodeNetworkUnavailable",  # 节点网络不可用，可能导致网络连接中断。
    "PodStuck",  # Pod在Pending状态停留过长时间，通常与调度或资源问题有关。
    # 容器和镜像问题
    "FailedPull",  # 拉取容器镜像失败，可能是镜像不存在或网络问题。
    "BackOff",  # Pod因启动失败而进入退避重试状态，通常与应用程序启动问题有关。
    "CrashLoopBackOff",  # Pod持续崩溃并重启，通常与应用程序错误或配置问题有关。
    "ImagePullBackOff",  # 因镜像拉取失败，Pod进入退避重试状态。
    "OOMKilled",  # Pod因超出内存限制而被操作系统终止。
    "ContainerCannotRun",  # 容器无法启动，可能由于命令或配置错误。
    # 存储和挂载问题
    "FailedMount",  # 存储卷无法挂载到Pod上，可能由于权限或网络问题。
    "FailedAttachVolume",  # 存储卷无法附加到节点，通常是存储设备问题或配置错误。
    "PVCBoundFailure",  # PersistentVolumeClaim无法绑定到PersistentVolume，可能由于资源不足。
    # 其他问题
    "Unhealthy",  # Pod健康检查失败，可能指示应用程序未正常运行。
    "Evicted",  # Pod被驱逐，通常由于节点资源压力或策略限制。
    "DeadlineExceeded",  # Job超出设置的运行时间限制。
    "NetworkPolicyViolation",  # Pod违反网络策略，可能导致网络连接被阻止。
    "CertificateExpiration",  # 集群使用的证书即将过期，可能影响集群的安全性和连接性。
]
