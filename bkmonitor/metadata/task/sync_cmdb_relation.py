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
    ds: DataSource, table_id: str, generated_token: str, time_series_group: TimeSeriesGroup | None = None
) -> str:
    return time_series_group.token if time_series_group and time_series_group.token else generated_token


def _canonical_graph_definitions(definitions: list) -> list[str]:
    return sorted(json.dumps(item, sort_keys=True, ensure_ascii=False) for item in definitions)


def _is_relation_surrealdb_dual_write_enabled(bk_biz_id: int, enabled_biz_ids: set[int] | None = None) -> bool:
    enabled_biz_ids = enabled_biz_ids if enabled_biz_ids is not None else _get_graph_relation_bkbase_sync_biz_ids()
    return bk_biz_id in enabled_biz_ids


def _compose_relation_graph_v4_storage_config(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    """校验 Graph V4 依赖，并生成普通 SurrealDB external storage 配置。"""
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

    vertices, relations = EntityMeta.auto_query_graph_definitions(bk_biz_id=bk_biz_id)
    if not vertices:
        raise ValueError(f"sync_relation_redis_data: bk_biz_id({bk_biz_id}) graph vertices are empty")
    if not relations:
        raise ValueError(f"sync_relation_redis_data: bk_biz_id({bk_biz_id}) graph relations are empty")

    return {
        "storage_cluster_id": default_clusters[0].cluster_id,
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
    """将 CMDB relation RT 配置为普通 Graph V4 VM + SurrealDB 双写链路。

    此函数只适用于包含 VM 的接入，因此复用 TimeSeriesGroup 创建的 ResultTable。
    如果未来改为 SurrealDB-only，应直接创建普通 ResultTable，不创建 TimeSeriesGroup，
    并将 ResultTable.default_storage 设置为 SurrealDB，而不是继续沿用本双写流程。
    """
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
    storage_config = storage_config or _compose_relation_graph_v4_storage_config(bk_tenant_id, bk_biz_id)
    return _modify_relation_graph_v4_result_table(result_table, storage_config)


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
    enabled_graph_dual_write_biz_ids = _get_graph_relation_bkbase_sync_biz_ids()
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

        bk_tenant_id = bk_biz_id_to_bk_tenant_id(biz_id)
        graph_storage_config = None
        if _is_relation_surrealdb_dual_write_enabled(biz_id, enabled_graph_dual_write_biz_ids):
            # 白名单业务必须先完成全部只读依赖检查。校验失败直接终止本次任务，
            # 此前不能修改 relation RT、storage、option、数据源 token 或 Redis token。
            graph_storage_config = _compose_relation_graph_v4_storage_config(bk_tenant_id, biz_id)

        token = value_dict.get("token")  # Redis缓存中的Token数据

        logger.info("sync_relation_redis_data start sync builtin redis data, field=%s", key)

        rt = existing_rts_dict.get(table_id)
        if rt:
            ds = None
            if graph_storage_config is not None:
                # Graph 配置失败需要直接向上抛出，不能被原有 Redis token
                # 修复逻辑吞掉；ResultTable.modify 自身负责事务和同步接入。
                ds = DataSource.objects.get(bk_tenant_id=bk_tenant_id, data_name=data_name)
                enable_relation_surrealdb_dual_write(
                    ds,
                    bk_tenant_id,
                    biz_id,
                    storage_config=graph_storage_config,
                )
            try:
                new_modify_time = str(int(time.time()))
                ds = ds or DataSource.objects.get(bk_tenant_id=bk_tenant_id, data_name=data_name)
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
                with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
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
                        # 白名单业务先只创建本地 RT 配置，避免普通 VM 接入先于
                        # 随后的 ResultTable.modify Graph V4 配置生效。
                        is_sync_db=graph_storage_config is None,
                    )
                    existing_time_series_groups_dict[(bk_tenant_id, table_id)] = ts_group
                    if graph_storage_config is not None:
                        enable_relation_surrealdb_dual_write(
                            ds,
                            bk_tenant_id,
                            biz_id,
                            storage_config=graph_storage_config,
                        )
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
                if graph_storage_config is not None:
                    raise

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_relation_redis_data", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("sync_relation_redis_data finished successfully,use->[%s] seconds", cost_time)
