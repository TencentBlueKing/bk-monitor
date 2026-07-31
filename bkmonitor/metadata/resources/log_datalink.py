"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from django.db.transaction import atomic
from rest_framework import serializers

from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.user import get_request_username
from core.drf_resource import Resource
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.service.space_redis import SpaceTableIDRedis

logger = logging.getLogger(__name__)


class ParamsSerializer(serializers.Serializer):
    """参数序列化器"""

    class RtOption(serializers.Serializer):
        name = serializers.CharField(required=True, label="名称")
        value = serializers.CharField(required=True, label="值")
        value_type = serializers.CharField(required=False, label="值类型", default="dict")
        creator = serializers.CharField(required=False, label="创建者", default="system")

    bk_tenant_id = TenantIdField(label="租户ID")
    options = serializers.ListField(required=False, child=RtOption(), default=list)


def _create_or_update_options(bk_tenant_id: str, table_id: str, options: list[dict]) -> None:
    """创建或者更新结果表 option。"""

    exist_objs = {
        obj.name: obj for obj in models.ResultTableOption.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
    }
    need_update_objs, need_add_objs = [], []
    update_fields = set()

    for option in options:
        exist_obj = exist_objs.get(option["name"])
        need_update = False
        if exist_obj:
            if option["value"] != exist_obj.value:
                exist_obj.value = option["value"]
                update_fields.add("value")
                need_update = True
            if option["value_type"] != exist_obj.value_type:
                exist_obj.value_type = option["value_type"]
                update_fields.add("value_type")
                need_update = True
            if need_update:
                need_update_objs.append(exist_obj)
        else:
            need_add_objs.append(models.ResultTableOption(bk_tenant_id=bk_tenant_id, table_id=table_id, **dict(option)))

    if need_add_objs:
        models.ResultTableOption.objects.bulk_create(need_add_objs, batch_size=BULK_CREATE_BATCH_SIZE)
    if need_update_objs:
        models.ResultTableOption.objects.bulk_update(
            need_update_objs, list(update_fields), batch_size=BULK_UPDATE_BATCH_SIZE
        )


def _resolve_route_cluster_id(
    *,
    storage_model,
    bk_tenant_id: str,
    origin_table_id: str | None,
    requested_cluster_id: int | None,
    current_cluster_id: int | None,
) -> int | None:
    """解析路由集群，请求值优先，其次沿当前路由或 origin Storage 继承。"""

    if requested_cluster_id is not None:
        return requested_cluster_id
    if current_cluster_id is not None:
        return current_cluster_id
    if not origin_table_id:
        return None
    return (
        storage_model.objects.filter(bk_tenant_id=bk_tenant_id, table_id=origin_table_id)
        .values_list("storage_cluster_id", flat=True)
        .first()
    )


