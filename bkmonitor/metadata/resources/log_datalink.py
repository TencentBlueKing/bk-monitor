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
from rest_framework.exceptions import ValidationError

from bkm_space.api import SpaceApi
from bkm_space.define import Space, SpaceTypeEnum
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.user import get_request_username
from core.drf_resource import Resource
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.service.space_redis import SpaceTableIDRedis, push_and_publish_es_aliases

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


class BaseLogRouter(Resource):
    STORAGE_MODEL_MAP = {
        models.ClusterInfo.TYPE_ES: models.ESStorage,
        models.ClusterInfo.TYPE_DORIS: models.DorisStorage,
    }

    @staticmethod
    def create_or_update_options(bk_tenant_id: str, table_id: str, options: list[dict]):
        """创建或者更新结果表 option"""
        # 查询结果表下的option
        exist_objs = {
            obj.name: obj
            for obj in models.ResultTableOption.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
        }
        need_update_objs, need_add_objs = [], []
        update_fields = set()

        for option in options:
            exist_obj = exist_objs.get(option["name"])
            need_update = False
            if exist_obj:
                # 更新数据
                if option["value"] != exist_obj.value:
                    exist_obj.value = option["value"]
                    update_fields.add("value")
                    need_update = True
                if option["value_type"] != exist_obj.value_type:
                    exist_obj.value_type = option["value_type"]
                    update_fields.add("value_type")
                    need_update = True
                # 判断是否需要更新
                if need_update:
                    need_update_objs.append(exist_obj)
            else:
                need_add_objs.append(
                    models.ResultTableOption(bk_tenant_id=bk_tenant_id, table_id=table_id, **dict(option))
                )

        # 批量创建
        if need_add_objs:
            models.ResultTableOption.objects.bulk_create(need_add_objs, batch_size=BULK_CREATE_BATCH_SIZE)
        # 批量更新
        if need_update_objs:
            models.ResultTableOption.objects.bulk_update(
                need_update_objs, list(update_fields), batch_size=BULK_UPDATE_BATCH_SIZE
            )

    @classmethod
    def _get_storage_model(cls, storage_type: str):
        try:
            return cls.STORAGE_MODEL_MAP[storage_type]
        except KeyError as error:
            raise ValidationError(f"Unsupported storage type: {storage_type}") from error

    @classmethod
    def _resolve_route_origin_table_id(
        cls,
        *,
        bk_tenant_id: str,
        table_id: str,
        storage_type: str,
        requested_origin_table_id: str | None,
    ) -> str | None:
        """解析虚拟路由表唯一关联的实体表。

        切换存储类型时调用方可以不重复传 origin_table_id，此时沿已有的 ES/Doris
        路由配置继承。两种存储若指向不同实体表则拒绝继续，避免同一个虚拟 RT 的
        当前路由与历史路由关联到不同实体表。
        """

        existing_origins: dict[str, str] = {}
        target_origin_table_id: str | None = None
        for current_storage_type, storage_model in cls.STORAGE_MODEL_MAP.items():
            origin_table_id = (
                storage_model.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
                .values_list("origin_table_id", flat=True)
                .first()
            )
            if current_storage_type == storage_type:
                target_origin_table_id = origin_table_id
            if origin_table_id and origin_table_id != table_id:
                existing_origins[current_storage_type] = origin_table_id

        if requested_origin_table_id:
            conflicting_origins = {
                origin_table_id
                for current_storage_type, origin_table_id in existing_origins.items()
                if current_storage_type != storage_type and origin_table_id != requested_origin_table_id
            }
            if conflicting_origins:
                raise ValidationError(
                    f"Route table {table_id} already points to another origin table: {sorted(conflicting_origins)}"
                )
            return requested_origin_table_id

        unique_origins = set(existing_origins.values())
        if len(unique_origins) > 1:
            raise ValidationError(f"Route table {table_id} has inconsistent origin tables: {sorted(unique_origins)}")
        return next(iter(unique_origins), target_origin_table_id)

    @classmethod
    def _resolve_route_cluster_id(
        cls,
        *,
        bk_tenant_id: str,
        storage_type: str,
        origin_table_id: str,
        requested_cluster_id: int | None,
    ) -> int:
        """从关联实体表解析虚拟路由使用的当前集群 ID。

        虚拟路由表的当前集群以关联实体 Storage 为权威来源；请求中的 cluster_id
        只用于一致性校验。
        """

        storage_model = cls._get_storage_model(storage_type)
        try:
            origin_result_table = models.ResultTable.objects.select_for_update().get(
                bk_tenant_id=bk_tenant_id,
                table_id=origin_table_id,
            )
        except models.ResultTable.DoesNotExist as error:
            raise ValidationError(f"Origin result table not found: {origin_table_id}") from error

        if origin_result_table.default_storage != storage_type:
            raise ValidationError(f"Origin result table {origin_table_id} does not use storage type {storage_type}")

        try:
            origin_storage = storage_model.objects.get(bk_tenant_id=bk_tenant_id, table_id=origin_table_id)
        except storage_model.DoesNotExist as error:
            raise ValidationError(
                f"Origin storage not found: {origin_table_id}, storage_type={storage_type}"
            ) from error

        cluster_id = origin_storage.storage_cluster_id
        if requested_cluster_id is not None and requested_cluster_id != cluster_id:
            raise ValidationError(
                f"Route cluster {requested_cluster_id} does not match origin storage cluster {cluster_id}"
            )

        if not models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id, cluster_id=cluster_id, cluster_type=storage_type
        ).exists():
            raise ValidationError(
                f"Origin storage cluster is invalid: cluster_id={cluster_id}, storage_type={storage_type}"
            )

        current_cluster_ids = list(
            models.StorageClusterRecord.objects.select_for_update()
            .filter(
                bk_tenant_id=bk_tenant_id,
                table_id=origin_table_id,
                is_current=True,
                is_deleted=False,
            )
            .values_list("cluster_id", flat=True)
        )
        if current_cluster_ids != [cluster_id]:
            raise ValidationError(
                f"Origin result table {origin_table_id} current storage record {current_cluster_ids} "
                f"does not match {storage_type} storage cluster {cluster_id}"
            )
        return cluster_id

    @classmethod
    def _create_route_storage(
        cls,
        *,
        bk_tenant_id: str,
        table_id: str,
        storage_type: str,
        table_info: dict,
        origin_table_id: str,
        cluster_id: int,
    ):
        """创建虚拟 ES/Doris 路由 Storage，不创建索引或历史分段。"""

        if storage_type == models.ClusterInfo.TYPE_ES:
            return models.ESStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                is_sync_db=False,
                cluster_id=cluster_id,
                enable_create_index=False,
                source_type=table_info.get("source_type", ""),
                index_set=table_info.get("index_set", ""),
                need_create_index=False,
                origin_table_id=origin_table_id,
                create_storage_cluster_record=False,
            )

        return models.DorisStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            is_sync_db=False,
            source_type=table_info.get("source_type", ""),
            bkbase_table_id=table_info.get("bkbase_table_id"),
            origin_table_id=origin_table_id,
            index_set=table_info.get("index_set"),
            storage_cluster_id=cluster_id,
            create_storage_cluster_record=False,
        )

    @classmethod
    def _update_route_storage(
        cls,
        *,
        storage,
        storage_type: str,
        table_info: dict,
        origin_table_id: str,
        cluster_id: int,
    ) -> None:
        """仅更新虚拟路由所需的 Storage 镜像字段，不维护历史分段。"""

        field_names = ["index_set", "source_type", "origin_table_id"]
        if storage_type == models.ClusterInfo.TYPE_ES:
            field_names.append("need_create_index")
        else:
            field_names.append("bkbase_table_id")

        update_values = {
            "origin_table_id": origin_table_id,
            "storage_cluster_id": cluster_id,
        }
        for field_name in field_names:
            if field_name == "origin_table_id":
                continue
            if field_name == "need_create_index":
                update_values[field_name] = False
            elif field_name in table_info:
                update_values[field_name] = table_info[field_name]

        update_fields: list[str] = []
        for field_name, value in update_values.items():
            if getattr(storage, field_name) != value:
                setattr(storage, field_name, value)
                update_fields.append(field_name)

        if update_fields:
            storage.save(update_fields=update_fields)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_or_update_route_storage(
        cls,
        *,
        bk_tenant_id: str,
        result_table: models.ResultTable,
        storage_type: str,
        table_info: dict,
    ):
        """原子补齐虚拟路由 Storage，并切换虚拟 ResultTable 的默认查询存储。

        该入口只编排索引集使用的虚拟路由表：不调用 ResultTable.modify()、不应用
        datalink、不准备 ES 物理索引，也不创建/推进虚拟 StorageClusterRecord。
        """

        result_table = models.ResultTable.objects.select_for_update().get(pk=result_table.pk)
        table_id = result_table.table_id
        origin_table_id = cls._resolve_route_origin_table_id(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            storage_type=storage_type,
            requested_origin_table_id=table_info.get("origin_table_id"),
        )

        if not origin_table_id or origin_table_id == table_id:
            raise ValidationError(f"Virtual route table {table_id} must reference an origin result table")

        cluster_id = cls._resolve_route_cluster_id(
            bk_tenant_id=bk_tenant_id,
            storage_type=storage_type,
            origin_table_id=origin_table_id,
            requested_cluster_id=table_info.get("cluster_id"),
        )

        storage_model = cls._get_storage_model(storage_type)
        storage = storage_model.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        if storage is None:
            storage = cls._create_route_storage(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                storage_type=storage_type,
                table_info=table_info,
                origin_table_id=origin_table_id,
                cluster_id=cluster_id,
            )
        else:
            cls._update_route_storage(
                storage=storage,
                storage_type=storage_type,
                table_info=table_info,
                origin_table_id=origin_table_id,
                cluster_id=cluster_id,
            )

        if result_table.default_storage != storage_type:
            result_table.default_storage = storage_type
            result_table.save(update_fields=["default_storage"])

        return result_table, storage


