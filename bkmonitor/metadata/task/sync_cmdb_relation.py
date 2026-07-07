"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from alarm_backends.core.lock.service_lock import share_lock
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.prometheus import metrics
from metadata.models import (
    ClusterInfo,
    DataLink,
    DataSource,
    DataSourceResultTable,
    Label,
    ResultTable,
    Space,
    TimeSeriesGroup,
)
from metadata.models.data_link.data_link import SURREALDB_RT_SUFFIX
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    GraphDataBusConfig,
    GraphRelationBindingConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.data_link.utils import compose_bkdata_table_id
from metadata.models.entity_relation import EntityMeta, NAMESPACE_ALL
from metadata.models.space.constants import EtlConfigs
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


def _get_graph_definition_binding_queryset(namespace: str):
    queryset = GraphRelationBindingConfig.objects.filter(
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
    ).filter(
        Q(
            write_mode__in=[
                GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
                GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
            ]
        )
        | Q(
            write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
            surrealdb_cluster_name__gt="",
            graph_result_table_name__gt="",
        )
    )
    if namespace and namespace != NAMESPACE_ALL:
        bk_biz_id = space_uid_to_bk_biz_id(namespace)
        if not bk_biz_id:
            logger.warning("sync_graph_definition_to_bkbase: namespace->[%s] cannot resolve bk_biz_id, skip", namespace)
            return GraphRelationBindingConfig.objects.none()
        queryset = queryset.filter(bk_biz_id=bk_biz_id)
    return queryset


def _get_data_source_and_table_id(graph_binding: GraphRelationBindingConfig) -> tuple[DataSource | None, str]:
    data_link = DataLink.objects.filter(
        bk_tenant_id=graph_binding.bk_tenant_id,
        namespace=graph_binding.namespace,
        data_link_name=graph_binding.data_link_name,
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    ).first()
    if not data_link:
        logger.warning("sync_graph_definition_to_bkbase: data_link->[%s] not found, skip", graph_binding.data_link_name)
        return None, ""

    data_source = DataSource.objects.filter(
        bk_tenant_id=data_link.bk_tenant_id,
        bk_data_id=data_link.bk_data_id,
    ).first()
    if not data_source:
        logger.warning(
            "sync_graph_definition_to_bkbase: data_link->[%s] data_id->[%s] not found, skip",
            data_link.data_link_name,
            data_link.bk_data_id,
        )
        return None, ""

    table_id = graph_binding.table_id
    if not table_id and data_link.table_ids:
        table_id = data_link.table_ids[0]
    if not table_id:
        table_id = (
            DataSourceResultTable.objects.filter(
                bk_tenant_id=data_link.bk_tenant_id,
                bk_data_id=data_source.bk_data_id,
            )
            .values_list("table_id", flat=True)
            .first()
        )
    if not table_id:
        logger.warning(
            "sync_graph_definition_to_bkbase: data_link->[%s] has no result table, skip", data_link.data_link_name
        )
        return None, ""

    return data_source, table_id


def _graph_definitions_changed(graph_binding: GraphRelationBindingConfig, vertices: list, relations: list) -> bool:
    if not graph_binding.should_write_surrealdb:
        return False

    if _canonical_graph_definitions(graph_binding.vertices) != _canonical_graph_definitions(
        vertices
    ) or _canonical_graph_definitions(graph_binding.relations) != _canonical_graph_definitions(relations):
        return True

    if not graph_binding.graph_result_table_name:
        return True

    common_filters = {
        "bk_tenant_id": graph_binding.bk_tenant_id,
        "namespace": graph_binding.namespace,
        "data_link_name": graph_binding.data_link_name,
    }
    surrealdb_binding = SurrealDBBindingConfig.objects.filter(
        **common_filters,
        name=graph_binding.surrealdb_binding_component_name,
    ).first()
    if not surrealdb_binding:
        return True

    if _canonical_graph_definitions(surrealdb_binding.vertices) != _canonical_graph_definitions(
        vertices
    ) or _canonical_graph_definitions(surrealdb_binding.relations) != _canonical_graph_definitions(relations):
        return True

    return not (
        ResultTableConfig.objects.filter(
            **common_filters,
            name=graph_binding.graph_result_table_name,
        ).exists()
        and GraphDataBusConfig.objects.filter(
            **common_filters,
            name=graph_binding.graph_databus_component_name,
        ).exists()
    )


