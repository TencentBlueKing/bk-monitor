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
import logging
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set

from opentelemetry.semconv.resource import TelemetrySdkLanguageValues

from apm_web.handlers import metric_group
from apm_web.handlers.metric_group import CalculationType, MetricHelper, TrpcMetricGroup
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.constants import SeriesAliasType
from apm_web.models import Application, CodeRedefinedConfigRelation
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
# TODO 后续可以利用集群上报的资源关联能力，增加「CPU、内存使用率」这类「系统容量」告警（如果有需求的话
STRATEGY_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    constants.TRPCApplyType.CALLER.value: {
        CalculationType.P99_DURATION: constants.CALLER_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.AVG_DURATION: constants.CALLER_AVG_DURATION_STRATEGY_CONFIG,
        CalculationType.SUCCESS_RATE: constants.CALLER_SUCCESS_RATE_STRATEGY_CONFIG,
    },
    constants.TRPCApplyType.CALLEE.value: {
        CalculationType.P99_DURATION: constants.CALLEE_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.AVG_DURATION: constants.CALLEE_AVG_DURATION_STRATEGY_CONFIG,
        CalculationType.SUCCESS_RATE: constants.CALLEE_SUCCESS_RATE_STRATEGY_CONFIG,
    },
    constants.TRPCApplyType.PANIC.value: {CalculationType.PANIC: constants.PANIC_STRATEGY_CONFIG},
}