def _create_es_router(validated_request_data: dict[str, Any]) -> None:
    """创建 ES 虚拟路由表。"""

    bk_tenant_id = validated_request_data["bk_tenant_id"]
    space = models.Space.objects.get(
        space_type_id=validated_request_data["space_type"],
        space_id=validated_request_data["space_id"],
        bk_tenant_id=bk_tenant_id,
    )

    with atomic(config.DATABASE_CONNECTION_NAME):
        result_table = models.ResultTable.objects.create(
            bk_tenant_id=bk_tenant_id,
            table_id=validated_request_data["table_id"],
            table_name_zh=validated_request_data["table_id"],
            is_custom_table=True,
            default_storage=models.ClusterInfo.TYPE_ES,
            creator="system",
            bk_biz_id=space.get_bk_biz_id(),
            data_label=validated_request_data.get("data_label") or "",
        )
        if validated_request_data["options"]:
            BaseLogRouter.create_or_update_options(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                options=validated_request_data["options"],
            )
        BaseLogRouter.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            storage_type=models.ClusterInfo.TYPE_ES,
            table_info=validated_request_data,
        )

    logger.info("create_es_router: try to push route for table_id->[%s]", validated_request_data["table_id"])
    SpaceTableIDRedis().push_space_table_ids(
        space_type=validated_request_data["space_type"],
        space_id=validated_request_data["space_id"],
        is_publish=True,
    )
    SpaceTableIDRedis().push_es_table_id_detail(
        table_id_list=[validated_request_data["table_id"]], is_publish=True, bk_tenant_id=bk_tenant_id
    )

    if validated_request_data.get("data_label"):
        logger.info(
            "create_es_router: try to push data label route for table_id->[%s], data_label->[%s]",
            validated_request_data["table_id"],
            validated_request_data["data_label"],
        )
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=[validated_request_data["data_label"]], bk_tenant_id=bk_tenant_id, is_publish=True
        )