def _graph_definition_sync_write_mode(graph_binding: GraphRelationBindingConfig) -> str:
    if (
        graph_binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
        and graph_binding.surrealdb_auto_restore
        and graph_binding.surrealdb_cluster_name
        and graph_binding.graph_result_table_name
        and not SurrealDBBindingConfig.objects.filter(
            bk_tenant_id=graph_binding.bk_tenant_id,
            namespace=graph_binding.namespace,
            data_link_name=graph_binding.data_link_name,
            name=graph_binding.surrealdb_binding_component_name,
        ).exists()
    ):
        return GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    return graph_binding.write_mode


def _graph_relation_binding_sync_healthy(graph_binding: GraphRelationBindingConfig) -> bool:
    if graph_binding.status == DataLinkResourceStatus.FAILED.value:
        return False

    common_filters = {
        "bk_tenant_id": graph_binding.bk_tenant_id,
        "namespace": graph_binding.namespace,
        "data_link_name": graph_binding.data_link_name,
    }
    component_checks = []
    if graph_binding.should_write_vm:
        component_checks.extend(
            [
                (ResultTableConfig, graph_binding.bkbase_result_table_name),
                (VMStorageBindingConfig, graph_binding.vm_binding_component_name),
                (DataBusConfig, graph_binding.vm_databus_component_name),
            ]
        )
    if graph_binding.should_write_surrealdb:
        component_checks.extend(
            [
                (ResultTableConfig, graph_binding.graph_result_table_name),
                (SurrealDBBindingConfig, graph_binding.surrealdb_binding_component_name),
                (GraphDataBusConfig, graph_binding.graph_databus_component_name),
            ]
        )

    return all(
        bool(component_name)
        and component.objects.filter(
            **common_filters,
            name=component_name,
            status=DataLinkResourceStatus.OK.value,
        ).exists()
        for component, component_name in component_checks
    )


def _get_builtin_relation_token(
    ds: DataSource, table_id: str, generated_token: str, time_series_group: TimeSeriesGroup | None = None
) -> str:
    return time_series_group.token if time_series_group and time_series_group.token else generated_token


def _canonical_graph_definitions(definitions: list) -> list[str]:
    return sorted(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in definitions)


def _graph_relation_preview_reason(
    *,
    graph_binding: GraphRelationBindingConfig,
    target_write_mode: str,
    graph_definitions_changed: bool,
    healthy: bool,
) -> str:
    if target_write_mode != graph_binding.write_mode:
        return "write_mode_changed"
    if graph_definitions_changed:
        return "graph_definitions_changed"
    if not healthy:
        return "component_unhealthy"
    return "no_change"


def _build_graph_relation_sync_preview(
    graph_binding: GraphRelationBindingConfig,
    *,
    target_write_mode: str,
    vertices: list,
    relations: list,
    would_apply: bool,
    reason: str,
    table_id: str = "",
) -> dict[str, Any]:
    return {
        "data_link_name": graph_binding.data_link_name,
        "name": graph_binding.name,
        "bk_tenant_id": graph_binding.bk_tenant_id,
        "namespace": graph_binding.namespace,
        "bk_biz_id": graph_binding.bk_biz_id,
        "status": graph_binding.status,
        "table_id": table_id or graph_binding.table_id,
        "current_write_mode": graph_binding.write_mode,
        "target_write_mode": target_write_mode,
        "would_apply": would_apply,
        "reason": reason,
        "surrealdb_auto_restore": graph_binding.surrealdb_auto_restore,
        "vm_target": {
            "result_table_name": graph_binding.bkbase_result_table_name,
            "storage_binding_name": graph_binding.vm_binding_component_name,
            "databus_name": graph_binding.vm_databus_component_name,
            "cluster_name": graph_binding.vm_cluster_name,
        },
        "surrealdb_target": {
            "result_table_name": graph_binding.graph_result_table_name,
            "binding_name": graph_binding.surrealdb_binding_component_name,
            "cluster_name": graph_binding.surrealdb_cluster_name,
            "table_type": graph_binding.table_type,
        },
        "graph_databus_target": {
            "databus_name": graph_binding.graph_databus_component_name,
        },
        "vertices_count": len(vertices),
        "relations_count": len(relations),
    }


