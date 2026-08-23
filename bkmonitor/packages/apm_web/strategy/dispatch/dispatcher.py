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
import logging
from collections import defaultdict
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

logger = logging.getLogger(__name__)


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

    def _list_same_origin_instances(self, service_names: list[str]) -> dict[str, list[dict[str, Any]]]:
        """按服务收集已下发的同源实例。"""
        service_instances_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        qs: models.QuerySet[StrategyInstance] = StrategyInstance.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name, service_name__in=service_names
        )
        for strategy_instance in StrategyInstance.filter_same_origin_instances(
            qs, self.strategy_template.id, self.strategy_template.root_id
        ).values("id", "strategy_id", "service_name", "strategy_template_id", "root_strategy_template_id", "md5"):
            service_instances_map[strategy_instance["service_name"]].append(strategy_instance)
        return service_instances_map

    def _split_own_and_others(
        self, instances: list[dict[str, Any]]
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """拆分当前模板实例与其他同源实例。"""
        own_instance: dict[str, Any] | None = None
        other_instances: list[dict[str, Any]] = []
        for instance in instances:
            if instance["strategy_template_id"] == self.strategy_template.id:
                own_instance = instance
            else:
                other_instances.append(instance)
        return own_instance, other_instances

    def _build_created_instance(
        self, service_name: str, service_config: base.DispatchConfig, strategy_id: int = 0
    ) -> StrategyInstance:
        return StrategyInstance(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            service_name=service_name,
            strategy_id=strategy_id,
            strategy_template_id=self.strategy_template.id,
            root_strategy_template_id=self.strategy_template.root_id,
            detect=service_config.detect,
            algorithms=service_config.algorithms,
            user_group_ids=service_config.user_group_ids,
            context=service_config.context,
            md5=base.calculate_strategy_md5_by_dispatch_config(service_config, self.query_template_wrapper),
        )

    def _build_updated_instance(
        self, instance_id: int, service_name: str, service_config: base.DispatchConfig
    ) -> StrategyInstance:
        return StrategyInstance(
            id=instance_id,
            service_name=service_name,
            detect=service_config.detect,
            algorithms=service_config.algorithms,
            user_group_ids=service_config.user_group_ids,
            context=service_config.context,
            md5=base.calculate_strategy_md5_by_dispatch_config(service_config, self.query_template_wrapper),
        )

    def dispatch(
        self,
        entity_set: entity.EntitySet,
        global_config: base.DispatchGlobalConfig | None = None,
        extra_configs: list[base.DispatchExtraConfig] | None = None,
        raise_exception: bool = True,
        *,
        overwrite_same_origin: bool = True,
        keep_strategy_template_ids: list[int] | None = None,
    ) -> dict[str, int]:
        """批量下发策略到服务
        :param entity_set: 实体集
        :param global_config: 全局下发配置
        :param extra_configs: 额外的下发配置
        :param raise_exception: 是否在服务校验过程中抛出异
        :param overwrite_same_origin: 是否覆盖同类模板策略
        :param keep_strategy_template_ids: 本次一并下发、不可覆盖的模板 ID
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

        keep_ids: set[int] = set(keep_strategy_template_ids or [])
        keep_ids.add(self.strategy_template.id)
        service_instances_map: dict[str, list[dict[str, Any]]] = self._list_same_origin_instances(
            entity_set.service_names
        )
        id_strategy_map: dict[int, dict[str, Any]] = helper.get_id_strategy_map(
            self.bk_biz_id,
            [instance["strategy_id"] for instances in service_instances_map.values() for instance in instances],
        )

        to_be_created_strategies: list[dict[str, Any]] = []
        to_be_updated_strategies: list[dict[str, Any]] = []
        to_be_created_strategy_instance_objs: list[StrategyInstance] = []
        to_be_updated_strategy_instance_objs: list[StrategyInstance] = []
        service_delete_instance_ids: dict[str, list[int]] = defaultdict(list)
        service_delete_strategy_ids: dict[str, list[int]] = defaultdict(list)

        for service_name, strategy_params in service_strategy_params_map.items():
            service_config: base.DispatchConfig = service_config_map[service_name]
            own_instance, other_instances = self._split_own_and_others(service_instances_map.get(service_name, []))
            overwrite_instances: list[dict[str, Any]] = [
                instance
                for instance in other_instances
                if overwrite_same_origin and instance["strategy_template_id"] not in keep_ids
            ]

            if own_instance is not None:
                if own_instance["strategy_id"] in id_strategy_map:
                    strategy_params["id"] = own_instance["strategy_id"]
                    to_be_updated_strategies.append(strategy_params)
                else:
                    to_be_created_strategies.append(strategy_params)
                to_be_updated_strategy_instance_objs.append(
                    self._build_updated_instance(own_instance["id"], service_name, service_config)
                )
            elif overwrite_instances and overwrite_instances[0]["strategy_id"] in id_strategy_map:
                # 当前模板尚未下发：复用一条可覆盖实例，保持原策略 ID 的覆盖语义。
                reused_instance: dict[str, Any] = overwrite_instances[0]
                strategy_params["id"] = reused_instance["strategy_id"]
                to_be_updated_strategies.append(strategy_params)
                service_delete_instance_ids[service_name].append(reused_instance["id"])
                to_be_created_strategy_instance_objs.append(
                    self._build_created_instance(service_name, service_config, reused_instance["strategy_id"])
                )
                overwrite_instances = overwrite_instances[1:]
            else:
                to_be_created_strategies.append(strategy_params)
                to_be_created_strategy_instance_objs.append(self._build_created_instance(service_name, service_config))

            for instance in overwrite_instances:
                service_delete_instance_ids[service_name].append(instance["id"])
                if instance["strategy_id"] in id_strategy_map:
                    service_delete_strategy_ids[service_name].append(instance["strategy_id"])

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
        invalid_service_name_set: set[str] = set(invalid_service_names)
        to_be_created_strategy_instance_objs = [
            obj for obj in to_be_created_strategy_instance_objs if obj.service_name not in invalid_service_name_set
        ]
        to_be_updated_strategy_instance_objs = [
            obj for obj in to_be_updated_strategy_instance_objs if obj.service_name not in invalid_service_name_set
        ]
        to_be_deleted_strategy_instance_ids: list[int] = [
            instance_id
            for service_name, instance_ids in service_delete_instance_ids.items()
            if service_name not in invalid_service_name_set
            for instance_id in instance_ids
        ]
        to_be_deleted_strategy_ids: list[int] = list(
            {
                strategy_id
                for service_name, strategy_ids in service_delete_strategy_ids.items()
                if service_name not in invalid_service_name_set
                for strategy_id in strategy_ids
            }
        )
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

        if to_be_deleted_strategy_ids:
            try:
                resource.strategies.delete_strategy_v2({"bk_biz_id": self.bk_biz_id, "ids": to_be_deleted_strategy_ids})
            except Exception as exc:  # pylint: disable=broad-except
                # 同源模板并行下发时，可能同时删除同一条重复策略。
                logger.warning(
                    "failed to delete overwritten strategies: bk_biz_id=%s, app_name=%s, ids=%s, error=%s",
                    self.bk_biz_id,
                    self.app_name,
                    to_be_deleted_strategy_ids,
                    exc,
                )

        if invalid_service_names:
            raise ValueError(_("创建部分服务策略失败：{}").format("，".join(invalid_service_names)))

        return service_strategy_id_map

    def check(self, entity_set: entity.EntitySet, is_check_diff: bool = False) -> list[dict[str, Any]]:
        """检查某个服务的策略下发结果"""
        service_instances_map: dict[str, list[dict[str, Any]]] = self._list_same_origin_instances(
            entity_set.service_names
        )
        id_strategy_map: dict[int, dict[str, Any]] = helper.get_id_strategy_map(
            self.bk_biz_id,
            [instance["strategy_id"] for instances in service_instances_map.values() for instance in instances],
        )

        results: list[dict[str, Any]] = []
        diff_instance_map: dict[str, dict[str, Any]] = {}
        for service_name in entity_set.service_names:
            own_instance, other_instances = self._split_own_and_others(service_instances_map.get(service_name, []))
            live_own: dict[str, Any] | None = (
                own_instance if own_instance and own_instance["strategy_id"] in id_strategy_map else None
            )
            live_others: list[dict[str, Any]] = [
                instance for instance in other_instances if instance["strategy_id"] in id_strategy_map
            ]
            same_origin_strategy_templates: list[dict[str, Any]] = [
                {
                    "id": instance["strategy_template_id"],
                    "strategy": {
                        "id": instance["strategy_id"],
                        "name": id_strategy_map[instance["strategy_id"]]["name"],
                    },
                }
                for instance in live_others
            ]
            result: dict[str, Any] = {
                "service_name": service_name,
                "strategy_template_id": self.strategy_template.id,
                "same_origin_strategy_template": (
                    {"id": same_origin_strategy_templates[0]["id"]} if same_origin_strategy_templates else None
                ),
                "same_origin_strategy_templates": same_origin_strategy_templates,
                "strategy": None,
                "has_been_applied": False,
            }
            diff_instance: dict[str, Any] | None = live_own or (live_others[0] if live_others else None)
            if live_own is not None:
                result["has_been_applied"] = True
                result["strategy"] = {
                    "id": live_own["strategy_id"],
                    "name": id_strategy_map[live_own["strategy_id"]]["name"],
                }
            elif live_others:
                result["strategy"] = same_origin_strategy_templates[0]["strategy"]

            if diff_instance is not None:
                diff_instance_map[service_name] = diff_instance
            results.append(result)

        if not is_check_diff:
            return results

        # raise_exception=False：跳过不符合当前模板所属系统类型的服务，并且对 results 进行二次过滤。
        service_config_map: dict[str, base.DispatchConfig] = self._enrich(entity_set, raise_exception=False)
        results = [result for result in results if result["service_name"] in service_config_map]

        service_result_map: dict[str, dict[str, Any]] = {result["service_name"]: result for result in results}
        for service_name, dispatch_config in service_config_map.items():
            result: dict[str, Any] = service_result_map[service_name]
            diff_instance = diff_instance_map.get(service_name)
            if diff_instance is None:
                result["has_diff"] = False
                continue

            md5: str = base.calculate_strategy_md5_by_dispatch_config(dispatch_config, self.query_template_wrapper)
            result["has_diff"] = diff_instance["md5"] != md5
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
