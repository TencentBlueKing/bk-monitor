from typing import Any
from collections.abc import Iterable, Callable

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from bkmonitor.models import UserGroup


class OptionValues:
    FIELD_ALIAS: dict[str, dict[str, str]] = {}

    def __init__(self, queryset: QuerySet):
        self.queryset = queryset

    def _get_default(self, field_name: str) -> list[dict[str, Any]]:
        return [
            {"value": v, "alias": self.FIELD_ALIAS.get(field_name, {}).get(v, v)}
            for v in self.queryset.values_list(field_name).distinct()
        ]

    def get_fields_option_values(self, fields: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
        option_values: dict[str, list[dict[str, Any]]] = {}
        for field_name in fields:
            handler_method: Callable[[], list[dict[str, Any]]] = getattr(self, f"get_{field_name}")
            option_values[field_name] = handler_method()
        return option_values


class StrategyTemplateOptionValues(OptionValues):
    SUPPORT_FIELDS = ["system", "user_group_id", "update_user", "is_enabled", "is_auto_apply"]
    FIELD_ALIAS: dict[str, dict[str, str]] = {
        "system": {
            "RPC": _("调用分析"),
            "K8S": _("容器"),
            "METRIC": _("自定义指标"),
            "LOG": _("日志"),
            "TRACE": _("调用链"),
            "EVENT": _("事件"),
        },
        "is_enabled": {
            True: _("启用"),
            False: _("禁用"),
        },
        "is_auto_apply": {
            True: _("自动下发"),
            False: _("手动下发"),
        },
    }

    def get_user_group_id(self) -> list[dict[str, str]]:
        ids_list = self.queryset.values_list("user_group_id", flat=True).distinct()
        flat_ids = set([_id for ids in ids_list for _id in ids])
        return [
            {"value": _id, "alias": alias}
            for _id, alias in UserGroup.objects.filter(id__in=flat_ids).values_list("id", "name")
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