def _save_changed_fields(storage, update_values: dict[str, Any]) -> None:
    """只保存发生变化的 Storage 字段。"""

    update_fields: list[str] = []
    for field_name, value in update_values.items():
        if getattr(storage, field_name) != value:
            setattr(storage, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        storage.save(update_fields=update_fields)


def _sync_es_route_storage(
    *,
    bk_tenant_id: str,
    result_table: models.ResultTable,
    requested_origin_table_id: str | None,
    requested_cluster_id: int | None,
    index_set: str | None,
    source_type: str | None,
) -> None:
    """同步 ES 日志路由 Storage，并将结果表切换为 ES。

    ``index_set`` 和 ``source_type`` 为 ``None`` 表示请求未提供，更新时保留原值；空字符串表示显式清空。
    """

    result_table = models.ResultTable.objects.select_for_update().get(pk=result_table.pk)
    storage = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=result_table.table_id).first()
    resolved_origin_table_id = (
        requested_origin_table_id
        if requested_origin_table_id is not None
        else storage.origin_table_id
        if storage
        else None
    )
    if resolved_origin_table_id == result_table.table_id:
        resolved_origin_table_id = None

    resolved_cluster_id = _resolve_route_cluster_id(
        storage_model=models.ESStorage,
        bk_tenant_id=bk_tenant_id,
        origin_table_id=resolved_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        current_cluster_id=storage.storage_cluster_id if storage else None,
    )

    if storage is None:
        storage = models.ESStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=result_table.table_id,
            cluster_id=resolved_cluster_id,
            is_sync_db=False,
            enable_create_index=False,
            source_type=source_type if source_type is not None else "",
            index_set=index_set if index_set is not None else "",
            need_create_index=False,
            origin_table_id=resolved_origin_table_id,
            create_storage_cluster_record=False,
        )
    else:
        update_values = {
            "origin_table_id": resolved_origin_table_id,
            "storage_cluster_id": resolved_cluster_id,
            "need_create_index": False,
        }
        if index_set is not None:
            update_values["index_set"] = index_set
        if source_type is not None:
            update_values["source_type"] = source_type
        _save_changed_fields(storage, update_values)

    if result_table.default_storage != models.ClusterInfo.TYPE_ES:
        result_table.default_storage = models.ClusterInfo.TYPE_ES
        result_table.save(update_fields=["default_storage"])


def _sync_doris_route_storage(
    *,
    bk_tenant_id: str,
    result_table: models.ResultTable,
    requested_origin_table_id: str | None,
    requested_cluster_id: int | None,
    index_set: str | None,
    source_type: str | None,
    bkbase_table_id: str | None,
) -> None:
    """同步 Doris 日志路由 Storage，并将结果表切换为 Doris。

    可选路由字段为 ``None`` 表示请求未提供，更新时保留原值；空字符串表示显式清空。
    """

    result_table = models.ResultTable.objects.select_for_update().get(pk=result_table.pk)
    storage = models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=result_table.table_id).first()
    resolved_origin_table_id = (
        requested_origin_table_id
        if requested_origin_table_id is not None
        else storage.origin_table_id
        if storage
        else None
    )
    if resolved_origin_table_id == result_table.table_id:
        resolved_origin_table_id = None

    resolved_cluster_id = _resolve_route_cluster_id(
        storage_model=models.DorisStorage,
        bk_tenant_id=bk_tenant_id,
        origin_table_id=resolved_origin_table_id,
        requested_cluster_id=requested_cluster_id,
        current_cluster_id=storage.storage_cluster_id if storage else None,
    )

    if storage is None:
        storage = models.DorisStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=result_table.table_id,
            is_sync_db=False,
            source_type=source_type if source_type is not None else "",
            bkbase_table_id=bkbase_table_id,
            origin_table_id=resolved_origin_table_id,
            index_set=index_set,
            storage_cluster_id=resolved_cluster_id,
            create_storage_cluster_record=False,
        )
    else:
        update_values = {
            "origin_table_id": resolved_origin_table_id,
            "storage_cluster_id": resolved_cluster_id,
        }
        if index_set is not None:
            update_values["index_set"] = index_set
        if source_type is not None:
            update_values["source_type"] = source_type
        if bkbase_table_id is not None:
            update_values["bkbase_table_id"] = bkbase_table_id
        _save_changed_fields(storage, update_values)

    if result_table.default_storage != models.ClusterInfo.TYPE_DORIS:
        result_table.default_storage = models.ClusterInfo.TYPE_DORIS
        result_table.save(update_fields=["default_storage"])