class TrpcStrategyGroup(base.BaseStrategyGroup):
    class Meta:
        name = define.GroupEnum.TRPC

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        notice_group_ids: List[int],
        metric_helper: MetricHelper,
        apply_types: Optional[List[str]] = None,
        metric_group_constructor: Optional[Callable[..., metric_group.BaseMetricGroup]] = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, **kwargs)
        self.metric_helper: MetricHelper = metric_helper
        # 策略告警组 ID 列表
        self.notice_group_ids: List[int] = notice_group_ids
        # 策略标签，目前的管理范围是一个具体的 APM 应用（APP）
        self.labels: List[str] = [f"tRPC({self.app_name})"]
        # 需要应用的策略类别
        self.apply_types: List[str] = apply_types or constants.TRPCApplyType.options()
        # 指标组构造器，后续场景不是一对一关系时，可从上层传入构造器，构造基于 BaseMetricGroup 接口实现的 group 实例
        self.metric_group_constructor: Callable[
            ..., metric_group.BaseMetricGroup
        ] = metric_group_constructor or partial(
            metric_group.MetricGroupRegistry.get,
            define.GroupEnum.TRPC,
            self.bk_biz_id,
            self.app_name,
            metric_helper=self.metric_helper,
        )

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

    def _get_key(self, strategy: StrategyT) -> StrategyKeyT:
        return strategy["name"]

    def _list_remote(self, *args, **kwargs) -> List[StrategyT]:
        conditions: List[Dict[str, Any]] = [{"key": "label_name", "value": [f"/{label}/"]} for label in self.labels]
        return resource.strategies.get_strategy_list_v2(
            bk_biz_id=self.bk_biz_id, conditions=conditions, page_size=1000
        ).get("strategy_config_list", [])

    def _list_caller_callee(self, kind: str, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        strategies: List[StrategyT] = []
        metric_field: str = TrpcMetricGroup.METRIC_FIELDS[kind]["rpc_handled_total"]
        server_field: str = (TRPCMetricTag.CALLEE_SERVER, TRPCMetricTag.CALLER_SERVER)[
            kind == SeriesAliasType.CALLER.value
        ]
        servers: List[str] = self.metric_helper.get_field_option_values(metric_field, server_field)
        code_redefined_configs: List[CodeRedefinedConfigRelation] = CodeRedefinedConfigRelation.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=servers
        )
        ret_code_as_exception_servers: List[str] = [
            code_redefined_config.service_name
            for code_redefined_config in code_redefined_configs
            if code_redefined_config.ret_code_as_exception
        ]

        def _collect(_server: str):
            _apps: List[str] = self.metric_helper.get_field_option_values(
                metric_field, TRPCMetricTag.APP, {f"{server_field}__eq": _server}
            )
            if _apps:
                _temporality: str = MetricTemporality.CUMULATIVE
                _filter_dict: Dict[str, str] = {f"{server_field}__eq": _server}
            else:
                _temporality: str = MetricTemporality.DELTA
                _filter_dict: Dict[str, str] = {f"{TRPCMetricTag.TARGET}__reg": f".*{_server}$"}

            _ret_code_as_exception: bool = False
            if _server in ret_code_as_exception_servers:
                _ret_code_as_exception = True

            _group: metric_group.BaseMetricGroup = self.metric_group_constructor(
                group_by=["time"],
                filter_dict=_filter_dict,
                kind=kind,
                temporality=_temporality,
                ret_code_as_exception=_ret_code_as_exception,
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

        run_threads([InheritParentThread(target=_collect, args=(server,)) for server in servers if server != "."])
        return strategies

    def _list_callee(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLEE.value, cal_type_config_mapping)

    def _list_caller(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLER.value, cal_type_config_mapping)

    def _list_panic(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        try:
            app = Application.objects.get(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        except Application.DoesNotExist:
            raise ValueError("Application not exist: bk_biz_id -> %s, app_name -> %s", self.bk_biz_id, self.app_name)

        # APM 的 service 在 tRPC 概念中实际上是 sever，这里的命名也沿用 tRPC 领域的设定。
        go_servers: Set[str] = set()
        for service in ServiceHandler.list_services(app):
            server: str = service["topo_key"]
            language: str = service.get("extra_data", {}).get("service_language", "")
            # 找出所有的 Go 服务
            if language == TelemetrySdkLanguageValues.GO.value and server != ".":
                go_servers.add(server)

        # 只有 Go 服务才有 Panic 告警
        if not go_servers:
            return []

        # 找出 Active 的服务
        group: metric_group.TrpcMetricGroup = self.metric_group_constructor()
        go_servers = go_servers & set(group.fetch_server_list())

        # 区分不同 SDK 上报行为
        with_service_name_attr_servers: Set[str] = (
            set(group.fetch_server_list(filter_dict={f"{TRPCMetricTag.APP}__neq": ""})) & go_servers
        )
        with_target_attr_servers: Set[str] = go_servers - with_service_name_attr_servers
        logger.info(
            "[_list_panic] discover: with_service_name_attr_servers -> %s, with_target_attr_servers -> %s",
            with_service_name_attr_servers,
            with_target_attr_servers,
        )

        strategies: List[StrategyT] = []

        def _handle(_servers: List[str], _entity_field: str, _temporality: str):
            if not _servers:
                return

            _group: metric_group.BaseMetricGroup = self.metric_group_constructor(
                group_by=["time", _entity_field],
                filter_dict={f"{_entity_field}__reg": [f".*{_server}$" for _server in _servers]},
                kind=SeriesAliasType.CALLEE.value,
                temporality=_temporality,
            )
            _strategy: StrategyT = self._build_strategy(CalculationType.PANIC, _group, cal_type_config_mapping)
            _strategy["name"] = str(_strategy["name"].format(scope=_entity_field, app_name=self.app_name))
            _strategy["labels"].append(f"tRPC({CalculationType.PANIC})")
            strategies.append(_strategy)

        # Panic 告警规则相对单一，此处聚合上报行为相同的服务为同一条告警策略，减少内置策略数
        _handle(list(with_target_attr_servers), TRPCMetricTag.TARGET, MetricTemporality.DELTA)
        _handle(list(with_service_name_attr_servers), "service_name", MetricTemporality.CUMULATIVE)
        return strategies

    def _list_local(self, *args, **kwargs) -> List[StrategyT]:
        def _collect(_apply_type: str):
            for strategy in apply_type_func_mapping[_apply_type](STRATEGY_CONFIGS[_apply_type]):
                strategies.append(strategy)

        strategies: List[StrategyT] = []
        apply_type_func_mapping: Dict[str, Callable[[Dict[str, Dict[str, Any]]], List[StrategyT]]] = {
            constants.TRPCApplyType.CALLER.value: self._list_caller,
            constants.TRPCApplyType.CALLEE.value: self._list_callee,
            CalculationType.PANIC: self._list_panic,
        }
        run_threads([InheritParentThread(target=_collect, args=(apply_type,)) for apply_type in self.apply_types])
        return strategies

    def _handle_add(self, strategies: List[StrategyT]):
        for strategy in strategies:
            resource.strategies.save_strategy_v2(**strategy)
        logger.info("[_handle_add] % created", len(strategies))

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
