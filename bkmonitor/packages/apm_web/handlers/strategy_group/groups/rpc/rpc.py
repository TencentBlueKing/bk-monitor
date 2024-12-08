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
import copy
import datetime
import logging
import re
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set

from django.conf import settings
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from opentelemetry.semconv.resource import TelemetrySdkLanguageValues
from rest_framework import exceptions as drf_exc
from rest_framework import serializers

from apm_web.container.helpers import ContainerHelper
from apm_web.handlers import metric_group
from apm_web.handlers.metric_group import CalculationType
from apm_web.handlers.metric_group import GroupEnum as MetricGroupEnum
from apm_web.handlers.metric_group import MetricHelper, TrpcMetricGroup
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.constants import SeriesAliasType
from apm_web.models import CodeRedefinedConfigRelation
from bkmonitor.data_source import q_to_dict
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from constants.apm import MetricTemporality, TRPCMetricTag
from constants.data_source import ApplicationsResultTableLabel
from core.drf_resource import resource

from ... import base, define
from ...typing import StrategyKeyT, StrategyT
from . import constants

logger = logging.getLogger(__name__)


# 策略配置 By 类别（主调、被调、Panic）
STRATEGY_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    constants.RPCApplyType.CALLER.value: {
        CalculationType.P99_DURATION: constants.CALLER_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.AVG_DURATION: constants.CALLER_AVG_DURATION_STRATEGY_CONFIG,
        CalculationType.SUCCESS_RATE: constants.CALLER_SUCCESS_RATE_STRATEGY_CONFIG,
    },
    constants.RPCApplyType.CALLEE.value: {
        CalculationType.P99_DURATION: constants.CALLEE_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.AVG_DURATION: constants.CALLEE_AVG_DURATION_STRATEGY_CONFIG,
        CalculationType.SUCCESS_RATE: constants.CALLEE_SUCCESS_RATE_STRATEGY_CONFIG,
    },
    constants.RPCApplyType.PANIC.value: {CalculationType.PANIC: constants.PANIC_STRATEGY_CONFIG},
    constants.RPCApplyType.RESOURCE.value: {
        CalculationType.KUBE_MEMORY_USAGE: constants.MEMORY_USAGE_STRATEGY_CONFIG,
        CalculationType.KUBE_CPU_USAGE: constants.CPU_USAGE_STRATEGY_CONFIG,
        CalculationType.KUBE_OOM_KILLED: constants.OOM_KILLED_STRATEGY_CONFIG,
        CalculationType.KUBE_ABNORMAL_RESTART: constants.ABNORMAL_RESTART_STRATEGY_CONFIG,
    },
}


class RPCStrategyCallerCalleeOptions(serializers.Serializer):
    extra_group_by = serializers.ListField(
        label=_("额外的下钻维度"), child=serializers.CharField(label=_("下钻维度")), required=False, default=[]
    )


class RPCStrategyOptions(serializers.Serializer):
    callee = RPCStrategyCallerCalleeOptions(label=_("被调"), required=False, default={})
    caller = RPCStrategyCallerCalleeOptions(label=_("主调"), required=False, default={})