def _create_or_update_log_router(
    *,
    bk_tenant_id: str,
    space: models.Space,
    result_table: models.ResultTable | None,
    table_id: str,
    storage_type: str,
    options: list[dict[str, Any]],
    data_label: str = "",
    is_enable: bool | None = None,
    requested_cluster_id: int | None = None,
    index_set: str | None = None,
    source_type: str | None = None,
    requested_origin_table_id: str | None = None,
    bkbase_table_id: str | None = None,
) -> models.ResultTable | None:
    """创建或更新日志路由的 ResultTable、options 和目标 Storage。"""

    if result_table is None:
        if is_enable is False:
            return None
        result_table = models.ResultTable.objects.create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            table_name_zh=table_id,
            is_custom_table=True,
            default_storage=storage_type,
            creator="system",
            bk_biz_id=space.get_bk_biz_id(),
            data_label=data_label,
            is_enable=True,
        )
    else:
        update_fields: list[str] = []
        if data_label and data_label != result_table.data_label:
            result_table.data_label = data_label
            update_fields.append("data_label")
        if is_enable is not None and is_enable != result_table.is_enable:
            result_table.is_enable = is_enable
            update_fields.append("is_enable")
        if update_fields:
            result_table.save(update_fields=update_fields)

    if options:
        _create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=options)

    if storage_type == models.ClusterInfo.TYPE_ES:
        _sync_es_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            requested_origin_table_id=requested_origin_table_id,
            requested_cluster_id=requested_cluster_id,
            index_set=index_set,
            source_type=source_type,
        )
    else:
        _sync_doris_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            requested_origin_table_id=requested_origin_table_id,
            requested_cluster_id=requested_cluster_id,
            index_set=index_set,
            source_type=source_type,
            bkbase_table_id=bkbase_table_id,
        )
    return result_table


