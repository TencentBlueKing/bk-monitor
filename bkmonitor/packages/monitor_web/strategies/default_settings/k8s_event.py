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

UNCONFIRMED_K8S_EVENTS = [
    "NodeOutOfDisk",  # 节点磁盘空间不足，可能导致Pod无法调度。
    "NodeMemoryPressure",  # 节点内存压力过大，可能导致Pod被驱逐或OOM。
    "NodeDiskPressure",  # 节点磁盘压力过大，可能影响Pod调度和性能。
    "PodStuck",  # Pod在Pending状态停留过长时间，通常与调度或资源问题有关。
    "FailedPull",  # 拉取容器镜像失败，可能是镜像不存在或网络问题。
    "ImagePullBackOff",  # 因镜像拉取失败，Pod进入退避重试状态。
    "ContainerCannotRun",  # 容器无法启动，可能由于命令或配置错误。
    "PVCBoundFailure",  # PersistentVolumeClaim无法绑定到PersistentVolume，可能由于资源不足。
    "DeadlineExceeded",  # Job超出设置的运行时间限制。
    "NetworkPolicyViolation",  # Pod违反网络策略，可能导致网络连接被阻止。
    "CertificateExpiration",  # 集群使用的证书即将过期，可能影响集群的安全性和连接性。
]

