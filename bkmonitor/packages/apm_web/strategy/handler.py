from typing import Any
from collections.abc import Iterable

from django.db.models import QuerySet

from bkmonitor.models import UserGroup
from apm_web.strategy.constants import StrategyTemplateSystem, StrategyTemplateIsEnabled, StrategyTemplateIsAutoApply


def get_user_groups(user_group_ids: Iterable[int]) -> dict[int, dict[str, int | str]]:
    return {
        user_group["id"]: user_group
        for user_group in UserGroup.objects.filter(id__in=user_group_ids).values("id", "name")
    }


class OptionValues:
    SUPPORT_FIELDS = []
    FIELD_ALIAS: dict[str, dict[str, str]] = {}

    def __init__(self, queryset: QuerySet):
        self.queryset = queryset

    @classmethod
    def is_matched(cls, field_name: str) -> bool:
        return field_name in cls.SUPPORT_FIELDS

    def _get_default(self, field_name: str) -> list[dict[str, Any]]:
        return [
            {"value": v, "alias": self.FIELD_ALIAS.get(field_name, {}).get(v, v)}
            for v in self.queryset.values_list(field_name).distinct()
        ]

    def get_fields_option_values(self, fields: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        return {field_name: getattr(self, f"get_{field_name}")() for field_name in fields}


class StrategyTemplateOptionValues(OptionValues):
    SUPPORT_FIELDS = ["system", "user_group_id", "update_user", "is_enabled", "is_auto_apply"]
    FIELD_ALIAS: dict[str, dict[str, str]] = {
        "system": dict(StrategyTemplateSystem.choices()),
        "is_enabled": dict(StrategyTemplateIsEnabled.choices()),
        "is_auto_apply": dict(StrategyTemplateIsAutoApply.choices()),
    }

    def get_user_group_id(self) -> list[dict[str, str]]:
        ids_list = self.queryset.values_list("user_group_ids", flat=True).distinct()
        flat_ids = set([_id for ids in ids_list for _id in ids])
        return [
            {"value": _id, "alias": user_group_dict["name"]}
            for _id, user_group_dict in get_user_groups(flat_ids).items()
        ]

    def get_system(self) -> list[dict[str, str]]:
        return self._get_default("system")

    def get_update_user(self) -> list[dict[str, str]]:
        return self._get_default("update_user")

    def get_is_enabled(self) -> list[dict[str, str]]:
        return self._get_default("is_enabled")

    def get_is_auto_apply(self) -> list[dict[str, str]]:
        return self._get_default("is_auto_apply")


class StrategyInstanceOptionValues(OptionValues):
    SUPPORT_FIELDS = ["applied_service_name"]

    def get_applied_service_name(self) -> list[dict[str, str]]:
        return self._get_default("service_name")