def _create_doris_router(validated_request_data: dict[str, Any]) -> None:
    """创建 Doris 虚拟路由表。"""

    bk_tenant_id = validated_request_data["bk_tenant_id"]
    space = models.Space.objects.get(
        space_type_id=validated_request_data["space_type"],
        space_id=validated_request_data["space_id"],
        bk_tenant_id=bk_tenant_id,
    )
    logger.info(
        "create_doris_router: try to create doris router,table_id->[%s],bkbase_table_id->[%s],bk_biz_id->[%s]",
        validated_request_data["table_id"],
        validated_request_data.get("bkbase_table_id"),
        space.get_bk_biz_id(),
    )

    with atomic(config.DATABASE_CONNECTION_NAME):
        result_table = models.ResultTable.objects.create(
            bk_tenant_id=bk_tenant_id,
            table_id=validated_request_data["table_id"],
            table_name_zh=validated_request_data["table_id"],
            is_custom_table=True,
            default_storage=models.ClusterInfo.TYPE_DORIS,
            creator="system",
            bk_biz_id=space.get_bk_biz_id(),
            data_label=validated_request_data.get("data_label", ""),
        )
        if validated_request_data["options"]:
            BaseLogRouter.create_or_update_options(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                options=validated_request_data["options"],
            )
        BaseLogRouter.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            storage_type=models.ClusterInfo.TYPE_DORIS,
            table_info=validated_request_data,
        )

    logger.info("create_doris_router: create doris datalink related records successfully,now try to push router")
    SpaceTableIDRedis().push_doris_table_id_detail(
        table_id_list=[validated_request_data["table_id"]], is_publish=True, bk_tenant_id=bk_tenant_id
    )
    SpaceTableIDRedis().push_space_table_ids(
        space_type=validated_request_data["space_type"],
        space_id=validated_request_data["space_id"],
        is_publish=True,
    )
    if validated_request_data.get("data_label"):
        logger.info(
            "create_doris_router: try to push data label router for table_id->[%s],data_label->[%s]",
            validated_request_data["table_id"],
            validated_request_data["data_label"],
        )
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=[validated_request_data["data_label"]], bk_tenant_id=bk_tenant_id, is_publish=True
        )

    logger.info("create_doris_router: push doris datalink router success")


