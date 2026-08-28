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
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.prometheus import metrics
from metadata import config
from metadata.models import (
    ClusterInfo,
    DataSource,
    DataSourceResultTable,
    GraphRelationV4DataLinkOption,
    Label,
    ResultTable,
    ResultTableOption,
    Space,
    SurrealDBStorage,
    TimeSeriesGroup,
)
from metadata.models.entity_relation import EntityMeta
from metadata.models.space.constants import EtlConfigs
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")
GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST = "GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST"


@dataclass
class _RelationSyncContext:
    """单个 Redis field 对应的 CMDB relation 同步上下文。"""

    field: bytes | str
    key: str
    value: dict[str, Any]
    space_type: str
    space_id: str
    bk_biz_id: int
    bk_tenant_id: str
    table_id: str
    data_name: str

    @property
    def redis_token(self) -> str:
        return self.value.get("token") or ""


def _get_graph_relation_bkbase_sync_biz_ids() -> set[int]:
    raw_biz_ids = getattr(settings, GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST, [])
    if raw_biz_ids is None:
        return set()
    if isinstance(raw_biz_ids, str):
        values = raw_biz_ids.split(",")
    elif isinstance(raw_biz_ids, list | tuple | set):
        values = raw_biz_ids
    else:
        values = [raw_biz_ids]

    biz_ids = set()
    for value in values:
        value = str(value).strip()
        if not value:
            continue
        try:
            biz_ids.add(int(value))
        except ValueError:
            logger.warning(
                "invalid %s item ignored: %s",
                GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST,
                value,
            )
    return biz_ids


def _get_builtin_relation_token(
    data_source: DataSource,
    bk_biz_id: int,
    data_name: str,
    time_series_group: TimeSeriesGroup | None = None,
) -> str:
    """获取 relation 上报 token。

    正常链路以 TimeSeriesGroup.token 为准；仅在历史 RT 缺少 TimeSeriesGroup
    记录时，使用可重复计算的 Prometheus token 作为兼容兜底。
    """
    if time_series_group and time_series_group.token:
        return time_series_group.token
    return transform_data_id_to_token(
        metric_data_id=data_source.bk_data_id,
        bk_biz_id=bk_biz_id,
        app_name=data_name,
    )


def _canonical_graph_definitions(definitions: list) -> list[str]:
    return sorted(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in definitions)


def _is_relation_surrealdb_dual_write_enabled(bk_biz_id: int, enabled_biz_ids: set[int] | None = None) -> bool:
    enabled_biz_ids = enabled_biz_ids if enabled_biz_ids is not None else _get_graph_relation_bkbase_sync_biz_ids()
    return bk_biz_id in enabled_biz_ids


def _compose_relation_graph_v4_storage_config(
    bk_tenant_id: str,
    bk_biz_id: int,
    table_id: str,
) -> dict[str, Any]:
    """校验 Graph V4 依赖，并生成保持已有集群稳定的 SurrealDB external storage 配置。"""
    surrealdb_storage = SurrealDBStorage.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
    ).first()
    if surrealdb_storage is not None:
        storage_cluster_id = surrealdb_storage.storage_cluster_id
    else:
        default_clusters = list(
            ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                cluster_type=ClusterInfo.TYPE_SURREALDB,
                is_default_cluster=True,
            )
        )
        if len(default_clusters) != 1:
            raise ValueError(
                f"sync_relation_redis_data: tenant({bk_tenant_id}) requires exactly one default SurrealDB cluster, "
                f"found {len(default_clusters)}"
            )
        storage_cluster_id = default_clusters[0].cluster_id

    vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=bk_biz_id)
    if not vertices:
        raise ValueError(f"sync_relation_redis_data: bk_biz_id({bk_biz_id}) graph vertices are empty")
    if not relations:
        raise ValueError(f"sync_relation_redis_data: bk_biz_id({bk_biz_id}) graph relations are empty")

    return {
        "storage_cluster_id": storage_cluster_id,
        "table_type": SurrealDBStorage.TEMPORARY_TABLE_TYPE,
        "vertices": vertices,
        "relations": relations,
    }