def preview_graph_definition_sync_to_bkbase(
    namespace: str = "",
    bk_biz_id: int | None = None,
    action: str = "manual",
) -> dict[str, Any]:
    """
    只读预览 ResourceDefinition / RelationDefinition 同步会影响哪些 GraphRelation 链路。

    与 sync_graph_definition_to_bkbase(dry_run=True) 使用同一批筛选与判定 helper，
    但额外返回每条 binding 的目标组件名，供 bkm-cli 激活前核验，不执行任何 apply 或状态写入。
    """
    if bk_biz_id is not None:
        namespace = bk_biz_id_to_space_uid(bk_biz_id)
        if not namespace:
            raise ValueError(f"cannot resolve namespace from bk_biz_id={bk_biz_id}")

    namespace = namespace or NAMESPACE_ALL
    bindings = list(_get_graph_definition_binding_queryset(namespace))
    result: dict[str, Any] = {
        "namespace": namespace,
        "action": action,
        "dry_run": True,
        "matched": len(bindings),
        "would_apply": 0,
        "would_skip": 0,
        "would_fail": 0,
        "previews": [],
    }

    for graph_binding in bindings:
        try:
            vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=graph_binding.bk_biz_id)
            target_write_mode = _graph_definition_sync_write_mode(graph_binding)

            if not vertices or not relations:
                data_source = None
                table_id = ""
                if graph_binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM:
                    result["would_skip"] += 1
                    reason = "vm_only_empty_graph_definitions_skipped"
                    would_apply = False
                elif graph_binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB:
                    data_source, table_id = _get_data_source_and_table_id(graph_binding)
                    if data_source and table_id:
                        result["would_apply"] += 1
                        reason = "empty_graph_definitions_would_downgrade_to_vm"
                        target_write_mode = GraphRelationBindingConfig.WRITE_MODE_VM
                        would_apply = True
                    else:
                        result["would_skip"] += 1
                        reason = "missing_data_source_or_table_id"
                        would_apply = False
                else:
                    result["would_fail"] += 1
                    reason = "graph_definitions_empty"
                    would_apply = False

                result["previews"].append(
                    _build_graph_relation_sync_preview(
                        graph_binding,
                        target_write_mode=target_write_mode,
                        vertices=vertices,
                        relations=relations,
                        would_apply=would_apply,
                        reason=reason,
                        table_id=table_id,
                    )
                )
                continue

            graph_definitions_changed = (
                _graph_definitions_changed(graph_binding, vertices, relations)
                or target_write_mode != graph_binding.write_mode
            )
            healthy = _graph_relation_binding_sync_healthy(graph_binding)
            if not graph_definitions_changed and healthy:
                result["would_skip"] += 1
                result["previews"].append(
                    _build_graph_relation_sync_preview(
                        graph_binding,
                        target_write_mode=target_write_mode,
                        vertices=vertices,
                        relations=relations,
                        would_apply=False,
                        reason="no_change",
                    )
                )
                continue

            data_source, table_id = _get_data_source_and_table_id(graph_binding)
            if not data_source or not table_id:
                result["would_skip"] += 1
                result["previews"].append(
                    _build_graph_relation_sync_preview(
                        graph_binding,
                        target_write_mode=target_write_mode,
                        vertices=vertices,
                        relations=relations,
                        would_apply=False,
                        reason="missing_data_source_or_table_id",
                    )
                )
                continue

            result["would_apply"] += 1
            result["previews"].append(
                _build_graph_relation_sync_preview(
                    graph_binding,
                    target_write_mode=target_write_mode,
                    vertices=vertices,
                    relations=relations,
                    would_apply=True,
                    reason=_graph_relation_preview_reason(
                        graph_binding=graph_binding,
                        target_write_mode=target_write_mode,
                        graph_definitions_changed=graph_definitions_changed,
                        healthy=healthy,
                    ),
                    table_id=table_id,
                )
            )
        except Exception as e:  # pylint: disable=broad-except
            result["would_fail"] += 1
            preview = _build_graph_relation_sync_preview(
                graph_binding,
                target_write_mode=graph_binding.write_mode,
                vertices=[],
                relations=[],
                would_apply=False,
                reason="preview_failed",
            )
            preview["error"] = str(e)
            result["previews"].append(preview)

    return result