def _update_es_router(validated_request_data: dict[str, Any]) -> None:
    """更新 ES 虚拟路由表。"""

    bk_tenant_id = validated_request_data["bk_tenant_id"]
    table_id = validated_request_data["table_id"]
    need_refresh_data_label = False
    with atomic(config.DATABASE_CONNECTION_NAME):
        try:
            result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except models.ResultTable.DoesNotExist as error:
            raise ValidationError("Result table not found") from error

        old_data_label = result_table.data_label
        if validated_request_data.get("data_label") and validated_request_data["data_label"] != old_data_label:
            result_table.data_label = validated_request_data["data_label"]
            result_table.save(update_fields=["data_label"])
            need_refresh_data_label = True

        BaseLogRouter.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            storage_type=models.ClusterInfo.TYPE_ES,
            table_info=validated_request_data,
        )

        if validated_request_data.get("options"):
            BaseLogRouter.create_or_update_options(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                options=validated_request_data["options"],
            )

    if need_refresh_data_label:
        logger.info(
            "update_es_router: try to push data label router for table_id->[%s], data_label->[%s]",
            table_id,
            validated_request_data["data_label"],
        )
        push_data_labels = [validated_request_data["data_label"]]
        if old_data_label:
            push_data_labels.append(old_data_label)
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=push_data_labels, bk_tenant_id=bk_tenant_id, is_publish=True
        )
        push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=validated_request_data["data_label"])
        if old_data_label:
            push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=old_data_label)

    logger.info("update_es_router: try to push es detail router for table_id->[%s]", table_id)
    SpaceTableIDRedis().push_es_table_id_detail(table_id_list=[table_id], bk_tenant_id=bk_tenant_id, is_publish=True)