def _modify_relation_graph_v4_result_table(
    result_table: ResultTable,
    storage_config: dict[str, Any],
) -> bool:
    """通过普通 ResultTable 变更流程同步刷新 Graph V4 storage、option 和接入链路。"""
    # storage、option 和 Graph V4 接入必须处于同一事务；同步 apply 失败时由
    # ResultTable.modify 回滚本地配置。
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        result_table = (
            ResultTable.objects.using(config.DATABASE_CONNECTION_NAME).select_for_update().get(pk=result_table.pk)
        )
        desired_graph_option = GraphRelationV4DataLinkOption(write_targets=["vm", "surrealdb"])
        surrealdb_storage = (
            SurrealDBStorage.objects.using(config.DATABASE_CONNECTION_NAME)
            .filter(
                bk_tenant_id=result_table.bk_tenant_id,
                table_id=result_table.table_id,
            )
            .first()
        )
        graph_option_record = (
            ResultTableOption.objects.using(config.DATABASE_CONNECTION_NAME)
            .filter(
                bk_tenant_id=result_table.bk_tenant_id,
                table_id=result_table.table_id,
                name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
            )
            .first()
        )
        current_graph_option = None
        if graph_option_record is not None:
            try:
                current_graph_option = GraphRelationV4DataLinkOption.from_option_value(graph_option_record.get_value())
            except (TypeError, ValueError):
                # 非法旧值视为配置变化，交给普通 modify 流程覆盖修复。
                pass

        storage_unchanged = bool(
            surrealdb_storage
            and surrealdb_storage.storage_cluster_id == storage_config["storage_cluster_id"]
            and surrealdb_storage.table_type == storage_config["table_type"]
            and _canonical_graph_definitions(surrealdb_storage.vertices)
            == _canonical_graph_definitions(storage_config["vertices"])
            and _canonical_graph_definitions(surrealdb_storage.relations)
            == _canonical_graph_definitions(storage_config["relations"])
        )
        option_unchanged = bool(
            current_graph_option and current_graph_option.model_dump() == desired_graph_option.model_dump()
        )
        if storage_unchanged and option_unchanged:
            logger.info(
                "sync_relation_redis_data: graph relation config unchanged, skip ResultTable.modify, "
                "bk_tenant_id->[%s], table_id->[%s]",
                result_table.bk_tenant_id,
                result_table.table_id,
            )
            return False

        # ResultTable.modify 会以传入 option 为完整期望状态，因此先合并当前全部
        # ResultTableOption，仅覆盖 Graph V4 配置，避免丢失已有查询或清洗选项。
        options = {
            option.name: option.get_value()
            for option in ResultTableOption.objects.using(config.DATABASE_CONNECTION_NAME).filter(
                bk_tenant_id=result_table.bk_tenant_id,
                table_id=result_table.table_id,
            )
        }
        options[ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK] = desired_graph_option.model_dump()
        result_table.modify(
            operator="system",
            external_storage={ClusterInfo.TYPE_SURREALDB: storage_config},
            option=options,
        )
        return True


def enable_relation_surrealdb_dual_write(
    ds: DataSource,
    bk_tenant_id: str,
    bk_biz_id: int,
    storage_config: dict[str, Any] | None = None,
) -> bool:
    """将 CMDB relation RT 配置为普通 Graph V4 VM + SurrealDB 双写链路"""
    table_ids = list(
        DataSourceResultTable.objects.filter(bk_data_id=ds.bk_data_id, bk_tenant_id=bk_tenant_id).values_list(
            "table_id", flat=True
        )
    )
    if len(table_ids) != 1:
        raise ValueError(
            f"enable_relation_surrealdb_dual_write: tenant({bk_tenant_id}) data_id({ds.bk_data_id}) "
            f"requires exactly one result table, found {len(table_ids)}"
        )
    result_table = ResultTable.objects.get(
        bk_tenant_id=bk_tenant_id,
        table_id=table_ids[0],
    )
    storage_config = storage_config or _compose_relation_graph_v4_storage_config(
        bk_tenant_id,
        bk_biz_id,
        result_table.table_id,
    )
    return _modify_relation_graph_v4_result_table(result_table, storage_config)


def _parse_relation_redis_value(field: bytes | str, raw_value: bytes | str) -> dict[str, Any]:
    """解析 Redis value；脏数据按空配置处理，由后续流程重新生成 token。"""
    try:
        value = json.loads(raw_value)
        if not isinstance(value, dict):
            raise ValueError(f"value is not a dictionary: {value!r}")
        return value
    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "sync_relation_redis_data: invalid redis value, field->[%s], value->[%s], error->[%s]; "
            "use empty value instead",
            field,
            raw_value,
            e,
        )
        return {"token": None, "modifyTime": None}


