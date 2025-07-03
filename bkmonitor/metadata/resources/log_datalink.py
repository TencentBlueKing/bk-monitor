"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import OrderedDict

from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.user import get_request_username
from core.drf_resource import Resource
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.service.space_redis import (
    push_and_publish_doris_table_id_detail,
    push_and_publish_es_aliases,
    push_and_publish_es_table_id,
    push_and_publish_log_space_router,
)

logger = logging.getLogger(__name__)

# TODO：LogDataLink整体接口 多租户验证


class ParamsSerializer(serializers.Serializer):
    """参数序列化器"""

    class RtOption(serializers.Serializer):
        name = serializers.CharField(required=True, label="名称")
        value = serializers.CharField(required=True, label="值")
        value_type = serializers.CharField(required=False, label="值类型", default="dict")
        creator = serializers.CharField(required=False, label="创建者", default="system")

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

    def perform_request(self, data: OrderedDict):
        space = models.Space.objects.get(
            space_type_id=data["space_type"], space_id=data["space_id"], bk_tenant_id=get_request_tenant_id()
        )
        bk_tenant_id = space.bk_tenant_id

        # 创建结果表和ES存储记录
        need_create_index = data.get("need_create_index", True)
        # 创建结果表
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ResultTable.objects.create(
                bk_tenant_id=bk_tenant_id,
                table_id=data["table_id"],
                table_name_zh=data["table_id"],
                is_custom_table=True,
                default_storage=models.ClusterInfo.TYPE_ES,
                creator="system",
                bk_biz_id=space.get_bk_biz_id(),
                data_label=data.get("data_label") or "",
            )
            # 创建结果表 option
            if data["options"]:
                self.create_or_update_options(
                    bk_tenant_id=bk_tenant_id, table_id=data["table_id"], options=data["options"]
                )
            # 创建es存储记录
            models.ESStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=data["table_id"],
                is_sync_db=False,
                cluster_id=data.get("cluster_id"),
                enable_create_index=False,
                source_type=data.get("source_type") or "",
                index_set=data.get("index_set") or "",
                need_create_index=need_create_index,
            )
        # 推送空间数据
        push_and_publish_log_space_router(space_type=data["space_type"], space_id=data["space_id"])
        # 推送别名到结果表数据
        push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=data["data_label"])


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

    def perform_request(self, data: dict):
        space = models.Space.objects.get(
            space_type_id=data["space_type"], space_id=data["space_id"], bk_tenant_id=get_request_tenant_id()
        )
        bk_tenant_id = space.bk_tenant_id

        # 创建结果表和存储记录
        logger.info(
            "CreateDorisRouter: try to create doris router,table_id->[%s],bkbase_table_id->[%s],bk_biz_id->[%s]",
            data["table_id"],
            data.get("bkbase_table_id"),
            space.get_bk_biz_id(),
        )

        # 创建结果表
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ResultTable.objects.create(
                bk_tenant_id=bk_tenant_id,
                table_id=data["table_id"],
                table_name_zh=data["table_id"],
                is_custom_table=True,
                default_storage=models.ClusterInfo.TYPE_DORIS,
                creator="system",
                bk_biz_id=space.get_bk_biz_id(),
                data_label=data.get("data_label", ""),
            )
            # 创建结果表 option
            if data["options"]:
                self.create_or_update_options(
                    bk_tenant_id=bk_tenant_id, table_id=data["table_id"], options=data["options"]
                )

            # 创建doris存储记录
            models.DorisStorage.create_table(
                bk_tenant_id=bk_tenant_id,
                table_id=data["table_id"],
                is_sync_db=False,
                source_type=data.get("source_type"),
                bkbase_table_id=data.get("bkbase_table_id"),
                index_set=data.get("index_set"),
                storage_cluster_id=data.get("cluster_id"),
            )

        logger.info("CreateDorisRouter: create doris datalink related records successfully,now try to push router")
        # 推送路由 空间路由+结果表详情路由
        push_and_publish_doris_table_id_detail(bk_tenant_id=bk_tenant_id, table_id=data["table_id"])
        push_and_publish_log_space_router(space_type=data["space_type"], space_id=data["space_id"])

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

    def perform_request(self, data: OrderedDict):
        bk_tenant_id = get_request_tenant_id()

        # 查询结果表存在
        table_id = data["table_id"]
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
        need_refresh_table_id_detail = False
        if data.get("data_label") and data["data_label"] != result_table.data_label:
            result_table.data_label = data["data_label"]
            result_table.save(update_fields=["data_label"])
            need_refresh_data_label = True
        # 更新索引集或者使用的集群
        update_es_fields = []
        if data.get("need_create_index"):
            es_storage.need_create_index = data.get("need_create_index")
            update_es_fields.append("need_create_index")
        if data.get("index_set") and data["index_set"] != es_storage.index_set:
            es_storage.index_set = data["index_set"]
            update_es_fields.append("index_set")
        if data.get("cluster_id") and data["cluster_id"] != es_storage.storage_cluster_id:
            es_storage.storage_cluster_id = data["cluster_id"]
            update_es_fields.append("storage_cluster_id")
        if update_es_fields:
            need_refresh_table_id_detail = True
            es_storage.save(update_fields=update_es_fields)
        # 更新options
        if data.get("options"):
            self.create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=data["options"])
            need_refresh_table_id_detail = True
        options = list(
            models.ResultTableOption.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).values(
                "name", "value", "value_type"
            )
        )
        # 如果别名或者索引集有变动，则需要通知到unify-query
        if need_refresh_data_label:
            push_and_publish_es_aliases(bk_tenant_id=bk_tenant_id, data_label=data["data_label"])
        if need_refresh_table_id_detail:
            push_and_publish_es_table_id(
                bk_tenant_id=result_table.bk_tenant_id,
                table_id=table_id,
                index_set=es_storage.index_set,
                source_type=es_storage.source_type,
                cluster_id=es_storage.storage_cluster_id,
                options=options,
            )