def _update_doris_router(validated_request_data: dict[str, Any]) -> None:
    """更新 Doris 虚拟路由表。"""

    bk_tenant_id = validated_request_data["bk_tenant_id"]
    table_id = validated_request_data["table_id"]
    logger.info("update_doris_router: try to update doris router for table_id->[%s]", table_id)

    need_refresh_data_label = False
    with atomic(config.DATABASE_CONNECTION_NAME):
        result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        old_data_label = result_table.data_label

        if validated_request_data.get("data_label") and validated_request_data["data_label"] != old_data_label:
            result_table.data_label = validated_request_data["data_label"]
            result_table.save(update_fields=["data_label"])
            need_refresh_data_label = True

        BaseLogRouter.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            storage_type=models.ClusterInfo.TYPE_DORIS,
            table_info=validated_request_data,
        )

        if validated_request_data.get("options"):
            BaseLogRouter.create_or_update_options(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                options=validated_request_data["options"],
            )

    logger.info(
        "update_doris_router:update doris router for table_id->[%s] successfully,now try to push router", table_id
    )
    SpaceTableIDRedis().push_doris_table_id_detail(table_id_list=[table_id], bk_tenant_id=bk_tenant_id, is_publish=True)

    if need_refresh_data_label:
        logger.info(
            "update_doris_router: try to push data label router for table_id->[%s], data_label->[%s]",
            table_id,
            validated_request_data["data_label"],
        )
        push_data_labels = [validated_request_data["data_label"]]
        if old_data_label:
            push_data_labels.append(old_data_label)
        SpaceTableIDRedis().push_data_label_table_ids(
            data_label_list=push_data_labels, bk_tenant_id=bk_tenant_id, is_publish=True
        )

    logger.info("update_doris_router:push doris router for table_id->[%s] successfully", table_id)


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
        need_create_index = serializers.BooleanField(required=False, label="是否需要创建索引")
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

        logger.info(
            "CreateOrUpdateLogRouter: try to create or update log router for table id->[%s],with storage_type->[%s]",
            table_id,
            validated_request_data["storage_type"],
        )

        # 根据存储类型选择内部创建/更新函数。
        create_router_map = {
            models.ClusterInfo.TYPE_DORIS: _create_doris_router,
            models.ClusterInfo.TYPE_ES: _create_es_router,
        }

        update_router_map = {
            models.ClusterInfo.TYPE_DORIS: _update_doris_router,
            models.ClusterInfo.TYPE_ES: _update_es_router,
        }

        router_map = update_router_map if result_table else create_router_map
        router = router_map[validated_request_data["storage_type"]]

        # 查询别名与虚拟路由 Storage/default_storage 使用同一个 metadata DB 事务。
        with atomic(config.DATABASE_CONNECTION_NAME):
            if validated_request_data.get("query_alias_settings") is not None:
                operator = get_request_username() or "system"
                models.ESFieldQueryAliasOption.manage_query_alias_settings(
                    table_id=table_id,
                    query_alias_settings=validated_request_data["query_alias_settings"],
                    operator=operator,
                    bk_tenant_id=bk_tenant_id,
                )
            router(validated_request_data)