def _build_relation_sync_context(field: bytes | str, raw_value: bytes | str) -> _RelationSyncContext | None:
    """解析 Redis field，并补齐单业务同步所需的租户、RT 和数据源标识。"""
    value = _parse_relation_redis_value(field, raw_value)
    try:
        key = field.decode("utf-8") if isinstance(field, bytes) else field
        space_type, space_id = key.split("__", maxsplit=1)
        if not space_type or not space_id:
            raise ValueError("space type or space id is empty")

        if space_type == "bkcc":
            bk_biz_id = int(space_id)
        else:
            bk_biz_id = Space.objects.get_biz_id_by_space(space_type, space_id)
            if not bk_biz_id:
                raise ValueError(f"space does not exist: {space_type}__{space_id}")

        data_name = f"{bk_biz_id}_{space_type}_built_in_time_series"
        table_id = f"{data_name}.__default__"
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "sync_relation_redis_data: invalid redis field, field->[%s], error->[%s]",
            field,
            e,
        )
        return None

    return _RelationSyncContext(
        field=field,
        key=key,
        value=value,
        space_type=space_type,
        space_id=space_id,
        bk_biz_id=bk_biz_id,
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        data_name=data_name,
    )


def _sync_relation_metadata(
    redis_key: str,
    context: _RelationSyncContext,
    result_table: ResultTable | None,
    time_series_group: TimeSeriesGroup | None,
    graph_storage_config: dict[str, Any] | None,
) -> DataSource:
    """创建或读取 relation 元数据，并统一回写 Redis token。"""
    # 步骤 1：复用已有 DataSource，或在一个事务内创建完整的 relation 元数据。
    if result_table is not None:
        data_source = DataSource.objects.get(
            bk_tenant_id=context.bk_tenant_id,
            data_name=context.data_name,
        )
        modify_time: str | int = str(int(time.time()))
    else:
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            data_source = DataSource.create_data_source(
                bk_tenant_id=context.bk_tenant_id,
                data_name=context.data_name,
                operator="system",
                type_label="time_series",
                source_label="bk_monitor",
                etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
                space_type_id=context.space_type,
                space_uid=context.key,
                bk_biz_id=context.bk_biz_id,
            )
            time_series_group = TimeSeriesGroup.create_time_series_group(
                bk_data_id=data_source.bk_data_id,
                bk_biz_id=context.bk_biz_id,
                time_series_group_name=context.data_name,
                label=Label.RESULT_TABLE_LABEL_OTHER,
                operator="system",
                table_id=context.table_id,
                is_builtin=True,
                bk_tenant_id=context.bk_tenant_id,
                # Graph 白名单业务先创建本地 RT，再由 ResultTable.modify 一次性
                # 下发 VM + SurrealDB，避免提前创建一条普通 VM 链路。
                is_sync_db=graph_storage_config is None,
            )
        modify_time = int(time_series_group.last_modify_time.timestamp())

    # 步骤 2：计算并回写 relation 生产端使用的 Redis token。
    # relation 生产端从 Redis 获取 TimeSeriesGroup token；DataSource.token
    # 是另一套独立上报凭证，不在这个周期任务中修改。
    context.value["token"] = _get_builtin_relation_token(
        data_source,
        context.bk_biz_id,
        context.data_name,
        time_series_group,
    )
    context.value["modifyTime"] = modify_time
    RedisTools.hset_to_redis(
        redis_key,
        context.key,
        json.dumps(context.value),
    )
    return data_source


