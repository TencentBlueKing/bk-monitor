"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import urllib.parse
from typing import Any

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import StrategyTemplate, StrategyInstance
from bkmonitor.data_source import q_to_conditions
from bkmonitor.query_template.core import QueryTemplateWrapper
from django.utils.translation import gettext_lazy as _

from apm_web.strategy.constants import StrategyTemplateCategory
from constants.apm import MetricTemporality, CommonMetricTag, RPCMetricTag, RPCLogTag
from core.drf_resource import resource

from .base import DispatchExtraConfig, DispatchGlobalConfig, DispatchConfig, calculate_strategy_md5_by_dispatch_config
from .builder import StrategyBuilder


class StrategyDispatcher:
    _BASE_MESSAGE_TEMPLATE: str = (
        "{{content.level}}\n"
        "{{content.begin_time}}\n"
        "{{content.time}}\n"
        "{{content.duration}}\n"
        "{{content.content}}\n"
        "{{content.biz}}\n"
    )

    def __init__(self, strategy_template: StrategyTemplate, query_template_wrapper: QueryTemplateWrapper) -> None:
        self.bk_biz_id: int = strategy_template.bk_biz_id
        self.app_name: str = strategy_template.app_name
        self.strategy_template: StrategyTemplate = strategy_template
        self.query_template_wrapper: QueryTemplateWrapper = query_template_wrapper

    def _list_relation_log_indexes(self, service_names: list[str]) -> dict[str, list[dict[str, Any]]]:
        """查询服务关联的日志索引集
        :param service_names: 服务列表
        :return: 服务名<>关联的日志索引集列表
        """

        service_indexes: dict[str, list[dict[str, Any]]] = {}
        datasource_index_set_id: int | None = ServiceLogHandler.get_and_check_datasource_index_set_id(
            self.bk_biz_id, self.app_name
        )
        if datasource_index_set_id:
            for service_name in service_names:
                service_indexes[service_name] = [{"index_set_id": datasource_index_set_id, "is_app_datasource": True}]

        for relation in ServiceLogHandler.get_log_relations(self.bk_biz_id, self.app_name, service_names):
            if relation.related_bk_biz_id != self.bk_biz_id:
                # 跨业务关联意味着告警也要跨业务下发，当前不支持。
                continue

            service_indexes.setdefault(relation.service_name, []).extend(
                [{"index_set_id": index_set_id, "is_app_datasource": False} for index_set_id in relation.value_list]
            )

        return service_indexes

    def _get_rpc_url_template(
        self, service_name: str, group_by: list[str], tag_key_map: dict[str, str] | None = None
    ) -> str:
        call_filter: list[dict[str, Any]] = []
        tag_key_map: dict[str, str] = tag_key_map or {}
        for tag in group_by:
            key: str = tag_key_map.get(tag, tag)
            if key in [RPCMetricTag.SERVICE_NAME, CommonMetricTag.APP_NAME]:
                continue

            call_filter.append(
                {
                    "key": key,
                    "method": "eq",
                    "value": f"{{{{alarm.dimensions['{tag}'].display_value}}}}",
                    "condition": "and",
                }
            )

        call_options: dict[str, Any] = {
            "kind": ("callee", "caller")[self.strategy_template.category == StrategyTemplateCategory.RPC_CALLER.value],
            "call_filter": call_filter,
            "perspective_type": "multiple",
            "perspective_group_by": [RPCMetricTag.CALLEE_METHOD, RPCMetricTag.CODE],
        }

        offset: int = 5 * 60 * 1000
        template_variables: dict[str, str] = {
            "VAR_FROM": f"{{{{alarm.begin_timestamp * 1000 - alarm.duration * 1000 - {offset}}}}}",
            "VAR_TO": f"{{{{alarm.begin_timestamp * 1000 + {offset}}}}}",
            "VAR_CALL_OPTIONS": json.dumps(call_options),
        }

        params: dict[str, str] = {
            "filter-app_name": self.app_name,
            "filter-service_name": service_name,
            "callOptions": "VAR_CALL_OPTIONS",
            "dashboardId": "service-default-caller_callee",
            "from": "VAR_FROM",
            "to": "VAR_TO",
            "sceneId": "apm_service",
        }
        encoded_params: str = urllib.parse.urlencode(params)
        for k, v in template_variables.items():
            encoded_params = encoded_params.replace(k, v)
        return urllib.parse.urljoin(settings.BK_MONITOR_HOST, f"?bizId={self.bk_biz_id}#/apm/service?{encoded_params}")

    def _handle_rpc(self, nodes: list[dict[str, Any]], service_config_map: dict[str, DispatchConfig]):
        invalid_service_names: list[str] = []
        service_rpc_config_map: dict[str, dict[str, Any]] = {}
        for node in nodes:
            service_name: str = node["topo_key"]
            rpc_service_config: dict[str, Any] | None = ServiceHandler.get_rpc_service_config_or_none(node)
            if not rpc_service_config:
                invalid_service_names.append(service_name)
                continue

            service_rpc_config_map[service_name] = rpc_service_config

        if invalid_service_names:
            raise ValueError(
                _("部分服务非 RPC 服务，无法下发调用分析类告警：{}").format(", ".join(invalid_service_names))
            )

        service_indexes_map: dict[str, list[dict[str, Any]]] = self._list_relation_log_indexes(
            list(service_config_map.keys())
        )
        for node in nodes:
            service_name: str = node["topo_key"]
            unit: str = self.query_template_wrapper.unit
            message_template: str = (
                f"{self._BASE_MESSAGE_TEMPLATE}\n"
                f"#当前 {self.query_template_wrapper.alias}# {{{{alarm.current_value}}}} {unit}"
            )

            tag_key_map: dict[str, str] = {}
            dispatch_config: DispatchConfig = service_config_map[service_name]
            group_by: list[str] = dispatch_config.context.get("GROUP_BY") or [
                "resource.server",
                "resource.env",
                "resource.instance",
            ]
            if self.strategy_template.category == StrategyTemplateCategory.RPC_LOG.value:
                try:
                    first_index_set_id: int = service_indexes_map[service_name][0]["index_set_id"]
                except (KeyError, IndexError):
                    raise ValueError(_("服务 {} 未关联日志索引集，无法下发日志类告警策略").format(service_name))

                dispatch_config.context.update({"SERVICE_NAME": service_name, "INDEX_SET_ID": first_index_set_id})

                for tag in group_by:
                    tag_enum: RPCLogTag = RPCLogTag.from_value(tag)
                    message_template += f"\n#{tag_enum.label}# {{{{alarm.dimensions['{tag}'].display_value}}}}"
                    tag_key_map[tag] = tag_enum.metric_tag
            else:
                # 在用户填写的基础上，增加服务、应用维度，用于限定监控范围。
                dispatch_config.context.setdefault("GROUP_BY", []).extend(
                    [CommonMetricTag.APP_NAME, RPCMetricTag.SERVICE_NAME]
                )
                dispatch_config.context.setdefault("CONDITIONS", []).extend(
                    q_to_conditions(Q(app_name=self.app_name, service_name=service_name))
                )
                if service_rpc_config_map[service_name]["temporality"] == MetricTemporality.DELTA:
                    dispatch_config.context["FUNCTIONS"] = []

                for tag in group_by:
                    tag_text: str = CommonMetricTag.get_text_or_default(tag) or RPCMetricTag.get_text_or_default(
                        tag, default=tag
                    )
                    message_template += f"\n#{tag_text}# {{{{alarm.dimensions['{tag}'].display_value}}}}"

            url_templ: str = self._get_rpc_url_template(service_name, group_by, tag_key_map)
            dispatch_config.message_template = f"{message_template}\n#调用分析# [查看]({url_templ})"

    def dispatch(
        self,
        service_names: list[str],
        global_config: DispatchGlobalConfig | None = None,
        extra_configs: list[DispatchExtraConfig] | None = None,
    ) -> dict[str, int]:
        """批量下发策略到服务
        :param service_names: 服务列表
        :param global_config: 全局下发配置
        :param extra_configs: 额外的下发配置
        :return: {service_name: strategy_id}
        """

        global_config: DispatchGlobalConfig = global_config or DispatchGlobalConfig()

        nodes: list[dict[str, Any]] = []
        duplicated_service_names: set[str] = set(service_names)
        for node in ServiceHandler.list_nodes(self.bk_biz_id, self.app_name):
            if node.get("topo_key") in duplicated_service_names:
                nodes.append(node)

        miss_service_names: set[str] = duplicated_service_names - {node["topo_key"] for node in nodes}
        if miss_service_names:
            raise ValueError(_("部分服务不存在：{}").format(", ".join(miss_service_names)))

        # 1. 场景识别（RPC、容器、索引集）：
        # - 补充 context
        # - 补充标签
        # - 生成告警模板
        service_config_map: dict[str, DispatchConfig] = {}
        service_extra_config_map: dict[str, DispatchExtraConfig] = {
            extra_config.service_name: extra_config for extra_config in extra_configs or {}
        }
        query_template_context: dict[str, Any] = self.query_template_wrapper.get_default_context()
        for node in nodes:
            service_name: str = node["topo_key"]
            extra_config: DispatchExtraConfig = service_extra_config_map.get(
                service_name, DispatchExtraConfig(service_name=service_name)
            )
            service_config_map[service_name] = DispatchConfig.from_configs(
                global_config, extra_config, self.strategy_template, query_template_context
            )

        self._handle_rpc(nodes, service_config_map)

        # 2. 组装告警策略参数
        service_strategy_params_map: dict[str, dict[str, Any]] = {}
        for service_name, dispatch_config in service_config_map.items():
            builder: StrategyBuilder = StrategyBuilder(
                service_name=service_name,
                dispatch_config=dispatch_config,
                strategy_template=self.strategy_template,
                query_template_wrapper=self.query_template_wrapper,
            )
            service_strategy_params_map[service_name] = builder.build()

        # 3. 获取已下发的同源实例
        service_strategy_instance_map: dict[str, dict[str, Any]] = {}
        qs: models.QuerySet[StrategyInstance] = StrategyInstance.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=list(service_strategy_params_map.keys())
        )
        for strategy_instance in StrategyInstance.filter_same_origin_instances(
            qs, self.strategy_template.id, self.strategy_template.root_id
        ).values("id", "strategy_id", "service_name", "strategy_template_id", "root_strategy_template_id"):
            service_strategy_instance_map[strategy_instance["service_name"]] = strategy_instance

        to_be_created_strategies: list[dict[str, Any]] = []
        to_be_updated_strategies: list[dict[str, Any]] = []
        to_be_deleted_strategy_instance_ids: list[int] = []
        to_be_created_strategy_instance_objs: list[StrategyInstance] = []
        to_be_updated_strategy_instance_objs: list[StrategyInstance] = []
        for service_name, strategy_params in service_strategy_params_map.items():
            service_config: DispatchConfig = service_config_map[service_name]
            strategy_instance: dict[str, Any] | None = service_strategy_instance_map.get(service_name)
            if strategy_instance is None:
                # 没有已下发实例，直接新增。
                to_be_created_strategies.append(strategy_params)
            else:
                # 记录 ID，用于更新。
                strategy_params["id"] = strategy_instance["strategy_id"]
                to_be_updated_strategies.append(strategy_params)
                if strategy_instance["strategy_template_id"] != self.strategy_template.id:
                    # 当前模板的同源模板已下发，需删除实例记录。
                    to_be_deleted_strategy_instance_ids.append(strategy_instance["id"])
                else:
                    # 当前模板已下发，更新实例记录。
                    to_be_updated_strategy_instance_objs.append(
                        StrategyInstance(
                            id=strategy_instance["id"],
                            detect=service_config.detect,
                            algorithms=service_config.algorithms,
                            user_group_ids=service_config.user_group_ids,
                            context=service_config.context,
                            md5=calculate_strategy_md5_by_dispatch_config(service_config, self.query_template_wrapper),
                        )
                    )
                    continue

            to_be_created_strategy_instance_objs.append(
                StrategyInstance(
                    bk_biz_id=self.bk_biz_id,
                    app_name=self.app_name,
                    service_name=service_name,
                    strategy_id=strategy_params.get("id", 0),
                    strategy_template_id=self.strategy_template.id,
                    root_strategy_template_id=self.strategy_template.root_id,
                    detect=service_config.detect,
                    algorithms=service_config.algorithms,
                    user_group_ids=service_config.user_group_ids,
                    context=service_config.context,
                    md5=calculate_strategy_md5_by_dispatch_config(service_config, self.query_template_wrapper),
                )
            )

        # 4. 下发告警策略
        # 更新 or 创建策略，并收集 ID 映射关系。
        service_strategy_id_map: dict[str, int] = {}
        for strategy_params in to_be_created_strategies + to_be_updated_strategies:
            strategy_id: int = resource.strategies.save_strategy_v2(**strategy_params)["id"]
            service_strategy_id_map[strategy_params["service_name"]] = strategy_id

        for strategy_instance_obj in to_be_created_strategy_instance_objs:
            strategy_instance_obj.strategy_id = service_strategy_id_map[strategy_instance_obj.service_name]

        with transaction.atomic():
            StrategyInstance.objects.filter(
                bk_biz_id=self.bk_biz_id, app_name=self.app_name, id__in=to_be_deleted_strategy_instance_ids
            ).delete()
            if to_be_created_strategy_instance_objs:
                StrategyInstance.objects.bulk_create(to_be_created_strategy_instance_objs, batch_size=500)
            if to_be_updated_strategy_instance_objs:
                StrategyInstance.objects.bulk_update(
                    to_be_updated_strategy_instance_objs,
                    fields=["detect", "algorithms", "user_group_ids", "context", "md5"],
                    batch_size=500,
                )

        return service_strategy_id_map

    def check(self, service_names: list[str]) -> dict[str, dict[str, Any]]:
        """检查某个服务的策略下发结果
        pass
        """

    def preview(self, service_names: list[str]) -> dict[str, Any]:
        """预览某个服务的策略下发结果
        :param service_names: 服务列表
        :return: 策略模板详情
        """

        # 1. 场景识别（RPC、容器、索引集）：
        # - 补充 context
        pass