def sync_graph_definition_to_bkbase(
    namespace: str,
    kind: str = "",
    name: str = "",
    generation: int | None = None,
    action: str = "apply",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    将 ResourceDefinition / RelationDefinition 的最新图定义同步到已有 BKBase graph relation 链路。

    只处理已存在且写入 SurrealDB 的 GraphRelationBindingConfig；首次创建链路仍由 CMDB relation 同步负责。
    """
    namespace = namespace or NAMESPACE_ALL
    bindings = list(_get_graph_definition_binding_queryset(namespace))
    result: dict[str, Any] = {
        "namespace": namespace,
        "kind": kind,
        "name": name,
        "generation": generation,
        "action": action,
        "dry_run": dry_run,
        "matched": len(bindings),
        "applied": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }

    logger.info(
        "sync_graph_definition_to_bkbase started: namespace=%s, kind=%s, name=%s, generation=%s, action=%s, matched=%s",
        namespace,
        kind,
        name,
        generation,
        action,
        len(bindings),
    )

    for graph_binding in bindings:
        try:
            vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=graph_binding.bk_biz_id)
            if not vertices or not relations:
                error_message = "graph definitions are empty, SurrealDB write requires non-empty vertices and relations"
                if graph_binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM:
                    result["skipped"] += 1
                    logger.info(
                        "sync_graph_definition_to_bkbase: data_link=%s, bk_biz_id=%s has empty graph definitions, "
                        "skip vm-only binding",
                        graph_binding.data_link_name,
                        graph_binding.bk_biz_id,
                    )
                    continue
                if graph_binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB:
                    data_source, table_id = _get_data_source_and_table_id(graph_binding)
                    if not data_source or not table_id:
                        result["skipped"] += 1
                        continue
                    if dry_run:
                        result["applied"] += 1
                        logger.info(
                            "sync_graph_definition_to_bkbase dry_run downgrade to vm: data_link=%s, bk_biz_id=%s",
                            graph_binding.data_link_name,
                            graph_binding.bk_biz_id,
                        )
                        continue
                    data_link = DataLink.objects.get(
                        bk_tenant_id=graph_binding.bk_tenant_id,
                        namespace=graph_binding.namespace,
                        data_link_name=graph_binding.data_link_name,
                        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
                    )
                    data_link.apply_data_link(
                        bk_biz_id=graph_binding.bk_biz_id,
                        data_source=data_source,
                        table_id=table_id,
                        storage_cluster_name=graph_binding.vm_cluster_name,
                        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
                        persist_graph_write_mode=True,
                        surrealdb_auto_restore=True,
                    )
                    result["applied"] += 1
                    logger.warning(
                        "sync_graph_definition_to_bkbase: data_link=%s, bk_biz_id=%s has empty graph definitions, "
                        "downgraded to vm-only",
                        graph_binding.data_link_name,
                        graph_binding.bk_biz_id,
                    )
                    continue

                if not dry_run:
                    graph_binding.status = DataLinkResourceStatus.FAILED.value
                    graph_binding.save(update_fields=["status"])
                result["failed"] += 1
                result["failures"].append(
                    {
                        "data_link_name": graph_binding.data_link_name,
                        "bk_biz_id": graph_binding.bk_biz_id,
                        "error": error_message,
                    }
                )
                logger.warning(
                    "sync_graph_definition_to_bkbase: data_link=%s, bk_biz_id=%s has empty graph definitions, "
                    "mark failed",
                    graph_binding.data_link_name,
                    graph_binding.bk_biz_id,
                )
                continue
            sync_write_mode = _graph_definition_sync_write_mode(graph_binding)
            graph_definitions_changed = (
                _graph_definitions_changed(graph_binding, vertices, relations)
                or sync_write_mode != graph_binding.write_mode
            )
            if not graph_definitions_changed and _graph_relation_binding_sync_healthy(graph_binding):
                result["skipped"] += 1
                continue

            data_source, table_id = _get_data_source_and_table_id(graph_binding)
            if not data_source or not table_id:
                result["skipped"] += 1
                continue

            if dry_run:
                result["applied"] += 1
                logger.info(
                    "sync_graph_definition_to_bkbase dry_run: data_link=%s, bk_biz_id=%s, vertices=%s, relations=%s",
                    graph_binding.data_link_name,
                    graph_binding.bk_biz_id,
                    len(vertices),
                    len(relations),
                )
                continue

            data_link = DataLink.objects.get(
                bk_tenant_id=graph_binding.bk_tenant_id,
                namespace=graph_binding.namespace,
                data_link_name=graph_binding.data_link_name,
                data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
            )
            data_link.apply_data_link(
                bk_biz_id=graph_binding.bk_biz_id,
                data_source=data_source,
                table_id=table_id,
                storage_cluster_name=graph_binding.vm_cluster_name,
                write_mode=sync_write_mode,
            )
            result["applied"] += 1
            logger.info(
                "sync_graph_definition_to_bkbase applied: data_link=%s, bk_biz_id=%s, vertices=%s, relations=%s",
                graph_binding.data_link_name,
                graph_binding.bk_biz_id,
                len(vertices),
                len(relations),
            )
        except Exception as e:  # pylint: disable=broad-except
            result["failed"] += 1
            if not dry_run:
                graph_binding.status = DataLinkResourceStatus.FAILED.value
                graph_binding.save(update_fields=["status"])
            result["failures"].append(
                {
                    "data_link_name": graph_binding.data_link_name,
                    "bk_biz_id": graph_binding.bk_biz_id,
                    "error": str(e),
                }
            )
            logger.exception(
                "sync_graph_definition_to_bkbase failed: data_link=%s, bk_biz_id=%s, error=%s",
                graph_binding.data_link_name,
                graph_binding.bk_biz_id,
                e,
            )

    logger.info("sync_graph_definition_to_bkbase finished: result=%s", result)
    return result


def _apply_relation_graph_link_best_effort(
    data_link: DataLink,
    ds: DataSource,
    bk_biz_id: int,
    table_id: str,
    vm_cluster_name: str,
    effective_write_mode: str,
    graph_binding: GraphRelationBindingConfig | None = None,
    persist_graph_write_mode: bool = True,
    surrealdb_auto_restore: bool = False,
) -> bool:
    """
    Relation data must keep the historical VM/event path available.

    SurrealDB graph link apply is best effort in this periodic sync path: failures are logged and retried by the next
    run instead of rolling back the built-in relation RT/token refresh.
    """
    try:
        data_link.apply_data_link(
            bk_biz_id=bk_biz_id,
            data_source=ds,
            table_id=table_id,
            storage_cluster_name=vm_cluster_name,
            write_mode=effective_write_mode,
            persist_graph_write_mode=persist_graph_write_mode,
            surrealdb_auto_restore=surrealdb_auto_restore,
        )
        return True
    except Exception as e:  # pylint: disable=broad-except
        if graph_binding:
            graph_binding.status = DataLinkResourceStatus.FAILED.value
            graph_binding.save(update_fields=["status"])
        logger.warning(
            "enable_relation_surrealdb_dual_write: best-effort graph link apply failed, data_id->[%s], "
            "bk_biz_id->[%s], write_mode->[%s], error->[%s]",
            ds.bk_data_id,
            bk_biz_id,
            effective_write_mode,
            e,
        )
        return False


def _is_graph_relation_binding_apply_config_unchanged(
    graph_binding: GraphRelationBindingConfig,
    effective_write_mode: str,
    graph_binding_defaults: dict[str, Any],
) -> bool:
    if graph_binding.write_mode != effective_write_mode:
        return False

    for field, value in graph_binding_defaults.items():
        current_value = getattr(graph_binding, field)
        if field in {"vertices", "relations"}:
            if _canonical_graph_definitions(current_value) != _canonical_graph_definitions(value):
                return False
            continue
        if current_value != value:
            return False
    return True


def _enable_relation_surrealdb_dual_write_best_effort(ds: DataSource, bk_tenant_id: str, bk_biz_id: int) -> None:
    try:
        enable_relation_surrealdb_dual_write(ds, bk_tenant_id, bk_biz_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "sync_relation_redis_data: graph relation dual-write best-effort setup failed, "
            "data_id->[%s], bk_biz_id->[%s], error->[%s]",
            ds.bk_data_id,
            bk_biz_id,
            e,
        )


def _is_relation_surrealdb_dual_write_enabled() -> bool:
    # 内置关系周期路径和图定义变更路径共用同一个 rollout 开关，保持默认关闭语义一致。
    return getattr(settings, "ENABLE_SYNC_GRAPH_DEFINITION_TO_BKBASE", False)


def enable_relation_surrealdb_dual_write(ds: DataSource, bk_tenant_id: str, bk_biz_id: int) -> None:
    table_ids = list(
        DataSourceResultTable.objects.filter(bk_data_id=ds.bk_data_id, bk_tenant_id=bk_tenant_id).values_list(
            "table_id", flat=True
        )
    )
    if not table_ids:
        logger.warning(
            "enable_relation_surrealdb_dual_write: data_id->[%s] has no result table, skip apply graph relation link",
            ds.bk_data_id,
        )
        return

    table_id = table_ids[0]
    data_link_name = compose_bkdata_table_id(f"{bk_tenant_id}_{ds.data_name}_graph_relation")
    existed_graph_binding = GraphRelationBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        name=data_link_name,
    ).first()
    current_write_mode = (
        existed_graph_binding.write_mode
        if existed_graph_binding
        else GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    )
    desired_write_mode = (
        _graph_definition_sync_write_mode(existed_graph_binding) if existed_graph_binding else current_write_mode
    )
    apply_write_mode = desired_write_mode
    is_auto_restoring_vm_binding = (
        bool(existed_graph_binding and existed_graph_binding.surrealdb_auto_restore)
        and current_write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
        and desired_write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    )
    should_write_vm = desired_write_mode in (
        GraphRelationBindingConfig.WRITE_MODE_VM,
        GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )
    should_write_surrealdb = desired_write_mode in (
        GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )

    vm_cluster = None
    if should_write_vm:
        vm_cluster_queryset = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=ClusterInfo.TYPE_VM,
        )
        vm_cluster = (
            vm_cluster_queryset.filter(cluster_name=existed_graph_binding.vm_cluster_name).first()
            if existed_graph_binding and existed_graph_binding.vm_cluster_name
            else vm_cluster_queryset.filter(is_default_cluster=True).first()
        )
    if should_write_vm and not vm_cluster:
        logger.warning(
            "enable_relation_surrealdb_dual_write: data_id->[%s] has no vm cluster, skip apply graph relation link",
            ds.bk_data_id,
        )
        return

    surrealdb_cluster = None
    if should_write_surrealdb:
        surrealdb_cluster_queryset = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=ClusterInfo.TYPE_SURREALDB,
        )
        surrealdb_cluster = (
            surrealdb_cluster_queryset.filter(cluster_name=existed_graph_binding.surrealdb_cluster_name).first()
            if existed_graph_binding and existed_graph_binding.surrealdb_cluster_name
            else (
                surrealdb_cluster_queryset.filter(is_default_cluster=True).first()
                or surrealdb_cluster_queryset.order_by("cluster_id").first()
            )
        )
    if should_write_surrealdb and not surrealdb_cluster:
        if is_auto_restoring_vm_binding:
            logger.warning(
                "enable_relation_surrealdb_dual_write: data_id->[%s] has no surrealdb cluster, "
                "fallback to vm-only graph relation link",
                ds.bk_data_id,
            )
            desired_write_mode = current_write_mode
            apply_write_mode = GraphRelationBindingConfig.WRITE_MODE_VM
            should_write_surrealdb = False
        else:
            logger.warning(
                "enable_relation_surrealdb_dual_write: data_id->[%s] has no surrealdb cluster, "
                "skip apply graph relation link",
                ds.bk_data_id,
            )
            return

    vertices = []
    relations = []
    if should_write_surrealdb:
        vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=bk_biz_id)
        if not vertices or not relations:
            if desired_write_mode == GraphRelationBindingConfig.WRITE_MODE_SURREALDB:
                logger.warning(
                    "enable_relation_surrealdb_dual_write: data_id->[%s] has empty graph definitions and "
                    "surrealdb-only mode, skip apply graph relation link",
                    ds.bk_data_id,
                )
                return
            logger.warning(
                "enable_relation_surrealdb_dual_write: data_id->[%s] has empty graph definitions, downgrade to vm-only",
                ds.bk_data_id,
            )
            apply_write_mode = GraphRelationBindingConfig.WRITE_MODE_VM
            should_write_surrealdb = False
            if current_write_mode == GraphRelationBindingConfig.WRITE_MODE_VM:
                desired_write_mode = current_write_mode

    if not should_write_surrealdb and existed_graph_binding:
        vertices = existed_graph_binding.vertices
        relations = existed_graph_binding.relations
    graph_table_id = table_id.replace(".__default__", f"{SURREALDB_RT_SUFFIX}.__default__", 1)
    if graph_table_id == table_id:
        graph_table_id = f"{table_id}{SURREALDB_RT_SUFFIX}"

    data_link, _ = DataLink.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        data_link_name=data_link_name,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        defaults={
            "bk_data_id": ds.bk_data_id,
            "table_ids": table_ids,
            "data_link_strategy": DataLink.GRAPH_RELATION_TIME_SERIES,
        },
    )
    vm_cluster_name = vm_cluster.cluster_name if vm_cluster else ""
    surrealdb_cluster_name = surrealdb_cluster.cluster_name if surrealdb_cluster else ""
    if existed_graph_binding:
        vm_cluster_name = vm_cluster_name or existed_graph_binding.vm_cluster_name
        surrealdb_cluster_name = surrealdb_cluster_name or existed_graph_binding.surrealdb_cluster_name

    bkbase_result_table_name = DataLink.resolve_graph_relation_vm_result_table_name(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        default_name=compose_bkdata_table_id(table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
    )
    graph_binding_defaults = {
        "data_link_name": data_link.data_link_name,
        "bk_biz_id": bk_biz_id,
        "vm_cluster_name": vm_cluster_name,
        "surrealdb_cluster_name": surrealdb_cluster_name,
        "table_id": table_id,
        "bkbase_result_table_name": bkbase_result_table_name,
        "vm_storage_binding_name": bkbase_result_table_name,
        "vm_databus_name": bkbase_result_table_name,
        "graph_result_table_name": compose_bkdata_table_id(graph_table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
        "table_type": existed_graph_binding.table_type if existed_graph_binding else "temporary",
        "vertices": vertices,
        "relations": relations,
        "surrealdb_auto_restore": (
            bool(existed_graph_binding and existed_graph_binding.surrealdb_auto_restore)
            and desired_write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
        ),
    }
    graph_binding, created = GraphRelationBindingConfig.objects.get_or_create(
        bk_tenant_id=bk_tenant_id,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        name=data_link.data_link_name,
        defaults={
            **graph_binding_defaults,
            "write_mode": desired_write_mode,
            "status": DataLinkResourceStatus.INITIALIZING.value,
        },
    )
    if not created:
        if (
            apply_write_mode == desired_write_mode
            and _graph_relation_binding_sync_healthy(graph_binding)
            and _is_graph_relation_binding_apply_config_unchanged(
                graph_binding=graph_binding,
                effective_write_mode=desired_write_mode,
                graph_binding_defaults=graph_binding_defaults,
            )
        ):
            logger.info(
                "enable_relation_surrealdb_dual_write: graph link unchanged, skip apply, data_id->[%s], "
                "data_link->[%s], bk_biz_id->[%s]",
                ds.bk_data_id,
                data_link.data_link_name,
                bk_biz_id,
            )
            return
        for field, value in graph_binding_defaults.items():
            setattr(graph_binding, field, value)
        graph_binding.write_mode = desired_write_mode
        graph_binding.status = DataLinkResourceStatus.INITIALIZING.value
        update_fields = [*graph_binding_defaults, "write_mode", "status"]
        graph_binding.save(update_fields=update_fields)

    _apply_relation_graph_link_best_effort(
        data_link=data_link,
        ds=ds,
        bk_biz_id=bk_biz_id,
        table_id=table_id,
        vm_cluster_name=vm_cluster_name,
        effective_write_mode=apply_write_mode,
        graph_binding=graph_binding,
        persist_graph_write_mode=apply_write_mode == desired_write_mode,
        surrealdb_auto_restore=graph_binding_defaults["surrealdb_auto_restore"],
    )


@share_lock(ttl=3600, identify="metadata_sync_relation_redis_data")
def sync_relation_redis_data():
    """
    同步cmdb-relation内置数据
    """
    logger.info("sync_relation_redis_data started")
    start_time = time.time()
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_STARTED, process_target=None
    ).inc()
    # 获取对应的Redis数据
    redis_key = settings.BUILTIN_DATA_RT_REDIS_KEY
    redis_data = RedisTools.hgetall(redis_key)
    # 批量获取所有内置RT对象
    existing_rts = ResultTable.objects.filter(is_builtin=True)
    existing_rts_dict = {rt.table_id: rt for rt in existing_rts}
    existing_time_series_groups = TimeSeriesGroup.objects.filter(table_id__in=existing_rts_dict.keys())
    existing_time_series_groups_dict = {
        (group.bk_tenant_id, group.table_id): group for group in existing_time_series_groups
    }
    enable_graph_dual_write = _is_relation_surrealdb_dual_write_enabled()
    for field, value in redis_data.items():
        try:
            # 将json解析放在try中，确保value是有效的JSON字符串
            value_dict: dict[str, str | None] = json.loads(value)
            if not isinstance(value_dict, dict):
                raise ValueError(
                    "sync_relation_redis_data: Value->[%s] of field->[%s] is not a valid dictionary", value, field
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "sync_relation_redis_data: error occurred, field->[%s], error->[%s]. Using default value_dict.",
                field,
                e,
            )
            value_dict = {"token": None, "modifyTime": None}  # 预期中的默认字典

        # 解码并解析field
        key = field.decode("utf-8")
        space_type, space_id = key.split("__")

        # 转义业务ID，非业务类型ID为负数
        if space_type == "bkcc":
            biz_id = int(space_id)
        else:
            biz_id = Space.objects.get_biz_id_by_space(space_type, space_id)
            if not biz_id:
                logger.error(
                    "sync_relation_redis_data: space not found, space_type->[%s], space_id->[%s]", space_type, space_id
                )
                continue

        table_id, data_name = TimeSeriesGroup.make_cmdb_relation_builtin_table_id_and_group_name(biz_id, space_type)

        token = value_dict.get("token")  # Redis缓存中的Token数据

        logger.info("sync_relation_redis_data start sync builtin redis data, field=%s", key)

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(biz_id)
        rt = existing_rts_dict.get(table_id)
        if rt:
            try:
                new_modify_time = str(int(time.time()))
                ds = DataSource.objects.get(bk_tenant_id=bk_tenant_id, data_name=data_name)
                generated_token = transform_data_id_to_token(
                    metric_data_id=ds.bk_data_id, bk_biz_id=biz_id, app_name=data_name
                )
                time_series_group = existing_time_series_groups_dict.get((bk_tenant_id, table_id))
                builtin_token = _get_builtin_relation_token(ds, table_id, generated_token, time_series_group)
                # 兼容历史问题，如果DB中存储的Token和实际采集校验 Token 不一致，更新之
                if ds.token != builtin_token:
                    logger.info(
                        "sync_relation_redis_data: data_id->[%s] ,token is not same,db_record->[%s],"
                        "builtin_token->[%s]",
                        ds.bk_data_id,
                        ds.token,
                        builtin_token,
                    )
                    ds.token = builtin_token
                    ds.save(update_fields=["token"])
                    ds.refresh_consul_config()

                # 更新Redis中的数据
                value_dict["token"] = builtin_token
                value_dict["modifyTime"] = new_modify_time
                RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
                if enable_graph_dual_write:
                    _enable_relation_surrealdb_dual_write_best_effort(ds, bk_tenant_id, biz_id)
                logger.info(
                    "sync_relation_redis_data: Update Data For Field->[%s],has completed,value->[%s]", key, value_dict
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "sync_relation_redis_data: update redis data failed, field->[%s], value->[%s],error->[%s]",
                    field,
                    value_dict,
                    e,
                )
                continue
        else:
            if token:  # RT不存在，Token存在场景 -> 跳过创建
                continue

            try:
                logger.info("sync_relation_redis_data: create builtin metadata for field->[%s]", key)
                with transaction.atomic():
                    # field下对应RT不存在且Token不存在，创建新DS与RT,使用事务保证实例同时成功创建
                    ds = DataSource.create_data_source(
                        bk_tenant_id=bk_tenant_id,
                        data_name=data_name,
                        operator="system",
                        type_label="time_series",
                        source_label="bk_monitor",
                        etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
                        space_type_id=space_type,
                        space_uid=key,
                        bk_biz_id=biz_id,
                    )
                    ts_group = TimeSeriesGroup.create_time_series_group(
                        bk_data_id=ds.bk_data_id,
                        bk_biz_id=biz_id,
                        time_series_group_name=data_name,
                        label=Label.RESULT_TABLE_LABEL_OTHER,
                        operator="system",
                        table_id=table_id,
                        is_builtin=True,
                        bk_tenant_id=bk_tenant_id,
                    )
                    existing_time_series_groups_dict[(bk_tenant_id, table_id)] = ts_group
                generated_token = transform_data_id_to_token(
                    metric_data_id=ds.bk_data_id,
                    bk_biz_id=biz_id,
                    app_name=data_name,
                )
                time_series_group = ts_group
                builtin_token = _get_builtin_relation_token(ds, table_id, generated_token, time_series_group)
                if ds.token != builtin_token:
                    ds.token = builtin_token
                    ds.save(update_fields=["token"])
                    ds.refresh_consul_config()
                # 更新Redis中的Token和modifyTime
                value_dict["token"] = builtin_token
                value_dict["modifyTime"] = int(ts_group.last_modify_time.timestamp())
                RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
                if enable_graph_dual_write:
                    _enable_relation_surrealdb_dual_write_best_effort(ds, bk_tenant_id, biz_id)
                logger.info(
                    "sync_relation_redis_data: Create Data For Field->[%s],has completed,value->[%s]",
                    key,
                    value_dict,
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "sync_relation_redis_data: create builtin metadata failed, field->[%s], value->[%s],error->[%s]",
                    field,
                    value_dict,
                    e,
                )

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_relation_redis_data", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("sync_relation_redis_data finished successfully,use->[%s] seconds", cost_time)
