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

from datetime import datetime
from typing import Dict, List, Optional

from django.utils import timezone
from django.utils.functional import cached_property
from humanize import naturaldelta

from bkmonitor.utils.common_utils import camel_obj_key_to_underscore

# 采集器up指标
BKM_METRICBEAT_ENDPOINT_UP = "bkm_metricbeat_endpoint_up"


class BcsClusterType:
    """meta返回的bcs空间下集群的类型 ."""

    SHARED = "shared"
    SINGLE = "single"


class BkmMetricbeatEndpointUpStatus:
    """采集器up指标值 ."""

    # 成功
    BeatErrCodeOK = 0
    # 未知
    BeatErrCodeUnknown = 1
    # 取消
    BeatErrCodeCancel = 2
    # 超时
    BeatErrCodeTimeout = 3
    # 系统内部异常
    BeatErrInternalErr = 4
    # 连接失败
    BeatErrCodeConnError = 1000
    # 连接超时
    BeatErrCodeConnTimeoutError = 1001
    # 连接代理失败
    BeatErrCodeConnProxyError = 1002
    # 连接DNS解析失败
    BeatErrCodeConnDNSResolveError = 1003
    # DNS解析失败
    BeatErrCodeDNSResolveError = 1004
    # 非法IP地址
    BeatInvalidIPError = 1005
    # 请求失败
    BeatErrCodeRequestError = 1100
    # 请求超时
    BeatErrCodeRequestTimeoutError = 1101
    # 超时设置错误
    BeatErrCodeRequestDeadLineError = 1102
    # 请求初始化失败
    BeatErrCodeRequestInitError = 1103
    # 响应失败
    BeatErrCodeResponseError = 1200
    # 响应超时
    BeatErrCodeResponseTimeoutError = 1201
    # 匹配失败
    BeatErrCodeResponseMatchError = 1202
    # 响应码不匹配
    BeatErrCodeResponseCodeError = 1203
    # 临时响应失败
    BeatErrCodeResponseTemporaryError = 1204
    # 服务无响应
    BeatErrCodeResponseNoRspError = 1205
    # 响应处理失败
    BeatErrCodeResponseHandleError = 1206
    # 链接拒绝
    BeatErrCodeResponseConnRefused = 1207
    # 响应读取失败
    BeatErrCodeResponseReadError = 1208
    # 响应头部为空
    BeatErrCodeResponseEmptyError = 1209
    # 响应头部不符合
    BeatErrCodeResponseHeaderError = 1210
    # 未找到ipv4地址
    BeatErrCodeResponseNotFindIpv4 = 1211
    # 未找到ipv6地址
    BeatErrCodeResponseNotFindIpv6 = 1212
    # url解析错误
    BeatErrCodeResponseParseUrlErr = 1213
    # 脚本配置中的时间单位设置异常
    BeatErrScriptTsUnitConfigError = 1301
    # 主机进程状态信息读取失败
    BeaterProcSnapshotReadError = 1402
    # 标准化模式主机套接字信息读取失败
    BeaterProcStdConnDetectError = 1403
    # Netlink模式主机套接字信息读取失败
    BeaterProcNetConnDetectError = 1404
    # 将相应同步至临时文件失败
    BeaterMetricBeatWriteTmpFileError = 1501
    # DNS解析失败
    BeatPingDNSResolveOuterError = 2101
    # IP 格式异常
    BeatPingInvalidIPOuterError = 2102
    # 脚本运行报错
    BeatScriptRunOuterError = 2301
    # 脚本打印的 Prom 数据格式异常 (按正常处理)
    BeatScriptPromFormatOuterError = 2302
    # PID文件不存在
    BeaterProcPIDFileNotFountOuterError = 2401
    # 单个进程状态信息读取失败
    BeaterProcStateReadOuterError = 2402
    # 进程关键字未匹配到任何进程
    BeaterProcNotMatchedOuterError = 2403
    # 连接用户端地址失败
    BeatMetricBeatConnOuterError = 2501
    # 服务返回的 Prom 数据格式异常 (按正常处理)
    BeatMetricBeatPromFormatOuterError = 2502


def is_k8s_target(scenario: str) -> bool:
    """判定该场景的目标是否为k8s ."""
    return scenario == "kubernetes"


class ReadyStatus:
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"

    ACTIVE = "active"
    FAILED = "failed"
    COMPLETE = "complete"


