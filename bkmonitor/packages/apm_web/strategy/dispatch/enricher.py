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
from typing import Any

from apm_web.models import StrategyTemplate
from apm_web.strategy.constants import StrategyTemplateCategory, StrategyTemplateSystem
from apm_web.strategy.dispatch import DispatchConfig
from apm_web.strategy.dispatch.entity import EntitySet
from apm_web.strategy.helper import simplify_conditions
from bkmonitor.data_source import q_to_conditions, conditions_to_q
from bkmonitor.query_template.core import QueryTemplateWrapper
from bkmonitor.utils.thread_backend import ThreadPool
from constants import apm as apm_constants
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class BaseSystemDiscoverer(abc.ABC):
    """策略模板系统服务发现器基类"""

    SYSTEM: str = ""

    def _fetch_service_names(self) -> list[str]:
        return self._entity_set.service_names

    def __init__(self, entity_set: EntitySet) -> None:
        self._entity_set: EntitySet = entity_set

    @abc.abstractmethod
    def discover(self) -> list[str]:
        raise NotImplementedError


class RPCSystemDiscoverer(BaseSystemDiscoverer):
    SYSTEM: str = StrategyTemplateSystem.RPC.value

    def _get_related_data(self, service_name: str) -> Any:
        return self._entity_set.get_rpc_service_config_or_none(service_name)

    def discover(self) -> list[str]:
        service_names: list[str] = []
        for service_name in self._fetch_service_names():
            related_data: Any = self._get_related_data(service_name)
            if related_data:
                service_names.append(service_name)
        return service_names


class K8SSystemDiscoverer(RPCSystemDiscoverer):
    SYSTEM: str = StrategyTemplateSystem.K8S.value

    def _get_related_data(self, service_name: str) -> Any:
        return self._entity_set.get_workloads(service_name)


class LogSystemDiscoverer(BaseSystemDiscoverer):
    SYSTEM: str = StrategyTemplateSystem.LOG.value

    def _get_index_set_id_or_none(self) -> str | None:
        return self._entity_set.get_log_datasource_index_set_id_or_none()

    def discover(self) -> list[str]:
        if not self._get_index_set_id_or_none():
            return []
        return self._fetch_service_names()


class TraceSystemDiscoverer(LogSystemDiscoverer):
    SYSTEM: str = StrategyTemplateSystem.TRACE.value

    def _get_index_set_id_or_none(self) -> str | None:
        return self._entity_set.get_trace_datasource_index_set_id_or_none()


class MetricSystemDiscoverer(BaseSystemDiscoverer):
    SYSTEM: str = StrategyTemplateSystem.METRIC.value

    def discover(self) -> list[str]:
        return self._fetch_service_names()


DISCOVERER_CLASSES: dict[str, type[BaseSystemDiscoverer]] = {
    RPCSystemDiscoverer.SYSTEM: RPCSystemDiscoverer,
    K8SSystemDiscoverer.SYSTEM: K8SSystemDiscoverer,
    LogSystemDiscoverer.SYSTEM: LogSystemDiscoverer,
    TraceSystemDiscoverer.SYSTEM: TraceSystemDiscoverer,
    MetricSystemDiscoverer.SYSTEM: MetricSystemDiscoverer,
}


class SystemChecker:
    """策略模板系统检查器"""

    def __init__(self, entity_set: EntitySet) -> None:
        self._entity_set: EntitySet = entity_set

    def _check(self, discoverer_cls: type[BaseSystemDiscoverer]) -> dict[str, list[str] | str]:
        return {
            "system": discoverer_cls.SYSTEM,
            "service_names": discoverer_cls(self._entity_set).discover(),
        }

    def check(self) -> dict[str, list[str]]:
        """检查实体集支持的策略模板系统"""
        pool: ThreadPool = ThreadPool(5)
        discover_iters = pool.imap_unordered(
            lambda discoverer_cls: self._check(discoverer_cls),
            [discoverer_cls for system, discoverer_cls in DISCOVERER_CLASSES.items()],
        )
        pool.close()

        return {result["system"]: result["service_names"] for result in discover_iters}

    def check_systems(self) -> list[str]:
        """返回实体集支持的策略模板系统列表"""
        return [system for system, service_names in self.check().items() if service_names]


