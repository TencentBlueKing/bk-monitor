import logging
from typing import Any

from apm.constants import GLOBAL_CONFIG_BK_BIZ_ID
from apm.models import ApmApplication, TraceDataSource, TraceScopeIndexSet
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models import ESStorage

logger = logging.getLogger("apm")


class TraceScopeIndexSetHandler:
    """维护 Trace 数据源域对应的 BKLog 聚合索引集。"""

    @staticmethod
    def build_index_set_name(bk_biz_id: int) -> str:
        """生成 Trace 数据源域索引集名称。"""
        if bk_biz_id > 0:
            return f"bkapm_cross_trace_{bk_biz_id}"
        return f"bkapm_cross_trace_space_{abs(bk_biz_id)}"

    @classmethod
    def get_index_set(cls, bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any] | None:
        """无缓存查询并精确匹配 Trace 数据源域索引集。"""
        index_set_name = cls.build_index_set_name(bk_biz_id)
        index_sets: list[dict[str, Any]] = api.log_search.search_index_set.request.cacheless(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        matched_index_sets = [item for item in index_sets if item["index_set_name"] == index_set_name]
        if len(matched_index_sets) > 1:
            raise ValueError(
                f"multiple Trace scope index sets found: bk_tenant_id={bk_tenant_id}, "
                f"bk_biz_id={bk_biz_id}, index_set_name={index_set_name}"
            )
        if not matched_index_sets:
            return None

        matched_index_set = matched_index_sets[0]
        return {
            "index_set_id": matched_index_set["index_set_id"],
            "index_set_name": matched_index_set["index_set_name"],
        }

    @staticmethod
    def build_indexes(bk_biz_id: int) -> list[dict[str, Any]]:
        """读取域内有效应用并构造完整、去重的 BKLog 索引成员快照。"""
        applications: list[dict[str, Any]] = list(
            ApmApplication.objects.filter(
                bk_biz_id=bk_biz_id,
                is_enabled=True,
                is_enabled_trace=True,
            )
            .values("id", "app_name", "bk_tenant_id")
            .order_by("id")
        )
        if not applications:
            return []

        app_names = [application["app_name"] for application in applications]
        trace_datasources: list[dict[str, Any]] = list(
            TraceDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name__in=app_names)
            .values(
                "app_name",
                "result_table_id",
                "shared_datasource_id",
            )
            .order_by("id")
        )
        deduplicated_datasources: dict[str, dict[str, Any]] = {}
        for datasource in trace_datasources:
            deduplicated_datasources[datasource["app_name"]] = datasource

        member_contexts: list[dict[str, Any]] = []
        for application in applications:
            app_name = application["app_name"]
            datasource = deduplicated_datasources.get(app_name)
            if datasource is None or not datasource["result_table_id"]:
                logger.warning(
                    "[TraceScopeIndexSetHandler] skipped application without Trace result table: "
                    "bk_biz_id=%s, app_name=%s",
                    bk_biz_id,
                    app_name,
                )
                continue

            is_shared = datasource["shared_datasource_id"] is not None
            member_contexts.append(
                {
                    "app_name": app_name,
                    "result_table_id": datasource["result_table_id"],
                    "tenant_id": DEFAULT_TENANT_ID if is_shared else application["bk_tenant_id"],
                    "bk_biz_id": GLOBAL_CONFIG_BK_BIZ_ID if is_shared else bk_biz_id,
                }
            )

        storage_tenant_ids = {context["tenant_id"] for context in member_contexts}
        result_table_ids = {context["result_table_id"] for context in member_contexts}
        storages: list[dict[str, Any]] = list(
            ESStorage.objects.filter(
                bk_tenant_id__in=storage_tenant_ids,
                table_id__in=result_table_ids,
            ).values("bk_tenant_id", "table_id", "storage_cluster_id", "index_set")
        )
        storage_by_location: dict[tuple[str, str], dict[str, Any]] = {
            (storage["bk_tenant_id"], storage["table_id"]): storage for storage in storages
        }

        deduplicated_indexes: dict[str, dict[str, Any]] = {}
        for context in member_contexts:
            result_table_id = context["result_table_id"]
            storage = storage_by_location.get((context["tenant_id"], result_table_id))
            if storage is None:
                logger.warning(
                    "[TraceScopeIndexSetHandler] skipped application without Trace storage: "
                    "bk_biz_id=%s, app_name=%s, bk_tenant_id=%s, result_table_id=%s",
                    bk_biz_id,
                    context["app_name"],
                    context["tenant_id"],
                    result_table_id,
                )
                continue
            if not storage["index_set"]:
                logger.warning(
                    "[TraceScopeIndexSetHandler] skipped application without Trace storage index_set: "
                    "bk_biz_id=%s, app_name=%s, bk_tenant_id=%s, result_table_id=%s",
                    bk_biz_id,
                    context["app_name"],
                    context["tenant_id"],
                    result_table_id,
                )
                continue

            index = {
                "bk_biz_id": context["bk_biz_id"],
                "result_table_id": f"{storage['index_set']}_*",
                "storage_cluster_id": storage["storage_cluster_id"],
            }
            existing_index = deduplicated_indexes.get(result_table_id)
            if existing_index is not None and existing_index != index:
                logger.warning(
                    "[TraceScopeIndexSetHandler] replaced conflicting Trace index member: "
                    "bk_biz_id=%s, result_table_id=%s",
                    bk_biz_id,
                    result_table_id,
                )
            deduplicated_indexes[result_table_id] = index

        return list(deduplicated_indexes.values())

    @staticmethod
    def _save_index_set_record(bk_tenant_id: str, bk_biz_id: int, index_set_id: int) -> None:
        TraceScopeIndexSet.origin_objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            defaults={"index_set_id": index_set_id, "is_deleted": False, "is_enabled": True},
        )

    @classmethod
    def sync(cls, bk_tenant_id: str, bk_biz_id: int) -> None:
        """按完整目标快照创建、更新或删除 Trace 数据源域索引集。"""
        indexes = cls.build_indexes(bk_biz_id)
        index_set = cls.get_index_set(bk_tenant_id, bk_biz_id)

        if not indexes:
            if index_set is not None:
                api.log_search.delete_index_set(
                    bk_tenant_id=bk_tenant_id,
                    index_set_id=index_set["index_set_id"],
                )
                logger.info(
                    "[TraceScopeIndexSetHandler] deleted empty Trace scope index set: "
                    "bk_tenant_id=%s, bk_biz_id=%s, index_set_id=%s",
                    bk_tenant_id,
                    bk_biz_id,
                    index_set["index_set_id"],
                )
            record = TraceScopeIndexSet.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).first()
            if record is not None:
                record.delete()
            return

        params: dict[str, Any] = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": bk_biz_id,
            "index_set_name": cls.build_index_set_name(bk_biz_id),
            "category_id": "application_check",
            "scenario_id": "es",
            "view_roles": [],
            "storage_cluster_id": indexes[0]["storage_cluster_id"],
            "time_field": "end_time",
            "time_field_type": "long",
            "time_field_unit": "microsecond",
            "indexes": indexes,
        }
        if index_set is not None:
            api.log_search.update_index_set(index_set_id=index_set["index_set_id"], **params)
            cls._save_index_set_record(bk_tenant_id, bk_biz_id, index_set["index_set_id"])
            logger.info(
                "[TraceScopeIndexSetHandler] updated Trace scope index set: "
                "bk_tenant_id=%s, bk_biz_id=%s, index_set_id=%s, indexes=%s",
                bk_tenant_id,
                bk_biz_id,
                index_set["index_set_id"],
                len(indexes),
            )
            return

        index_set = api.log_search.create_index_set(**params)
        cls._save_index_set_record(bk_tenant_id, bk_biz_id, index_set["index_set_id"])
        logger.info(
            "[TraceScopeIndexSetHandler] created Trace scope index set: "
            "bk_tenant_id=%s, bk_biz_id=%s, index_set_id=%s, indexes=%s",
            bk_tenant_id,
            bk_biz_id,
            index_set["index_set_id"],
            len(indexes),
        )
