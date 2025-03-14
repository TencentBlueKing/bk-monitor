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
import sys
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Dict

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from constants.apm import CachedEnum


class EventDomain(CachedEnum):
    """事件领域
    一个领域的事件具有多个源。
    例如 CICD 可能来源于 BKCI、ARGO、GITHUB_ACTIONS
    """

    K8S: str = "K8S"
    CICD: str = "CICD"
    SYSTEM: str = "SYSTEM"

    @cached_property
    def label(self):
        return str({self.K8S: _("Kubernetes"), self.CICD: _("CICD"), self.SYSTEM: _("系统")}.get(self, self.value))

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default

    @classmethod
    def choices(cls):
        return [(cls.K8S.value, cls.K8S.value), (cls.CICD.value, cls.CICD.value), (cls.SYSTEM.value, cls.SYSTEM.value)]


class EventSource(CachedEnum):
    """事件来源，需要保持唯一"""

    # CICD
    BKCI: str = "BKCI"
    # K8S
    BCS: str = "BCS"
    # HOST
    HOST: str = "HOST"

    @classmethod
    def choices(cls):
        return [(cls.BCS.value, cls.BCS.value), (cls.BKCI.value, cls.BKCI.value), (cls.HOST.value, cls.HOST.value)]

    @cached_property
    def label(self):
        return str({self.BKCI: _("蓝盾"), self.BCS: _("BCS"), self.HOST: _("主机")}.get(self, self.value))

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


class EventType(Enum):
    """
    事件类型
    """

    Normal = "Normal"
    Warning = "Warning"
    Default = "Default"


class EventCategory(Enum):
    """
    事件类别枚举
    """

    COMMON = "common"
    SYSTEM_EVENT = "system_event"
    K8S_EVENT = "k8s_event"
    CICD_EVENT = "cicd_event"
    UNKNOWN_EVENT = ""


class CategoryWeight(IntEnum):
    """
    事件类别权重枚举
    """

    COMMON = 0
    SYSTEM_EVENT = 1
    K8S_EVENT = 2
    CICD_EVENT = 3
    UNKNOWN = sys.maxsize


# 事件类别和权重映射
CATEGORY_WEIGHTS = {
    EventCategory.COMMON.value: CategoryWeight.COMMON.value,
    EventCategory.SYSTEM_EVENT.value: CategoryWeight.SYSTEM_EVENT.value,
    EventCategory.K8S_EVENT.value: CategoryWeight.K8S_EVENT.value,
    EventCategory.CICD_EVENT.value: CategoryWeight.CICD_EVENT.value,
}


@dataclass
class EventOrigin:
    domain: str
    source: str


EventLabelOriginMapping: Dict[str, EventOrigin] = {
    EventCategory.SYSTEM_EVENT.value: EventOrigin(
        domain=EventDomain.SYSTEM.value,
        source=EventSource.HOST.value,
    ),
    EventCategory.K8S_EVENT.value: EventOrigin(
        domain=EventDomain.K8S.value,
        source=EventSource.BCS.value,
    ),
    EventCategory.CICD_EVENT.value: EventOrigin(
        domain=EventDomain.CICD.value,
        source=EventSource.BKCI.value,
    ),
}


class DisplayFieldType(Enum):
    ATTACH: str = "attach"
    LINK: str = "link"
    DESCRIPTIONS: str = "descriptions"
    ICON: str = "icon"


class EventOriginDefaultValue(Enum):
    """
    事件类型
    """

    DEFAULT_DOMAIN = "DEFAULT"
    DEFAULT_SOURCE = "DEFAULT"


class EventDimensionTypeEnum(Enum):
    """
    事件维度类型枚举
    """

    KEYWORD: str = "keyword"
    TEXT: str = "text"
    INTEGER: str = "integer"
    DATE: str = "date"


