"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

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

from core.drf_resource import resource
from bkmonitor.documents import AlertDocument
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from bkmonitor.utils.user import get_global_user
from bkmonitor.query_template.core import QueryTemplateWrapper
from bkmonitor.query_template.constants import VariableType
from constants.alert import EventStatus
from utils import count_md5

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
        if self.action in ["update", "destroy", "apply", "clone", "batch_partial_update"]:
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
        return Response(self._preview(strategy_template_obj, self.query_data["service_name"]))

    def _get_id_strategy_map(self, ids: Iterable[int]) -> dict[int, dict[str, Any]]:
        strategies: list[dict[str, Any]] = resource.strategies.plain_strategy_list_v2(
            {"bk_biz_id": self.query_data["bk_biz_id"], "ids": list(ids)}
        )
        return {
            strategy_dict["id"]: {"id": strategy_dict["id"], "name": strategy_dict["name"]}
            for strategy_dict in strategies
        }

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateApplyRequestSerializer)
    @user_visit_record
    def apply(self, *args, **kwargs) -> Response:
        extra_configs_map: dict[int, list[dispatch.DispatchExtraConfig]] = defaultdict(list)
        for extra_config in self.query_data["extra_configs"]:
            strategy_template_id: int = extra_config.pop("strategy_template_id", 0)
            extra_configs_map[strategy_template_id].append(dispatch.DispatchExtraConfig(**extra_config))

        entity_set: dispatch.EntitySet = dispatch.EntitySet(
            self.query_data["bk_biz_id"], self.query_data["app_name"], self.query_data["service_names"]
        )
        strategy_templates: list[StrategyTemplate] = list(
            self.get_queryset().filter(id__in=self.query_data["strategy_template_ids"])
        )

        strategy_ids: list[int] = []
        template_dispatch_map: dict[int, dict[str, int]] = {}
        query_template_map: dict[tuple[int, str], QueryTemplateWrapper] = (
            handler.StrategyTemplateHandler.get_query_template_map(strategy_templates)
        )
        global_config = dispatch.DispatchGlobalConfig(**self.query_data["global_config"])
        for strategy_template_obj in strategy_templates:
            qtw = handler.StrategyTemplateHandler.get_query_template_or_none(strategy_template_obj, query_template_map)
            dispatcher = dispatch.StrategyDispatcher(strategy_template_obj, qtw)
            service_strategy_map: dict[str, int] = dispatcher.dispatch(
                entity_set,
                global_config,
                extra_configs_map.get(strategy_template_obj.pk, []),
            )
            strategy_ids.extend(list(service_strategy_map.values()))
            template_dispatch_map[strategy_template_obj.pk] = service_strategy_map

        apply_data: list[dict[str, Any]] = []
        id_strategy_map = self._get_id_strategy_map(strategy_ids)
        for strategy_template_id, service_strategy_map in template_dispatch_map.items():
            for service_name, strategy_id in service_strategy_map.items():
                apply_data.append(
                    {
                        "service_name": service_name,
                        "strategy_template_id": strategy_template_id,
                        "strategy": {
                            "id": strategy_id,
                            "name": id_strategy_map.get(strategy_id, {}).get("name", ""),
                        },
                    }
                )
        return Response({"app_name": self.query_data["app_name"], "list": apply_data})

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

        # 批量进行模板下发检查
        # TODO 此处可以改成多线程
        results: list[dict[str, Any]] = []
        for strategy_template_obj in strategy_templates:
            qtw = query_template_map[
                (strategy_template_obj.query_template["bk_biz_id"], strategy_template_obj.query_template["name"])
            ]
            dispatcher: dispatch.StrategyDispatcher = dispatch.StrategyDispatcher(strategy_template_obj, qtw)
            results.extend(dispatcher.check(entity_set, self.query_data["is_check_diff"]))

        # 填充模板、策略信息
        strategy_ids: set[int] = set()
        strategy_template_ids: set[int] = set()
        for result in results:
            if result.get("strategy"):
                strategy_ids.add(result["strategy"]["id"])
            if result.get("same_origin_strategy_template"):
                strategy_template_ids.add(result["same_origin_strategy_template"]["id"])

        def _set_name(_result: dict[str, Any], _field: str, _id_info_map: dict[int, dict[str, Any]]) -> None:
            try:
                _result[_field]["name"] = _id_info_map[_result[_field]["id"]]["name"]
            except (KeyError, TypeError):
                pass

        id_strategy_map: dict[int, dict[str, Any]] = self._get_id_strategy_map(strategy_ids)
        id_strategy_template_map: dict[int, dict[str, Any]] = {
            strategy_template["id"]: strategy_template
            for strategy_template in self.get_queryset().filter(id__in=strategy_template_ids).values("id", "name")
        }
        for result in results:
            _set_name(result, "strategy", id_strategy_map)
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
        for field_name in ["detect", "algorithms", "user_group_list", "context"]:
            # 第一步取值
            if field_name == "user_group_list":
                current = current_dict.get("user_group_list", [])
                applied_user_group_ids: set[int] = set(applied_instance_obj.user_group_ids)
                applied = list(helper.get_user_groups(applied_user_group_ids).values())
            else:
                current = current_dict.get(field_name)
                applied = getattr(applied_instance_obj, field_name)

            # 第二步比较
            if count_md5(current) == count_md5(applied):
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
