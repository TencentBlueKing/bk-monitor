"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
import time
from functools import cached_property
from typing import Any

from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.log_handler import ServiceLogHandler, get_biz_index_sets_with_cache
from apm_web.strategy.dispatch import EntitySet
from apm_web.log.resources import log_relation_list
from apm_web.topo.handle.relation.define import (
    SourceSystem,
    SourceDatasource,
    SourceK8sNode,
    Relation,
    Source,
    SourceK8sPod,
)
from apm_web.topo.handle.relation.query import RelationQ
from bkmonitor.documents import AlertDocument
from constants.alert import K8S_RESOURCE_TYPE, K8STargetType, APMTargetType, EventTargetType


class BaseTarget(abc.ABC):
    """告警目标对象基类

    为什么需要这个模块？
    告警目标以某一个具体的实体（例如容器、主机..）出现，然而实体之间存在多对多的关系，例如容器目标存在关联的主机、日志索引等信息，
    例如在关联容器、事件等接口，都需要基于告警目标，获取关联容器信息，因此需要统一的目标对象接口，来整体复用关联信息的获取逻辑。
    """

    TARGET_TYPE = ""

    # 通过 unifyquery 接口关联日志索引集的最大数量
    _MAX_LOG_RELATION_NUM: int = 5

    def __init__(self, alert: AlertDocument):
        self._alert: AlertDocument = alert

    @cached_property
    def dimensions(self) -> dict[str, int | str]:
        """获取告警的所有维度信息。

        从告警事件的 tags 中提取维度键值对。

        :return: 维度键值对字典
        :rtype: dict[str, int | str]
        """
        dimensions: dict[str, int | str] = {tag["key"]: tag["value"] for tag in self._alert.event.tags}

        # dimensions 有一些额外的关联信息，也需要补充进来。
        for d in self._alert.dimensions:
            if d["key"].startswith("tag."):
                # 忽略已经存在于 tags 中的维度。
                continue
            dimensions[d["key"]] = d["value"]
        return dimensions

    def _get_dimension_value(self, possible_keys: list[str], default: Any = None) -> Any:
        """获取可能存在的维度值
        :param possible_keys: 维度字段列表
        :param default: 默认值
        :return: 维度值
        """
        for key in possible_keys:
            if key in self.dimensions:
                return self.dimensions[key]
        return default

    def _get_time_range(
        self,
        left_shift: int = -20 * 60,
        right_shift: int = 20 * 60,
        max_duration: int = 60 * 60,
    ) -> tuple[int, int]:
        """获取关联数据查询时间范围
        :param left_shift: 起始时间相对于「首次告警事件」的偏移，单位秒，默认 -20 分钟
        :param right_shift: 结束时间相对于「告警结束时间」的偏移，单位秒，默认 +20 分钟
        :param max_duration: 最大持续时间，单位秒，默认 1 小时
        :return: 起始时间和结束时间的元组
        """
        # Q: 为什么不直接取首次告警事件到结束时间作为时间范围？
        # A: 告警可能持续较长时间，取告警持续时间范围会导致查询数据量过大，影响查询性能。
        # Q：为什么不基于告警结束时间计算时间范围？
        # A: 例如 Pod 持续 OOM 导致告警，Pod 被系统回收后，无法再查询到相关数据，因此基于首次告警时间计算时间范围更合理。
        start_time: int = self._alert.first_anomaly_time + left_shift
        if self._alert.end_time:
            end_time: int = self._alert.end_time + right_shift
        else:
            end_time: int = int(time.time())

        end_time: int = min(end_time, start_time + max_duration)

        return start_time, end_time

    @classmethod
    def _list_related_log_targets(
        cls,
        bk_biz_id: int,
        relation_qs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        data_ids: set[str] = set()
        relations: list[Relation] = RelationQ.query(relation_qs, fill_with_empty=True)
        for r in relations:
            if not r:
                continue

            for n in r.nodes:
                source_info: dict[str, Any] = n.source_info.to_source_info()
                bk_data_id: str | None = source_info.get("bk_data_id")
                if bk_data_id and bk_data_id not in data_ids and len(data_ids) < cls._MAX_LOG_RELATION_NUM:
                    data_ids.add(bk_data_id)

        log_targets: list[dict[str, Any]] = []
        tables: list[str] = ServiceLogHandler.list_tables_by_data_ids(list(data_ids))
        for index_set in get_biz_index_sets_with_cache(bk_biz_id=bk_biz_id):
            indices: list[dict[str, Any]] = index_set.get("indices") or []
            if indices and len(indices) == 1 and indices[0].get("result_table_id") in tables:
                log_target: dict[str, Any] = copy.deepcopy(index_set)
                log_target["addition"] = []
                log_targets.append(log_target)

        return log_targets

    @abc.abstractmethod
    def _get_k8s_resource_type(self) -> str:
        """获取 K8S 资源类型。

        :return: K8S 资源类型
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _list_related_k8s_targets(self) -> list[dict[str, Any]]:
        """获取关联的 K8S 目标列表。

        :return: 关联 K8S 目标信息列表
        """
        raise NotImplementedError

    def list_related_k8s_targets(self) -> dict[str, str | list]:
        """获取关联 K8S 目标信息。

        :return: 包含资源类型和目标列表的字典
        """
        resource_type: str = self._get_k8s_resource_type()
        target_list: list[dict[str, Any]] = self._list_related_k8s_targets()
        for target in target_list:
            # 补充资源类型字段
            target[resource_type] = self._alert.event.target

        return {"resource_type": resource_type, "target_list": target_list}

    def list_related_host_targets(self) -> list[dict[str, Any]]:
        """获取关联主机目标信息。
        :return: 主机目标信息列表
        """
        ip: str | None = self._get_dimension_value(["ip", "bk_target_ip"])
        bk_cloud_id: int = self._get_dimension_value(["bk_cloud_id"], 0)
        bk_host_id: int | None = self._get_dimension_value(["bk_host_id", "host_id"])
        if not ip or bk_host_id is None:
            return []

        target: dict[str, Any] = {
            "bk_target_ip": ip,
            "bk_host_id": bk_host_id,
            "bk_cloud_id": bk_cloud_id,
            "display_name": ip,
            "bk_host_name": "",
        }
        return [target]

    @abc.abstractmethod
    def list_related_apm_targets(self) -> list[dict[str, Any]]:
        """获取关联 APM 目标信息。

        :return: APM 目标信息列表
        """
        raise NotImplementedError

    @abc.abstractmethod
    def list_related_log_targets(self) -> list[dict[str, Any]]:
        """获取关联日志目标信息。

        :return: 日志目标信息列表
        """
        raise NotImplementedError


class DefaultTarget(BaseTarget):
    """默认目标对象。

    当告警目标类型为空或未知时使用的默认实现。
    """

    TARGET_TYPE = EventTargetType.EMPTY

    def _get_k8s_resource_type(self) -> str:
        return ""

    def _list_related_k8s_targets(self) -> list[dict[str, Any]]:
        return []

    def list_related_apm_targets(self) -> list[dict[str, Any]]:
        return []

    def list_related_log_targets(self) -> list[dict[str, Any]]:
        # TODO 日志类告警，直接取 query_config 的索引集 ID 作为日志目标，并根据告警维度、策略生成过滤条件（addition）。
        return []


class BaseK8STarget(BaseTarget):
    """K8S 目标对象基类。

    为所有 Kubernetes 相关的目标对象提供通用实现，例如根据 ``TARGET_TYPE`` 解析 K8S 资源类型，以及基于告警维度构造目标信息。

    子类通常只需设置 :attr:`TARGET_TYPE` 并复用本类实现的通用方法，例如
    :meth:`_get_k8s_resource_type` 和 :meth:`_list_related_k8s_targets`，即可完成针对
    Pod、Workload 等不同 K8S 实体的告警目标建模。
    """

    def _get_k8s_resource_type(self) -> str:
        return K8S_RESOURCE_TYPE[self.TARGET_TYPE]

    def _list_related_k8s_targets(self) -> list[dict[str, Any]]:
        alert_dimensions: dict[str, int | str] = self.dimensions
        target: dict[str, Any] = {"bcs_cluster_id": alert_dimensions.get("bcs_cluster_id", "")}
        if "namespace" in alert_dimensions:
            target["namespace"] = alert_dimensions["namespace"]
        if "workload_kind" in alert_dimensions and "workload_name" in alert_dimensions:
            # 如果存在工作负载信息，组合成 workload 字段
            target["workload"] = f"{alert_dimensions['workload_kind']}:{alert_dimensions['workload_name']}"

        return [target]

    def list_related_apm_targets(self) -> list[dict[str, Any]]:
        return []

    def list_related_log_targets(self) -> list[dict[str, Any]]:
        related_k8s_targets: list[dict[str, Any]] = self.list_related_k8s_targets().get("target_list", [])
        if not related_k8s_targets:
            return []

        qs: list[dict[str, Any]] = []
        start_time, end_time = self._get_time_range()
        related_k8s_target: dict[str, Any] = related_k8s_targets[0]
        if not related_k8s_target.get("bcs_cluster_id"):
            return []

        resource_type: str = self._get_k8s_resource_type()
        workload: str | None = related_k8s_target.pop("workload", "")
        is_workload: bool = workload and resource_type == K8S_RESOURCE_TYPE[K8STargetType.WORKLOAD]
        if is_workload:
            kind, name = workload.split(":", 1)
            related_k8s_target[kind.lower()] = name
            related_k8s_target["name"] = kind.lower()
        else:
            related_k8s_target["name"] = resource_type

        paths: list[type[Source]] = [SourceK8sPod]
        if resource_type == K8S_RESOURCE_TYPE[K8STargetType.NODE]:
            # 关联关系默认按最短路返回，因此 Node 需要额外关联 Pod，才能找到尽可能准确的日志索引。
            paths: list[type[Source]] = [SourceK8sPod, SourceK8sNode]

        for path in paths:
            qs.extend(
                RelationQ.generate_q(
                    bk_biz_id=self._alert.event.bk_biz_id,
                    source_info=related_k8s_target,
                    target_type=SourceDatasource,
                    start_time=start_time,
                    end_time=end_time,
                    path_resource=[path],
                )
            )

        if not qs:
            return []

        addition: list[dict[str, Any]] = []
        if "namespace" in related_k8s_target:
            addition.append(
                {
                    "operator": "=",
                    "field": "__ext.io_kubernetes_pod_namespace",
                    "value": [related_k8s_target["namespace"]],
                }
            )

        # 使用 Pod 更精确地过滤日志
        # Case1 - 从维度中获取 Pod 名称
        # Case2 - 如果是 Workload 目标，则使用 contains 方式模糊匹配 Pod 名称
        pod: str | None = related_k8s_target.get(K8STargetType.POD)
        if not pod:
            pod = self._get_dimension_value(["pod", "pod_name"])
        if pod:
            addition.append({"field": "__ext.io_kubernetes_pod", "operator": "=", "value": [pod]})
        elif is_workload:
            __, name = workload.split(":", 1)
            addition.append({"field": "__ext.io_kubernetes_pod", "operator": "contains", "value": [name]})

        # 使用 主机 IP 进一步过滤日志
        if not pod:
            # 有 Pod 的情况下已经可以精确匹配了，无需增加主机过滤。
            related_host_targets: list[dict[str, Any]] = self.list_related_host_targets()
            if related_host_targets:
                host_target: dict[str, Any] = related_host_targets[0]
                addition.append({"field": "serverIp", "operator": "=", "value": [host_target["bk_target_ip"]]})

        related_log_targets: list[dict[str, Any]] = []
        for related_log_target in self._list_related_log_targets(self._alert.event.bk_biz_id, qs):
            related_log_target.setdefault("addition", []).extend(addition)
            related_log_targets.append(related_log_target)
        return related_log_targets


class K8SPodTarget(BaseK8STarget):
    """K8S Pod 目标对象"""

    TARGET_TYPE = K8STargetType.POD


class K8SWorkloadTarget(BaseK8STarget):
    """K8S Workload 目标对象"""

    TARGET_TYPE = K8STargetType.WORKLOAD


class K8SServiceTarget(BaseK8STarget):
    """K8S Service 目标对象"""

    TARGET_TYPE = K8STargetType.SERVICE


class K8SNodeTarget(BaseK8STarget):
    """K8S Node 目标对象"""

    TARGET_TYPE = K8STargetType.NODE


class APMServiceTarget(BaseTarget):
    """APM 服务目标对象"""

    TARGET_TYPE = APMTargetType.SERVICE

    def _get_k8s_resource_type(self) -> str:
        # APM 场景下资源类型都为 workload。
        return K8S_RESOURCE_TYPE[K8STargetType.WORKLOAD]

    def _list_related_k8s_targets(self) -> list[dict[str, Any]]:
        apm_target_list: list[dict[str, Any]] = self.list_related_apm_targets()
        if not apm_target_list:
            return []

        apm_target: dict[str, Any] = apm_target_list[0]
        entity_set: EntitySet = EntitySet(
            bk_biz_id=self._alert.event.bk_biz_id,
            app_name=apm_target["app_name"],
            service_names=[apm_target["service_name"]],
        )

        target_list: list[dict[str, Any]] = []
        for workload in entity_set.get_workloads(apm_target["service_name"]):
            bcs_cluster_id: str = workload.get("bcs_cluster_id", "")
            namespace: str = workload.get("namespace", "")
            workload_kind: str = workload.get("kind", "")
            workload_name: str = workload.get("name", "")

            if not all([bcs_cluster_id, namespace, workload_kind, workload_name]):
                continue

            target_list.append(
                {
                    "workload": f"{workload_kind}:{workload_name}",
                    "bcs_cluster_id": bcs_cluster_id,
                    "namespace": namespace,
                }
            )

        return target_list

    def list_related_apm_targets(self) -> list[dict[str, Any]]:
        app_name, service_name = APMTargetType.parse_target(self._alert.event.target)
        return [{"app_name": app_name, "service_name": service_name}]

    def list_related_host_targets(self) -> list[dict[str, Any]]:
        apm_target_list: list[dict[str, Any]] = self.list_related_apm_targets()
        if not apm_target_list:
            return []

        # 调用 HostHandler 获取 APM 应用关联的主机列表
        apm_target: dict[str, Any] = apm_target_list[0]
        host_list: list[dict] = HostHandler.list_application_hosts(
            bk_biz_id=self._alert.event.bk_biz_id,
            app_name=apm_target["app_name"],
            service_name=apm_target["service_name"],
        )

        # 若无关联的主机，则返回空列表
        if not host_list:
            return []

        # 提取主机 id 列表，将字符串格式的主机 id 转换为整数
        target_hosts: list[dict[str, str | int]] = []
        for host in host_list:
            bk_host_id: str | None = host.get("bk_host_id")
            if not bk_host_id or not str(bk_host_id).isdigit():
                continue

            target_hosts.append(
                {
                    "bk_host_id": int(bk_host_id),
                    "bk_target_ip": host["bk_host_innerip"],
                    "bk_cloud_id": int(host["bk_cloud_id"]),
                    "display_name": host["bk_host_innerip"],
                    "bk_host_name": "",
                }
            )

        return target_hosts

    def list_related_log_targets(self) -> list[dict[str, Any]]:
        apm_target_list: list[dict[str, Any]] = self.list_related_apm_targets()
        if not apm_target_list:
            return []

        apm_target: dict[str, Any] = apm_target_list[0]
        start_time, end_time = self._get_time_range()
        return list(
            log_relation_list(
                bk_biz_id=self._alert.event.bk_biz_id,
                app_name=apm_target["app_name"],
                service_name=apm_target["service_name"],
                start_time=start_time,
                end_time=end_time,
            )
        )


class HostTarget(DefaultTarget):
    """主机目标对象"""

    TARGET_TYPE = EventTargetType.HOST

    def list_related_host_targets(self) -> list[dict[str, Any]]:
        return [
            {
                "bk_host_id": self._alert.event.bk_host_id,
                "bk_target_ip": self._alert.event.ip,
                "bk_cloud_id": self._alert.event.bk_cloud_id,
                "display_name": self._alert.event.ip,
                "bk_host_name": "",
            }
        ]

    def list_related_log_targets(self) -> list[dict[str, Any]]:
        if not self._alert.event.ip:
            return []

        start_time, end_time = self._get_time_range()
        qs: list[dict[str, Any]] = []
        for path in [SourceK8sPod, SourceK8sNode]:
            qs.extend(
                RelationQ.generate_q(
                    bk_biz_id=self._alert.event.bk_biz_id,
                    source_info=SourceSystem(
                        bk_target_ip=self._alert.event.ip,
                    ),
                    target_type=SourceDatasource,
                    start_time=start_time,
                    end_time=end_time,
                    path_resource=[path],
                )
            )

        related_log_targets: list[dict[str, Any]] = []
        addition: list[dict[str, Any]] = [{"field": "serverIp", "operator": "=", "value": [self._alert.event.ip]}]
        for related_log_target in self._list_related_log_targets(self._alert.event.bk_biz_id, qs):
            related_log_target.setdefault("addition", []).extend(addition)
            related_log_targets.append(related_log_target)
        return related_log_targets


_TARGET_TYPE_MAP: dict[str, type[BaseTarget]] = {
    EventTargetType.EMPTY: DefaultTarget,
    EventTargetType.HOST: HostTarget,
    K8STargetType.POD: K8SPodTarget,
    K8STargetType.NODE: K8SNodeTarget,
    K8STargetType.SERVICE: K8SServiceTarget,
    K8STargetType.WORKLOAD: K8SWorkloadTarget,
    APMTargetType.SERVICE: APMServiceTarget,
}


def get_target_instance(alert: AlertDocument) -> BaseTarget:
    """获取目标对象实例。

    :param alert: 告警对象
    :return: 目标对象实例
    """
    target_type: str | None = alert.event.target_type
    target_cls: type[BaseTarget] = _TARGET_TYPE_MAP.get(target_type, DefaultTarget)
    return target_cls(alert)