DEFAULT_K8S_EVENT_NAME = [
    # Node Events
    "SystemOOM",  # 节点上的系统内存不足，导致系统必须杀死一些进程以释放内存。
    "Rebooted",  # 节点已经重启。
    "KubeletSetupFailed",  # 设置或启动程序失败。
    "EvictionThresholdMet",  # 节点上的资源压力已经达到了驱逐（Eviction）的阈值，Kubernetes 可能会开始驱逐节点上的 Pod 来释放资源。
    "InvalidDiskCapacity",  # 磁盘容量无效或不足，或者 Kubernetes 无法正确检测到磁盘的容量。
    "FreeDiskSpaceFailed",  # 尝试对镜像进行垃圾回收失败。
    "readOnlySysFS",  # 系统被设置为只读，可能会影响 Kubernetes 的运行。
    "ContainerGCFailed",  # 容器的垃圾回收失败，可能由于无法列出容器、无法列出 pod 沙箱、无法读取 podLogsRootDirectory。
    "ImageGCFailed",  # 镜像的垃圾回收失败。
    "MissingClusterDNS",  # 缺少集群的 ClusterDNS IP设置，无法创建pod。
    "FailedToCreateRoute",  # 创建网络路由失败。
    "FailedToStartProxierHealthcheck",  # 启动网络代理的健康检查失败。
    "HostNetworkNotSupported",  # 主机网络不受支持。
    "HostPortConflict",  # 主机/端口冲突。
    "NilShaper",  # 未定义控制网络带宽使用的整形器对象为空，可能会影响到网络的流量控制。
    "NodeNetworkUnavailable",  # 节点的网络不可用。
    "VolumeAttachmentStuck",  # Volume尝试Attach到节点时失败，节点需要重新启动才能修复受损状态。
    "CheckLimitsForResolvConf",  # 检查 resolv.conf 文件的limits失败。
    "OwnerRefInvalidNamespace",  # 命名空间中不存在ownerRef。
    "FailedNodeAllocatableEnforcement",  # 未能强制实施系统保留的 Cgroup 限制。
    "KernelDeadlock",  # 节点上的内核发生了死锁。
    "DockerHung",  # 节点上的 Docker 服务无响应。
    "CorruptDockerOverlay2",  # 节点上的 Docker overlay2 存储驱动出现了问题。
    "NodeUnderDiskPressure",  # 节点正在经历磁盘压力。
    "NodeUnderMemoryPressure",  # 节点正在经历内存压力。
    "NodeUnderPIDPressure",  # 节点正在经历 PID 压力。
    "NodeNotReady",  # 节点无法接受 Pod。
    "NodeNotSchedulable",  # 节点无法被调度。
    "NodeHasInsufficientPID",  # 节点 PID 资源不足
    "NodeHasInsufficientMemory",  # 节点内存资源不足。
    "NodeHasInsufficientDisk",  # 节点磁盘资源不足。
    # Pod Event
    "FailedKillPod",  # 尝试终止kill Pod 时失败，可能是由于权限问题、系统错误等。
    # Exec/HTTP 生命周期钩子失败。在 K8s中，PostStart 钩子是在容器创建后立即执行的操作。如果这个钩子执行失败，那么 Pod 将无法正常运行
    "FailedPostStartHook",
    "FailedPreStopHook",  # 执行容器的 PreStop 钩子失败，可能是钩子脚本的问题。
    "Failed",  # Pod 中的一个或多个容器失败，可能原因：无法创建/启动容器，内部PreCreateContainer 钩子失败。
    "FailedCreatePodContainer",  # 创建容器失败。
    "Preempting",  # Pod 被抢占，通常是因为调度器需要释放资源给优先级更高的 Pod。
    "CrashLoopBackOff",  # 容器反复崩溃并重启，可能是应用程序的问题或者其他问题。
    "ExceededGracePeriod",  # 容器运行时没在指定的时间内杀掉pod。
    "InspectFailed",  # 检查镜像失败。
    "ErrImageNeverPull",  # 容器镜像不存在，且拉取策略为Never。
    "InvalidEnvironmentVariableNames",  # 环境变量的名字无效。
    "FailedValidation",  # 由于Pod名称重复导致校验失败。
    "UnexpectedAdmissionError",  # 相关的命名空间下的配额设置不正确，Pod无法创建。
    "OOMKilled",  # 容器因为内存溢出被kill。
    "NetworkNotReady",  # 网络问题：可能由于网络插件或者网络配置问题。
    "NetworkFailed",  # pod 的网络接口已经丢失，pod 也将被停止。
    "FailedScheduling",  # 没有可用于调度 Pod 的节点。
    "Evicted",  # pod被驱逐。
    "TopologyAffinityError",  # 节点缺少足够的资源来满足 Pod 请求/Pod 的请求因为特定的拓扑管理器策略限制而被拒绝。
    "FailedCreatePodSandBox",  # 创建 Pod 的沙箱环境失败，可能是网络插件或者运行时环境的问题。
    "FailedPodSandBoxStatus",  # 获取 Pod 沙箱的状态失败。
    "FailedMount",  # 挂载存储卷失败，可能是由于节点亲和性、设备挂负载路径问题。
    "AlreadyMountedVolume",  # 存储卷已经被挂载，可能无法共享。
    "FailedAttachVolume",  # attach存储卷失败，可能由于已经被attached到一个节点/不同的namespace。
    "FailedMapVolume",  # 映射存储卷失败。
    "VolumeResizeFailed",  # 调整存储卷大小（扩展/缩减）失败。
    "FailedBinding",  # 没有可用的持久性卷，而且未设置存储类。
    "VolumeConditionAbnormal",  # 存储卷的状态异常。
    "FileSystemResizeFailed",  # 调整文件系统大小失败。
    "Unhealthy",  # 容器不健康。
    "ProbeWarning",  # 健康检查警告，可能是容器的状态有问题。
    "SysctlForbidden",  # 使用了禁止的系统调用，可能是 Pod 的安全策略问题。
    "AppArmor",  # 无法强制执行 AppArmor，AppArmor用于限制容器对资源的访问。
    "NoNewPrivs",  # 无法强制执行 NoNewPrivs。
    "ProcMount",  # 无法强制执行 ProcMount，ProcMount用于更改容器中 /proc 文件系统的挂载方式。
    "InvalidNodeInfo",  # 节点的信息无效。
    "TaintManagerEviction",  # Pod 被 Taint Manager 驱逐。
    "BackOff",  # 拉取镜像失败进入持续重启状态/通过指定的镜像启动容器后，容器内部没有常驻进程，导致容器启动成功后即退出，从而进行了持续的重启
    # Deployment Events
    "FailedRollover",  # Deployment 控制器在尝试执行滚动更新时失败
    # ReplicaSet Events
    # Kubernetes 在尝试创建一个新的 Pod（以满足 ReplicaSet 的副本数要求）时失败了。可能由于：资源限制、镜像拉取失败、配置错误等
    "FailedCreate",
    # Kubernetes 在尝试删除一个现有的 Pod（通常是因为 ReplicaSet 的副本数要求发生了变化）时失败了。可能由于：权限问题、系统错误等。
    "FailedDelete",
    # 其他事件
    "BackoffLimitExceeded",  # Job 控制器创建的 Pod 失败了多次，且次数超过了 backoffLimit 的值，Kubernetes 将停止重试启动新的 Pod。
    # Kubernetes 无法为 Service 创建 Endpoint，可能是由于关联的 Pod 没有正确运行，或者 Service 的选择器标签不匹配任何 Pod。
    "FailedToCreateEndpoint",
    # Kubernetes 无法更新 Service 的 Endpoint 信息，可能是因为网络或 API 服务器的问题，或者是资源版本冲突导致的。
    "FailedToUpdateEndpoint",
    "InvalidEntry",  # 常常与配置错误相关，可能是在 ConfigMap 或 Secret 中有无效的条目，或者在资源定义中有错误的字段。
    # 通常表明控制器（例如，ReplicaSet、Deployment）无法与集群状态同步。可能是由于网络问题、API 服务器故障或者权限问题导致的。
    "FailedSync",
    # 通常是指在确保某种资源状态（如卷、网络配置等）时失败。可能的原因是权限不足、资源不足或配置错误。
    "ensure fail",
    # 处理 Ingress 资源失败。可能的原因是 Ingress 配置错误、关联的 Service 或 Backend 不存在、网络插件问题等。
    "process ingress failed",
]
