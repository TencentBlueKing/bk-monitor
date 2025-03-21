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
from enum import Enum, IntEnum
from typing import Dict, Tuple

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
    DEFAULT: str = "DEFAULT"

    @cached_property
    def label(self):
        return str(
            {
                self.K8S: _("Kubernetes"), self.CICD: _("CICD"), self.SYSTEM: _("系统"), self.DEFAULT: _("默认")
            }.get(self, self.value)
        )

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default

    @classmethod
    def choices(cls):
        return [
            (cls.K8S.value, cls.K8S.value),
            (cls.CICD.value, cls.CICD.value),
            (cls.SYSTEM.value, cls.SYSTEM.value),
            (cls.DEFAULT.value, cls.DEFAULT.value)
        ]


class EventSource(CachedEnum):
    """事件来源，需要保持唯一"""

    BKCI: str = "BKCI"
    BCS: str = "BCS"
    HOST: str = "HOST"
    DEFAULT: str = "DEFAULT"

    @classmethod
    def choices(cls):
        return [
            (cls.BCS.value, cls.BCS.value),
            (cls.BKCI.value, cls.BKCI.value),
            (cls.HOST.value, cls.HOST.value),
            (cls.DEFAULT.value, cls.DEFAULT.value)
        ]

    @cached_property
    def label(self):
        return str({
                self.BKCI: _("蓝盾"), self.BCS: _("BCS"), self.HOST: _("主机"), self.DEFAULT: _("业务上报")
            }.get(self, self.value)
        )

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


class EventType(CachedEnum):
    """
    事件类型
    """

    Normal = "Normal"
    Warning = "Warning"
    Default = "Default"

    @classmethod
    def choices(cls):
        return [
            (cls.Normal.value, cls.Normal.value),
            (cls.Warning.value, cls.Warning.value),
            (cls.Default.value, cls.Default.value)
        ]

    @cached_property
    def label(self):
        return str({
            self.Normal: self.Normal.value, self.Warning: self.Warning.value, self.Default: self.Default.value
        }.get(self, self.value))

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


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


DEFAULT_EVENT_ORIGIN: Tuple[str, str] = (EventDomain.DEFAULT.value, EventSource.DEFAULT.value)

