"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import json
from collections import defaultdict
from typing import Any
from collections.abc import Iterable

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.generics import get_object_or_404
from rest_framework.serializers import Serializer, ValidationError

from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from bkmonitor.utils.user import get_global_user
from bkmonitor.query_template.core import QueryTemplateWrapper
from bkmonitor.query_template.constants import VariableType
from core.drf_resource import resource
from constants.alert import EventStatus
from utils import count_md5
from core.prometheus import metrics

from apm_web.models import StrategyTemplate, StrategyInstance, Application
from apm_web.decorators import user_visit_record
from . import serializers, handler, dispatch, helper, query_template, constants


class StrategyTemplateViewSet(GenericViewSet):
    queryset = StrategyTemplate.objects.all()
    serializer_class = serializers.StrategyTemplateModelSerializer

    def __init__(self, **kwargs):
        self._query_data = None
        super().__init__(**kwargs)

    @property
    def query_data(self) -> dict:
        if self._query_data:
            return self._query_data
        original_data = self.request.query_params if self.request.method == "GET" else self.request.data
        serializer_inst = self.get_serializer(data=original_data)
        serializer_inst.is_valid(raise_exception=True)
        self._query_data = serializer_inst.validated_data
        return self._query_data

    def get_permissions(self) -> list[InstanceActionForDataPermission]:
        if self.action in ["update", "destroy", "apply", "clone", "batch_partial_update", "unapply"]:
            return [
                InstanceActionForDataPermission(
                    "app_name",
                    [ActionEnum.MANAGE_APM_APPLICATION],
                    ResourceEnum.APM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        return [
            InstanceActionForDataPermission(
                "app_name",
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    def get_serializer_class(self) -> type[Serializer]:
        action_serializer_map = {
            "retrieve": serializers.StrategyTemplateDetailRequestSerializer,
            "destroy": serializers.StrategyTemplateDeleteRequestSerializer,
            "update": serializers.StrategyTemplateUpdateRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

    def get_queryset(self) -> QuerySet[StrategyTemplate]:
        return (
            super().get_queryset().filter(bk_biz_id=self.query_data["bk_biz_id"], app_name=self.query_data["app_name"])
        )

    def retrieve(self, *args, **kwargs) -> Response:
        return Response(helper.format2strategy_template_detail(self.get_object(), self.serializer_class))

    def destroy(self, *args, **kwargs) -> Response:
        strategy_template_obj: StrategyTemplate = self.get_object()
        if strategy_template_obj.type == constants.StrategyTemplateType.BUILTIN_TEMPLATE.value:
            raise ValidationError(_("内置模板不允许删除"))
        if StrategyInstance.objects.filter(strategy_template_id=strategy_template_obj.id).exists():
            raise ValidationError(_("已下发的模板不允许删除"))
        strategy_template_obj.delete()
        return Response({})

    def update(self, *args, **kwargs) -> Response:
        instance = self.serializer_class().update(self.get_object(), self.query_data)
        return Response(self.serializer_class(instance).data)

    def _filter_by_conditions(
        self, queryset: QuerySet[StrategyTemplate], conditions: list[dict[str, Any]]
    ) -> QuerySet[StrategyTemplate]:
        bk_biz_id = self.query_data["bk_biz_id"]
        app_name = self.query_data["app_name"]
        fuzzy_match_fields = ["name"]
        exact_match_fields = ["type", "system", "update_user", "is_enabled", "is_auto_apply"]
        for cond in conditions:
            q = Q()
            field_name = cond["key"]
            if field_name == "query":
                for v in cond["value"]:
                    for f in fuzzy_match_fields:
                        q |= Q(**{f"{f}__icontains": v})
            elif field_name in fuzzy_match_fields:
                for v in cond["value"]:
                    q |= Q(**{f"{field_name}__icontains": v})
            elif field_name in exact_match_fields:
                for v in cond["value"]:
                    q |= Q(**{f"{field_name}__exact": v})
            elif field_name == "applied_service_name":
                strategy_template_ids = StrategyInstance.objects.filter(
                    bk_biz_id=bk_biz_id, app_name=app_name, service_name__in=cond["value"]
                ).values_list("strategy_template_id", flat=True)
                q |= Q(id__in=strategy_template_ids)
            elif field_name == "user_group_id":
                for v in cond["value"]:
                    q |= Q(**{"user_group_ids__contains": v})
            queryset = queryset.filter(q)
        return queryset

    @staticmethod
    def _search_page(queryset: QuerySet[StrategyTemplate], page: int, page_size: int) -> QuerySet[StrategyTemplate]:
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return queryset[start_index:end_index]

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateSearchRequestSerializer)
    @user_visit_record
    def search(self, *args, **kwargs) -> Response:
        queryset = self._filter_by_conditions(self.get_queryset(), self.query_data["conditions"]).order_by(
            *self.query_data["order_by"]
        )
        total = queryset.count()
        if self.query_data["simple"]:
            strategy_template_list = serializers.StrategyTemplateSimpleSearchModelSerializer(queryset, many=True).data
        else:
            queryset = self._search_page(queryset, self.query_data["page"], self.query_data["page_size"])
            strategy_template_list = serializers.StrategyTemplateSearchModelSerializer(queryset, many=True).data
        return Response(
            {
                "total": total,
                "list": strategy_template_list,
            }
        )

    def _preview(self, strategy_template_obj: StrategyTemplate, service_name: str) -> dict[str, Any]:
        dispatcher: dispatch.StrategyDispatcher = dispatch.StrategyDispatcher(
            strategy_template=strategy_template_obj,
            query_template_wrapper=query_template.QueryTemplateWrapperFactory.get_wrapper(
                strategy_template_obj.query_template["bk_biz_id"], strategy_template_obj.query_template["name"]
            ),
        )
        entity_set: dispatch.EntitySet = dispatch.EntitySet(
            self.query_data["bk_biz_id"], self.query_data["app_name"], [service_name]
        )
        return dispatcher.preview(entity_set)[service_name]

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplatePreviewRequestSerializer)
    def preview(self, *args, **kwargs) -> Response:
        strategy_template_obj: StrategyTemplate = get_object_or_404(
            self.get_queryset(), id=self.query_data["strategy_template_id"]
        )
        preview_data: dict[str, Any] = self._preview(strategy_template_obj, self.query_data["service_name"])
        strategy_instance_obj: StrategyInstance = StrategyInstance.objects.filter(
            bk_biz_id=self.query_data["bk_biz_id"],
            app_name=self.query_data["app_name"],
            strategy_template_id=strategy_template_obj.pk,
            service_name=self.query_data["service_name"],
        ).first()
        if not strategy_instance_obj:
            return Response(preview_data)
        preview_data["detect"] = strategy_instance_obj.detect
        preview_data["algorithms"] = strategy_instance_obj.algorithms
        preview_data["user_group_list"] = list(helper.get_user_groups(strategy_instance_obj.user_group_ids).values())
        preview_data["context"] = {
            k: strategy_instance_obj.context.get(k, v) for k, v in preview_data["context"].items()
        }
        return Response(preview_data)

    def _get_id_strategy_map(self, ids: Iterable[int]) -> dict[int, dict[str, Any]]:
        return helper.get_id_strategy_map(self.query_data["bk_biz_id"], ids)

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateApplyRequestSerializer)
    @user_visit_record
    def apply(self, *args, **kwargs) -> Response:
        extra_config_map: dict[int, dict[str, dispatch.DispatchExtraConfig]] = {}
        if self.query_data["is_reuse_instance_config"]:
            # 复用已下发配置，查询实例快照并构造配置对象。
            strategy_instances: QuerySet[StrategyInstance] = StrategyInstance.objects.filter(
                bk_biz_id=self.query_data["bk_biz_id"],
                app_name=self.query_data["app_name"],
                service_name__in=self.query_data["service_names"],
                strategy_template_id__in=self.query_data["strategy_template_ids"],
            )
            for strategy_instance in strategy_instances:
                extra_config_map.setdefault(strategy_instance.strategy_template_id, {})[
                    strategy_instance.service_name
                ] = dispatch.DispatchExtraConfig(
                    service_name=strategy_instance.service_name,
                    context=strategy_instance.context,
                    detect=strategy_instance.detect,
                    algorithms=strategy_instance.algorithms,
                    user_group_list=[{"id": user_group_id} for user_group_id in strategy_instance.user_group_ids],
                )

        strategy_templates: list[StrategyTemplate] = list(
            self.get_queryset().filter(id__in=self.query_data["strategy_template_ids"])
        )
        for extra_config in self.query_data["extra_configs"]:
            service_name: str = extra_config["service_name"]
            strategy_template_id: int = extra_config.pop("strategy_template_id", 0)
            extra_config_obj: dispatch.DispatchExtraConfig = dispatch.DispatchExtraConfig(**extra_config)
            applied_config: dispatch.DispatchExtraConfig | None = extra_config_map.get(strategy_template_id, {}).get(
                service_name
            )
            if applied_config:
                # 合并配置，优先级：已下发配置 < 额外配置。
                applied_config.merge(extra_config_obj)
            else:
                extra_config_map.setdefault(strategy_template_id, {})[service_name] = extra_config_obj

        extra_configs_map: dict[int, list[dispatch.DispatchExtraConfig]] = defaultdict(list)
        for strategy_template_id, service_extra_config_map in extra_config_map.items():
            for extra_config in service_extra_config_map.values():
                extra_configs_map[strategy_template_id].append(extra_config)

        global_config = dispatch.DispatchGlobalConfig(**self.query_data["global_config"])
        apply_data = handler.StrategyTemplateHandler.apply(
            bk_biz_id=self.query_data["bk_biz_id"],
            app_name=self.query_data["app_name"],
            service_names=self.query_data["service_names"],
            strategy_templates=strategy_templates,
            extra_configs_map=extra_configs_map,
            global_config=global_config,
        )
        return Response({"app_name": self.query_data["app_name"], "list": apply_data})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateUnapplyResponseSerializer)
    def unapply(self, *args, **kwargs) -> Response:
        entity_set: dispatch.EntitySet = dispatch.EntitySet(
            self.query_data["bk_biz_id"], self.query_data["app_name"], self.query_data["service_names"]
        )
        strategy_instance_qs = StrategyInstance.objects.filter(
            bk_biz_id=self.query_data["bk_biz_id"],
            app_name=self.query_data["app_name"],
            service_name__in=entity_set.service_names,
            strategy_template_id__in=self.query_data["strategy_template_ids"],
        )
        ids: list[int] = list(strategy_instance_qs.values_list("strategy_id", flat=True))
        if not ids:
            return Response({})
        # 先删除策略
        resource.strategies.delete_strategy_v2({"bk_biz_id": self.query_data["bk_biz_id"], "ids": ids})
        # 再删除策略实例
        strategy_instance_qs.delete()

        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCheckRequestSerializer)
    def check(self, *args, **kwargs) -> Response:
        entity_set: dispatch.EntitySet = dispatch.EntitySet(
            self.query_data["bk_biz_id"], self.query_data["app_name"], self.query_data["service_names"]
        )
        strategy_templates: list[StrategyTemplate] = list(
            self.get_queryset().filter(id__in=self.query_data["strategy_template_ids"])
        )
        query_template_map: dict[tuple[int, str], QueryTemplateWrapper] = (
            query_template.QueryTemplateWrapperFactory.get_wrappers(
                [(obj.query_template["bk_biz_id"], obj.query_template["name"]) for obj in strategy_templates]
            )
        )

        def _check(_obj: StrategyTemplate) -> list[dict[str, Any]]:
            return dispatch.StrategyDispatcher(
                _obj, query_template_map[(_obj.query_template["bk_biz_id"], _obj.query_template["name"])]
            ).check(entity_set, self.query_data["is_check_diff"])

        # 批量进行模板下发检查
        pool = ThreadPool(5)
        check_results_iter: Iterable[list[dict[str, Any]]] = pool.imap_unordered(
            lambda _obj: _check(_obj), strategy_templates
        )
        pool.close()

        results: list[dict[str, Any]] = list(itertools.chain.from_iterable(check_results_iter))

        # 填充模板信息
        strategy_template_ids: set[int] = set()
        for result in results:
            if result.get("same_origin_strategy_template"):
                strategy_template_ids.add(result["same_origin_strategy_template"]["id"])

        def _set_name(_result: dict[str, Any], _field: str, _id_info_map: dict[int, dict[str, Any]]) -> None:
            try:
                _result[_field]["name"] = _id_info_map[_result[_field]["id"]]["name"]
            except (KeyError, TypeError):
                pass

        id_strategy_template_map: dict[int, dict[str, Any]] = {
            strategy_template["id"]: strategy_template
            for strategy_template in self.get_queryset().filter(id__in=strategy_template_ids).values("id", "name")
        }
        for result in results:
            _set_name(result, "same_origin_strategy_template", id_strategy_template_map)

        return Response({"list": results})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCloneRequestSerializer)
    def clone(self, *args, **kwargs) -> Response:
        compare_field_names: list[str] = [
            "algorithms",
            "detect",
            "user_group_ids",
            "context",
            "is_enabled",
            "is_auto_apply",
        ]
        source_compare_data: dict[str, Any] = {}
        edit_compare_data: dict[str, Any] = {}
        source_obj: StrategyTemplate = get_object_or_404(self.get_queryset(), id=self.query_data["source_id"])
        edit_data: dict[str, Any] = self.query_data["edit_data"]
        for field_name in compare_field_names:
            source_compare_data[field_name] = getattr(source_obj, field_name)
            edit_compare_data[field_name] = edit_data[field_name]

        qtw: QueryTemplateWrapper = query_template.QueryTemplateWrapperFactory.get_wrapper(
            bk_biz_id=source_obj.query_template["bk_biz_id"], name=source_obj.query_template["name"]
        )
        default_context: dict[str, Any] = qtw.get_default_context()
        edit_compare_data["context"] = {**default_context, **edit_compare_data["context"]}
        source_compare_data["context"] = {
            k: v
            for k, v in {**default_context, **source_compare_data["context"]}.items()
            if k in edit_compare_data["context"]
        }
        if count_md5(source_compare_data) == count_md5(edit_compare_data):
            raise ValidationError(_("克隆配置不能和源模板一致"))

        edit_data.update(
            {
                "bk_biz_id": self.query_data["bk_biz_id"],
                "app_name": self.query_data["app_name"],
                "parent_id": source_obj.id,
                "type": constants.StrategyTemplateType.APP_TEMPLATE.value,
                "root_id": source_obj.id
                if source_obj.type == constants.StrategyTemplateType.BUILTIN_TEMPLATE.value
                else source_obj.root_id,
            }
        )
        copy_field_names: list[str] = ["code", "system", "category", "monitor_type", "query_template"]
        for field_name in copy_field_names:
            edit_data[field_name] = getattr(source_obj, field_name)
        return Response({"id": serializers.StrategyTemplateModelSerializer().create(edit_data).id})

    @action(
        methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateBatchPartialUpdateRequestSerializer
    )
    def batch_partial_update(self, *args, **kwargs) -> Response:
        update_user: str | None = get_global_user()
        if not update_user:
            raise ValueError(_("未获取到用户信息"))

        edit_data: dict[str, Any] = {
            **self.query_data["edit_data"],
            "bk_biz_id": self.query_data["bk_biz_id"],
            "app_name": self.query_data["app_name"],
            "update_user": update_user,
            "update_time": timezone.now(),
        }

        editable_fields: list[str] = serializers.StrategyTemplateBatchPartialUpdateRequestSerializer.EDITABLE_FIELDS
        strategy_template_objs: list[StrategyTemplate] = list(
            self.get_queryset()
            .filter(id__in=self.query_data["ids"])
            .only(*editable_fields, "id", "root_id", "auto_applied_at")
        )
        model_serializer = serializers.StrategyTemplateModelSerializer
        model_serializer.validate_auto_apply(strategy_template_objs, edit_data)
        for obj in strategy_template_objs:
            model_serializer.set_auto_apply(edit_data, obj, edit_data["update_time"])

            # 设置更新字段。
            for field_name in edit_data:
                setattr(obj, field_name, edit_data[field_name])
            edit_data.pop("auto_applied_at", None)

        StrategyTemplate.objects.bulk_update(
            strategy_template_objs, fields=editable_fields + ["auto_applied_at"], batch_size=500
        )

        return Response({"ids": [obj.pk for obj in strategy_template_objs]})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCompareRequestSerializer)
    def compare(self, *args, **kwargs) -> Response:
        strategy_template_obj: StrategyTemplate = get_object_or_404(
            self.get_queryset(), id=self.query_data["strategy_template_id"]
        )
        applied_instance_obj: StrategyInstance | None = StrategyInstance.filter_same_origin_instances(
            StrategyInstance.objects.filter(
                bk_biz_id=self.query_data["bk_biz_id"],
                app_name=self.query_data["app_name"],
                service_name=self.query_data["service_name"],
            ),
            strategy_template_id=strategy_template_obj.pk,
            root_strategy_template_id=strategy_template_obj.root_id,
        ).first()
        if not applied_instance_obj:
            return Response({})

        diff_data: list[dict[str, Any]] = []
        current_dict: dict[str, Any] = self._preview(strategy_template_obj, self.query_data["service_name"])
        is_connector_update: bool = False
        for field_name in ["detect", "algorithms", "user_group_list", "context"]:
            # 第一步取值
            if field_name == "user_group_list":
                current = current_dict.get("user_group_list", [])
                applied_user_group_ids: set[int] = set(applied_instance_obj.user_group_ids)
                applied = list(helper.get_user_groups(applied_user_group_ids).values())
            else:
                current = current_dict.get(field_name)
                applied = getattr(applied_instance_obj, field_name)
                if field_name == "detect":
                    # 向前兼容
                    current.setdefault("connector", constants.DetectConnector.AND.value)
                    applied.setdefault("connector", constants.DetectConnector.AND.value)
                    is_connector_update = current["connector"] != applied["connector"]

            # 第二步比较
            # 如果检测算法关系发生变化，同时返回 algorithms
            is_algorithm_connector_changed = field_name == "algorithms" and is_connector_update
            if not is_algorithm_connector_changed and count_md5(current) == count_md5(applied):
                continue

            # 第三步对差异值进行排序处理
            if field_name == "algorithms":
                current.sort(key=lambda x: x["level"])
                applied.sort(key=lambda x: x["level"])
            elif field_name == "user_group_list":
                current.sort(key=lambda x: x["id"])
                applied.sort(key=lambda x: x["id"])

            if field_name != "context":
                diff_data.append({"field": field_name, "current": current, "applied": applied})
                continue

            # 根据 context 字段处理 variables
            name_variable_map: dict[str, dict[str, Any]] = {
                variable_dict["name"]: variable_dict for variable_dict in current_dict["query_template"]["variables"]
            }
            current_variables: list[dict[str, Any]] = []
            applied_variables: list[dict[str, Any]] = []
            for variable_name, variable_dict in name_variable_map.items():
                if variable_name in applied:
                    if count_md5(current.get(variable_name)) == count_md5(applied.get(variable_name)):
                        continue
                    applied_variables.append({**variable_dict, "value": applied.get(variable_name)})
                current_variables.append({**variable_dict, "value": current.get(variable_name)})

            for variable_name in applied:
                if variable_name not in name_variable_map:
                    applied_variables.append(
                        {
                            "name": variable_name,
                            "type": VariableType.CONSTANTS.value,
                            "alias": _("[变量已失效] {}").format(variable_name),
                            "value": "--",
                        }
                    )
            diff_data.append({"field": "variables", "current": current_variables, "applied": applied_variables})

        strategy_id: int = applied_instance_obj.strategy_id
        strategy_name: str = self._get_id_strategy_map(ids=[strategy_id]).get(strategy_id, {}).get("name", "")
        return Response(
            {
                "current": {"strategy_template_id": strategy_template_obj.pk},
                "applied": {
                    "strategy_template_id": applied_instance_obj.strategy_template_id,
                    "strategy": {"id": applied_instance_obj.strategy_id, "name": strategy_name},
                },
                "diff": diff_data,
            }
        )

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateAlertsRequestSerializer)
    def alerts(self, *args, **kwargs) -> Response:
        bk_biz_id = self.query_data.get("bk_biz_id")
        app_name = self.query_data.get("app_name")
        template_ids = self.query_data.get("ids", [])
        need_strategies = self.query_data.get("need_strategies", False)

        # 使用指定的模板ID查询策略实例
        strategy_instances = StrategyInstance.objects.filter(
            strategy_template_id__in=template_ids, bk_biz_id=bk_biz_id, app_name=app_name
        ).values("strategy_template_id", "strategy_id", "service_name")

        # 构建策略ID和模板映射集
        template_strategy_instance_map = defaultdict(list)
        strategy_ids = []
        for instance in strategy_instances:
            strategy_ids.append(instance["strategy_id"])
            template_strategy_instance_map.setdefault(instance["strategy_template_id"], []).append(
                {k: v for k, v in instance.items() if k != "strategy_template_id"}
            )

        # 查询告警数量
        alert_numbers = {}
        if strategy_ids:
            search_object = (
                AlertDocument.search(all_indices=True)
                .filter("term", **{"event.bk_biz_id": bk_biz_id})
                .filter("term", status=EventStatus.ABNORMAL)
                .filter("terms", strategy_id=strategy_ids)[:0]
            )
            search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000)
            search_result = search_object.execute()

            if search_result.aggs:
                for bucket in search_result.aggs.strategy_id.buckets:
                    alert_numbers[int(bucket.key)] = bucket.doc_count

        # 构建响应数据
        alert_list = []
        for template_id in template_ids:
            if template_id not in template_strategy_instance_map:
                alert_list.append(
                    {"id": template_id, "alert_number": 0, **({"strategies": []} if need_strategies else {})}
                )
                continue

            strategies_data = []
            template_alert_number = 0
            for strategy_instance in template_strategy_instance_map[template_id]:
                alert_number = alert_numbers.get(strategy_instance["strategy_id"], 0)
                template_alert_number += alert_number
                if need_strategies:
                    strategies_data.append({"alert_number": alert_number, **strategy_instance})

            alert_list.append(
                {
                    "id": template_id,
                    "alert_number": template_alert_number,
                    **({"strategies": strategies_data} if need_strategies else {}),
                }
            )

        return Response({"list": alert_list})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateOptionValuesRequestSerializer)
    def option_values(self, *args, **kwargs) -> Response:
        template_fields: list[str] = []
        instance_fields: list[str] = []
        for field_name in self.query_data["fields"]:
            if handler.StrategyTemplateOptionValues.is_matched(field_name):
                template_fields.append(field_name)
            elif handler.StrategyInstanceOptionValues.is_matched(field_name):
                instance_fields.append(field_name)

        strategy_template_qs = self.get_queryset()

        option_values: dict[str, list[dict[str, Any]]] = {}
        if template_fields:
            option_values.update(
                handler.StrategyTemplateOptionValues(strategy_template_qs).get_fields_option_values(template_fields)
            )
        if instance_fields:
            strategy_instance_qs = StrategyInstance.objects.filter(
                bk_biz_id=self.query_data["bk_biz_id"],
                app_name=self.query_data["app_name"],
                strategy_template_id__in=list(strategy_template_qs.values_list("id", flat=True)),
            )
            option_values.update(
                handler.StrategyInstanceOptionValues(strategy_instance_qs).get_fields_option_values(instance_fields)
            )

        return Response(option_values)

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateSearchRequestSerializer)
    def search_v2(self, *args, **kwargs) -> Response:
        # 执行过滤。
        queryset: QuerySet[StrategyTemplate] = self._filter_by_conditions(
            self.get_queryset(), self.query_data["conditions"]
        ).order_by(*self.query_data["order_by"])

        labels: dict[str, int] = {"bk_biz_id": self.query_data["bk_biz_id"], "app_name": self.query_data["app_name"]}
        with metrics.APM_STRATEGY_SEARCH_DB_REQUEST_DURATION_SECOND.labels(
            **labels, query_body=json.dumps(self.query_data)
        ).time():
            data_list: dict[str, Any] = serializers.StrategyTemplateV2SearchModelSerializer(queryset, many=True).data

        for data in data_list:
            metrics.APM_STRATEGY_SEARCH_NUM.labels(**labels, strategy_template_id=data["id"]).inc()

        return Response(
            {
                # 获取总数用于列表分分页。
                "total": self.get_queryset().count(),
                "list": data_list,
            }
        )
