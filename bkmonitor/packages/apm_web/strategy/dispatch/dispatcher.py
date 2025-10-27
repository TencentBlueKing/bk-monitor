"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from threading import Lock
from typing import Any

from django.db import models, transaction

from apm_web.models import StrategyTemplate, StrategyInstance
from bkmonitor.query_template.core import QueryTemplateWrapper
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from django.utils.translation import gettext_lazy as _
from core.drf_resource import resource
from . import entity, enricher, builder, base
from .. import helper, serializers


class StrategyDispatcher:
    def __init__(self, strategy_template: StrategyTemplate, query_template_wrapper: QueryTemplateWrapper) -> None:
        self.bk_biz_id: int = strategy_template.bk_biz_id
        self.app_name: str = strategy_template.app_name
        self.strategy_template: StrategyTemplate = strategy_template
        self.query_template_wrapper: QueryTemplateWrapper = query_template_wrapper

    def _enrich(
        self,
        entity_set: entity.EntitySet,
        global_config: base.DispatchGlobalConfig | None = None,
        extra_configs: list[base.DispatchExtraConfig] | None = None,
        raise_exception: bool = True,
    ) -> dict[str, base.DispatchConfig]:
        """丰富下发配置"""
        service_config_map: dict[str, base.DispatchConfig] = {}
        global_config: base.DispatchGlobalConfig = global_config or base.DispatchGlobalConfig()
        service_extra_config_map: dict[str, base.DispatchExtraConfig] = {
            extra_config.service_name: extra_config for extra_config in extra_configs or {}
        }
        query_template_context: dict[str, Any] = self.query_template_wrapper.get_default_context()

        for service_name in entity_set.service_names:
            extra_config: base.DispatchExtraConfig = service_extra_config_map.get(
                service_name, base.DispatchExtraConfig(service_name=service_name)
            )
            service_config_map[service_name] = base.DispatchConfig.from_configs(
                global_config, extra_config, self.strategy_template, query_template_context
            )

        validated_service_names: list[str] = enricher.ENRICHER_CLASSES[self.strategy_template.system](
            entity_set, self.strategy_template, self.query_template_wrapper
        ).enrich(service_config_map, raise_exception=raise_exception)

        # 仅保留通过校验的服务
        return {service_name: service_config_map[service_name] for service_name in validated_service_names}

    def _is_same_origin_instance(self, instance: dict[str, Any]) -> bool:
        """判断是否为同源模板的下发实例
        :param instance: 下发实例
        :return:
        """
        return instance["strategy_template_id"] != self.strategy_template.id

    def dispatch(
        self,
        entity_set: entity.EntitySet,
        global_config: base.DispatchGlobalConfig | None = None,
        extra_configs: list[base.DispatchExtraConfig] | None = None,
        raise_exception: bool = True,
    ) -> dict[str, int]:
        """批量下发策略到服务
        :param entity_set: 实体集
        :param global_config: 全局下发配置
        :param extra_configs: 额外的下发配置
        :param raise_exception: 是否在服务校验过程中抛出异
        :return: {service_name: strategy_id}
        """
        # 组装告警策略参数
        service_strategy_params_map: dict[str, dict[str, Any]] = {}
        service_config_map: dict[str, base.DispatchConfig] = self._enrich(
            entity_set, global_config, extra_configs, raise_exception
        )
        for service_name, dispatch_config in service_config_map.items():
            service_strategy_params_map[service_name] = builder.StrategyBuilder(
                service_name=service_name,
                dispatch_config=dispatch_config,
                strategy_template=self.strategy_template,
                query_template_wrapper=self.query_template_wrapper,
            ).build()

        # 获取已下发的同源实例
        service_strategy_instance_map: dict[str, dict[str, Any]] = {}
        qs: models.QuerySet[StrategyInstance] = StrategyInstance.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=entity_set.service_names
        )
        for strategy_instance in StrategyInstance.filter_same_origin_instances(
            qs, self.strategy_template.id, self.strategy_template.root_id
        ).values("id", "strategy_id", "service_name", "strategy_template_id", "root_strategy_template_id"):
            service_strategy_instance_map[strategy_instance["service_name"]] = strategy_instance

        id_strategy_map: dict[int, dict[str, Any]] = helper.get_id_strategy_map(
            self.bk_biz_id, [instance["strategy_id"] for instance in service_strategy_instance_map.values()]
        )

        to_be_created_strategies: list[dict[str, Any]] = []
        to_be_updated_strategies: list[dict[str, Any]] = []
        to_be_deleted_strategy_instance_ids: list[int] = []
        to_be_created_strategy_instance_objs: list[StrategyInstance] = []
        to_be_updated_strategy_instance_objs: list[StrategyInstance] = []
        for service_name, strategy_params in service_strategy_params_map.items():
            service_config: base.DispatchConfig = service_config_map[service_name]
            strategy_instance: dict[str, Any] | None = service_strategy_instance_map.get(service_name)
            if strategy_instance is None:
                # 没有已下发实例直接新增。
                to_be_created_strategies.append(strategy_params)
            else:
                # 记录 ID，用于更新。
                if strategy_instance["strategy_id"] in id_strategy_map:
                    # 已下发实例对应的策略存在，更新策略。
                    strategy_params["id"] = strategy_instance["strategy_id"]
                    to_be_updated_strategies.append(strategy_params)
                else:
                    # 已下发实例对应的策略不存在，视为未下发，新增策略。
                    to_be_created_strategies.append(strategy_params)

                if self._is_same_origin_instance(strategy_instance):
                    # 当前模板的同源模板已下发，需删除实例记录。
                    to_be_deleted_strategy_instance_ids.append(strategy_instance["id"])
                else:
                    # 当前模板已下发，更新实例记录。
                    to_be_updated_strategy_instance_objs.append(
                        StrategyInstance(
                            id=strategy_instance["id"],
                            service_name=service_name,
                            detect=service_config.detect,
                            algorithms=service_config.algorithms,
                            user_group_ids=service_config.user_group_ids,
                            context=service_config.context,
                            md5=base.calculate_strategy_md5_by_dispatch_config(
                                service_config, self.query_template_wrapper
                            ),
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
                    md5=base.calculate_strategy_md5_by_dispatch_config(service_config, self.query_template_wrapper),
                )
            )

        def _save_strategy(_params: dict[str, Any]):
            _strategy_id: int = resource.strategies.save_strategy_v2(**_params)["id"]
            with lock:
                service_strategy_id_map[_params["service_name"]] = _strategy_id

        # 下发告警策略：更新 or 创建策略，并收集 ID 映射关系。
        lock: Lock = Lock()
        service_strategy_id_map: dict[str, int] = {}
        run_threads(
            [
                InheritParentThread(target=_save_strategy, args=(_strategy_params,))
                for _strategy_params in to_be_created_strategies + to_be_updated_strategies
            ]
        )

        invalid_service_names: list[str] = []
        for strategy_instance_obj in to_be_created_strategy_instance_objs + to_be_updated_strategy_instance_objs:
            # 回填策略 ID。
            try:
                strategy_instance_obj.strategy_id = service_strategy_id_map[strategy_instance_obj.service_name]
            except KeyError:
                # 没有策略 ID，说明下发失败。
                invalid_service_names.append(strategy_instance_obj.service_name)

        # 仅对策略下发成功的服务进行实例记录的创建或更新，尽可能记录成功下发的策略，而不是遇到异常即刻抛出，减少脏数据的产生。
        to_be_created_strategy_instance_objs = [
            obj for obj in to_be_created_strategy_instance_objs if obj.service_name not in invalid_service_names
        ]
        to_be_updated_strategy_instance_objs = [
            obj for obj in to_be_updated_strategy_instance_objs if obj.service_name not in invalid_service_names
        ]
        with transaction.atomic():
            StrategyInstance.objects.filter(
                bk_biz_id=self.bk_biz_id, app_name=self.app_name, id__in=to_be_deleted_strategy_instance_ids
            ).delete()
            if to_be_created_strategy_instance_objs:
                StrategyInstance.objects.bulk_create(to_be_created_strategy_instance_objs, batch_size=500)
            if to_be_updated_strategy_instance_objs:
                StrategyInstance.objects.bulk_update(
                    to_be_updated_strategy_instance_objs,
                    fields=["detect", "algorithms", "user_group_ids", "context", "md5", "strategy_id"],
                    batch_size=500,
                )

        if invalid_service_names:
            raise ValueError(_("创建部分服务策略失败：{}").format("，".join(invalid_service_names)))

        return service_strategy_id_map

    def check(self, entity_set: entity.EntitySet, is_check_diff: bool = False) -> list[dict[str, Any]]:
        """检查某个服务的策略下发结果"""

        # 获取已下发的同源实例
        service_strategy_instance_map: dict[str, dict[str, Any]] = {}
        qs: models.QuerySet[StrategyInstance] = StrategyInstance.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=entity_set.service_names
        )
        for strategy_instance in StrategyInstance.filter_same_origin_instances(
            qs, self.strategy_template.id, self.strategy_template.root_id
        ).values("id", "strategy_id", "service_name", "strategy_template_id", "root_strategy_template_id", "md5"):
            service_strategy_instance_map[strategy_instance["service_name"]] = strategy_instance

        id_strategy_map: dict[int, dict[str, Any]] = helper.get_id_strategy_map(
            self.bk_biz_id, [instance["strategy_id"] for instance in service_strategy_instance_map.values()]
        )

        results: list[dict[str, Any]] = []
        for service_name in entity_set.service_names:
            result: dict[str, Any] = {
                "service_name": service_name,
                "strategy_template_id": self.strategy_template.id,
                "same_origin_strategy_template": None,
                "strategy": None,
                "has_been_applied": False,
            }
            strategy_instance: dict[str, Any] | None = service_strategy_instance_map.get(service_name)
            if strategy_instance is None:
                results.append(result)
                continue

            try:
                strategy_id: int = strategy_instance["strategy_id"]
                result["strategy"] = {"id": strategy_id, "name": id_strategy_map[strategy_id]["name"]}
            except KeyError:
                # 已下发策略被删除，视为未下发。
                results.append(result)
                continue

            if self._is_same_origin_instance(strategy_instance):
                result["same_origin_strategy_template"] = {"id": strategy_instance["strategy_template_id"]}
            else:
                result["has_been_applied"] = True

            results.append(result)

        if not is_check_diff:
            return results

        # raise_exception=False：跳过不符合当前模板所属系统类型的服务，并且对 results 进行二次过滤。
        service_config_map: dict[str, base.DispatchConfig] = self._enrich(entity_set, raise_exception=False)
        results = [result for result in results if result["service_name"] in service_config_map]

        service_result_map: dict[str, dict[str, Any]] = {result["service_name"]: result for result in results}
        for service_name, dispatch_config in service_config_map.items():
            result: dict[str, Any] = service_result_map[service_name]
            if result.get("strategy") is None:
                # 没有下发实例，无需对比。
                result["has_diff"] = False
                continue

            md5: str = base.calculate_strategy_md5_by_dispatch_config(dispatch_config, self.query_template_wrapper)
            result["has_diff"] = service_strategy_instance_map[service_name]["md5"] != md5
        return results

    def preview(self, entity_set: entity.EntitySet) -> dict[str, dict[str, Any]]:
        """预览某个服务的策略下发结果
        :param entity_set: 实体集
        :return: 服务<>策略模板详情
        """
        strategy_template_detail: dict[str, Any] = helper.format2strategy_template_detail(
            self.strategy_template, serializers.StrategyTemplateModelSerializer
        )
        service_strategy_template_detail: dict[str, dict[str, Any]] = {}
        for service_name, dispatch_config in self._enrich(entity_set).items():
            copy_strategy_template_detail: dict[str, Any] = copy.deepcopy(strategy_template_detail)
            copy_strategy_template_detail["context"] = dispatch_config.context
            service_strategy_template_detail[service_name] = copy_strategy_template_detail
        return service_strategy_template_detail