EVENT_ORIGIN_MAPPING: Dict[str, Tuple[str, str]] = {
    EventCategory.SYSTEM_EVENT.value: (EventDomain.SYSTEM.value, EventSource.HOST.value,),
    EventCategory.K8S_EVENT.value: (EventDomain.K8S.value, EventSource.BCS.value,),
    EventCategory.CICD_EVENT.value: (EventDomain.CICD.value, EventSource.BKCI.value),
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
        "fs": _("文件系统"),
        "position": _("磁盘位置"),
        "type": _("只读原因"),
        "bk_agent_id": _("AgentID"),
        "corefile": _("CoreDump 文件"),
        "executable": _("可执行文件"),
    },
    EventCategory.K8S_EVENT.value: {
        "bcs_cluster_id": _("集群 ID"),
        "namespace": _("命名空间"),
        "kind": _("资源类型"),
        "apiVersion": _("API 版本"),
        "name": _("资源名称"),
        "uid": _("资源标识"),
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
    {"type": "ip", "alias": _("主机"), "fields": ["bk_target_ip", "ip", "serverip", "bk_host_id"]},
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
        # refer：https://www.cnblogs.com/alisystemsoftware/p/16919263.html
        "FailedPostStartHook": _("PostStart 回调失败"),
        "FailedPreStopHook": _("PreStop 回调失败"),
        "Failed": _("拉取/创建/启动失败"),
        "FailedCreatePodContainer": _("创建容器失败"),
        "Preempting": _("抢占中"),
        "Preempted": _("被抢占"),
        "ExceededGracePeriod": _("指定期限内未能停止 Pod"),
        "InspectFailed": _("镜像检查失败"),
        "ErrImageNeverPull": _("设置 Never 拉取策略且无本地镜像"),
        "InvalidEnvironmentVariableNames": _("环境变量名无效"),
        "FailedValidation": _("Pod 配置验证失败"),
        "UnexpectedAdmissionError": _("Pod 无法被创建"),
        "OOMKilled": _("内存溢出终止"),
        "NetworkNotReady": _("网络未就绪"),
        "NetworkFailed": _("Pod 网络接口丢失即将停止"),
        "FailedScheduling": _("Pod 调度失败"),
        "Evicted": _("Pod 被驱逐"),
        "TopologyAffinityError": _("无满足 Pod 亲和性节点"),
        "FailedCreatePodSandBox": _("Pod 沙箱创建失败"),
        "FailedPodSandBoxStatus": _("Pod 沙箱状态获取失败"),
        "FailedMount": _("卷挂载失效"),
        "AlreadyMountedVolume": _("卷已挂载"),
        "FailedAttachVolume": _("卷附加失败"),
        "FailedMapVolume": _("卷映射失败"),
        "VolumeResizeFailed": _("卷扩展/缩减失败"),
        "FailedBinding": _("无可用持久卷"),
        "VolumeConditionAbnormal": _("卷状态异常"),
        "FileSystemResizeFailed": _("文件系统扩展/缩减失败"),
        "Unhealthy": _("容器异常"),
        "ProbeWarning": _("健康检查异常"),
        "SysctlForbidden": _("使用禁止的系统调用"),
        "AppArmor": _("AppArmor 强制失败"),
        "NoNewPrivs": _("NoNewPrivs 无法强制执行"),
        "ProcMount": _("ProcMount 无法强制执行"),
        "InvalidNodeInfo": _("节点信息无效"),
        "BackOff": _("容器启动/镜像拉取重试中"),
        "TaintManagerEviction": _("污点驱逐"),
        "Killing": _("镜像终止中"),
        "Pulling": _("镜像拉取中"),
        "Pulled": _("镜像已拉取"),
        "Created": _("容器已创建"),
        "Started": _("容器已启动"),
        "Scheduled": _("Pod 已调度"),
    },
    "Job": {
        "BackoffLimitExceeded": _("退避超限"),
        "SuccessfulCreate": _("Pod 已创建"),
        "SuccessfulDelete": _("Pod 已删除"),
        "Completed": _("已完成"),
    },
    "CronJob": {
        "BackoffLimitExceeded": _("退避超限"),
        "SuccessfulCreate": _("Pod 已创建"),
        "SuccessfulDelete": _("Pod 已删除 "),
        "SawCompletedJob": _("已完成"),
    },
    "Deployment": {
        "FailedRollover": _("滚动更新失败"),
        "ScalingReplicaSet": _("副本数调整中"),
        "ScaledReplicaSet": _("副本数已调整"),
        "SuccessfulRollover": _("滚动更新成功"),
    },
    "ReplicaSet": {
        "FailedCreate": _("创建 Pod 失败"),
        "FailedDelete": _("销毁 Pod 失败"),
        "SuccessfulCreate": _("创建 Pod 成功"),
        "SuccessfulDelete": _("销毁 Pod 成功"),
    },
    "HorizontalPodAutoscaler": {
        "FailedGetResourceMetric": _("指标获取失败"),
        "FailedComputeMetricsReplicas": _("副本计算失败"),
        "SelectorRequired": _("需选择器"),
        "InvalidSelector": _("选择器转换失败"),
        "FailedGetObjectMetric": _("HPA 副本计算失败"),
        "InvalidMetricSourceType": _("未知指标类型"),
        "FailedConvertHPA": _("HPA 转换失败"),
        "FailedGetScale": _("规模获取失败"),
        "FailedUpdateStatus": _("状态更新失败"),
        "SuccessfulRescale": _("副本数已调整"),
        "ValidMetricFound": _("HPA 副本计算成功"),
        "SucceededGetScale": _("规模获取成功"),
    },
    "DaemonSet": {
        "FailedCreate": _("Pod 创建失败"),
        "FailedPlacement": _("Pod 部署到节点失败"),
        "FailedDaemonPod": _("终止异常 Daemon Pod 失败"),
    },
    "Node": {
        "SystemOOM": _("内存不足"),
        "Rebooted": _("已重启"),
        "KubeletSetupFailed": _("kubelet 初始化失败"),
        "EvictionThresholdMet": _("资源压力达到驱逐阈值"),
        "InvalidDiskCapacity": _("磁盘容量无效或不足"),
        "FreeDiskSpaceFailed": _("磁盘可用空间检测失败"),
        "readOnlySysFS": _("系统磁盘只读"),
        "ContainerGCFailed": _("容器垃圾回收失败"),
        "ImageGCFailed": _("镜像垃圾回收失败"),
        "MissingClusterDNS": _("缺少 ClusterDNS IP 设置"),
        "FailedToCreateRoute": _("网络路由创建失败"),
        "FailedToStartProxierHealthcheck": _("网络代理健康检查失败"),
        "HostNetworkNotSupported": _("主机网络不支持"),
        "HostPortConflict": _("端口冲突"),
        "NilShaper": _("未定义整形器"),
        "NodeNetworkUnavailable": _("节点网络不可用"),
        "VolumeAttachmentStuck": _("卷挂载卡住"),
        "CheckLimitsForResolvConf": _("resolv.conf 限制检查失败"),
        "OwnerRefInvalidNamespace": _("命名空间 ownerRef 不存在"),
        "FailedNodeAllocatableEnforcement": _("未能强制实施系统保留的 Cgroup 限制"),
        "KernelDeadlock": _("内核死锁"),
        "DockerHung": _("Docker 无响应"),
        "CorruptDockerOverlay2": _("Docker overlay2 损坏"),
        "NodeUnderDiskPressure": _("节点正在经历磁盘压力"),
        "NodeUnderMemoryPressure": _("节点正在经历内存压力"),
        "NodeUnderPIDPressure": _("节点正在经历 PID 压力"),
        "NodeNotReady": _("节点未就绪"),
        "NodeNotSchedulable": _("节点不可调度"),
        "NodeHasInsufficientPID": _("节点 PID 不足"),
        "NodeHasInsufficientMemory": _("节点内存不足"),
        "NodeHasInsufficientDisk": _("节点磁盘不足"),
        "NodeReady": _("节点已就绪"),
        "NodeSchedulable": _("节点可调度"),
        "NodeHasSufficientMemory": _("节点内存充足"),
        "NodeHasSufficientDisk": _("节点磁盘充足"),
        "NodeHasSufficientPID": _("节点 PID 充足"),
    },
}

DIMENSION_PREFIX = "dimensions."

NEVER_REFRESH_INTERVAL = "-1"


class EventScenario(Enum):
    CONTAINER_MONITOR = _("容器监控")
    HOST_MONITOR = _("主机监控")


class SystemEventTypeEnum(Enum):
    OOM: str = "OOM"
    DiskFull: str = "DiskFull"
    DiskReadOnly: str = "DiskReadOnly"
    CoreFile: str = "CoreFile"
    AgentLost: str = "AgentLost"
    PingUnreachable: str = "PingUnreachable"


SYSTEM_EVENT_TRANSLATIONS = {
    "DiskFull": _("磁盘写满"),
    "DiskReadOnly": _("磁盘只读"),
    "CoreFile": _("Corefile 产生"),
    "OOM": _("OOM 异常事件告警"),
    "AgentLost": _("Agent 心跳丢失"),
    "PingUnreachable": _("PING 不可达告警"),
}