class BaseEnricher(abc.ABC):
    """告警下发配置丰富器基类
    借助模板模式（Template Method Design Pattern）的设计思路，将处理流程（enrich、validate、upsert_message_template）作为
    模板方法在基类固定，而具体的处理步骤（_enrich、_handle_invalid_services_exception 等）由子类实现。
    """

    SYSTEM: str = ""

    _TAG_ENUMS: list[type[apm_constants.CachedEnum]] = [apm_constants.CommonMetricTag]

    _BASE_MESSAGE_TEMPLATE: str = (
        "{{content.level}}\n"
        "{{content.begin_time}}\n"
        "{{content.time}}\n"
        "{{content.duration}}\n"
        "{{content.target_type}}\n"
        "{{content.data_source}}\n"
        "{{content.biz}}"
    )

    def __init__(
        self, entity_set: EntitySet, strategy_template: StrategyTemplate, query_template_wrapper: QueryTemplateWrapper
    ) -> None:
        # shortcut
        self.bk_biz_id: int = entity_set.bk_biz_id
        self.app_name: str = entity_set.app_name

        self._entity_set: EntitySet = entity_set
        self._strategy_template: StrategyTemplate = strategy_template
        self._query_template_wrapper: QueryTemplateWrapper = query_template_wrapper
        self._discoverer: BaseSystemDiscoverer = DISCOVERER_CLASSES[self.SYSTEM](entity_set)

    @abc.abstractmethod
    def _handle_invalid_services_exception(self, invalid_service_names: list[str]) -> Exception:
        """
        非法服务异常处理
        :param invalid_service_names: 不合法的服务名称列表
        :return:
        """
        raise NotImplementedError

    def validate(self, raise_exception: bool = True) -> list[str]:
        """
        校验实体集在当前策略模板系统下的合法性
        :param raise_exception: 是否抛出异常。
        :return:
        """
        service_names: list[str] = self._discoverer.discover()
        invalid_service_names: list[str] = list(set(self._entity_set.service_names) - set(service_names))
        if invalid_service_names and raise_exception:
            raise self._handle_invalid_services_exception(invalid_service_names)
        return service_names

    def enrich(self, service_config_map: dict[str, DispatchConfig], raise_exception: bool = True) -> list[str]:
        """
        丰富服务配置。
        :param service_config_map: 服务<>配置映射关系。
        :param raise_exception: 是否抛出异常，不抛出异常时，直接跳过不满足模板系统要求的服务。
        :return:
        """
        # 记录有效服务
        validated_service_names: list[str] = self.validate(raise_exception=raise_exception)
        for service_name in validated_service_names:
            self._enrich(service_name, service_config_map[service_name])
        return validated_service_names

    @abc.abstractmethod
    def _enrich(self, service_name: str, dispatch_config: DispatchConfig) -> None:
        """
        丰富单个服务配置。
        :param service_name: 服务名称。
        :param dispatch_config: 服务配置。
        :return:
        """
        raise NotImplementedError

    @classmethod
    def upsert_group_by(cls, dispatch_config: DispatchConfig, group_by: list[str]) -> None:
        """
        在用户填写的基础上，增加分组维度，用于告警消息展示。
        :param dispatch_config: 下发配置。
        :param group_by: 补充维度。
        :return:
        """
        # 不改变顺序的前提下，对 group_by 进行去重和更新。
        processed_group_by: list[str] = [*group_by]
        for tag in dispatch_config.context.get("GROUP_BY", []):
            if tag not in processed_group_by:
                processed_group_by.append(tag)

        dispatch_config.context["GROUP_BY"] = processed_group_by

    @classmethod
    def upsert_conditions(cls, dispatch_config: DispatchConfig, q: Q) -> None:
        """
        在用户填写的基础上，增加过滤条件，用于限定监控范围。
        :param dispatch_config: 下发配置。
        :param q: 额外的查询条件。
        :return:
        """
        conditions: list[dict[str, Any]] = dispatch_config.context.get("CONDITIONS", [])
        # 多个上下文的条件合并，通过 simplify_conditions 避免产生重复条件，误判成差异。
        dispatch_config.context["CONDITIONS"] = simplify_conditions(q_to_conditions(conditions_to_q(conditions) & q))

    def upsert_message_template(self, dispatch_config: DispatchConfig) -> None:
        """设置告警通知模板"""
        tmpls: list[str] = [
            self._BASE_MESSAGE_TEMPLATE,
            self._entity_info_tmpl(dispatch_config),
            self._current_value_tmpl(dispatch_config),
            self._dimension_tmpl(dispatch_config),
            self._detail_tmpl(dispatch_config),
            self._links_tmpl(dispatch_config),
        ]
        dispatch_config.message_template = "\n".join([t for t in tmpls if t])

    def _current_value_tmpl(self, dispatch_config: DispatchConfig) -> str:
        """当前值模板
        包含content和当前值
        """
        unit: str = dispatch_config.algorithms[0].get("unit_prefix", "")
        return "\n".join(
            [
                "{{content.content}}",
                str(_(f"#当前 {self._query_template_wrapper.alias}# {{{{alarm.current_value}}}} {unit}")),
            ]
        )

    def _entity_info_tmpl(self, dispatch_config: DispatchConfig) -> str:
        """实体信息模板"""
        return "{{content.target}}"

    def _dimension_tmpl(self, dispatch_config: DispatchConfig) -> str:
        """维度模板"""
        return "{{content.dimension}}"

    def _detail_tmpl(self, dispatch_config: DispatchConfig) -> str:
        """详情模板"""
        return "{{content.detail}}\n{{content.assign_detail}}\n{{content.related_info}}"

    def _links_tmpl(self, dispatch_config: DispatchConfig) -> str:
        """场景链接模板"""
        return ""