class UpdateDorisRouter(BaseLogRouter):
    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        bkbase_table_id = serializers.CharField(required=False, label="计算平台结果表ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, allow_null=True, label="集群ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")

    def perform_request(self, data: OrderedDict):
        space = models.Space.objects.get(
            space_type_id=data["space_type"], space_id=data["space_id"], bk_tenant_id=get_request_tenant_id()
        )
        bk_tenant_id = space.bk_tenant_id

        table_id = data["table_id"]
        doris_storage = models.DorisStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        result_table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        logger.info("UpdateDorisRouter: try to update doris router for table_id->[%s]", table_id)

        update_doris_fields = []
        need_refresh_table_id_detail = False

        try:
            # data_label
            if data.get("data_label") and data["data_label"] != result_table.data_label:
                result_table.data_label = data["data_label"]
                result_table.save(update_fields=["data_label"])
            # index_set
            if data.get("index_set") and data["index_set"] != doris_storage.index_set:
                doris_storage.index_set = data["index_set"]
                update_doris_fields.append("index_set")
            # bkbase_table_id
            if data.get("bkbase_table_id") and data["bkbase_table_id"] != doris_storage.bkbase_table_id:
                doris_storage.bkbase_table_id = data["bkbase_table_id"]
                update_doris_fields.append("bkbase_table_id")
            # storage_cluster_id
            if data.get("cluster_id") and data["cluster_id"] != doris_storage.storage_cluster_id:
                doris_storage.storage_cluster_id = data["cluster_id"]
                update_doris_fields.append("storage_cluster_id")
            if update_doris_fields:
                need_refresh_table_id_detail = True
                doris_storage.save(update_fields=update_doris_fields)
        except Exception as e:  # pylint:disable=broad-except
            logger.error("UpdateDorisRouter: failed to update doris router for table_id->[%s],error->[%s]", table_id, e)
            raise e

        # 更新options
        if data.get("options"):
            self.create_or_update_options(bk_tenant_id=bk_tenant_id, table_id=table_id, options=data["options"])
            need_refresh_table_id_detail = True

        logger.info(
            "UpdateDorisRouter:update doris router for table_id->[%s] successfully,now try to push router", table_id
        )

        if need_refresh_table_id_detail:
            # 推送结果表详情路由
            push_and_publish_doris_table_id_detail(bk_tenant_id=result_table.bk_tenant_id, table_id=table_id)

        logger.info("UpdateDorisRouter:push doris router for table_id->[%s] successfully", table_id)


class CreateOrUpdateLogRouter(Resource):
    """更新或者创建es路由信息"""

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

        class QueryAliasSettingSerializer(serializers.Serializer):
            field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
            query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")

        query_alias_settings = QueryAliasSettingSerializer(
            required=False, label="查询别名设置", default=list, many=True
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

        # 更新查询别名
        if validated_request_data.get("query_alias_settings"):
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