# 事件字段别名
EVENT_FIELD_ALIAS: Dict[str, Dict[str, str]] = {
    EventCategory.COMMON.value: {
        "time": _("数据上报时间"),
        "event_name": _("事件名"),
        "domain": _("事件域"),
        "source": _("事件来源"),
        "type": _("事件类型"),
        "event.count": _("事件数"),
        "event.content": _("事件内容"),
        "target": _("目标"),
        "bk_biz_id": _("业务 ID"),
        "bk_cloud_id": _("管控区域"),
        "bk_target_cloud_id": _("管控区域"),
        "bk_target_ip": _("IP"),
        "ip": _("IP"),
        "host": _("IP"),
        "bk_agent_id": _("AgentID"),
    },
    EventCategory.SYSTEM_EVENT.value: {
        "disk": _("磁盘"),
        "file_system": _("文件系统"),
        "fstype": _("文件系统类型"),
        "process": _("进程"),
        # 被 OOM Killer 终止的 进程所属的 Cgroup，可能与 oom_memcg 不同（尤其在嵌套 Cgroup 结构中）。
        # 若进程属于子 Cgroup，父 Cgroup 触发了 OOM，则 task_memcg 指向子 Cgroup 的路径。
        "task_memcg": _("被终止内存组"),
        # 触发 OOM 的 内存控制组（Memory Cgroup），即因内存使用超限而引发 OOM 的 Cgroup 层级。
        "oom_memcg": _("触发 OOM 内存组"),
    },
    EventCategory.K8S_EVENT.value: {
        "bcs_cluster_id": _("集群 ID"),
        "namespace": _("命名空间"),
        "kind": _("资源类型"),
        "apiVersion": _("API 版本"),
        "name": _("资源名称"),
        "uid": _("资源标识"),
        "dimensions.bcs_cluster_id": _("集群"),
        "dimensions.namespace": _("命名空间"),
        "dimensions.name": _("工作负载"),
    },
    EventCategory.CICD_EVENT.value: {
        "projectId": _("项目 ID"),
        "pipelineId": _("流水线 ID"),
        "pipelineName": _("流水线名称"),
        "buildId": _("构建 ID"),
        "trigger": _("触发类型"),
        "triggerUser": _("触发用户"),
        "status": _("任务状态"),
        "duration": _("耗时"),
        "start_time": _("启动时间"),
    },
}

DISPLAY_FIELDS = [
    {"name": "time", "alias": _("数据上报时间")},
    {"name": "type", "alias": _("事件类型"), "type": DisplayFieldType.ATTACH.value},
    {"name": "event_name", "alias": _("事件名")},
    {"name": "event.content", "alias": _("内容"), "type": DisplayFieldType.DESCRIPTIONS.value},
    {"name": "target", "alias": _("目标"), "type": DisplayFieldType.LINK.value},
]

# 内置字段类型映射集
INNER_FIELD_TYPE_MAPPINGS = {
    "time": EventDimensionTypeEnum.DATE.value,
    "event_name": EventDimensionTypeEnum.KEYWORD.value,
    "event.content": EventDimensionTypeEnum.TEXT.value,
    "event.count": EventDimensionTypeEnum.INTEGER.value,
    "target": EventDimensionTypeEnum.KEYWORD.value,
}


# 查询操作符
class Operation:
    EQ = {"alias": "=", "value": "eq"}
    NE = {"alias": "!=", "value": "ne"}
    INCLUDE = {"alias": _("包含"), "value": "include"}
    EXCLUDE = {"alias": _("不包含"), "value": "exclude"}
    EQ_WITH_WILDCARD = {"alias": _("包含"), "value": "include", "options": {"label": _("使用通配符"), "name": "is_wildcard"}}
    NE_WITH_WILDCARD = {"alias": _("不包含"), "value": "exclude", "options": {"label": _("使用通配符"), "name": "is_wildcard"}}


# 类型和操作符映射
TYPE_OPERATION_MAPPINGS = {
    "date": [Operation.EQ, Operation.NE],
    "keyword": [Operation.EQ, Operation.NE, Operation.INCLUDE, Operation.EXCLUDE],
    "text": [Operation.EQ_WITH_WILDCARD, Operation.NE_WITH_WILDCARD],
    "integer": [Operation.EQ, Operation.NE],
}

ENTITIES = [
    # 规则越靠前解析优先级越高。
    # 跳转到容器监控（仅当存在 bcs_cluster_id），默认跳转到新版。
    # 注意：bcs_cluster_id 存在的情况下，host 形式是 "node-127-0-0-1"，此时跳转到旧版容器监控页面的 Node
    {
        "type": "k8s",
        "alias": _("容器"),
        "fields": ["container_id", "namespace", "bcs_cluster_id", "host"],
        # 原始数据存在这个字段，本规则才生效
        "dependent_fields": ["bcs_cluster_id"],
    },
    # 跳转到主机监控
    {"type": "ip", "alias": _("主机"), "fields": ["host", "bk_target_ip", "ip", "serverip", "bk_host_id"]},
]

DEFAULT_DIMENSION_FIELDS = ["time", "event_name", "event.count", "event.content", "target", "type"]

