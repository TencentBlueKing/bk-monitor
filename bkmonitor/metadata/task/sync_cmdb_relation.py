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

from alarm_backends.core.lock.service_lock import share_lock
from bkm_space.utils import space_uid_to_bk_biz_id
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
from metadata.models.data_link.data_link_configs import GraphRelationBindingConfig, SurrealDBBindingConfig
from metadata.models.data_link.utils import compose_bkdata_table_id
from metadata.models.entity_relation import EntityMeta, NAMESPACE_ALL
from metadata.models.space.constants import EtlConfigs
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


def _get_graph_definition_binding_queryset(namespace: str):
    queryset = GraphRelationBindingConfig.objects.filter(
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        write_mode__in=[
            GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
            GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        ],
    )
    if namespace and namespace != NAMESPACE_ALL:
        bk_biz_id = space_uid_to_bk_biz_id(namespace)
        if not bk_biz_id:
            logger.warning(
                "sync_graph_definition_to_bkbase: namespace->[%s] cannot resolve bk_biz_id, skip", namespace
            )
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
        logger.warning(
            "sync_graph_definition_to_bkbase: data_link->[%s] not found, skip", graph_binding.data_link_name
        )
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
    if graph_binding.vertices != vertices or graph_binding.relations != relations:
        return True

    if not graph_binding.graph_result_table_name:
        return True

    return not SurrealDBBindingConfig.objects.filter(
        bk_tenant_id=graph_binding.bk_tenant_id,
        namespace=graph_binding.namespace,
        data_link_name=graph_binding.data_link_name,
        name=graph_binding.graph_result_table_name,
    ).exists()


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
            if not vertices and not relations:
                result["skipped"] += 1
                logger.warning(
                    "sync_graph_definition_to_bkbase: data_link=%s, bk_biz_id=%s has empty graph definitions, skip",
                    graph_binding.data_link_name,
                    graph_binding.bk_biz_id,
                )
                continue
            if not _graph_definitions_changed(graph_binding, vertices, relations):
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
            )
            data_link.apply_data_link(
                bk_biz_id=graph_binding.bk_biz_id,
                data_source=data_source,
                table_id=table_id,
                storage_cluster_name=graph_binding.vm_cluster_name,
                write_mode=graph_binding.write_mode,
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

    return all(getattr(graph_binding, field) == value for field, value in graph_binding_defaults.items())


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
    data_link_name = f"{ds.data_name}_graph_relation"
    existed_graph_binding = GraphRelationBindingConfig.objects.filter(
        bk_tenant_id=bk_tenant_id,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        name=data_link_name,
    ).first()
    effective_write_mode = (
        existed_graph_binding.write_mode
        if existed_graph_binding
        else GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    )
    should_write_vm = effective_write_mode in (
        GraphRelationBindingConfig.WRITE_MODE_VM,
        GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )
    should_write_surrealdb = effective_write_mode in (
        GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )

    vm_cluster = None
    if should_write_vm:
        vm_cluster = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=ClusterInfo.TYPE_VM,
            is_default_cluster=True,
        ).first()
    if should_write_vm and not vm_cluster:
        logger.warning(
            "enable_relation_surrealdb_dual_write: data_id->[%s] has no default vm cluster, skip apply graph relation link",
            ds.bk_data_id,
        )
        return

    surrealdb_cluster = None
    if should_write_surrealdb:
        surrealdb_cluster = ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_type=ClusterInfo.TYPE_SURREALDB,
            is_default_cluster=True,
        ).first()
    if should_write_surrealdb and not surrealdb_cluster:
        logger.warning(
            "enable_relation_surrealdb_dual_write: data_id->[%s] has no default surrealdb cluster, skip apply graph relation link",
            ds.bk_data_id,
        )
        return

    vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=bk_biz_id)
    if should_write_surrealdb and not vertices and not relations:
        if effective_write_mode == GraphRelationBindingConfig.WRITE_MODE_SURREALDB:
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
        effective_write_mode = GraphRelationBindingConfig.WRITE_MODE_VM
        should_write_surrealdb = False
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

    graph_binding_defaults = {
        "data_link_name": data_link.data_link_name,
        "bk_biz_id": bk_biz_id,
        "vm_cluster_name": vm_cluster_name,
        "surrealdb_cluster_name": surrealdb_cluster_name,
        "table_id": table_id,
        "bkbase_result_table_name": compose_bkdata_table_id(table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
        "graph_result_table_name": compose_bkdata_table_id(graph_table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
        "table_type": "temporary",
        "vertices": vertices,
        "relations": relations,
    }
    graph_binding, created = GraphRelationBindingConfig.objects.get_or_create(
        bk_tenant_id=bk_tenant_id,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        name=data_link.data_link_name,
        defaults={
            **graph_binding_defaults,
            "write_mode": effective_write_mode,
            "status": DataLinkResourceStatus.INITIALIZING.value,
        },
    )
    if not created:
        if (
            graph_binding.component_status == DataLinkResourceStatus.OK.value
            and _is_graph_relation_binding_apply_config_unchanged(
                graph_binding=graph_binding,
                effective_write_mode=effective_write_mode,
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
        graph_binding.write_mode = effective_write_mode
        graph_binding.status = DataLinkResourceStatus.INITIALIZING.value
        graph_binding.save(update_fields=[*graph_binding_defaults, "write_mode", "status"])

    _apply_relation_graph_link_best_effort(
        data_link=data_link,
        ds=ds,
        bk_biz_id=bk_biz_id,
        table_id=table_id,
        vm_cluster_name=vm_cluster_name,
        effective_write_mode=effective_write_mode,
        graph_binding=graph_binding,
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

        data_name = f"{biz_id}_{space_type}_built_in_time_series"
        table_id = f"{biz_id}_{space_type}_built_in_time_series.__default__"  # table_id有限制，必须以业务ID数字开头
        token = value_dict.get("token")  # Redis缓存中的Token数据

        logger.info("sync_relation_redis_data start sync builtin redis data, field=%s", key)

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(biz_id)
        rt = existing_rts_dict.get(table_id)
        if rt:
            try:
                new_modify_time = str(int(time.time()))
                ds = DataSource.objects.get(data_name=data_name)
                generated_token = transform_data_id_to_token(
                    metric_data_id=ds.bk_data_id, bk_biz_id=biz_id, app_name=data_name
                )
                # 兼容历史问题，如果DB中存储的Token和生成的不一致，更新之
                if ds.token != generated_token:
                    logger.info(
                        "sync_relation_redis_data: data_id->[%s] ,token is not same,db_record->[%s],"
                        "generated_token->[%s]",
                        ds.bk_data_id,
                        ds.token,
                        generated_token,
                    )
                    ds.token = generated_token
                    ds.save()

                # 更新Redis中的数据
                value_dict["token"] = generated_token
                value_dict["modifyTime"] = new_modify_time
                enable_relation_surrealdb_dual_write(ds, bk_tenant_id, biz_id)
                RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
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
            if token:  # RT不存在，Token不存在场景 -> 创建新DS&RT -> 写入Redis
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
                    new_rt = TimeSeriesGroup.create_time_series_group(
                        bk_data_id=ds.bk_data_id,
                        bk_biz_id=biz_id,
                        time_series_group_name=data_name,
                        label=Label.RESULT_TABLE_LABEL_OTHER,
                        operator="system",
                        table_id=table_id,
                        is_builtin=True,
                        default_storage_config={
                            ClusterInfo.TYPE_INFLUXDB,
                        },
                        bk_tenant_id=bk_tenant_id,
                    )
                    generated_token = transform_data_id_to_token(
                        metric_data_id=ds.bk_data_id,
                        bk_biz_id=biz_id,
                        app_name=data_name,
                    )
                    enable_relation_surrealdb_dual_write(ds, bk_tenant_id, biz_id)
                ds.token = generated_token
                ds.save()
                # 更新Redis中的Token和modifyTime
                value_dict["token"] = generated_token
                value_dict["modifyTime"] = int(new_rt.last_modify_time.timestamp())
                RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
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