def get_cpu_without_unit(cpu_with_unit: str):
    """CPU资源量单位转换 ."""
    if cpu_with_unit.endswith("m"):
        return int(cpu_with_unit[:-1]) / 1000
    return int(cpu_with_unit)


def get_memory_without_unit(memory_with_unit: str):
    """内存资源量单位转换 ."""
    # https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
    units = ["K", "M", "G", "T", "P", "E"]
    is_power_of_two = False
    if memory_with_unit.endswith("i"):
        is_power_of_two = True
        memory_with_unit = memory_with_unit[:-1]
    memory_unit = memory_with_unit[-1]
    if memory_unit not in units:
        try:
            return int(memory_with_unit)
        except Exception:
            return 0
    memory_number = int(memory_with_unit[:-1])
    unit_index = units.index(memory_unit)
    power = 1000
    if is_power_of_two:
        power = 1024
    return memory_number * pow(power, (unit_index + 1))


def translate_timestamp_since(start_time):
    """获得资源创建到现在经过的时间 ."""
    if not start_time:
        return None
    # 获得UTC时间
    start_at = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
    start_at_utc = timezone.make_aware(start_at, timezone.utc)
    # 转换为当前时区的时间
    start_at_current_timezone = start_at_utc.astimezone(timezone.get_current_timezone())
    start_at_current_timezone_naive = timezone.make_naive(start_at_current_timezone)
    return naturaldelta(start_at_current_timezone_naive)


def get_progress_value(value: float):
    """
    计算进度条数据
    """
    if not value:
        percent = 0
        label = ""
        status = "NODATA"
    else:
        percent = value / 100
        label = f"{round(value, 2)}%"
        if percent > 80:
            status = "FAILED"
        else:
            status = "SUCCESS"
    return {"value": round(percent * 100, 2), "label": label, "status": status}


class KubernetesV1ObjectJsonParser:
    def __init__(self, config: Dict):
        self.config = config
        # API的版本
        api_version = self.config.get("apiVersion")
        if api_version is None:
            api_version = self.config.get("api_version")
        self.api_version = api_version

        self.kind = self.config.get("kind")
        self.spec = self.config.get("spec", {})
        self.metadata = self.config.get("metadata", {})

        self.name = self.metadata.get("name")
        self.labels = self.metadata.get("labels", {})
        self.namespace = self.metadata.get("namespace")
        # 资源实例创建的时间
        creation_timestamp = self.metadata.get("creationTimestamp")
        if creation_timestamp is None:
            creation_timestamp = self.metadata.get("creation_timestamp")
        self.creation_timestamp = creation_timestamp
        # 资源的版本号
        resource_version = self.metadata.get("resourceVersion")
        if resource_version is None:
            resource_version = self.metadata.get("resource_version")
        self.resource_version = resource_version

    @cached_property
    def age(self):
        """获得运行的时间 ."""
        return translate_timestamp_since(self.creation_timestamp)

    @cached_property
    def template(self):
        """获得模板配置 ."""
        return self.spec.get("template", {})

    @cached_property
    def label_list(self):
        """将标签从字段转换列表格式 ."""
        if not self.labels:
            return []
        label_list = []
        for k, v in self.labels.items():
            label_list.append(
                {
                    "key": k,
                    "value": v,
                }
            )
        return sorted(label_list, key=lambda item: item["key"])


class KubernetesWorkloadJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def template(self):
        """获得模板配置 ."""
        if self.kind == "CronJob":
            template = self.spec.get("jobTemplate", {}).get("spec", {}).get("template", {})
        else:
            template = self.spec.get("template", {})
        return template

    @cached_property
    def containers(self):
        """获得定义的容器 ."""
        return self.template.get("spec", {}).get("containers", [])

    @cached_property
    def container_count(self):
        """获得容器的数量 ."""
        return len(self.containers)

    @cached_property
    def image_list(self):
        """获得容器包含的所有镜像列表 ."""
        return [container.get("image") for container in self.containers if container.get("image")]

    @cached_property
    def status(self):
        return self.config.get("status", {})

    @cached_property
    def owner_references(self):
        return self.metadata.get("ownerReferences", [])

    @cached_property
    def top_workload_type(self) -> Optional[str]:
        """获得顶层的workload类型 ."""
        result = None
        workload_type = self.kind
        if self.owner_references:
            owner_reference = self.owner_references[0]
            if workload_type in ["ReplicaSet", "Job"]:
                # ReplicaSet 的上一层通常是 Deployment
                # Job 的上一层通常是 CronJob
                result = owner_reference.get("kind")

        return result

    @cached_property
    def workload_status(self):
        result = {}
        workload_type = self.kind
        status = self.status
        if workload_type == "Deployment":
            ready = status.get("readyReplicas")
            if ready is None:
                ready = status.get("ready_replicas")
            result["ready"] = ready

            up_to_date = status.get("updatedReplicas")
            if up_to_date is None:
                up_to_date = status.get("updated_replicas")
            result["up_to_date"] = up_to_date

            available = status.get("availableReplicas")
            if available is None:
                available = status.get("available_replicas")
            result["available"] = available

            unavailable_replicas = status.get("unavailableReplicas")
            if unavailable_replicas is None:
                unavailable_replicas = status.get("unavailable_replicas")

            if unavailable_replicas and unavailable_replicas > 0:
                result["ready_status"] = ReadyStatus.UNAVAILABLE
            else:
                result["ready_status"] = ReadyStatus.AVAILABLE
        elif workload_type == "StatefulSet":
            ready = status.get("readyReplicas")
            if ready is None:
                ready = status.get("ready_replicas")
            result["ready"] = ready

            if status.get("replicas", 0) == ready:
                result["ready_status"] = ReadyStatus.AVAILABLE
            else:
                result["ready_status"] = ReadyStatus.UNAVAILABLE
        elif workload_type == "DaemonSet":
            desired = status.get("desiredNumberScheduled")
            if desired is None:
                desired = status.get("desired_number_scheduled")
            result["desired"] = desired

            current = status.get("currentNumberScheduled")
            if current is None:
                current = status.get("current_number_scheduled")
            result["current"] = current

            ready = status.get("numberReady")
            if ready is None:
                ready = status.get("number_ready")
            result["ready"] = ready

            up_to_date = status.get("updatedNumberScheduled")
            if up_to_date is None:
                up_to_date = status.get("updated_number_scheduled")
            result["up_to_date"] = up_to_date

            available = status.get("numberAvailable")
            if available is None:
                available = status.get("number_available")
            result["available"] = available

            desired_number_scheduled = status.get("desiredNumberScheduled")
            if desired_number_scheduled is None:
                desired_number_scheduled = status.get("desired_number_scheduled")

            if desired_number_scheduled == available:
                result["ready_status"] = ReadyStatus.AVAILABLE
            else:
                result["ready_status"] = ReadyStatus.UNAVAILABLE
        elif workload_type == "CronJob":
            result["schedule"] = self.spec.get("schedule")
            if self.spec.get("suspend"):
                suspend = "true"
            else:
                suspend = "false"
            result["suspend"] = suspend
            if status.get("active"):
                result["active"] = len(status.get("active"))
            else:
                result["active"] = 0
        elif workload_type == "Job":
            result["ready_status"] = ReadyStatus.AVAILABLE
            conditions = status.get("conditions", [])
            if conditions:
                condition = conditions[0]
                if condition.get("type") == "Failed" and condition.get("status") == "True":
                    result["ready_status"] = ReadyStatus.UNAVAILABLE
                if condition.get("type") == "Complete" and condition.get("status") == "True":
                    result["ready_status"] = ReadyStatus.AVAILABLE
            if self.spec.get("completions"):
                completions = f"{status.get('succeeded')}/{self.spec.get('completions')}"
            else:
                parallelism = self.spec.get("parallelism", 0)
                if parallelism > 1:
                    completions = f"{status.get('succeeded')}/1 of {parallelism}"
                else:
                    completions = f"{status.get('succeeded')}/1"
            result["completions"] = completions

        if result.get("ready_status", "") == ReadyStatus.UNAVAILABLE:
            result["status"] = "failed"
        else:
            result["status"] = "success"

        return result

    @cached_property
    def service_status(self):
        return self.workload_status["status"]


class KubernetesNodeJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def status(self):
        return self.config.get("status", {})

    @cached_property
    def node_ip(self):
        """获得node的ip地址 ."""
        node_ip = ""
        for address in self.status.get("addresses", []):
            if address.get("type") == "InternalIP":
                node_ip = address.get("address")
        return node_ip

    def get_pod_number(self, endpoints):
        """获得node拥有的pod的数量 ."""
        return len(self.get_pod_name_list(endpoints))

    def get_pod_name_list(self, endpoints):
        """获得节点拥有的pod名称列表 ."""
        pod_name_list = []
        for endpoint in endpoints:
            subsets = endpoint.get("subsets", [])
            if not subsets:
                subsets = []
            for subset in subsets:
                addresses = subset.get("addresses", [])
                if not addresses:
                    addresses = []
                for address in addresses:
                    target_ref = address.get("targetRef", {})
                    if target_ref and target_ref.get("kind", "") == "Pod" and address.get("nodeName", "") == self.name:
                        pod_name_list.append(target_ref.get("name"))
        return pod_name_list

    def get_endpoints_count(self, endpoints):
        count = 0
        for endpoint in endpoints:
            subsets = endpoint.get("subsets", [])
            if not subsets:
                subsets = []
            for subset in subsets:
                addresses = subset.get("addresses", [])
                if not addresses:
                    addresses = []
                # 获得node上可用的地址的数量
                address_count = 0
                for address in addresses:
                    if address.get("nodeName", "") == self.name:
                        address_count += 1

                ports = subset.get("ports", [])
                if not ports:
                    ports = []
                count += address_count * len(ports)
        return count

    @cached_property
    def role_list(self):
        """获得node角色 ."""
        node_role_key_prefix = "node-role.kubernetes.io/"
        roles = []
        for label in self.label_list:
            key = label.get("key", "")
            if key.startswith(node_role_key_prefix):
                value = key[len(node_role_key_prefix) :]
                if value:
                    roles.append(value)
        return sorted(roles)

    @cached_property
    def service_status(self):
        """获得node的服务状态 ."""
        status_list = []
        condition_map = {}
        for condition in self.status.get("conditions", []):
            condition_map[condition.get("type")] = condition

        for valid_condition_type in ["Ready"]:
            condition = condition_map.get(valid_condition_type)
            if condition:
                if condition.get("status") == "True":
                    status_list.append(valid_condition_type)
                else:
                    status_list.append(f"Not{valid_condition_type}")

        if not status_list:
            status_list.append("Unknown")

        if self.spec.get("unschedulable"):
            status_list.append("SchedulingDisabled")

        return ",".join(status_list)

    @cached_property
    def taints(self):
        """获得污点配置 ."""
        return self.config.get("spec", {}).get("taints", [])

    @cached_property
    def taint_labels(self):
        """获得节点的污点配置 ."""
        labels = []
        for meta_taint in self.taints:
            k = meta_taint.get("key", "")
            v = meta_taint.get("value", "")
            e = meta_taint.get("effect", "")
            labels.append(f"{k}={v}:{e}")
        return labels


class KubernetesPodJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def status(self):
        return self.config.get("status", {})

    @cached_property
    def pod_ip(self):
        return self.status.get("podIP")

    @cached_property
    def node_ip(self):
        return self.status.get("hostIP")

    @cached_property
    def image_list(self):
        container_statuses = self.status.get("containerStatuses", [])
        if not container_statuses:
            return []
        images = []
        for container_status in container_statuses:
            image = container_status.get("image", "")
            if not image:
                continue
            images.append(image)
        return sorted(images)

    @cached_property
    def restart_count(self):
        container_statuses = self.status.get("containerStatuses", [])
        if not container_statuses:
            return 0
        restarts = 0
        for container_status in container_statuses:
            restarts += container_status.get("restartCount", 0)
        return restarts

    @cached_property
    def ready_total(self):
        container_statuses = self.status.get("containerStatuses", [])
        return len(container_statuses)

    @cached_property
    def ready_count(self):
        container_statuses = self.status.get("containerStatuses", [])
        if not container_statuses:
            return 0
        ready_count = 0
        for container_status in container_statuses:
            if container_status.get("ready", False):
                ready_count += 1
        return ready_count

    @cached_property
    def resources(self):
        """获得资源限额配置 ."""
        requests_cpu = 0
        limits_cpu = 0
        requests_memory = 0
        limits_memory = 0
        containers = self.spec.get("containers", [])
        # 获得所有容器的资源总和
        for container in containers:
            limits = container.get("resources", {}).get("limits", {})
            requests = container.get("resources", {}).get("requests", {})
            if not limits:
                limits = {}
            if not requests:
                requests = {}
            requests_cpu += get_cpu_without_unit(requests.get("cpu", "0"))
            limits_cpu += get_cpu_without_unit(limits.get("cpu", "0"))
            requests_memory += get_memory_without_unit(requests.get("memory", "0"))
            limits_memory += get_memory_without_unit(limits.get("memory", "0"))
        return {
            "requests_cpu": requests_cpu,
            "limits_cpu": limits_cpu,
            "requests_memory": requests_memory,
            "limits_memory": limits_memory,
        }

    def has_ready_condition(self):
        for condition in self.status.get("conditions"):
            if condition.get("type") == "Ready" and condition.get("status") == "True":
                return True
        return False

    @cached_property
    def service_status(self):
        initializing = False
        phase = self.status.get("phase")
        reason = self.status.get("reason")
        if not reason:
            reason = phase
        init_container_statuses = self.status.get("initContainerStatuses")
        if init_container_statuses is None:
            init_container_statuses = self.status.get("init_container_statuses")
        if init_container_statuses:
            for index, init_container in enumerate(init_container_statuses):
                container_state = init_container.get("state", {})
                terminated = container_state.get("terminated")
                waiting = container_state.get("waiting")
                if terminated:
                    exit_code = terminated.get("exitCode")
                    if exit_code is None:
                        exit_code = terminated.get("exit_code")
                    if exit_code == 0:
                        continue
                    terminated_reason = terminated.get("reason")
                    if terminated_reason:
                        reason = f"Init:{terminated_reason}"
                    else:
                        terminated_signal = terminated.get("signal")
                        if terminated_signal:
                            reason = f"Init:Signal:{terminated_signal}"
                        else:
                            reason = f"Init:ExitCode:{exit_code}"
                    initializing = True
                elif waiting:
                    waiting_reason = waiting.get("reason")
                    if waiting_reason and waiting_reason != "PodInitializing":
                        reason = f"Init:{waiting_reason}"
                    initializing = True
                else:
                    init_containers = self.spec.get("initContainers")
                    if init_containers is None:
                        init_containers = self.spec.get("init_containers")
                    init_containers_count = len(init_containers)
                    reason = f"Init:{index}/{init_containers_count}"
                    initializing = True

        if not initializing:
            has_running = False
            container_statuses = self.status.get("containerStatuses")
            if container_statuses is None:
                container_statuses = self.status.get("container_statuses")
            if container_statuses:
                for container in reversed(container_statuses):
                    ready = container.get("ready")
                    waiting = container.get("state", {}).get("terminated")
                    terminated = container.get("state", {}).get("terminated")
                    running = container.get("state", {}).get("running")
                    if waiting and waiting.get("reason"):
                        reason = waiting["reason"]
                    elif terminated:
                        terminated_reason = terminated.get("reason")
                        if terminated_reason:
                            reason = terminated["reason"]
                        else:
                            terminated_signal = terminated.get("signal")
                            terminated_exit_code = terminated.get("exitCode")
                            if terminated_signal != 0:
                                reason = f"Signal:{terminated_signal}"
                            else:
                                reason = f"ExitCode:{terminated_exit_code}"
                    elif ready and running:
                        has_running = True

            if reason == "Completed" and has_running:
                if self.has_ready_condition():
                    reason = "Running"
                else:
                    reason = "NotReady"

        deletion_timestamp = self.config.get("deletionTimestamp")
        if deletion_timestamp is None:
            deletion_timestamp = self.config.get("deletion_timestamp")
        if deletion_timestamp:
            # 级联删除模式
            if self.status.get("reason") == "NodeLost":
                reason = "Unknown"
            else:
                reason = "Terminating"

        return reason

    def get_workloads(self, replica_set_list, job_list):
        # 获取垃圾回收配置
        owner_references = self.metadata.get("ownerReferences", [])
        if not owner_references:
            owner_references = []
        workload_type = ""
        workload_name = ""
        if owner_references:
            workload_name = owner_references[0].get("name", "")
            workload_type = owner_references[0].get("kind", "")
            if "ReplicaSet" == workload_type:
                for replica_set in replica_set_list:
                    replica_set_owner_references = replica_set.get("metadata", {}).get("ownerReferences", [])
                    if not replica_set_owner_references:
                        continue

                    rs_workload_name = replica_set_owner_references[0].get("name", "")
                    rs_workload_type = replica_set_owner_references[0].get("kind", "")
                    rs_name = replica_set.get("metadata", {}).get("name")
                    if replica_set_owner_references and rs_name in workload_name:
                        owner_references += replica_set_owner_references
                        self.metadata["ownerReferences"] = owner_references
                        workload_name = rs_workload_name
                        workload_type = rs_workload_type
            elif "Job" == workload_type:
                for job in job_list:
                    parent_owner_references = job.get("metadata", {}).get("ownerReferences", [])
                    if not parent_owner_references:
                        continue

                    rs_workload_name = parent_owner_references[0].get("name", "")
                    rs_workload_type = parent_owner_references[0].get("kind", "")
                    job_name = job.get("metadata", {}).get("name")
                    if parent_owner_references and job_name in workload_name:
                        owner_references += parent_owner_references
                        self.metadata["ownerReferences"] = owner_references
                        workload_name = rs_workload_name
                        workload_type = rs_workload_type

        return {
            "owner_references": owner_references,
            "workload_name": workload_name,
            "workload_type": workload_type,
        }

    @cached_property
    def containers(self) -> List:
        return self.spec.get("containers", [])

    @cached_property
    def container_statuses(self) -> List:
        return self.status.get("containerStatuses", [])


