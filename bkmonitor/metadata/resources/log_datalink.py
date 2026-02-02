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
    def create_or_update_options(self, bk_tenant_id: str, table_id: str, options: list[dict]):
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


class CreateEsRouter(BaseLogRouter):
    """同步es路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
        need_create_index = serializers.BooleanField(required=False, label="是否创建索引")
        origin_table_id = serializers.CharField(required=False, label="原始结果表ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        space = models.Space.objects.get(
            space_type_id=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            bk_tenant_id=bk_tenant_id,
        )

        # 创建结果表和ES存储记录
        need_create_index = validated_request_data.get("need_create_index", True)
        # 创建结果表
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ResultTable.objects.create(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                table_name_zh=validated_request_data["table_id"],
                is_custom_table=True,
                default_storage=models.ClusterInfo.TYPE_ES,
                creator="system",
                bk_biz_id=space.get_bk_biz_id(),
                data_label=validated_request_data.get("data_label") or "",
            )
            # 创建结果表 option
            if validated_request_data["options"]:
                self.create_or_update_options(
                    bk_tenant_id=bk_tenant_id,
                    table_id=validated_request_data["table_id"],
                    options=validated_request_data["options"],
                )
            # 创建es存储记录
            models.ESStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                is_sync_db=False,
                cluster_id=validated_request_data.get("cluster_id"),
                enable_create_index=False,
                source_type=validated_request_data.get("source_type") or "",
                index_set=validated_request_data.get("index_set") or "",
                need_create_index=need_create_index,
                origin_table_id=validated_request_data.get("origin_table_id", ""),
            )
        # 推送空间数据
        logger.info("CreateEsRouter: try to push route for table_id->[%s]", validated_request_data["table_id"])
        SpaceTableIDRedis().push_space_table_ids(
            space_type=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            is_publish=True,
        )
        SpaceTableIDRedis().push_es_table_id_detail(
            table_id_list=[validated_request_data["table_id"]], is_publish=True, bk_tenant_id=bk_tenant_id
        )

        if validated_request_data.get("data_label", None):
            logger.info(
                "CreateEsRouter: try to push data label route for table_id->[%s], data_label->[%s]",
                validated_request_data["table_id"],
                validated_request_data["data_label"],
            )
            SpaceTableIDRedis().push_data_label_table_ids(
                data_label_list=[validated_request_data.get("data_label")], bk_tenant_id=bk_tenant_id, is_publish=True
            )


class CreateDorisRouter(BaseLogRouter):
    """同步doris路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        space = models.Space.objects.get(
            space_type_id=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            bk_tenant_id=bk_tenant_id,
        )

        # 创建结果表和存储记录
        logger.info(
            "CreateDorisRouter: try to create doris router,table_id->[%s],bkbase_table_id->[%s],bk_biz_id->[%s]",
            validated_request_data["table_id"],
            validated_request_data.get("bkbase_table_id"),
            space.get_bk_biz_id(),
        )

        # 创建结果表
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ResultTable.objects.create(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                table_name_zh=validated_request_data["table_id"],
                is_custom_table=True,
                default_storage=models.ClusterInfo.TYPE_DORIS,
                creator="system",
                bk_biz_id=space.get_bk_biz_id(),
                data_label=validated_request_data.get("data_label", ""),
            )
            # 创建结果表 option
            if validated_request_data["options"]:
                self.create_or_update_options(
                    bk_tenant_id=bk_tenant_id,
                    table_id=validated_request_data["table_id"],
                    options=validated_request_data["options"],
                )

            # 创建doris存储记录
            models.DorisStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=validated_request_data["table_id"],
                is_sync_db=False,
                source_type=validated_request_data.get("source_type", ""),
                bkbase_table_id=validated_request_data.get("bkbase_table_id"),
                index_set=validated_request_data.get("index_set"),
                storage_cluster_id=validated_request_data.get("cluster_id"),
            )

        logger.info("CreateDorisRouter: create doris datalink related records successfully,now try to push router")
        # 推送路由 空间路由+结果表详情路由
        SpaceTableIDRedis().push_doris_table_id_detail(
            table_id_list=[validated_request_data["table_id"]], is_publish=True, bk_tenant_id=bk_tenant_id
        )
        SpaceTableIDRedis().push_space_table_ids(
            space_type=validated_request_data["space_type"],
            space_id=validated_request_data["space_id"],
            is_publish=True,
        )
        if validated_request_data.get("data_label", None):
            logger.info(
                "CreateDorisRouter: try to push data label router for table_id->[%s],data_label->[%s]",
                validated_request_data["table_id"],
                validated_request_data["data_label"],
            )
            SpaceTableIDRedis().push_data_label_table_ids(
                data_label_list=[validated_request_data["data_label"]], bk_tenant_id=bk_tenant_id, is_publish=True
            )

        logger.info("CreateDorisRouter: push doris datalink router success")