class CreateOrUpdateLogRouter(Resource):
    """更新或者创建log路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
        bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
        storage_type = serializers.ChoiceField(
            required=False,
            choices=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
            label="存储类型",
            default=models.ClusterInfo.TYPE_ES,
        )
        origin_table_id = serializers.CharField(required=False, label="原始结果表ID")

        class QueryAliasSettingSerializer(serializers.Serializer):
            field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
            query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")

        query_alias_settings = QueryAliasSettingSerializer(
            required=False, label="查询别名设置", default=None, many=True
        )

    def perform_request(self, validated_request_data: dict) -> None:
        space = models.Space.objects.get(
            space_type_id=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            bk_tenant_id=get_request_tenant_id(),
        )
        bk_tenant_id: str = space.bk_tenant_id

        # 根据结果表判断是创建或更新
        table_id: str = validated_request_data["table_id"]
        result_table = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        is_create = result_table is None
        old_data_label = result_table.data_label if result_table else ""
        storage_type = validated_request_data["storage_type"]
        options = validated_request_data["options"]
        data_label = validated_request_data.get("data_label", "")
        requested_cluster_id = validated_request_data.get("cluster_id")
        index_set = validated_request_data.get("index_set")
        source_type = validated_request_data.get("source_type")
        requested_origin_table_id = validated_request_data.get("origin_table_id")
        bkbase_table_id = validated_request_data.get("bkbase_table_id")

        logger.info(
            "CreateOrUpdateLogRouter: try to create or update log router for table id->[%s],with storage_type->[%s]",
            table_id,
            storage_type,
        )

        # 查询别名与日志路由 Storage/default_storage 使用同一个 metadata DB 事务。
        with atomic(config.DATABASE_CONNECTION_NAME):
            if validated_request_data.get("query_alias_settings") is not None:
                operator = get_request_username() or "system"
                models.ESFieldQueryAliasOption.manage_query_alias_settings(
                    table_id=table_id,
                    query_alias_settings=validated_request_data["query_alias_settings"],
                    operator=operator,
                    bk_tenant_id=bk_tenant_id,
                )

            _create_or_update_log_router(
                bk_tenant_id=bk_tenant_id,
                space=space,
                result_table=result_table,
                table_id=table_id,
                storage_type=storage_type,
                options=options,
                data_label=data_label,
                requested_cluster_id=requested_cluster_id,
                index_set=index_set,
                source_type=source_type,
                requested_origin_table_id=requested_origin_table_id,
                bkbase_table_id=bkbase_table_id,
            )

        space_client = SpaceTableIDRedis()
        logger.info("CreateOrUpdateLogRouter: try to push table detail route for table_id->[%s]", table_id)
        space_client.push_table_id_detail(
            bk_tenant_id=bk_tenant_id,
            table_id_list=[table_id],
            is_publish=True,
        )

        if is_create:
            logger.info("CreateOrUpdateLogRouter: try to push space route for table_id->[%s]", table_id)
            space_client.push_space_table_ids(
                space_type=space.space_type_id,
                space_id=space.space_id,
                is_publish=True,
            )

        if data_label and data_label != old_data_label:
            data_labels = [data_label]
            if old_data_label:
                data_labels.append(old_data_label)
            logger.info(
                "CreateOrUpdateLogRouter: try to push data label routes for table_id->[%s], data_labels->[%s]",
                table_id,
                data_labels,
            )
            space_client.push_data_label_table_ids(
                data_label_list=data_labels,
                bk_tenant_id=bk_tenant_id,
                is_publish=True,
            )


class BulkCreateOrUpdateLogRouter(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        space_type = serializers.CharField(label="空间类型")
        space_id = serializers.CharField(label="空间ID")
        data_label = serializers.CharField(allow_blank=True, label="数据标签")

        class TableInfoSerializer(ParamsSerializer):
            table_id = serializers.CharField(required=True, label="结果表ID")
            cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
            index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
            source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
            bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
            origin_table_id = serializers.CharField(required=False, label="原始结果表ID")
            storage_type = serializers.ChoiceField(
                required=False,
                choices=[models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS],
                label="存储类型",
                default=models.ClusterInfo.TYPE_ES,
            )
            is_enable = serializers.BooleanField(required=False, label="是否启用")

            class QueryAliasSettingSerializer(serializers.Serializer):
                field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
                query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")

            query_alias_settings = QueryAliasSettingSerializer(
                required=False, label="查询别名设置", default=None, many=True
            )

        table_info = serializers.ListField(child=TableInfoSerializer(), label="结果表信息列表", min_length=1)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        space_type = validated_request_data["space_type"]
        space_id = validated_request_data["space_id"]
        data_label = validated_request_data.get("data_label", "")
        table_info_list = validated_request_data["table_info"]

        space = models.Space.objects.get(space_type_id=space_type, space_id=space_id, bk_tenant_id=bk_tenant_id)
        logger.info(
            "CreateOrUpdateLogDataLink: processing %d table(s) for space [%s:%s] with data_label [%s]",
            len(table_info_list),
            space_type,
            space_id,
            data_label,
        )

        # 批量处理所有表信息
        processed_table_ids = []
        with atomic(config.DATABASE_CONNECTION_NAME):
            table_mapping = {
                table.table_id: table
                for table in models.ResultTable.objects.filter(
                    bk_tenant_id=bk_tenant_id, table_id__in=[info["table_id"] for info in table_info_list]
                )
            }

            for table_info in table_info_list:
                table_id = table_info["table_id"]
                storage_type = table_info.get("storage_type", models.ClusterInfo.TYPE_ES)
                options = table_info["options"]
                is_enable = table_info.get("is_enable")
                requested_origin_table_id = table_info.get("origin_table_id")
                requested_cluster_id = table_info.get("cluster_id")
                index_set = table_info.get("index_set")
                source_type = table_info.get("source_type")
                bkbase_table_id = table_info.get("bkbase_table_id")

                try:
                    result_table = _create_or_update_log_router(
                        bk_tenant_id=bk_tenant_id,
                        space=space,
                        result_table=table_mapping.get(table_id),
                        table_id=table_id,
                        storage_type=storage_type,
                        options=options,
                        data_label=data_label,
                        is_enable=is_enable,
                        requested_cluster_id=requested_cluster_id,
                        index_set=index_set,
                        source_type=source_type,
                        requested_origin_table_id=requested_origin_table_id,
                        bkbase_table_id=bkbase_table_id,
                    )
                    if result_table is None:
                        logger.info(
                            "CreateOrUpdateLogDataLink: skip disabled new route table [%s]",
                            table_id,
                        )
                        continue

                    # 处理查询别名设置
                    if table_info.get("query_alias_settings") is not None:
                        operator = get_request_username() or "system"
                        models.ESFieldQueryAliasOption.manage_query_alias_settings(
                            table_id=table_id,
                            query_alias_settings=table_info["query_alias_settings"],
                            operator=operator,
                            bk_tenant_id=bk_tenant_id,
                        )

                    processed_table_ids.append(table_id)
                    logger.info("CreateOrUpdateLogDataLink: processed table_id [%s]", table_id)
                except Exception as e:
                    logger.error(
                        "CreateOrUpdateLogDataLink: failed to process table_id [%s], error: %s",
                        table_id,
                        str(e),
                    )
                    raise e

        # 清理data_label下多余的配置
        if data_label:
            self._cleanup_excess_data_label_config(bk_tenant_id, data_label, processed_table_ids)

        self._push_space_routes(space_type, space_id)
        if processed_table_ids:
            logger.info("CreateOrUpdateLogDataLink: pushing routes for %d tables", len(processed_table_ids))
            SpaceTableIDRedis().push_table_id_detail(
                bk_tenant_id=bk_tenant_id,
                table_id_list=processed_table_ids,
                is_publish=True,
            )
        if data_label and processed_table_ids:
            logger.info("CreateOrUpdateLogDataLink: pushing data_label route for [%s]", data_label)
            SpaceTableIDRedis().push_data_label_table_ids(
                data_label_list=[data_label],
                bk_tenant_id=bk_tenant_id,
                is_publish=True,
            )

        logger.info(
            "CreateOrUpdateLogDataLink: successfully processed all %d table(s) for space [%s:%s]",
            len(table_info_list),
            space_type,
            space_id,
        )

    def _push_space_routes(self, space_type: str, space_id: str) -> None:
        """推送当前空间及关联业务空间路由。"""

        logger.info("CreateOrUpdateLogDataLink: pushing routes for space [%s:%s]", space_type, space_id)
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)

        if space_type != "bkcc":
            related_space: Space = SpaceApi.get_related_space(f"{space_type}__{space_id}", SpaceTypeEnum.BKCC.value)
            if related_space:
                SpaceTableIDRedis().push_space_table_ids(
                    space_type=related_space.space_type_id, space_id=related_space.space_id, is_publish=True
                )

    def _cleanup_excess_data_label_config(self, bk_tenant_id: str, data_label: str, processed_table_ids: list):
        """清理data_label下多余的配置"""
        logger.info("CreateOrUpdateLogDataLink: cleaning up excess configurations for data_label [%s]", data_label)

        # 查找该data_label下的所有结果表
        existing_tables = models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, data_label=data_label
        ).values_list("table_id", flat=True)

        # 找出需要清理的table_ids（存在于数据库中但不在当前处理列表中的）
        excess_table_ids = set(existing_tables) - set(processed_table_ids)

        if excess_table_ids:
            logger.info(
                "CreateOrUpdateLogDataLink: found %d excess tables to clean up: %s",
                len(excess_table_ids),
                list(excess_table_ids),
            )

            # 清理多余的结果表data_label
            models.ResultTable.objects.filter(
                bk_tenant_id=bk_tenant_id, table_id__in=excess_table_ids, data_label=data_label
            ).update(data_label="")

            logger.info("CreateOrUpdateLogDataLink: cleaned up %d excess table configurations", len(excess_table_ids))
        else:
            logger.info("CreateOrUpdateLogDataLink: no excess configurations found for data_label [%s]", data_label)


class CleanLogRouter(Resource):
    """清理日志路由数据"""

    class RequestSerializer(ParamsSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        data_label = serializers.CharField(label="数据标签")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        data_label = validated_request_data["data_label"]

        # 将data_label关联的所有结果表都设为不启用
        models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, data_label=data_label).update(is_enable=False)
