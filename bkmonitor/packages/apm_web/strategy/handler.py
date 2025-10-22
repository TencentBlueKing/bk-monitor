import datetime
from typing import Any
from collections.abc import Iterable

from django.db.models import QuerySet

from bkmonitor.query_template.core import QueryTemplateWrapper
from bkmonitor.utils.common_utils import count_md5
from constants.apm import CachedEnum
from . import constants, helper, query_template, dispatch

from bkmonitor.utils.time_tools import str2datetime
import logging

from ..constants import TopoNodeKind
from ..handlers.service_handler import ServiceHandler
from ..models import StrategyTemplate
from .dispatch import EntitySet

logger = logging.getLogger(__name__)


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


class StrategyTemplateHandler:
    @classmethod
    def get_query_template_map(
        cls, strategy_templates: list[StrategyTemplate]
    ) -> dict[tuple[int, str], QueryTemplateWrapper]:
        query_template_keys: list[tuple[int, str]] = [
            (obj.query_template["bk_biz_id"], obj.query_template["name"]) for obj in strategy_templates
        ]
        return query_template.QueryTemplateWrapperFactory.get_wrappers(query_template_keys)

    @classmethod
    def get_query_template_or_none(
        cls, strategy_template: StrategyTemplate, query_template_map: dict[tuple[int, str], QueryTemplateWrapper]
    ) -> QueryTemplateWrapper | None:
        return query_template_map.get(
            (strategy_template.query_template["bk_biz_id"], strategy_template.query_template["name"])
        )

    @classmethod
    def _str2datetime(cls, _dt_str: str) -> datetime.datetime:
        return str2datetime(_dt_str, "%Y-%m-%d %H:%M:%S%z")

    @classmethod
    def _filter_nodes_created_since(cls, nodes: list[dict[str, Any]], dt: datetime.datetime) -> list[dict[str, Any]]:
        """查找指定时间后创建的新服务节点"""
        new_nodes: list[dict[str, Any]] = []
        for node in nodes:
            # 策略只针对真实服务做下发，忽略虚拟节点。
            kind: str | None = node.get("extra_data", {}).get("kind")
            if kind != TopoNodeKind.SERVICE:
                continue

            try:
                created_at: datetime.datetime = cls._str2datetime(node["created_at"])
            except Exception:  # pylint: disable=broad-except
                continue

            if created_at > dt:
                new_nodes.append(node)

        return sorted(new_nodes, key=lambda x: cls._str2datetime(x["created_at"]))

    @classmethod
    def handle_auto_apply(cls, bk_biz_id: int, app_name: str):
        """
        应用模板自动下发
        :param bk_biz_id: 业务 ID
        :param app_name: 应用名
        :return:
        """
        # 过滤出应用下需自动下发的策略模板
        strategy_templates: list[StrategyTemplate] = list(
            StrategyTemplate.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, is_auto_apply=True, is_enabled=True)
        )
        if not strategy_templates:
            logger.info(
                "[handle_auto_apply] no auto apply strategy templates found: bk_biz_id=%s, app_name=%s",
                bk_biz_id,
                app_name,
            )
            return

        logger.info(
            "[handle_auto_apply] start to handle auto apply strategy templates: bk_biz_id=%s, app_name=%s, count=%s",
            bk_biz_id,
            app_name,
            len(strategy_templates),
        )

        entity_set_pool: dict[str, EntitySet] = {}
        nodes: list[dict[str, Any]] = ServiceHandler.list_nodes(bk_biz_id, app_name)
        query_template_map: dict[tuple[int, str], QueryTemplateWrapper] = cls.get_query_template_map(strategy_templates)
        for strategy_template in strategy_templates:
            unapplied_nodes: list[dict[str, Any]] = cls._filter_nodes_created_since(
                nodes, strategy_template.auto_applied_at
            )
            to_be_applied_service_names: list[str] = [node["topo_key"] for node in unapplied_nodes]
            if not unapplied_nodes:
                continue

            # 经过一次自动下发后，后续不同模板需下发的服务整体会一致，直接复用实体集缓存。
            pool_key: str = count_md5(to_be_applied_service_names)
            entity_set: EntitySet | None = entity_set_pool.get(pool_key)
            if not entity_set:
                entity_set = EntitySet(bk_biz_id, app_name, to_be_applied_service_names)
                entity_set_pool[pool_key] = entity_set

            qtw: QueryTemplateWrapper | None = cls.get_query_template_or_none(strategy_template, query_template_map)
            if qtw is None:
                logger.warning(
                    "[handle_auto_apply] query template not found, skip auto apply: bk_biz_id=%s, app_name=%s, name=%s",
                    bk_biz_id,
                    app_name,
                    strategy_template.name,
                )
                continue

            try:
                # 服务检测过程中不抛异常，尽可能将模板下发到符合条件的服务上。
                dispatch_num: int = len(
                    dispatch.StrategyDispatcher(strategy_template, qtw).dispatch(entity_set, raise_exception=False)
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(
                    "[handle_auto_apply] failed to auto apply strategy: bk_biz_id=%s, app_name=%s, name=%s, error=%s",
                    bk_biz_id,
                    app_name,
                    strategy_template.name,
                    str(e),
                )
                continue

            if dispatch_num == 0:
                # 本次下发没有匹配到服务，可能是服务信息发现不完整，不更新下次下发时间，后续继续重试。
                logger.info(
                    "[handle_auto_apply] no service matched, skip auto apply: bk_biz_id=%s, app_name=%s, name=%s",
                    bk_biz_id,
                    app_name,
                    strategy_template.name,
                )
                continue

            strategy_template.auto_applied_at = cls._str2datetime(unapplied_nodes[-1]["created_at"])
            strategy_template.save(update_fields=["auto_applied_at"])
            logger.info(
                "[handle_auto_apply] succeed to auto apply strategy: "
                "bk_biz_id=%s, app_name=%s, name=%s, dispatch_num=%s, auto_applied_at=%s",
                bk_biz_id,
                app_name,
                strategy_template.name,
                dispatch_num,
                strategy_template.auto_applied_at,
            )

        logger.info(
            "[handle_auto_apply] finish handling auto apply strategy templates: bk_biz_id=%s, app_name=%s",
            bk_biz_id,
            app_name,
        )