class RPCEnricher(BaseEnricher):
    SYSTEM: str = StrategyTemplateSystem.RPC.value

    _TAG_ENUMS: list[type[apm_constants.CachedEnum]] = [
        apm_constants.CommonMetricTag,
        apm_constants.RPCMetricTag,
        apm_constants.RPCLogTag,
    ]

    _UPSERT_TAGS: list[str] = [
        apm_constants.CommonMetricTag.APP_NAME.value,
        apm_constants.RPCMetricTag.SERVICE_NAME.value,
    ]

    def _handle_invalid_services_exception(self, invalid_service_names: list[str]) -> Exception:
        return ValueError(
            _("部分服务非 RPC 服务，无法下发「{system}」类告警：{service_names}").format(
                system=StrategyTemplateCategory.from_value(self._strategy_template.category).label,
                service_names=", ".join(invalid_service_names),
            )
        )

    def is_rpc_log(self) -> bool:
        """是否为 RPC 日志告警"""
        return self._strategy_template.category == StrategyTemplateCategory.RPC_LOG.value

    def _enrich(self, service_name: str, dispatch_config: DispatchConfig) -> None:
        if self.is_rpc_log():
            dispatch_config.context.update(
                {
                    "SERVICE_NAME": service_name,
                    "GROUP_BY": [
                        apm_constants.RPCLogTag.RESOURCE_SERVER.value,
                        apm_constants.RPCLogTag.RESOURCE_ENV.value,
                        apm_constants.RPCLogTag.RESOURCE_INSTANCE.value,
                    ],
                    "INDEX_SET_ID": self._entity_set.get_first_log_index_set_id_or_none(service_name),
                }
            )
        else:
            # 在用户填写的基础上，增加服务、应用维度，用于限定监控范围。
            self.upsert_group_by(dispatch_config, self._UPSERT_TAGS)
            self.upsert_conditions(dispatch_config, Q(app_name=self.app_name) & Q(service_name=service_name))

            rpc_service_config: dict[str, Any] | None = self._entity_set.get_rpc_service_config_or_none(service_name)
            if rpc_service_config["temporality"] == apm_constants.MetricTemporality.DELTA:
                dispatch_config.context["FUNCTIONS"] = []

        self.upsert_message_template(dispatch_config)
        if self.is_rpc_log():
            # 日志告警维度固定且不可修改。
            dispatch_config.context.pop("GROUP_BY", None)


