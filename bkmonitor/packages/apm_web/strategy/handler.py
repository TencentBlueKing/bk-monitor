from typing import Any
from collections.abc import Iterable

from django.db.models import QuerySet

from constants.apm import CachedEnum
from . import constants, helper


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
        "system": constants.StrategyTemplateSystem,
        "is_enabled": constants.StrategyTemplateIsEnabled,
        "is_auto_apply": constants.StrategyTemplateIsAutoApply,
    }

    def get_user_group_id(self) -> list[dict[str, Any]]:
        user_group_ids: set[int] = set()
        for partial_user_group_ids in self.queryset.values_list("user_group_ids", flat=True):
            user_group_ids.update(partial_user_group_ids)
        return [
            {"value": user_group_id, "alias": user_group["name"]}
            for user_group_id, user_group in helper.get_user_groups(user_group_ids).items()
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