def _sync_relation_redis_item(
    redis_key: str,
    context: _RelationSyncContext,
    result_table: ResultTable | None,
    time_series_group: TimeSeriesGroup | None,
    enabled_graph_biz_ids: set[int],
) -> None:
    """同步单个 relation field，并将异常隔离在当前业务。"""
    logger.info("sync_relation_redis_data: start sync field->[%s]", context.key)

    # 步骤 1：先处理不能安全自动修复的历史状态。
    if result_table is None and context.redis_token:
        # Redis 已有 token 说明生产端可能仍在使用历史链路。此时自动创建新
        # DataSource 会生成新的 data_id/token，因此保守跳过，避免覆盖在线凭证。
        logger.warning(
            "sync_relation_redis_data: result table is missing but redis token exists, skip auto creation, "
            "field->[%s], table_id->[%s]",
            context.key,
            context.table_id,
        )
        return

    # 步骤 2：为白名单业务准备 Graph 配置。依赖异常时仅跳过本轮 Graph。
    graph_storage_config = None
    if _is_relation_surrealdb_dual_write_enabled(context.bk_biz_id, enabled_graph_biz_ids):
        try:
            graph_storage_config = _compose_relation_graph_v4_storage_config(
                context.bk_tenant_id,
                context.bk_biz_id,
                context.table_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            # Graph 依赖异常只影响本轮 Graph 配置，普通 relation RT 和
            # Redis token 仍按主流程维护。
            logger.warning(
                "sync_relation_redis_data: graph relation dependency check failed, "
                "bk_tenant_id->[%s], bk_biz_id->[%s], error->[%s]",
                context.bk_tenant_id,
                context.bk_biz_id,
                e,
            )

    # 步骤 3：创建或复用 relation 元数据，并完成 Redis token 回写。
    # 失败只终止当前 field，后续业务继续处理。
    action = "update" if result_table is not None else "create"
    try:
        data_source = _sync_relation_metadata(
            redis_key,
            context,
            result_table,
            time_series_group,
            graph_storage_config,
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "sync_relation_redis_data: %s relation metadata failed, field->[%s], value->[%s], error->[%s]",
            action,
            context.field,
            context.value,
            e,
        )
        return

    # 步骤 4：Graph 接入作为附加能力 best-effort 执行。
    # 接入失败只记录告警，并在下个
    # 周期重试，不回滚已经完成的 RT 创建和 Redis token 更新。
    if graph_storage_config is not None:
        try:
            enable_relation_surrealdb_dual_write(
                data_source,
                context.bk_tenant_id,
                context.bk_biz_id,
                storage_config=graph_storage_config,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "sync_relation_redis_data: graph relation dual-write best-effort setup failed, "
                "data_id->[%s], bk_biz_id->[%s], error->[%s]",
                data_source.bk_data_id,
                context.bk_biz_id,
                e,
            )

    logger.info(
        "sync_relation_redis_data: %s relation metadata completed, field->[%s], value->[%s]",
        action,
        context.key,
        context.value,
    )


@share_lock(ttl=3600, identify="metadata_sync_relation_redis_data")
def sync_relation_redis_data():
    """按 Redis field 同步 CMDB relation 内置 RT、token 和 Graph V4 配置。

    主流程只负责批量加载已有元数据和逐项调度。单业务的数据解析、创建/更新
    以及 Graph best-effort 异常均在各自 helper 内隔离，避免影响后续业务。
    """
    logger.info("sync_relation_redis_data started")
    start_time = time.time()
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_STARTED, process_target=None
    ).inc()

    # 步骤 1：读取 CMDB relation 生产端维护的全部空间配置。
    redis_key = settings.BUILTIN_DATA_RT_REDIS_KEY
    redis_data = RedisTools.hgetall(redis_key)

    # 步骤 2：预加载已有 relation 元数据，循环内只进行精确匹配和必要的写操作。
    # 多租户下 table_id 可能相同，因此必须使用 tenant + table_id 作为身份。
    existing_result_tables = list(ResultTable.objects.filter(is_builtin=True))
    existing_result_table_map = {
        (result_table.bk_tenant_id, result_table.table_id): result_table for result_table in existing_result_tables
    }
    existing_time_series_groups = TimeSeriesGroup.objects.filter(
        table_id__in=[result_table.table_id for result_table in existing_result_tables]
    )
    existing_time_series_group_map = {
        (group.bk_tenant_id, group.table_id): group for group in existing_time_series_groups
    }
    enabled_graph_biz_ids = _get_graph_relation_bkbase_sync_biz_ids()

    # 步骤 3：逐个解析 Redis field 并同步，单 field 异常在内部隔离。
    for field, raw_value in redis_data.items():
        context = _build_relation_sync_context(field, raw_value)
        if context is None:
            continue

        identity = (context.bk_tenant_id, context.table_id)
        _sync_relation_redis_item(
            redis_key,
            context,
            existing_result_table_map.get(identity),
            existing_time_series_group_map.get(identity),
            enabled_graph_biz_ids,
        )

    # 步骤 4：所有 field 处理完成后统一上报本轮任务指标。
    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_relation_redis_data", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("sync_relation_redis_data finished successfully,use->[%s] seconds", cost_time)
