"""APM 服务关联 K8S 日志索引后台采集处理器。"""

import logging
import time
from collections import defaultdict
from typing import Any, TypeVar

from apm_web.handlers.log_handler import ServiceLogHandler, get_biz_index_sets_with_cache
from apm_web.strategy.dispatch.entity import EntitySet
from apm_web.topo.handle.relation.define import (
    Node,
    Relation,
    Source,
    SourceDatasource,
    SourceK8sDaemonSet,
    SourceK8sDeployment,
    SourceK8sPod,
    SourceK8sStatefulSet,
    SourceService,
)
from apm_web.topo.handle.relation.query import RelationQ
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.thread_backend import ThreadPool

WorkloadKey = frozenset[tuple[str, str]]
RelationKey = TypeVar("RelationKey", str, WorkloadKey)

logger = logging.getLogger("apm")


class ServiceLogTaskHandler:
    """批量获取应用下各服务关联的 K8S 日志索引集。"""

    QUERY_TIME_RANGE_SECONDS = 30 * 60
    QUERY_CHUNK_SIZE = 5
    QUERY_CONCURRENCY_PER_PATH = 2

    WORKLOAD_SOURCE_TYPE_MAP: dict[str, type[Source]] = {
        "Deployment": SourceK8sDeployment,
        "DaemonSet": SourceK8sDaemonSet,
        "StatefulSet": SourceK8sStatefulSet,
    }

    @classmethod
    def get_k8s_related_log_indexes(cls, bk_biz_id: int, app_name: str) -> dict[str, list[dict[str, Any]]]:
        """获取应用下所有服务关联的 K8S 日志索引集。"""
        entity_set = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
        service_names: list[str] = entity_set.service_names
        service_workloads: dict[str, list[dict[str, Any]]] = cls._fetch_app_workloads(entity_set, service_names)
        if not any(service_workloads.values()):
            return {}

        queryable_workloads: list[dict[str, str]] = cls._normalize_and_deduplicate_workloads(service_workloads)
        with ThreadPool(2) as pool:
            workload_future = pool.apply_async(
                cls._query_workload_related_indexes, args=(bk_biz_id, queryable_workloads)
            )
            service_future = pool.apply_async(
                cls._query_service_related_indexes, args=(bk_biz_id, app_name, service_names)
            )
            workload_indexes, workload_failed_count = workload_future.get()
            service_indexes, service_failed_count = service_future.get()

        query_count: int = len(queryable_workloads) + len(service_names)
        failed_count: int = workload_failed_count + service_failed_count
        if failed_count == query_count:
            raise RuntimeError(
                f"all relation queries failed: bk_biz_id={bk_biz_id}, app_name={app_name}, total={query_count}"
            )

        if failed_count:
            logger.warning(
                "[GET_K8S_RELATED_LOG_INDEXES] relation query partially failed: "
                "bk_biz_id=%s, app_name=%s, failed=%s, total=%s",
                bk_biz_id,
                app_name,
                failed_count,
                query_count,
            )

        return cls._merge_by_service(service_workloads, workload_indexes, service_indexes)

    @staticmethod
    def _fetch_app_workloads(entity_set: EntitySet, service_names: list[str]) -> dict[str, list[dict[str, Any]]]:
        """按服务收集应用的原始 workload 关联。"""
        return {service_name: entity_set.get_workloads(service_name) for service_name in service_names}

    @classmethod
    def _normalize_workload(cls, workload: dict[str, Any]) -> dict[str, str] | None:
        """提取关系查询需要的标准 workload 字段。"""
        workload_fields = ("bcs_cluster_id", "namespace", "kind", "name")
        if workload.get("kind") not in cls.WORKLOAD_SOURCE_TYPE_MAP or not all(
            workload.get(field) for field in workload_fields
        ):
            return None

        return {field: workload[field] for field in workload_fields}

    @classmethod
    def _normalize_and_deduplicate_workloads(
        cls, service_workloads: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, str]]:
        """标准化并去重可直接作为 UQ 查询源的 workload。"""
        workload_map: dict[WorkloadKey, dict[str, str]] = {}
        for workloads in service_workloads.values():
            for workload in workloads:
                normalized_workload = cls._normalize_workload(workload)
                if not normalized_workload:
                    continue

                workload_map.setdefault(frozenset(normalized_workload.items()), normalized_workload)

        return list(workload_map.values())

    @classmethod
    def _query_workload_related_indexes(
        cls, bk_biz_id: int, workloads: list[dict[str, str]]
    ) -> tuple[dict[WorkloadKey, list[dict[str, Any]]], int]:
        """按 workload 批量查询关联的日志索引集。"""
        if not workloads:
            return {}, 0

        workload_chunks: list[list[dict[str, str]]] = list(chunks(workloads, cls.QUERY_CHUNK_SIZE))
        end_time = int(time.time())
        start_time = end_time - cls.QUERY_TIME_RANGE_SECONDS

        def _query_chunk(
            workload_chunk: list[dict[str, str]],
        ) -> tuple[dict[WorkloadKey, set[int | str]], int]:
            source_infos: list[Source] = []
            for workload in workload_chunk:
                source_type = cls.WORKLOAD_SOURCE_TYPE_MAP[workload["kind"]]
                source_infos.append(
                    source_type.create(
                        {
                            "bcs_cluster_id": workload["bcs_cluster_id"],
                            "namespace": workload["namespace"],
                            source_type.name: workload["name"],
                        }
                    )
                )

            relation_qs: list[dict[str, Any]] = RelationQ.generate_multi_q(
                bk_biz_id=bk_biz_id,
                source_infos=source_infos,
                target_type=SourceDatasource,
                start_time=start_time,
                end_time=end_time,
                path_resource=[SourceK8sPod],
            )

            related_data_ids: defaultdict[WorkloadKey, set[int | str]] = defaultdict(set)
            relations, failed_count = cls._query_relations(relation_qs)
            for relation in relations:
                workload = cls._workload_from_relation_source_info(relation.source_info)
                if not workload:
                    continue

                workload_key = frozenset(workload.items())
                related_data_ids[workload_key].update(cls._get_relation_data_ids(relation.nodes))

            return dict(related_data_ids), failed_count

        related_data_ids: dict[WorkloadKey, set[int | str]] = {}
        failed_count: int = 0
        with ThreadPool(min(len(workload_chunks), cls.QUERY_CONCURRENCY_PER_PATH)) as pool:
            for chunk_result, chunk_failed_count in pool.imap_unordered(_query_chunk, workload_chunks):
                related_data_ids.update(chunk_result)
                failed_count += chunk_failed_count

        return cls._convert_data_ids_to_indexes(bk_biz_id, related_data_ids), failed_count

    @classmethod
    def _query_service_related_indexes(
        cls, bk_biz_id: int, app_name: str, service_names: list[str]
    ) -> tuple[dict[str, list[dict[str, Any]]], int]:
        """按服务批量查询关联的日志索引集，用于覆盖自定义 CRD。"""
        service_name_chunks: list[list[str]] = list(chunks(service_names, cls.QUERY_CHUNK_SIZE))
        end_time = int(time.time())
        start_time = end_time - cls.QUERY_TIME_RANGE_SECONDS

        def _query_chunk(service_name_chunk: list[str]) -> tuple[dict[str, set[int | str]], int]:
            source_infos: list[Source] = [
                SourceService(apm_application_name=app_name, apm_service_name=service_name)
                for service_name in service_name_chunk
            ]
            relation_qs: list[dict[str, Any]] = RelationQ.generate_multi_q(
                bk_biz_id=bk_biz_id,
                source_infos=source_infos,
                target_type=SourceDatasource,
                start_time=start_time,
                end_time=end_time,
                path_resource=[SourceK8sPod],
            )

            related_data_ids: defaultdict[str, set[int | str]] = defaultdict(set)
            relations, failed_count = cls._query_relations(relation_qs)
            for relation in relations:
                service_name = relation.source_info.get("apm_service_name")
                if not service_name:
                    continue

                related_data_ids[service_name].update(cls._get_relation_data_ids(relation.nodes))

            return dict(related_data_ids), failed_count

        related_data_ids: dict[str, set[int | str]] = {}
        failed_count: int = 0
        with ThreadPool(min(len(service_name_chunks), cls.QUERY_CONCURRENCY_PER_PATH)) as pool:
            for chunk_result, chunk_failed_count in pool.imap_unordered(_query_chunk, service_name_chunks):
                related_data_ids.update(chunk_result)
                failed_count += chunk_failed_count

        return cls._convert_data_ids_to_indexes(bk_biz_id, related_data_ids), failed_count

    @staticmethod
    def _query_relations(relation_qs: list[dict[str, Any]]) -> tuple[list[Relation], int]:
        """执行关系查询，并区分正常空结果与 UQ 分项失败。"""
        query_results: list[Relation | None] = RelationQ.query(relation_qs, fill_with_empty=True)
        aligned_results: list[Relation | None] = query_results[: len(relation_qs)]
        failed_count: int = len(relation_qs) - len(aligned_results) + sum(result is None for result in aligned_results)
        return [result for result in aligned_results if result is not None], failed_count

    @classmethod
    def _merge_by_service(
        cls,
        service_workloads: dict[str, list[dict[str, Any]]],
        workload_indexes: dict[WorkloadKey, list[dict[str, Any]]],
        service_indexes: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        """将 workload 和 service 两路索引合并回服务并去重。"""
        merged_indexes: dict[str, list[dict[str, Any]]] = {}
        for service_name, workloads in service_workloads.items():
            indexes: list[dict[str, Any]] = []
            for workload in workloads:
                normalized_workload = cls._normalize_workload(workload)
                if not normalized_workload:
                    continue

                indexes.extend(workload_indexes.get(frozenset(normalized_workload.items()), []))

            indexes.extend(service_indexes.get(service_name, []))
            deduped_indexes: dict[str, dict[str, Any]] = {}
            for index in indexes:
                deduped_indexes.setdefault(str(index["index_set_id"]), index)

            if deduped_indexes:
                merged_indexes[service_name] = list(deduped_indexes.values())

        return merged_indexes

    @classmethod
    def _workload_from_relation_source_info(cls, source_info: dict[str, Any]) -> dict[str, str] | None:
        """从 UQ 关系结果的 source_info 还原 workload。"""
        for kind, source_type in cls.WORKLOAD_SOURCE_TYPE_MAP.items():
            workload_name_field = source_type.name
            if workload_name_field is None:
                continue

            workload_name = source_info.get(workload_name_field)
            if not workload_name:
                continue

            return cls._normalize_workload(
                {
                    "bcs_cluster_id": source_info.get("bcs_cluster_id"),
                    "namespace": source_info.get("namespace"),
                    "kind": kind,
                    "name": workload_name,
                }
            )

        return None

    @staticmethod
    def _get_relation_data_ids(nodes: list[Node]) -> set[int | str]:
        """从关系节点提取有效的 data_id。"""
        data_ids: set[int | str] = set()
        for node in nodes:
            bk_data_id = node.source_info.to_source_info().get("bk_data_id")
            if bk_data_id:
                data_ids.add(bk_data_id)

        return data_ids

    @staticmethod
    def _convert_data_ids_to_indexes(
        bk_biz_id: int,
        related_data_ids: dict[RelationKey, set[int | str]],
    ) -> dict[RelationKey, list[dict[str, Any]]]:
        """将各关系源关联的 data_id 转换为日志索引集。"""
        if not any(related_data_ids.values()):
            return {}

        full_indexes: list[dict[str, Any]] = get_biz_index_sets_with_cache(bk_biz_id=bk_biz_id)
        table_ids_cache: dict[frozenset[int | str], set[str]] = {}
        related_indexes: dict[RelationKey, list[dict[str, Any]]] = {}
        for relation_key, data_ids in related_data_ids.items():
            if not data_ids:
                continue

            data_id_key = frozenset(data_ids)
            if data_id_key not in table_ids_cache:
                table_ids_cache[data_id_key] = set(ServiceLogHandler.list_tables_by_data_ids(list(data_ids)))

            table_ids = table_ids_cache[data_id_key]
            if not table_ids:
                continue

            indexes: list[dict[str, Any]] = []
            for index in full_indexes:
                indices: list[dict[str, Any]] = index.get("indices") or []
                if len(indices) == 1 and indices[0].get("result_table_id") in table_ids:
                    indexes.append({"index_set_id": index["index_set_id"], "bk_biz_id": bk_biz_id})

            if indexes:
                related_indexes[relation_key] = indexes

        return related_indexes
