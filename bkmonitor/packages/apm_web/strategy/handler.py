from typing import Any
from collections.abc import Iterable

from django.db.models import QuerySet, Q
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from rest_framework import serializers
from bkmonitor.models import UserGroup, StrategyModel
from constants.apm import CachedEnum
from apm_web.strategy.constants import (
    StrategyTemplateSystem,
    StrategyTemplateIsEnabled,
    StrategyTemplateIsAutoApply,
    DEFAULT_ROOT_ID,
)
from apm_web.models import StrategyTemplate, StrategyInstance


def get_user_groups(user_group_ids: Iterable[int]) -> dict[int, dict[str, int | str]]:
    return {
        user_group["id"]: user_group
        for user_group in UserGroup.objects.filter(id__in=user_group_ids).values("id", "name")
    }


class OptionValues:
    _SUPPORT_FIELDS: list[str] = []
    _FIELD_ALIAS: dict[str, CachedEnum] = {}

    def __init__(self, queryset: QuerySet):
        self.queryset = queryset

    @classmethod
    def is_matched(cls, field_name: str) -> bool:
        return field_name in cls._SUPPORT_FIELDS

    def _get_default(self, field_name: str) -> list[dict[str, Any]]:
        option_values: list[dict[str, Any]] = []
        for field_value in self.queryset.values_list(field_name, flat=True).distinct():
            alias_enum = self._FIELD_ALIAS.get(field_name)
            option_values.append(
                {
                    "value": field_value,
                    "alias": field_value if alias_enum is None else alias_enum.from_value(field_value).label,
                }
            )
        return option_values

    def get_fields_option_values(self, fields: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        return {field_name: getattr(self, f"get_{field_name}")() for field_name in fields}


class StrategyTemplateOptionValues(OptionValues):
    _SUPPORT_FIELDS: list[str] = ["system", "user_group_id", "update_user", "is_enabled", "is_auto_apply"]
    _FIELD_ALIAS: dict[str, CachedEnum] = {
        "system": StrategyTemplateSystem,
        "is_enabled": StrategyTemplateIsEnabled,
        "is_auto_apply": StrategyTemplateIsAutoApply,
    }

    def get_user_group_id(self) -> list[dict[str, Any]]:
        user_group_ids: set[int] = set()
        for partial_user_group_ids in self.queryset.values_list("user_group_ids", flat=True):
            user_group_ids.update(partial_user_group_ids)
        return [
            {"value": user_group_id, "alias": user_group["name"]}
            for user_group_id, user_group in get_user_groups(user_group_ids).items()
        ]

    def get_system(self) -> list[dict[str, str]]:
        return self._get_default("system")

    def get_update_user(self) -> list[dict[str, str]]:
        return self._get_default("update_user")

    def get_is_enabled(self) -> list[dict[str, Any]]:
        return self._get_default("is_enabled")

    def get_is_auto_apply(self) -> list[dict[str, Any]]:
        return self._get_default("is_auto_apply")


class StrategyInstanceOptionValues(OptionValues):
    _SUPPORT_FIELDS: list[str] = ["applied_service_name"]

    def get_applied_service_name(self) -> list[dict[str, str]]:
        return self._get_default("service_name")


class StrategyTemplateCheckHandler:
    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        strategy_template_ids: list[int],
        service_names: list[str],
        strategy_template_qs: QuerySet[StrategyTemplate],
    ):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.strategy_template_ids = strategy_template_ids
        self.service_names = service_names
        self.strategy_template_qs = strategy_template_qs

    @cached_property
    def root_template_ids(self) -> list[int]:
        """根模板的id
        不同于 root_id，root_template_id 是根模板的 id
        """
        root_template_ids: set[int] = set()
        templates: list[dict[str, Any]] = list(
            self.strategy_template_qs.filter(id__in=self.strategy_template_ids).values("id", "root_id")
        )
        for templ in templates:
            if templ["root_id"] == DEFAULT_ROOT_ID:
                root_template_ids.add(templ["id"])
            else:
                root_template_ids.add(templ["root_id"])
        return list(root_template_ids)

    @cached_property
    def template_obj_by_id(self) -> dict[int, StrategyTemplate]:
        """同源模板的查询集
        查询逻辑：
        1. 传的内置模板
        1.1 查对应内置模板 -> id=strategy_template_id
        1.2 查对应内置模板的同源模板 -> root_id=root_template_id
        2. 传的克隆模板
        2.1 查对应克隆模板 -> id=strategy_template_id
        2.2 查对应克隆模板的同源模板 -> id=root_template_id | root_id=root_template_id
        """
        same_origin_template_qs: QuerySet[StrategyTemplate] = self.strategy_template_qs.filter(
            Q(id__in=set(self.strategy_template_ids + self.root_template_ids)) | Q(root_id__in=self.root_template_ids)
        )
        return {templ.pk: templ for templ in same_origin_template_qs}

    @cached_property
    def same_origin_instances(self) -> list[dict[str, Any]]:
        """同源模板的策略实例查询集"""
        return list(
            StrategyInstance.objects.filter(
                bk_biz_id=self.bk_biz_id,
                app_name=self.app_name,
                service_name__in=self.service_names,
            )
            .filter(
                Q(strategy_template_id__in=set(self.strategy_template_ids + self.root_template_ids))
                | Q(root_strategy_template_id__in=self.root_template_ids)
            )
            .values("service_name", "strategy_id", "md5", "strategy_template_id", "root_strategy_template_id")
        )

    @cached_property
    def instance_map(self) -> dict[tuple[int, str], dict[str, Any]]:
        """同源模板的策略实例映射
        :key (tuple[int, str]): (root_template_id, service_name)
        :value (StrategyInstance): 同源模板的策略实例
        """
        instance_map: dict[tuple[int, str], dict[str, Any]] = {}
        for instance_dict in self.same_origin_instances:
            root_template_id = (
                instance_dict["root_strategy_template_id"]
                if instance_dict["root_strategy_template_id"] != DEFAULT_ROOT_ID
                else instance_dict["strategy_template_id"]
            )
            map_key: tuple[int, str] = (root_template_id, instance_dict["service_name"])
            if map_key in instance_map:
                raise serializers.ValidationError(
                    _(f"数据异常，id 为 {instance_dict['strategy_template_id']} 的策略模板存在多个策略实例")
                )
            instance_map[map_key] = instance_dict
        return instance_map

    @cached_property
    def strategy_dict_by_id(self) -> dict[int, dict[str, Any]]:
        strategy_ids: set[int] = {instance_dict["strategy_id"] for instance_dict in self.same_origin_instances}
        strategies: list[dict[str, Any]] = list(
            StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, id__in=strategy_ids).values("id", "name")
        )
        return {strategy["id"]: strategy for strategy in strategies}

    def get_check_results(self) -> list[dict[str, Any]]:
        check_results: list[dict[str, Any]] = []
        for service_name in self.service_names:
            for template_id in self.strategy_template_ids:
                check_info: dict[str, Any] = {
                    "service_name": service_name,
                    "strategy_template_id": template_id,
                    "same_origin_strategy_template": None,
                    "strategy": None,
                    "has_diff": False,
                    "has_been_applied": False,
                }
                check_results.append(check_info)

                template_obj: StrategyTemplate | None = self.template_obj_by_id.get(template_id)
                if not template_obj:
                    continue

                root_template_id: int = (
                    template_obj.root_id if template_obj.root_id != DEFAULT_ROOT_ID else template_obj.pk
                )
                instance_dict: dict[str, Any] = self.instance_map.get((root_template_id, service_name))
                if not instance_dict:
                    continue

                if instance_dict["strategy_template_id"] == template_id:
                    check_info["has_been_applied"] = True
                else:
                    same_origin_template_obj = self.template_obj_by_id.get(instance_dict["strategy_template_id"])
                    check_info["same_origin_strategy_template"] = (
                        {
                            "id": same_origin_template_obj.pk,
                            "name": same_origin_template_obj.name,
                        }
                        if same_origin_template_obj
                        else None
                    )
                # TODO has_diff 判断： instance_obj 和 template_obj
                strategy_dict: dict[str, Any] | None = self.strategy_dict_by_id.get(instance_dict["strategy_id"])
                check_info["strategy"] = (
                    {
                        "id": strategy_dict["id"],
                        "name": strategy_dict["name"],
                    }
                    if strategy_dict
                    else None
                )

        return check_results