class KubernetesContainerJsonParser:
    def __init__(self, pod: Dict, container: Dict):
        self.pod_parser = KubernetesPodJsonParser(pod)
        self.container = container

    @cached_property
    def container_status(self) -> Dict:
        """获得容器当前的状态 ."""
        container_statuses = self.pod_parser.container_statuses
        for container_status in container_statuses:
            if container_status.get("name") == self.name:
                return container_status
        return {}

    @cached_property
    def service_status(self):
        status_text = ""
        for key, value in self.container_status.get("state", {}).items():
            if not status_text and value:
                status_text = key
        return status_text

    @cached_property
    def image(self):
        """获得容器使用的镜像 ."""
        return self.container.get("image")

    @cached_property
    def name(self):
        """获得容器的名称 ."""
        return self.container.get("name")

    @cached_property
    def ports(self):
        """获得容器暴露的端口 ."""
        return self.container.get("ports", [])

    @cached_property
    def name_with_pod(self):
        return f"{self.name}:{self.pod_parser.name}"

    @cached_property
    def resources(self):
        """获得容器资源配置 ."""
        # 集群限制的配置
        limits = self.container.get("resources", {}).get("limits", {})
        # 集群调度使用的资源
        requests = self.container.get("resources", {}).get("requests", {})

        requests_cpu = float(get_cpu_without_unit(requests.get("cpu", "0")))
        # CPU上限值
        limits_cpu = float(get_cpu_without_unit(limits.get("cpu", "0")))
        requests_memory = get_memory_without_unit(requests.get("memory", "0"))
        # 内存上限值
        limits_memory = get_memory_without_unit(limits.get("memory", "0"))

        return {
            "requests_cpu": requests_cpu,
            "limits_cpu": limits_cpu,
            "requests_memory": requests_memory,
            "limits_memory": limits_memory,
        }

    @cached_property
    def created_at(self):
        """容器创建时间 ."""
        started_at = None
        for key, value in self.container_status.get("state", {}).items():
            if key == "running" and value.get("startedAt"):
                started_at = value.get("startedAt")
        if not started_at:
            started_at = self.pod_parser.creation_timestamp
        return started_at

    @cached_property
    def age(self) -> str:
        return translate_timestamp_since(self.created_at)


class KubernetesServiceJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def status(self) -> Dict:
        return self.config.get("status", {})

    @cached_property
    def service_type(self) -> str:
        """获得服务的类型 ."""
        return self.spec.get("type")

    def load_balancer_status_stringer(self, load_balancer: Dict) -> str:
        """解析负载均衡器配置 ."""
        ingress_list = load_balancer.get("ingress", [])
        result = set()
        for ingress in ingress_list:
            ip = ingress.get("ip")
            hostname = ingress.get("hostname")
            if ip:
                result.add(ip)
            elif hostname:
                result.add(hostname)
        return ",".join(result)

    @cached_property
    def cluster_ip(self) -> str:
        """获得集群的内部IP，该值只能够在集群内部访问 ."""
        return self.spec.get("clusterIP", "")

    @cached_property
    def cluster_ips(self) -> List:
        return self.spec.get("clusterIPs", [])

    @cached_property
    def internal_ip(self):
        """集群内部IP，取第一个值 ."""
        if self.cluster_ips:
            return self.cluster_ips[0]
        return "<none>"

    @cached_property
    def external_ip(self) -> str:
        service_type = self.service_type
        # 获得外部IP，可以通过外部IP进入到集群，externalIPs 不会被 Kubernetes 管理，它属于集群管理员的职责范畴。
        spec_external_ips = self.spec.get("externalIPs", [])
        if service_type in ["ClusterIP", "NodePort"]:
            if spec_external_ips:
                return ",".join(spec_external_ips)
            return "<none>"
        elif service_type == "LoadBalancer":
            # 使用云提供商的负载均衡器向外部暴露服务
            load_balancer = self.status.get("loadBalancer", {})
            load_balancer_ips = self.load_balancer_status_stringer(load_balancer)
            if spec_external_ips:
                results = []
                if load_balancer_ips:
                    results.extend(load_balancer_ips.split(","))
                results.extend(spec_external_ips)
                return ",".join(results)
            if load_balancer_ips:
                return load_balancer_ips
            return "<pending>"
        elif service_type == "ExternalName":
            return self.spec.get("externalName", "")
        return "<unknown>"

    @cached_property
    def svc_ports(self):
        """获得服务端口 ."""
        ports = self.spec.get("ports", [])
        pieces = []
        for port_item in ports:
            node_port = port_item.get("nodePort")
            port = port_item.get("port")
            protocol = port_item.get("protocol")
            if node_port:
                pieces.append(f"{port}:{node_port}/{protocol}")
            else:
                pieces.append(f"{port}/{protocol}")
        return ",".join(pieces)

    def get_endpoints_count(self, endpoints):
        """获得endpoints数量 ."""
        count = 0
        endpoint = self.get_endpoint(endpoints)
        if not endpoint:
            return count
        subsets = endpoint.get("subsets", [])
        if not subsets:
            subsets = []
        for subset in subsets:
            addresses = subset.get("addresses", [])
            if not addresses:
                addresses = []
            ports = subset.get("ports", [])
            if not ports:
                ports = []
            count += len(addresses) * len(ports)
        return count

    def get_endpoint(self, endpoints) -> Dict:
        """获得匹配的endpoint ."""
        # 创建service对象的同时，kubernetes会创建同名的endpoints的对象
        for e in endpoints:
            if e.get("metadata", {}).get("name") == self.name:
                return e

    def get_pod_count(self, endpoints) -> int:
        """获得pod的数量 ."""
        return len(self.get_pod_name_list(endpoints))

    def get_pod_name_list(self, endpoints) -> List:
        """获得配置的所有pod的名称列表 ."""
        pod_name_list = []
        endpoint = self.get_endpoint(endpoints)
        if not endpoint:
            return pod_name_list
        subsets = endpoint.get("subsets", [])
        for subset in subsets:
            addresses = subset.get("addresses", [])
            for address in addresses:
                target_ref = address.get("targetRef", {})
                if target_ref and target_ref.get("kind", "") == "Pod":
                    pod_name_list.append(target_ref.get("name"))
        return pod_name_list


class KubernetesServiceMonitorJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def endpoints(self) -> []:
        """获得endpoints配置 ."""
        result = []
        endpoint_list = self.spec.get("endpoints", [])
        for endpoint in endpoint_list:
            # 使用默认值补齐配置
            result.append(
                {
                    "path": endpoint.get("path", "/metrics"),
                    "port": endpoint.get("port", "80"),
                    "interval": endpoint.get("interval", "30s"),
                }
            )
        return result

    @cached_property
    def endpoint_count(self) -> int:
        """获得endpoints的数量 ."""
        return len(self.endpoints)


class KubernetesPodMonitorJsonParser(KubernetesV1ObjectJsonParser):
    @cached_property
    def endpoints(self) -> []:
        """获得endpoints配置 ."""
        result = []
        endpoint_list = self.spec.get("podMetricsEndpoints", [])
        for endpoint in endpoint_list:
            # 使用默认值补齐配置
            result.append(
                {
                    "path": endpoint.get("path", "/metrics"),
                    "port": endpoint.get("port", "80"),
                    "interval": endpoint.get("interval", "30s"),
                }
            )
        return result

    @cached_property
    def endpoint_count(self) -> int:
        """获得endpoints的数量 ."""
        return len(self.endpoints)


class KubernetesEndpointJsonParser(KubernetesV1ObjectJsonParser):
    """Endpoints JSON解析器 ."""

    @cached_property
    def subsets(self) -> []:
        subsets = self.config.get("subsets", [])
        return camel_obj_key_to_underscore(subsets)