DETAIL_MOCK_DATA = {
    "bcs_cluster_id": {
        "label": "集群",
        "value": "BCS-K8S-90001",
        "alias": "[共享集群] 蓝鲸公共-广州(BCS-K8S-90001)",
        "type": "link",
        "scenario": "容器监控",
        # 带集群 ID 跳转到新版容器监控页面
        "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001",
    },
    "namespace": {
        "label": "NameSpace",
        "value": "127.0.0.1",
        "alias": "kube-system",
        # 带 namespace & 集群 ID 跳转到新版容器监控页面
        "type": "link",
        "scenario": "容器监控",
        "url": "https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",
    },
    "name": {
        "label": "工作负载",
        "value": "bk-log-collector-fx97q",
        "alias": "Pod / bk-log-collector-fx97q",
    },
    "event.content": {
        "label": "事件内容",
        "value": "MountVolume.SetUp failed for volume bk-log-main-config: "
        "failed to sync configmap cache: timed out waiting for the condition",
        "alias": "MountVolume.SetUp failed for volume bk-log-main-config: "
        "failed to sync configmap cache: timed out waiting for the condition",
    },
}

URL_MOCK_DATA = ("https://bk.monitor.com/k8s-new/?=bcs_cluster_id=BCS-K8S-90001&namespace=xxx",)

DIMENSION_DISTINCT_VALUE = 0

BK_BIZ_ID_DEFAULT_TABLE_ID = "gse_system_event"

BK_BIZ_ID_DEFAULT_DATA_LABEL = "system_event"

QUERY_MAX_LIMIT = 10000

BK_BIZ_ID = "bk_biz_id"