class UpdateEsRouter(BaseLogRouter):
    """更新es路由信息"""

    class RequestSerializer(ParamsSerializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        data_label = serializers.CharField(required=False, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, label="索引集规则")
        source_type = serializers.CharField(required=False, label="数据源类型")
        need_create_index = serializers.BooleanField(required=False, label="是否创建索引")
        origin_table_id = serializers.CharField(required=False, label="原始结果表ID")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]

        # 查询结果表存在
        table_id = validated_request_data["table_id"]
        try:
            result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except models.ResultTable.DoesNotExist:
            raise ValidationError("Result table not found")
        # 查询es存储记录
        try:
            es_storage = models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except models.ESStorage.DoesNotExist:
            raise ValidationError("ES storage not found")
        # 因为可以重复执行，这里可以不设置事务
        # 更新结果表别名
        need_refresh_data_label = False
        old_data_label = result_table.data_label
        if validated_request_data.get("data_label") and validated_request_data["data_label"] != result_table.data_label:
            result_table.data_label = validated_request_data["data_label"]
            result_table.save(update_fields=["data_label"])
            need_refresh_data_label = True
        # 更新索引集或者使用的集群
        update_es_fields = []
        if validated_request_data.get("need_create_index"):
            es_storage.need_create_index = validated_request_data.get("need_create_index")
            update_es_fields.append("need_create_index")
        if validated_request_data.get("index_set") and validated_request_data["index_set"] != es_storage.index_set:
            es_storage.index_set = validated_request_data["index_set"]
            update_es_fields.append("index_set")
        if (
            validated_request_data.get("cluster_id")
            and validated_request_data["cluster_id"] != es_storage.storage_cluster_id
        ):
            es_storage.storage_cluster_id = validated_request_data["cluster_id"]
            update_es_fields.append("storage_cluster_id")
        if (
            validated_request_data.get("origin_table_id")
            and validated_request_data["origin_table_id"] != es_storage.origin_table_id
        ):
            es_storage.origin_table_id = validated_request_data["origin_table_id"]
            update_es_fields.append("origin_table_id")
        if update_es_fields:
            es_storage.save(update_fields=update_es_fields)
        # 更新options
        if validated_request_data.get("options"):
            self.create_or_update_options(
                bk_tenant_id=bk_tenant_id, table_id=table_id, options=validated_request_data["options"]
            )
        # 如果别名或者索引集有变动，则需要通知到unify-query
        if need_refresh_data_label:
            logger.info(
                "UpdateEsRouter: try to push data label router for table_id->[%s], data_label->[%s]",
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
        logger.info("UpdateEsRouter: try to push es detail router for table_id->[%s]", table_id)
        SpaceTableIDRedis().push_es_table_id_detail(
            table_id_list=[table_id], bk_tenant_id=bk_tenant_id, is_publish=True
        )


class UpdateDorisRouter(BaseLogRouter):
    class RequestSerializer(ParamsSerializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data["table_id"]
        doris_storage = models.DorisStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        logger.info("UpdateDorisRouter: try to update doris router for table_id->[%s]", table_id)

        update_doris_fields = []
        need_refresh_data_label = False
        old_data_label = result_table.data_label

        try:
            # data_label
            if (
                validated_request_data.get("data_label")
                and validated_request_data["data_label"] != result_table.data_label
            ):
                result_table.data_label = validated_request_data["data_label"]
                result_table.save(update_fields=["data_label"])
                need_refresh_data_label = True
            # index_set
            if (
                validated_request_data.get("index_set")
                and validated_request_data["index_set"] != doris_storage.index_set
            ):
                doris_storage.index_set = validated_request_data["index_set"]
                update_doris_fields.append("index_set")
            # bkbase_table_id
            if (
                validated_request_data.get("bkbase_table_id")
                and validated_request_data["bkbase_table_id"] != doris_storage.bkbase_table_id
            ):
                doris_storage.bkbase_table_id = validated_request_data["bkbase_table_id"]
                update_doris_fields.append("bkbase_table_id")
            # storage_cluster_id
            if (
                validated_request_data.get("cluster_id")
                and validated_request_data["cluster_id"] != doris_storage.storage_cluster_id
            ):
                doris_storage.storage_cluster_id = validated_request_data["cluster_id"]
                update_doris_fields.append("storage_cluster_id")
            if update_doris_fields:
                doris_storage.save(update_fields=update_doris_fields)
        except Exception as e:  # pylint:disable=broad-except
            logger.error("UpdateDorisRouter: failed to update doris router for table_id->[%s],error->[%s]", table_id, e)
            raise e

        # 更新options
        if validated_request_data.get("options"):
            self.create_or_update_options(
                bk_tenant_id=bk_tenant_id, table_id=table_id, options=validated_request_data["options"]
            )

        logger.info(
            "UpdateDorisRouter:update doris router for table_id->[%s] successfully,now try to push router", table_id
        )

        SpaceTableIDRedis().push_doris_table_id_detail(
            table_id_list=[table_id], bk_tenant_id=bk_tenant_id, is_publish=True
        )

        if need_refresh_data_label:
            logger.info(
                "UpdateDorisRouter: try to push data label router for table_id->[%s], data_label->[%s]",
                table_id,
                validated_request_data["data_label"],
            )

            push_data_labels = [validated_request_data["data_label"]]
            if old_data_label:
                push_data_labels.append(old_data_label)
            SpaceTableIDRedis().push_data_label_table_ids(
                data_label_list=push_data_labels, bk_tenant_id=bk_tenant_id, is_publish=True
            )

        logger.info("UpdateDorisRouter:push doris router for table_id->[%s] successfully", table_id)


class CreateOrUpdateLogRouter(Resource):
    """更新或者创建log路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=False, label="空间类型")
        space_id = serializers.CharField(required=False, label="空间ID")
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
        tableObj = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()

        logger.info(
            "CreateOrUpdateLogRouter: try to create or update log router for table id->[%s],with storage_type->[%s]",
            table_id,
            validated_request_data["storage_type"],
        )

        # 更新查询别名,兼容[]空列表
        if validated_request_data.get("query_alias_settings") is not None:
            operator = get_request_username() or "system"
            models.ESFieldQueryAliasOption.manage_query_alias_settings(
                table_id=table_id,
                query_alias_settings=validated_request_data["query_alias_settings"],
                operator=operator,
                bk_tenant_id=bk_tenant_id,
            )

        # 定义创建器和更新器的映射
        create_router_map = {
            models.ClusterInfo.TYPE_DORIS: CreateDorisRouter,
            models.ClusterInfo.TYPE_ES: CreateEsRouter,
        }

        update_router_map = {
            models.ClusterInfo.TYPE_DORIS: UpdateDorisRouter,
            models.ClusterInfo.TYPE_ES: UpdateEsRouter,
        }

        # 根据是否存在tableObj决定是创建还是更新
        if not tableObj:
            router_class = create_router_map.get(validated_request_data["storage_type"])
        else:
            router_class = update_router_map.get(validated_request_data["storage_type"])

        # 调用对应的router
        if router_class:
            router_class().request(validated_request_data)
        else:
            raise ValueError(f"Unsupported storage type: {validated_request_data['storage_type']}")


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
                        self._create_new_table(bk_tenant_id, space, table_id, table_info, data_label, storage_type)

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

        # 根据存储类型更新存储记录
        if storage_type == models.ClusterInfo.TYPE_ES:
            self._update_es_storage(bk_tenant_id, table_id, table_info)
        elif storage_type == models.ClusterInfo.TYPE_DORIS:
            self._update_doris_storage(bk_tenant_id, table_id, table_info)

    def _create_new_table(
        self, bk_tenant_id: str, space, table_id: str, table_info: dict, data_label: str, storage_type: str
    ):
        """创建新的结果表"""
        # 如果结果表不启用，则不创建
        is_enable = table_info.get("is_enable", True)
        if is_enable is False:
            return

        # 创建结果表
        models.ResultTable.objects.create(
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

        # 根据存储类型创建存储记录
        if storage_type == models.ClusterInfo.TYPE_ES:
            models.ESStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                is_sync_db=False,
                cluster_id=table_info.get("cluster_id"),
                enable_create_index=False,
                source_type=table_info.get("source_type", ""),
                index_set=table_info.get("index_set", ""),
                need_create_index=table_info.get("need_create_index", False),
                origin_table_id=table_info.get("origin_table_id", ""),
            )
        elif storage_type == models.ClusterInfo.TYPE_DORIS:
            models.DorisStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                is_sync_db=False,
                source_type=table_info.get("source_type", ""),
                bkbase_table_id=table_info.get("bkbase_table_id"),
                index_set=table_info.get("index_set"),
                storage_cluster_id=table_info.get("cluster_id"),
            )

    def _update_es_storage(self, bk_tenant_id: str, table_id: str, table_info: dict):
        """更新ES存储记录"""
        try:
            es_storage = models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
            update_fields = []

            if table_info.get("index_set") and table_info["index_set"] != es_storage.index_set:
                es_storage.index_set = table_info["index_set"]
                update_fields.append("index_set")

            if table_info.get("cluster_id") and table_info["cluster_id"] != es_storage.storage_cluster_id:
                es_storage.storage_cluster_id = table_info["cluster_id"]
                update_fields.append("storage_cluster_id")

            if table_info.get("origin_table_id") and table_info["origin_table_id"] != es_storage.origin_table_id:
                es_storage.origin_table_id = table_info["origin_table_id"]
                update_fields.append("origin_table_id")

            if update_fields:
                es_storage.save(update_fields=update_fields)
        except models.ESStorage.DoesNotExist:
            logger.warning("ESStorage not found for table_id [%s], skipping ES storage update", table_id)

    def _update_doris_storage(self, bk_tenant_id: str, table_id: str, table_info: dict):
        """更新Doris存储记录"""
        try:
            doris_storage = models.DorisStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
            update_fields = []

            if table_info.get("index_set") and table_info["index_set"] != doris_storage.index_set:
                doris_storage.index_set = table_info["index_set"]
                update_fields.append("index_set")

            if table_info.get("bkbase_table_id") and table_info["bkbase_table_id"] != doris_storage.bkbase_table_id:
                doris_storage.bkbase_table_id = table_info["bkbase_table_id"]
                update_fields.append("bkbase_table_id")

            if table_info.get("cluster_id") and table_info["cluster_id"] != doris_storage.storage_cluster_id:
                doris_storage.storage_cluster_id = table_info["cluster_id"]
                update_fields.append("storage_cluster_id")

            if update_fields:
                doris_storage.save(update_fields=update_fields)
        except models.DorisStorage.DoesNotExist:
            logger.warning("DorisStorage not found for table_id [%s], skipping Doris storage update", table_id)

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