class BulkCreateOrUpdateLogRouter(BaseLogRouter):
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
            need_create_index = serializers.BooleanField(required=False, label="是否创建索引")
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
        es_table_ids = []
        doris_table_ids = []
        need_refresh_data_label = False

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

                try:
                    # 检查结果表是否存在
                    result_table = table_mapping.get(table_id)
                    if result_table:
                        # 更新现有表
                        self._update_existing_table(bk_tenant_id, table_id, table_info, data_label, result_table)
                    else:
                        # 创建新表
                        created = self._create_new_table(
                            bk_tenant_id, space, table_id, table_info, data_label, storage_type
                        )
                        if not created:
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
                    if storage_type == models.ClusterInfo.TYPE_ES:
                        es_table_ids.append(table_id)
                    elif storage_type == models.ClusterInfo.TYPE_DORIS:
                        doris_table_ids.append(table_id)

                    if data_label:
                        need_refresh_data_label = True

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

        # 统一推送路由信息
        self._push_routes(
            bk_tenant_id, space_type, space_id, es_table_ids, doris_table_ids, data_label, need_refresh_data_label
        )

        logger.info(
            "CreateOrUpdateLogDataLink: successfully processed all %d table(s) for space [%s:%s]",
            len(table_info_list),
            space_type,
            space_id,
        )

    def _update_existing_table(
        self, bk_tenant_id: str, table_id: str, table_info: dict, data_label: str, result_table: models.ResultTable
    ):
        """更新现有结果表"""
        storage_type = table_info.get("storage_type", models.ClusterInfo.TYPE_ES)

        # 更新结果表data_label
        if data_label and data_label != result_table.data_label:
            result_table.data_label = data_label
            result_table.save(update_fields=["data_label"])

        # 更新结果表是否启用
        if table_info.get("is_enable") is not None and table_info["is_enable"] != result_table.is_enable:
            result_table.is_enable = table_info["is_enable"]
            result_table.save(update_fields=["is_enable"])

        # 更新options
        if table_info.get("options"):
            self.create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=table_info["options"])

        self.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id, result_table=result_table, storage_type=storage_type, table_info=table_info
        )

    def _create_new_table(
        self, bk_tenant_id: str, space, table_id: str, table_info: dict, data_label: str, storage_type: str
    ):
        """创建新的结果表"""
        # 如果结果表不启用，则不创建
        is_enable = table_info.get("is_enable", True)
        if is_enable is False:
            return False

        # 创建结果表
        result_table = models.ResultTable.objects.create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            table_name_zh=table_id,
            is_custom_table=True,
            default_storage=storage_type,
            creator="system",
            bk_biz_id=space.get_bk_biz_id(),
            data_label=data_label,
        )

        # 创建结果表options
        if table_info.get("options"):
            self.create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=table_info["options"])

        self.create_or_update_route_storage(
            bk_tenant_id=bk_tenant_id,
            result_table=result_table,
            storage_type=storage_type,
            table_info=table_info,
        )
        return True

    def _push_routes(
        self,
        bk_tenant_id: str,
        space_type: str,
        space_id: str,
        es_table_ids: list,
        doris_table_ids: list,
        data_label: str,
        need_refresh_data_label: bool,
    ):
        """统一推送路由信息"""
        logger.info("CreateOrUpdateLogDataLink: pushing routes for space [%s:%s]", space_type, space_id)

        # 推送空间路由
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)

        # 如果是非bkcc空间，推送关联的bkcc空间路由
        if space_type != "bkcc":
            related_space: Space = SpaceApi.get_related_space(f"{space_type}__{space_id}", SpaceTypeEnum.BKCC.value)
            if related_space:
                SpaceTableIDRedis().push_space_table_ids(
                    space_type=related_space.space_type_id, space_id=related_space.space_id, is_publish=True
                )

        # 批量推送ES表详情路由
        if es_table_ids:
            logger.info("CreateOrUpdateLogDataLink: pushing ES routes for %d tables", len(es_table_ids))
            SpaceTableIDRedis().push_es_table_id_detail(
                table_id_list=es_table_ids, is_publish=True, bk_tenant_id=bk_tenant_id
            )

        # 批量推送Doris表详情路由
        if doris_table_ids:
            logger.info("CreateOrUpdateLogDataLink: pushing Doris routes for %d tables", len(doris_table_ids))
            SpaceTableIDRedis().push_doris_table_id_detail(
                table_id_list=doris_table_ids, is_publish=True, bk_tenant_id=bk_tenant_id
            )

        # 推送data_label路由并处理别名
        if need_refresh_data_label and data_label:
            logger.info("CreateOrUpdateLogDataLink: pushing data_label route for [%s]", data_label)
            SpaceTableIDRedis().push_data_label_table_ids(
                data_label_list=[data_label], bk_tenant_id=bk_tenant_id, is_publish=True
            )
            push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=data_label)

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