K8S_EVENT_TRANSLATIONS = {
    "Pod": {
        "FailedKillPod": _("停止 Pod 失败"),
        "FailedPostStartHook": _("处理程序因为 Pod 启动而失败"),
        "FailedPreStopHook": _("处理程序因为预停止而失败"),
        "Failed": _("拉取/创建/启动失败"),
        "FailedCreatePodContainer": _("创建容器失败"),
        "Preempting": _("正在抢占其他 Pod"),
        "Preempted": _("被其他 Pod 抢占"),
        "ExceededGracePeriod": _("指定期限内未能停止 Pod"),
        "InspectFailed": _("检查镜像失败"),
        "ErrImageNeverPull": _("设置 Never 拉取策略但找不到本地镜像"),
        "InvalidEnvironmentVariableNames": _("环境变量的名字无效"),
        "FailedValidation": _("Pod 配置验证失败"),
        "UnexpectedAdmissionError": _("Pod 无法被创建"),
        "OOMKilled": _("容器因为内存溢出被 Kill"),
        "NetworkNotReady": _("网络未就绪（）"),
        "NetworkFailed": _("Pod 因网络接口丢失而将被停止"),
        "FailedScheduling": _("未能调度 Pod"),
        "Evicted": _("Pod 被驱逐"),
        "TopologyAffinityError": _("没有能满足 Pod 亲和性的节点"),
        "FailedCreatePodSandBox": _("创建 Pod 沙箱失败"),
        "FailedPodSandBoxStatus": _("获取 Pod 沙箱的状态失败"),
        "FailedMount": _("卷挂载已失效"),
        "AlreadyMountedVolume": _("卷已经被挂载"),
        "FailedAttachVolume": _("附加卷失败"),
        "FailedMapVolume": _("映射存储卷失败"),
        "VolumeResizeFailed": _("扩展/缩减卷失败"),
        "FailedBinding": _("没有可用持久性卷。"),
        "VolumeConditionAbnormal": _("存储卷的状态异常"),
        "FileSystemResizeFailed": _("扩展/缩减文件系统失败"),
        "Unhealthy": _("容器不健康"),
        "ProbeWarning": _("健康检查警告"),
        "SysctlForbidden": _("使用禁止的系统调用"),
        "AppArmor": _("无法强制执行 AppArmor"),
        "NoNewPrivs": _("无法强制执行 NoNewPrivs"),
        "ProcMount": _("无法强制执行 ProcMount"),
        "InvalidNodeInfo": _("节点的信息无效"),
        "BackOff": _("退避容器启动、镜像拉取"),
        "TaintManagerEviction": _("污点驱逐管理"),
        "Killing": _("正在终止容器"),
        "Pulling": _("正在拉取镜像"),
        "Pulled": _("成功拉取镜像"),
        "Created": _("已创建容器"),
        "Started": _("容器已启动"),
        "Scheduled": _("Pod 已成功分配给节点"),
    },
    "Job": {
        "BackoffLimitExceeded": _("多次尝试启动后已达到退避机制"),
        "SuccessfulCreate": _("已创建 Pod"),
        "SuccessfulDelete": _("已删除 Pod"),
        "Completed": _("任务已完成"),
    },
    "CronJob": {
        "BackoffLimitExceeded": _("多次尝试启动后已达到退避机制"),
        "SuccessfulCreate": _("已创建 Pod"),
        "SuccessfulDelete": _("已删除 Pod"),
        "SawCompletedJob": _("任务已完成"),
    },
    "Deployment": {
        "FailedRollover": _("滚动更新失败"),
        "ScalingReplicaSet": _("正在调整副本数"),
        "ScaledReplicaSet": _("已完成副本数调整"),
        "SuccessfulRollover": _("滚动更新成功"),
    },
    "ReplicaSet": {
        "FailedCreate": _("创建 Pod 失败"),
        "FailedDelete": _("销毁 Pod 失败"),
        "SuccessfulCreate": _("创建 Pod 成功"),
        "SuccessfulDelete": _("销毁 Pod 成功"),
    },
    "HorizontalPodAutoscaler": {
        "FailedGetResourceMetric": _("无法获取指标"),
        "FailedComputeMetricsReplicas": _("未能根据指标计算出所需的副本数"),
        "SelectorRequired": _("需要选择器"),
        "InvalidSelector": _("转为内部选择器对象失败"),
        "FailedGetObjectMetric": _("HPA 无法计算副本数"),
        "InvalidMetricSourceType": _("未知的指标源类型"),
        "FailedConvertHPA": _("未能转换给定的 HPA"),
        "FailedGetScale": _("无法获取目标的当前规模"),
        "FailedUpdateStatus": _("未能更新状态"),
        "SuccessfulRescale": _("调整副本数成功"),
        "ValidMetricFound": _("HPA 能够成功计算副本数"),
        "SucceededGetScale": _("成功获取目标的当前规模"),
    },
    "DaemonSet": {
        "FailedCreate": _("创建 Pod 失败"),
        "FailedPlacement": _("未能将 Pod 部署到节点"),
        "FailedDaemonPod": _("尝试终止失败 Daemon pod"),
    },
    "Node": {
        "SystemOOM": _("内存不足"),
        "Rebooted": _("节点已重启"),
        "KubeletSetupFailed": _("kubelet 设置失败"),
        "EvictionThresholdMet": _("资源压力达到驱逐阈值"),
        "InvalidDiskCapacity": _("磁盘容量无效或不足"),
        "FreeDiskSpaceFailed": _("可用磁盘空间失败"),
        "readOnlySysFS": _("系统被设置只读"),
        "ContainerGCFailed": _("容器垃圾回收失败"),
        "ImageGCFailed": _("镜像垃圾回收失败"),
        "MissingClusterDNS": _("缺少 ClusterDNS IP 设置"),
        "FailedToCreateRoute": _("创建网络路由失败"),
        "FailedToStartProxierHealthcheck": _("启动网络代理的健康检查失败"),
        "HostNetworkNotSupported": _("主机网络不受支持"),
        "HostPortConflict": _("主机/端口冲突"),
        "NilShaper": _("未定义整形器"),
        "NodeNetworkUnavailable": _("节点的网络不可用"),
        "VolumeAttachmentStuck": _("卷挂载失败"),
        "CheckLimitsForResolvConf": _("检查 resolv.conf 文件的 limits 失败"),
        "OwnerRefInvalidNamespace": _("命名空间中不存在 ownerRef"),
        "FailedNodeAllocatableEnforcement": _("未能强制实施系统保留的 Cgroup 限制"),
        "KernelDeadlock": _("内核发生死锁"),
        "DockerHung": _("Docker 服务无响应"),
        "CorruptDockerOverlay2": _("Docker overlay2 存在问题"),
        "NodeUnderDiskPressure": _("节点正在经历磁盘压力"),
        "NodeUnderMemoryPressure": _("节点正在经历内存压力"),
        "NodeUnderPIDPressure": _("节点正在经历 PID 压力"),
        "NodeNotReady": _("节点无法接受 Pod"),
        "NodeNotSchedulable": _("节点无法被调度"),
        "NodeHasInsufficientPID": _("节点 PID 资源不足"),
        "NodeHasInsufficientMemory": _("节点内存资源不足"),
        "NodeHasInsufficientDisk": _("节点磁盘资源不足"),
        "NodeReady": _("节点已经准备好接受 Pod"),
        "NodeSchedulable": _("节点可以被调度"),
        "NodeHasSufficientMemory": _("节点有足够的内存资源"),
        "NodeHasSufficientDisk": _("节点有足够的磁盘资源"),
        "NodeHasSufficientPID": _("节点有足够的 PID 资源"),
    },
}

DIMENSION_PREFIX = "dimensions."

NEVER_REFRESH_INTERVAL = "-1"


class EventScenario(Enum):
    CONTAINER_MONITOR = _("容器监控")
    HOST_MONITOR = _("主机监控")
