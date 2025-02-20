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
import json
import logging
import re
import urllib.parse
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Set

import six
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
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
from bkmonitor.action.serializers import UserGroupDetailSlz
from bkmonitor.data_source import q_to_dict
from bkmonitor.models import UserGroup
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE, PUBLIC_NOTICE_CONFIG
from constants.apm import MetricTemporality, TRPCMetricTag
from core.drf_resource import resource

from ... import base, define
from ...builder import StrategyBuilder
from ...typing import StrategyKeyT, StrategyT
from . import constants

logger = logging.getLogger(__name__)


# 策略配置 By 类别（主调、被调、Panic）
STRATEGY_CONFIGS: Dict[str, Dict[str, Dict[str, Any]]] = {
    constants.RPCApplyType.CALLER.value: {
        # 均值告警更实用，为了让服务策略数更精简，此处先行注释
        # CalculationType.P99_DURATION: constants.CALLER_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.AVG_DURATION: constants.CALLER_AVG_DURATION_STRATEGY_CONFIG,
        CalculationType.SUCCESS_RATE: constants.CALLER_SUCCESS_RATE_STRATEGY_CONFIG,
    },
    constants.RPCApplyType.CALLEE.value: {
        # CalculationType.P99_DURATION: constants.CALLEE_P99_DURATION_STRATEGY_CONFIG,
        CalculationType.REQUEST_TOTAL: constants.CALLEE_REQUEST_TOTAL_STRATEGY_CONFIG,
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
    group_by = serializers.ListField(
        label=_("下钻维度"), child=serializers.CharField(label=_("下钻维度")), required=False, default=[]
    )
    filter_dict = serializers.DictField(label=_("检索条件"), required=False, default={})


class RPCStrategyOptions(serializers.Serializer):
    callee = RPCStrategyCallerCalleeOptions(label=_("被调"), required=False, default={})
    caller = RPCStrategyCallerCalleeOptions(label=_("主调"), required=False, default={})


class RPCStrategyGroup(base.BaseStrategyGroup):
    _NOT_SUPPORT_FILTER_RPC_DIMENSIONS: List[str] = ["time", TRPCMetricTag.TARGET, TRPCMetricTag.SERVICE_NAME]

    DEPLOYMENT_POD_NAME_PATTERN = re.compile("^([a-z0-9-]+?)(-[a-z0-9]{5,10}-[a-z0-9]{5})$")
    STATEFUL_SET_POD_NAME_PATTERN = re.compile(r"^([a-z0-9-]+?)-\d+$")

    class Meta:
        name = define.GroupType.RPC.value

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        notice_group_ids: List[int],
        metric_helper: MetricHelper,
        apply_types: Optional[List[str]] = None,
        apply_services: Optional[List[str]] = None,
        options: Dict[str, Any] = None,
        rpc_metric_group_constructor: Optional[Callable[..., metric_group.BaseMetricGroup]] = None,
        resource_metric_group_constructor: Optional[Callable[..., metric_group.BaseMetricGroup]] = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, **kwargs)
        self.metric_helper: MetricHelper = metric_helper
        # 策略告警组 ID 列表
        self.notice_group_ids: List[int] = notice_group_ids
        if not self.notice_group_ids:
            self.notice_group_ids = [self._apply_default_notice_group()]

        # 策略标签，目前的管理范围是一个具体的 APM 应用（APP）的某个场景（RPC）
        self.scene_label: str = define.StrategyLabelType.scene_label(app_name)
        self.labels: List[str] = [self.scene_label, define.StrategyLabelType.system_label(self.Meta.name.upper())]

        # 需要应用的服务
        self.apply_services: List[str] = list(set(apply_services or []))

        # 需要应用的策略类别
        self.apply_types: List[str] = (apply_types or constants.RPCApplyType.options())[:]
        if self.apply_services:
            # 指定服务时，移除应用级别类型的策略
            self.apply_types = list(
                set(self.apply_types) - {constants.RPCApplyType.PANIC.value, constants.RPCApplyType.RESOURCE.value}
            )

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
            MetricGroupEnum.RESOURCE,
            self.bk_biz_id,
            self.app_name,
            metric_helper=self.metric_helper,
        )

        self._service_infos: List[Dict[str, Any]] = [
            service_info
            for service_info in self._fetch_service_infos()
            if not self.apply_services or service_info["name"] in self.apply_services
        ]

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

    def _get_caller_callee_url_template(
        self, kind: str, service_name: str, group_by: List[str], perspective_group_by: List[str]
    ) -> str:
        # 在告警持续时间基础上，前后增加偏移量，
        offset: int = 5 * 60 * 1000
        template_variables: Dict[str, str] = {
            "VAR_FROM": "{{alarm.begin_timestamp * 1000 - alarm.duration * 1000 - %s}}" % offset,
            "VAR_TO": "{{alarm.begin_timestamp * 1000 + %s}}" % offset,
        }
        call_options: Dict[str, Any] = {
            "kind": kind,
            "call_filter": [],
            "time_shift": ["1w"],
            "perspective_type": "multiple",
            "perspective_group_by": perspective_group_by,
        }

        # Q：为什么用 VAR_xxx？
        # A：避免 url 转义导致策略模板变量失效。
        for dimension in group_by:
            template_key: str = f"VAR_{dimension.upper()}"
            template_variables[template_key] = "{{alarm.dimensions['%s'].display_value}}" % dimension
            call_options["call_filter"].append({"key": dimension, "method": "eq", "value": [template_key]})

        params: Dict[str, str] = {
            "filter-app_name": self.app_name,
            "filter-service_name": service_name,
            "callOptions": json.dumps(call_options),
            "dashboardId": "service-default-caller_callee",
            "from": "VAR_FROM",
            "to": "VAR_TO",
            "sceneId": "apm_service",
        }
        encoded_params: str = urllib.parse.urlencode(params)
        for k, v in template_variables.items():
            encoded_params = encoded_params.replace(k, v)
        return urllib.parse.urljoin(settings.BK_MONITOR_HOST, f"?bizId={self.bk_biz_id}#/apm/service?{encoded_params}")

    def _build_strategy(
        self, cal_type: str, group: metric_group.BaseMetricGroup, cal_type_config_mapping: Dict[str, Dict[str, Any]]
    ) -> StrategyT:
        try:
            conf: Dict[str, Any] = cal_type_config_mapping[cal_type]
        except KeyError:
            raise KeyError("[_build_strategy] config(%s) not found", cal_type)

        return StrategyBuilder(
            bk_biz_id=self.bk_biz_id,
            query_config=group.query_config(cal_type),
            labels=self.labels,
            notice_group_ids=self.notice_group_ids,
            message_templates=DEFAULT_NOTICE_MESSAGE_TEMPLATE,
            **conf,
        ).build()

    @classmethod
    def _add_member_to_notice_group(
        cls, bk_biz_id: int, user_id: str, group_name: str, notice_ways: Optional[List[str]] = None
    ) -> int:
        """增加成员到告警组，告警组不存在时默认创建
        :param bk_biz_id: 业务 ID
        :param user_id: 用户 ID
        :param group_name: 告警组名称
        :param notice_ways: 通知方式
        :return:
        """
        user_group_inst: Optional[UserGroup] = UserGroup.objects.filter(bk_biz_id=bk_biz_id, name=group_name).first()
        if user_group_inst is None:
            notice_config: Dict[str, Any] = copy.deepcopy(PUBLIC_NOTICE_CONFIG)
            for notice_way_config in (
                notice_config["alert_notice"][0]["notify_config"] + notice_config["action_notice"][0]["notify_config"]
            ):
                notice_way_config["type"] = notice_ways or ["rtx"]

            user_group: Dict[str, Any] = {
                "name": group_name,
                "notice_receiver": [{"id": user_id, "type": "user"}],
                **notice_config,
            }
            user_group_serializer: UserGroupDetailSlz = UserGroupDetailSlz(
                data={
                    "bk_biz_id": bk_biz_id,
                    "name": six.text_type(user_group["name"]),
                    "duty_arranges": [{"users": user_group["notice_receiver"]}],
                    "desc": user_group["message"],
                    "alert_notice": user_group["alert_notice"],
                    "action_notice": user_group["action_notice"],
                }
            )
        else:
            # 检索用户是否已经存在在当前告警组，存在则跳过添加步骤
            duty_arranges: List[Dict[str, Any]] = UserGroupDetailSlz(user_group_inst).data["duty_arranges"]
            current_users: List[Dict[str, Any]] = duty_arranges[0]["users"]
            if user_id in {user["id"] for user in current_users if user["type"] == "user"}:
                # 已存在，无需重复添加
                return user_group_inst.id

            current_users.append({"id": user_id, "type": "user"})
            user_group_serializer = UserGroupDetailSlz(
                user_group_inst, data={"duty_arranges": [{"users": current_users}]}, partial=True
            )

        user_group_serializer.is_valid(raise_exception=True)
        return user_group_serializer.save().id

    def _apply_default_notice_group(self) -> int:
        return self._add_member_to_notice_group(
            bk_biz_id=self.bk_biz_id,
            user_id=self.application.update_user,
            group_name=_("【APM】{app_name} 告警组".format(app_name=self.app_name)),
        )

    def _fetch_service_infos(self) -> List[Dict[str, Any]]:
        service_config: Dict[str, Any] = (
            settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG.get(f"{self.bk_biz_id}-{self.app_name}") or {}
        )
        config_server_field: str = service_config.get("server_field") or TRPCMetricTag.SERVICE_NAME
        if config_server_field == MetricTemporality.DYNAMIC_SERVER_FIELD:
            caller_server_field: str = TRPCMetricTag.CALLER_SERVER
            callee_server_field: str = TRPCMetricTag.CALLEE_SERVER
        else:
            caller_server_field: str = config_server_field
            callee_server_field: str = config_server_field

        callee_servers: Set[str] = set(
            self.metric_helper.get_field_option_values(
                TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLEE.value]["rpc_handled_total"], callee_server_field
            )
        )
        caller_servers: Set[str] = set(
            self.metric_helper.get_field_option_values(
                TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLER.value]["rpc_handled_total"], caller_server_field
            )
        )

        group: metric_group.TrpcMetricGroup = self.rpc_metric_group_constructor()
        with_app_attr_services: Set[str] = set(group.fetch_server_list(filter_dict={f"{TRPCMetricTag.APP}__neq": ""}))

        code_redefined_configs = CodeRedefinedConfigRelation.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=callee_servers | caller_servers
        )
        ret_code_as_exception_services: List[str] = [
            code_redefined_config.service_name
            for code_redefined_config in code_redefined_configs
            if code_redefined_config.ret_code_as_exception
        ]

        service_infos: List[Dict[str, Any]] = []
        for service in ServiceHandler.list_nodes(self.bk_biz_id, self.app_name):
            service_name: str = service["topo_key"]
            if service_name == "." or (service_name not in callee_servers and service_name not in caller_servers):
                continue

            service_info: Dict[str, Any] = {
                "name": service_name,
                SeriesAliasType.CALLEE.value: service_name in callee_servers,
                SeriesAliasType.CALLER.value: service_name in caller_servers,
                "language": service.get("extra_data", {}).get("service_language", ""),
                "temporality": MetricTemporality.DELTA,
                "server_filter_method": "eq",
                "server_filter_value": service_name,
                "server_fields": {
                    SeriesAliasType.CALLER.value: caller_server_field,
                    SeriesAliasType.CALLEE.value: callee_server_field,
                },
                "ret_code_as_exception": service_name in ret_code_as_exception_services,
            }

            if service_name in with_app_attr_services:
                service_info["temporality"] = MetricTemporality.CUMULATIVE

            service_info.update(service_config)
            service_infos.append(service_info)

        return service_infos

    def _get_key(self, strategy: StrategyT) -> StrategyKeyT:
        return strategy["name"]

    def _list_remote(self, *args, **kwargs) -> List[StrategyT]:
        conditions: List[Dict[str, Any]] = [{"key": "label_name", "value": [f"/{self.scene_label}/"]}]
        strategies: List[StrategyT] = resource.strategies.get_strategy_list_v2(
            bk_biz_id=self.bk_biz_id, conditions=conditions, page_size=1000
        ).get("strategy_config_list", [])

        filtered_strategies: List[StrategyT] = []
        label_set: Set[str] = set(self.labels)
        service_label_set: Set[str] = {
            define.StrategyLabelType.service_label(service_name) for service_name in self.apply_services
        }
        for strategy in strategies:
            strategy_label_set: Set[str] = set(strategy.get("labels") or [])

            # 策略不支持 labels 间的 and 查询，此处先查询应用关联的策略，再二次过滤。
            # 过滤规则 1：策略标签需包含 label_set（本次导入影响的策略范围）
            if not strategy_label_set.issuperset(label_set):
                continue

            # 过滤规则 2：指定服务场景下，仅保留服务列表内的策略
            if not service_label_set or service_label_set & strategy_label_set:
                filtered_strategies.append(strategy)

        return filtered_strategies

    def _list_caller_callee(self, kind: str, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        service_names: List[str] = []
        service_infos: List[Dict[str, Any]] = []
        for service_info in self._service_infos:
            if service_info[kind]:
                service_infos.append(service_info)
                service_names.append(service_info["name"])

        if not service_infos:
            logger.info("[_list_caller_callee] no services found: kind -> %s")
            return []
        logger.info("[_list_caller_callee] found services -> %s", service_names)

        strategies: List[StrategyT] = []

        def _collect(_service_info: Dict[str, Any]):
            _service_name: str = _service_info["name"]
            _server_field: str = _service_info["server_fields"][kind]
            _construct_config: Dict[str, Any] = {
                # 增加服务实体作为维度，虽然策略已经按实体维度划分，但补充维度能在事件中心进行更好的下钻。
                "group_by": ["time", _server_field, *self.options[kind]["group_by"]],
                "filter_dict": {
                    f"{_server_field}__{_service_info['server_filter_method']}": _service_info['server_filter_value'],
                    **(self.options[kind].get("filter_dict") or {}),
                },
                "kind": kind,
                "temporality": _service_info["temporality"],
                "ret_code_as_exception": _service_info["ret_code_as_exception"],
            }
            _group: metric_group.BaseMetricGroup = self.rpc_metric_group_constructor(**_construct_config)
            logger.info(
                "[_list_caller_callee] constructed group: service -> %s, construct_config -> %s",
                _service_name,
                _construct_config,
            )

            for _cal_type in cal_type_config_mapping:
                _strategy: StrategyT = self._build_strategy(_cal_type, _group, cal_type_config_mapping)
                _strategy["name"] = str(_strategy["name"].format(scope=_service_name, app_name=self.app_name))
                _strategy["labels"].extend(
                    [define.StrategyLabelType.service_label(_service_name), define.StrategyLabelType.alert_type(kind)]
                )

                # 异常分析下钻
                _group_by: List[str] = list(
                    set(self.options[kind]["group_by"]) - set(self._NOT_SUPPORT_FILTER_RPC_DIMENSIONS)
                )
                _perspective_group_by: Set[str] = {TRPCMetricTag.CALLEE_METHOD} | set(_group_by)
                if _cal_type == CalculationType.SUCCESS_RATE:
                    _perspective_group_by.add(TRPCMetricTag.CODE)

                _url_templ: str = self._get_caller_callee_url_template(
                    kind, _service_name, _group_by, list(_perspective_group_by)
                )
                message_tmpl: str = _strategy["notice"]["config"]["template"][0]["message_tmpl"]
                # TODO(crayon) 后续 APM 具有服务告警页面时，在告警后台增加 APM URL 模板
                # 可能的模板方案：
                # - 识别策略标签，得到应用名（APM-APP）、服务（APM-SERVICE）、系统（APM-SYSTEM）、告警类别（APM-ALERT）
                # - 增加 UrlProcessor，根据标签计算和告警信息，计算出需要跳转到哪个页面
                _strategy["notice"]["config"]["template"][0]["message_tmpl"] = "{}\n调用分析：[查看]({})".format(
                    message_tmpl, _url_templ
                )

                logger.info(
                    "[_list_caller_callee] kind -> %s, service -> %s, cal_type -> %s, name -> %s",
                    kind,
                    _service_name,
                    _cal_type,
                    _strategy["name"],
                )
                strategies.append(_strategy)

        run_threads([InheritParentThread(target=_collect, args=(service_info,)) for service_info in service_infos])
        return strategies

    def _list_callee(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLEE.value, cal_type_config_mapping)

    def _list_caller(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        return self._list_caller_callee(SeriesAliasType.CALLER.value, cal_type_config_mapping)

    def _list_panic(self, cal_type_config_mapping: Dict[str, Dict[str, Any]]) -> List[StrategyT]:
        # APM 的 service 在 RPC 概念中实际上是 sever，这里的命名也沿用 RPC 领域的设定。
        with_target_attr_services: List[str] = []
        with_service_name_attr_services: List[str] = []
        for service_info in self._service_infos:
            if service_info["language"] != TelemetrySdkLanguageValues.GO.value:
                continue

            if service_info["server_fields"][SeriesAliasType.CALLEE.value] == TRPCMetricTag.TARGET:
                with_target_attr_services.append(service_info["name"])
            else:
                with_service_name_attr_services.append(service_info["name"])
        logger.info(
            "[_list_panic] discover: with_service_name_attr_servers -> %s, with_target_attr_servers -> %s",
            with_service_name_attr_services,
            with_target_attr_services,
        )

        strategies: List[StrategyT] = []

        def _handle(_services: List[str], _entity_field: str, _temporality: str):
            if not _services:
                return

            _group: metric_group.BaseMetricGroup = self.rpc_metric_group_constructor(
                group_by=["time", _entity_field],
                filter_dict={f"{_entity_field}__reg": [f".*{_service}$" for _service in _services]},
                kind=SeriesAliasType.CALLEE.value,
                temporality=_temporality,
            )
            _strategy: StrategyT = self._build_strategy(CalculationType.PANIC, _group, cal_type_config_mapping)
            _strategy["name"] = str(_strategy["name"].format(scope=_entity_field, app_name=self.app_name))
            _strategy["labels"].append(define.StrategyLabelType.alert_type(constants.RPCApplyType.PANIC.value))
            strategies.append(_strategy)

        # Panic 告警规则相对单一，此处聚合上报行为相同的服务为同一条告警策略，减少内置策略数
        _handle(list(with_target_attr_services), TRPCMetricTag.TARGET, MetricTemporality.DELTA)
        _handle(list(with_service_name_attr_services), TRPCMetricTag.SERVICE_NAME, MetricTemporality.CUMULATIVE)
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
                    namespace: Optional[str] = source_info.get("namespace")
                    bcs_cluster_id: Optional[str] = source_info.get("bcs_cluster_id")
                    pod_name_prefix: Optional[str] = self._get_pod_name_prefix(source_info.get("pod") or "")
                    if namespace and bcs_cluster_id and pod_name_prefix:
                        namespaces.add(namespace)
                        bcs_cluster_ids.add(bcs_cluster_id)
                        pod_name_prefixes.add(pod_name_prefix)

        end_time: int = int(datetime.datetime.now().timestamp())
        start_time: int = end_time - int(datetime.timedelta(hours=1).total_seconds())
        run_threads(
            [
                InheritParentThread(
                    target=_collect,
                    args=(
                        service_info["name"],
                        start_time,
                        end_time,
                    ),
                )
                for service_info in self._service_infos
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
            strategy["labels"].append(define.StrategyLabelType.alert_type(constants.RPCApplyType.RESOURCE.value))
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
            constants.RPCApplyType.RESOURCE.value: self._list_resource,
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