class K8SEnricher(BaseEnricher):
    SYSTEM: str = StrategyTemplateSystem.K8S.value

    _TAG_ENUMS: list[type[apm_constants.CachedEnum]] = [apm_constants.K8SMetricTag]

    def _entity_info_tmpl(self, dispatch_config: DispatchConfig) -> str:
        # 目标信息用于更好地与观测场景实体联动。
        return "\n".join(
            [
                _("#APM 应用# {app_name}\n#APM 服务# {service_name}").format(
                    app_name=self.app_name, service_name=dispatch_config.service_name
                ),
                "{{content.target}}",
            ]
        )

    @classmethod
    def _filter_by_workloads(cls, workloads: list[dict[str, Any]]) -> Q:
        q: Q = Q()
        for workload in workloads:
            name: str | None = workload.get("name")
            kind: str | None = workload.get("kind")
            namespace: str | None = workload.get("namespace")
            bcs_cluster_id: str | None = workload.get("bcs_cluster_id")
            if not bcs_cluster_id:
                # 无效关联信息：没有关联集群
                continue

            base_cond: dict[str, str] = {"bcs_cluster_id": bcs_cluster_id, "namespace": namespace}
            if not (kind and name):
                # 关联一个具体的 Namespace
                q |= Q(**base_cond)
                continue

            # 关联 Workload
            kind_pod_reg_map: dict[str, Any] = {
                "Job": f"^{name}-[a-z0-9]{{5,10}}$",
                "Deployment": f"^{name}(-[a-z0-9]{{5,10}}){{1,2}}$",
                "DaemonSet": f"^{name}-[a-z0-9]{{5}}$",
                "StatefulSet": f"^{name}-[0-9]+$",
            }
            for workload_kind, pod_reg in kind_pod_reg_map.items():
                # 为什么采取模糊匹配？因为有类似 xxxDeployment 的 CRD 存在。
                if kind not in workload_kind:
                    continue

                # 为什么按 pod_name 构造查询条件而不是 workload？
                # 大部分容器指标没有 workload 维度，pod_name 是通用维度。
                q |= Q(**base_cond, pod_name__req=pod_reg)
                break
        return q

    def _handle_invalid_services_exception(self, invalid_service_names: list[str]) -> Exception:
        return ValueError(
            _("部分服务未关联容器，无法下发「{system}」类告警：{service_names}").format(
                system=StrategyTemplateCategory.from_value(self._strategy_template.category).label,
                service_names=", ".join(invalid_service_names),
            )
        )

    def _enrich(self, service_name: str, dispatch_config: DispatchConfig) -> None:
        self.upsert_conditions(dispatch_config, self._filter_by_workloads(self._entity_set.get_workloads(service_name)))
        self.upsert_message_template(dispatch_config)


class LogEnricher(BaseEnricher):
    SYSTEM: str = StrategyTemplateSystem.LOG.value

    def _get_index_set_id_or_none(self):
        return self._entity_set.get_log_datasource_index_set_id_or_none()

    def _handle_invalid_services_exception(self, invalid_service_names: list[str]) -> Exception:
        raise ValueError(
            _("应用[{app_name}]未配置{system}数据源，无法下发「{system}」类告警").format(
                app_name=self.app_name,
                system=StrategyTemplateCategory.from_value(self._strategy_template.category).label,
            )
        )

    def _enrich(self, service_name: str, dispatch_config: DispatchConfig) -> None:
        dispatch_config.context.update({"SERVICE_NAME": service_name, "INDEX_SET_ID": self._get_index_set_id_or_none()})
        self.upsert_message_template(dispatch_config)


class TraceEnricher(LogEnricher):
    SYSTEM: str = StrategyTemplateSystem.TRACE.value

    def _get_index_set_id_or_none(self):
        return self._entity_set.get_trace_datasource_index_set_id_or_none()


class MetricEnricher(BaseEnricher):
    SYSTEM: str = StrategyTemplateSystem.METRIC.value

    _TAG_ENUMS: list[type[apm_constants.CachedEnum]] = [apm_constants.CommonMetricTag]

    _UPSERT_TAGS: list[str] = [
        apm_constants.CommonMetricTag.APP_NAME.value,
        apm_constants.RPCMetricTag.SERVICE_NAME.value,
    ]

    def _handle_invalid_services_exception(self, invalid_service_names: list[str]) -> Exception:
        raise ValueError(
            _("应用[{app_name}]未配置{system}数据源，无法下发「{system}」类告警").format(
                app_name=self.app_name,
                system=StrategyTemplateCategory.from_value(self._strategy_template.category).label,
            )
        )

    def _enrich(self, service_name: str, dispatch_config: DispatchConfig) -> None:
        # 在用户填写的基础上，增加服务、应用作为过滤条件，用于限定监控范围。
        self.upsert_conditions(dispatch_config, Q(app_name=self.app_name) & Q(service_name=service_name))
        self.upsert_message_template(dispatch_config)


ENRICHER_CLASSES: dict[str, type[BaseEnricher]] = {
    RPCEnricher.SYSTEM: RPCEnricher,
    K8SEnricher.SYSTEM: K8SEnricher,
    LogEnricher.SYSTEM: LogEnricher,
    TraceEnricher.SYSTEM: TraceEnricher,
    MetricEnricher.SYSTEM: MetricEnricher,
}