class RPCStrategyGroup(base.BaseStrategyGroup):

    DEPLOYMENT_POD_NAME_PATTERN = re.compile("^([a-z0-9-]+?)(-[a-z0-9]{5,10}-[a-z0-9]{5})$")
    STATEFUL_SET_POD_NAME_PATTERN = re.compile(r"^([a-z0-9-]+?)-\d+$")

    class Meta:
        name = define.GroupEnum.RPC

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        notice_group_ids: List[int],
        metric_helper: MetricHelper,
        apply_types: Optional[List[str]] = None,
        options: Dict[str, Any] = None,
        rpc_metric_group_constructor: Optional[Callable[..., metric_group.BaseMetricGroup]] = None,
        resource_metric_group_constructor: Optional[Callable[..., metric_group.BaseMetricGroup]] = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, **kwargs)
        self.metric_helper: MetricHelper = metric_helper
        # 策略告警组 ID 列表
        self.notice_group_ids: List[int] = notice_group_ids
        # 策略标签，目前的管理范围是一个具体的 APM 应用（APP）
        self.labels: List[str] = [f"tRPC({self.app_name})"]
        # 需要应用的策略类别
        self.apply_types: List[str] = apply_types or constants.RPCApplyType.options()

        options_serializer = RPCStrategyOptions(data=options or {})
        try:
            options_serializer.is_valid(raise_exception=True)
        except drf_exc.ValidationError as err:
            raise ValueError("[TrpcStrategyGroup] initial group got err -> %s", err)
        else:
            self.options = options_serializer.validated_data

        # 指标组构造器，后续场景不是一对一关系时，可从上层传入构造器，构造基于 BaseMetricGroup 接口实现的 group 实例
        self.rpc_metric_group_constructor: Callable[
            ..., metric_group.BaseMetricGroup
        ] = rpc_metric_group_constructor or partial(
            metric_group.MetricGroupRegistry.get,
            MetricGroupEnum.TRPC,
            self.bk_biz_id,
            self.app_name,
            metric_helper=self.metric_helper,
        )
        self.resource_metric_group_constructor: Callable[
            ..., metric_group.BaseMetricGroup
        ] = resource_metric_group_constructor or partial(
            metric_group.MetricGroupRegistry.get,
            MetricGroupEnum,
            self.bk_biz_id,
            self.app_name,
            metric_helper=self.metric_helper,
        )

        self._server_infos: List[Dict[str, Any]] = self._fetch_server_infos()

    @classmethod
    def _get_pod_name_prefix(cls, pod_name: str) -> Optional[str]:
        if not pod_name:
            return None

        patterns = [cls.DEPLOYMENT_POD_NAME_PATTERN, cls.STATEFUL_SET_POD_NAME_PATTERN]
        for pattern in patterns:
            match = pattern.match(pod_name)
            if match:
                return match.group(1)
        return None

    def _build_strategy(
        self, cal_type: str, group: metric_group.BaseMetricGroup, cal_type_config_mapping: Dict[str, Dict[str, Any]]
    ) -> StrategyT:
        try:
            conf: Dict[str, Any] = copy.deepcopy(cal_type_config_mapping[cal_type])
        except KeyError:
            raise KeyError("[_build_strategy] config(%s) not found", cal_type)

        conf["labels"] = copy.deepcopy(self.labels)
        conf["notice"]["user_groups"] = copy.deepcopy(self.notice_group_ids)
        conf["notice"]["config"]["template"] = DEFAULT_NOTICE_MESSAGE_TEMPLATE

        # 配置指标查询信息
        query_config: Dict[str, Any] = group.query_config(cal_type)
        conf["items"][0]["name"] = str(conf["items"][0]["name"])
        conf["items"][0]["expression"] = query_config["expression"]
        conf["items"][0]["query_configs"] = query_config["query_configs"]
        conf["items"][0]["functions"] = query_config.get("functions") or []

        return {
            **conf,
            "actions": [],
            "bk_biz_id": self.bk_biz_id,
            "scenario": ApplicationsResultTableLabel.application_check,
        }

    def _fetch_server_infos(self) -> List[Dict[str, Any]]:
        server_config: Dict[str, Any] = (
            settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG.get(f"{self.bk_biz_id}-{self.app_name}") or {}
        )
        callee_servers: Set[str] = set(
            self.metric_helper.get_field_option_values(
                TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLEE.value]["rpc_handled_total"],
                server_config.get("server_field") or TRPCMetricTag.CALLEE_SERVER,
            )
        )
        caller_servers: Set[str] = set(
            self.metric_helper.get_field_option_values(
                TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLER.value]["rpc_handled_total"],
                server_config.get("server_field") or TRPCMetricTag.CALLER_SERVER,
            )
        )

        group: metric_group.TrpcMetricGroup = self.rpc_metric_group_constructor()
        with_app_attr_servers: Set[str] = set(group.fetch_server_list(filter_dict={f"{TRPCMetricTag.APP}__neq": ""}))

        code_redefined_configs: List[CodeRedefinedConfigRelation] = CodeRedefinedConfigRelation.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=callee_servers | caller_servers
        )
        ret_code_as_exception_servers: List[str] = [
            code_redefined_config.service_name
            for code_redefined_config in code_redefined_configs
            if code_redefined_config.ret_code_as_exception
        ]

        server_infos: List[Dict[str, Any]] = []
        for service in ServiceHandler.list_nodes(self.bk_biz_id, self.app_name):
            service_name: str = service["topo_key"]
            if service_name == "." or (service_name not in callee_servers and service_name not in caller_servers):
                continue

            server_field: Optional[str] = server_config.get("server_field")
            server_info: Dict[str, Any] = {
                "name": service_name,
                SeriesAliasType.CALLEE.value: service_name in callee_servers,
                SeriesAliasType.CALLER.value: service_name in callee_servers,
                "language": service.get("extra_data", {}).get("service_language", ""),
                "ret_code_as_exception": service_name in ret_code_as_exception_servers,
            }
            if service_name in with_app_attr_servers:
                server_info.update(
                    {
                        "temporality": MetricTemporality.CUMULATIVE,
                        "server_filter_method": "eq",
                        "server_fields": {
                            SeriesAliasType.CALLER.value: server_field or TRPCMetricTag.CALLER_SERVER,
                            SeriesAliasType.CALLEE.value: server_field or TRPCMetricTag.CALLEE_SERVER,
                        },
                        "server_filter_value": service_name,
                    }
                )
            else:
                server_info.update(
                    {
                        "temporality": MetricTemporality.DELTA,
                        "server_filter_method": "reg",
                        "server_fields": {
                            SeriesAliasType.CALLER.value: server_field or TRPCMetricTag.TARGET,
                            SeriesAliasType.CALLEE.value: server_field or TRPCMetricTag.TARGET,
                        },
                        "server_filter_value": f".*{service_name}$",
                    }
                )

            server_info.update(server_config)
            server_infos.append(server_info)

        return server_infos

    def _get_key(self, strategy: StrategyT) -> StrategyKeyT:
        return strategy["name"]

    def _list_remote(self, *args, **kwargs) -> List[StrategyT]:
        conditions: List[Dict[str, Any]] = [{"key": "label_name", "value": [f"/{label}/"]} for label in self.labels]
        return resource.strategies.get_strategy_list_v2(
            bk_biz_id=self.bk_biz_id, conditions=conditions, page_size=1000
        ).get("strategy_config_list", [])

    def _list_caller_callee(self, kind: str, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        server_names: List[str] = []
        server_infos: List[Dict[str, Any]] = []
        for server_info in self._server_infos:
            if server_info[kind]:
                server_infos.append(server_info)
                server_names.append(server_info["name"])

        if not server_infos:
            logger.info("[_list_caller_callee] no servers found: kind -> %s")
            return []
        logger.info("[_list_caller_callee] found servers -> %s", server_names)

        strategies: List[StrategyT] = []

        def _collect(_server_info: Dict[str, Any]):
            _server: str = _server_info["name"]
            _server_field: str = _server_info["server_fields"][kind]
            _construct_config: Dict[str, Any] = {
                # 增加服务实体作为维度，虽然策略已经按实体维度划分，但补充维度能在事件中心进行更好的下钻。
                "group_by": ["time", _server_field, *self.options[kind]["extra_group_by"]],
                "filter_dict": {
                    f"{_server_field}__{_server_info['server_filter_method']}": _server_info['server_filter_value']
                },
                "kind": kind,
                "temporality": _server_info["temporality"],
                "ret_code_as_exception": _server_info["ret_code_as_exception"],
            }
            _group: metric_group.BaseMetricGroup = self.rpc_metric_group_constructor(**_construct_config)
            logger.info(
                "[_list_caller_callee] constructed group: server -> %s, construct_config -> %s",
                _server,
                _construct_config,
            )

            for _cal_type in cal_type_config_mapping:
                _strategy: StrategyT = self._build_strategy(_cal_type, _group, cal_type_config_mapping)
                _strategy["name"] = str(_strategy["name"].format(scope=_server, app_name=self.app_name))
                _strategy["labels"].append(_server)
                logger.info(
                    "[_list_caller_callee] kind -> %s, server -> %s, cal_type -> %s, name -> %s",
                    kind,
                    _server,
                    _cal_type,
                    _strategy["name"],
                )
                strategies.append(_strategy)

        run_threads([InheritParentThread(target=_collect, args=(server_info,)) for server_info in server_infos])
        return strategies

    def _list_callee(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLEE.value, cal_type_config_mapping)

    def _list_caller(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLER.value, cal_type_config_mapping)

    def _list_panic(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        # APM 的 service 在 RPC 概念中实际上是 sever，这里的命名也沿用 RPC 领域的设定。

        with_target_attr_servers: List[str] = []
        with_service_name_attr_servers: List[str] = []
        for server_info in self._server_infos:
            if server_info["language"] != TelemetrySdkLanguageValues.GO.value:
                continue

            if server_info["server_fields"][SeriesAliasType.CALLEE.value] == TRPCMetricTag.TARGET:
                with_target_attr_servers.append(server_info["name"])
            else:
                with_service_name_attr_servers.append(server_info["name"])
        logger.info(
            "[_list_panic] discover: with_service_name_attr_servers -> %s, with_target_attr_servers -> %s",
            with_service_name_attr_servers,
            with_target_attr_servers,
        )

        strategies: List[StrategyT] = []

        def _handle(_servers: List[str], _entity_field: str, _temporality: str):
            if not _servers:
                return

            _group: metric_group.BaseMetricGroup = self.rpc_metric_group_constructor(
                group_by=["time", _entity_field],
                filter_dict={f"{_entity_field}__reg": [f".*{_server}$" for _server in _servers]},
                kind=SeriesAliasType.CALLEE.value,
                temporality=_temporality,
            )
            _strategy: StrategyT = self._build_strategy(CalculationType.PANIC, _group, cal_type_config_mapping)
            _strategy["name"] = str(_strategy["name"].format(scope=_entity_field, app_name=self.app_name))
            _strategy["labels"].append(f"tRPC({constants.RPCApplyType.PANIC})")
            strategies.append(_strategy)

        # Panic 告警规则相对单一，此处聚合上报行为相同的服务为同一条告警策略，减少内置策略数
        _handle(list(with_target_attr_servers), TRPCMetricTag.TARGET, MetricTemporality.DELTA)
        _handle(list(with_service_name_attr_servers), TRPCMetricTag.SERVICE_NAME, MetricTemporality.CUMULATIVE)
        return strategies

    def _list_resource(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:

        namespaces: Set[str] = set()
        bcs_cluster_ids: Set[str] = set()
        pod_name_prefixes: Set[str] = set()

        def _collect(_service_name: str, _start_time: int, _end_time: int):
            relations = ContainerHelper.list_pod_relations(
                self.bk_biz_id, self.app_name, _service_name, _start_time, _end_time
            )
            for relation in relations:
                for node in relation.nodes:
                    source_info = node.source_info.to_source_info()
                    namespaces.add(source_info.get("namespace") or "")
                    bcs_cluster_ids.add(source_info.get("bcs_cluster_id") or "")
                    pod_name_prefixes.add(self._get_pod_name_prefix(source_info.get("pod") or ""))

        end_time: int = int(datetime.datetime.now().timestamp())
        start_time: int = end_time - int(datetime.timedelta(hours=1).total_seconds())
        run_threads(
            [
                InheritParentThread(
                    target=_collect,
                    args=(
                        server_info["name"],
                        start_time,
                        end_time,
                    ),
                )
                for server_info in self._server_infos
            ]
        )

        strategies: List[StrategyT] = []
        _group: metric_group.BaseMetricGroup = self.resource_metric_group_constructor(
            group_by=["bcs_cluster_id", "namespace", "pod_name"],
            filter_dict=q_to_dict(
                Q(
                    bcs_cluster_id__eq=[cluster_id for cluster_id in bcs_cluster_ids if cluster_id],
                    namespace__eq=[namespace for namespace in namespaces if namespace],
                    pod_name__reg=[f"^{prefix}-.+" for prefix in pod_name_prefixes if prefix],
                )
            ),
        )
        for cal_type in cal_type_config_mapping:
            strategy: StrategyT = self._build_strategy(cal_type, _group, cal_type_config_mapping)
            strategy["name"] = str(strategy["name"].format(scope="Pod", app_name=self.app_name))
            strategy["labels"].append(_("{group}（容量告警）").format(group=define.GroupEnum.RPC.upper()))
            strategies.append(strategy)

        return strategies

    def _list_local(self, *args, **kwargs) -> List[StrategyT]:
        def _collect(_apply_type: str):
            for strategy in apply_type_func_mapping[_apply_type](STRATEGY_CONFIGS[_apply_type]):
                strategies.append(strategy)

        strategies: List[StrategyT] = []
        apply_type_func_mapping: Dict[str, Callable[[Dict[str, Dict[str, Any]]], List[StrategyT]]] = {
            constants.RPCApplyType.CALLER.value: self._list_caller,
            constants.RPCApplyType.CALLEE.value: self._list_callee,
            constants.RPCApplyType.PANIC.value: self._list_panic,
            constants.RPCApplyType.RESOURCE: self._list_resource,
        }
        run_threads([InheritParentThread(target=_collect, args=(apply_type,)) for apply_type in self.apply_types])
        return strategies

    def _handle_add(self, strategies: List[StrategyT]):
        for strategy in strategies:
            resource.strategies.save_strategy_v2(**strategy)
        logger.info("[_handle_add] %s created", len(strategies))

    def _handle_delete(self, strategies: List[StrategyT]):
        ids: List[int] = [strategy["id"] for strategy in strategies]
        resource.strategies.delete_strategy_v2(bk_biz_id=self.bk_biz_id, ids=ids)
        logger.info("[_handle_delete] %s deleted", len(ids))

    def _handle_update(
        self, local_strategies_map: Dict[StrategyKeyT, StrategyT], remote_strategies_map: Dict[StrategyKeyT, StrategyT]
    ):
        for key, strategy in local_strategies_map.items():
            strategy["id"] = remote_strategies_map[key]["id"]
            # TODO 这里可以增加 No change 的判断，处理无需变更的场景
            resource.strategies.save_strategy_v2(**strategy)
        logger.info("[_handle_update] %s updated", len(local_strategies_map))
