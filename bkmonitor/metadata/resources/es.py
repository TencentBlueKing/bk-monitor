# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import OrderedDict
from typing import Dict, List, Optional

from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE, BULK_UPDATE_BATCH_SIZE
from metadata.service.space_redis import (
    push_and_publish_es_aliases,
    push_and_publish_es_space_router,
    push_and_publish_es_table_id,
)


class ParamsSerializer(serializers.Serializer):
    """参数序列化器"""

    class RtOption(serializers.Serializer):
        name = serializers.CharField(required=True, label="名称")
        value = serializers.CharField(required=True, label="值")
        value_type = serializers.CharField(required=False, label="值类型", default="dict")
        creator = serializers.CharField(required=False, label="创建者", default="system")

    options = serializers.ListField(required=False, child=RtOption(), default=list)


class BaseEsRouter(Resource):
    def create_or_update_options(self, table_id: str, options: List[Dict]):
        """创建或者更新结果表 option"""
        # 查询结果表下的option
        exist_objs = {obj.name: obj for obj in models.ResultTableOption.objects.filter(table_id=table_id)}
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
                need_add_objs.append(models.ResultTableOption(table_id=table_id, **dict(option)))

        # 批量创建
        if need_add_objs:
            models.ResultTableOption.objects.bulk_create(need_add_objs, batch_size=BULK_CREATE_BATCH_SIZE)
        # 批量更新
        if need_update_objs:
            models.ResultTableOption.objects.bulk_update(
                need_update_objs, update_fields, batch_size=BULK_UPDATE_BATCH_SIZE
            )


class CreateEsRouter(BaseEsRouter):
    """同步es路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="ES 结果表 ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=True, label="ES 集群 ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
        need_create_index = serializers.BooleanField(required=False, label="是否创建索引")

    def perform_request(self, data: OrderedDict):
        # 创建结果表和ES存储记录
        biz_id = models.Space.objects.get_biz_id_by_space(space_type=data["space_type"], space_id=data["space_id"])
        need_create_index = data.get("need_create_index", True)
        # 创建结果表
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ResultTable.objects.create(
                table_id=data["table_id"],
                table_name_zh=data["table_id"],
                is_custom_table=True,
                default_storage=models.ClusterInfo.TYPE_ES,
                creator="system",
                bk_biz_id=biz_id,
                data_label=data.get("data_label") or "",
            )
            # 创建结果表 option
            if data["options"]:
                self.create_or_update_options(data["table_id"], data["options"])
            # 创建es存储记录
            models.ESStorage.create_table(
                data["table_id"],
                is_sync_db=False,
                cluster_id=data["cluster_id"],
                enable_create_index=False,
                source_type=data.get("source_type") or "",
                index_set=data.get("index_set") or "",
                need_create_index=need_create_index,
            )
        # 推送空间数据
        push_and_publish_es_space_router(space_type=data["space_type"], space_id=data["space_id"])
        # 推送别名到结果表数据
        push_and_publish_es_aliases(data_label=data["data_label"])
        # 推送结果表ID详情数据
        push_and_publish_es_table_id(
            table_id=data["table_id"],
            index_set=data.get("index_set"),
            source_type=data.get("source_type"),
            cluster_id=data["cluster_id"],
            options=data.get("options"),
        )


class UpdateEsRouter(BaseEsRouter):
    """更新es路由信息"""

    class RequestSerializer(ParamsSerializer):
        table_id = serializers.CharField(required=True, label="ES 结果表 ID")
        data_label = serializers.CharField(required=False, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, label="ES 集群 ID")
        index_set = serializers.CharField(required=False, label="索引集规则")
        source_type = serializers.CharField(required=False, label="数据源类型")
        need_create_index = serializers.BooleanField(required=False, label="是否创建索引")

    def perform_request(self, data: OrderedDict):
        # 查询结果表存在
        table_id = data["table_id"]
        try:
            result_table = models.ResultTable.objects.get(table_id=table_id)
        except models.ResultTable.DoesNotExist:
            raise ValidationError("Result table not found")
        # 查询es存储记录
        try:
            es_storage = models.ESStorage.objects.get(table_id=table_id)
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
            self.create_or_update_options(table_id, data["options"])
            need_refresh_table_id_detail = True
        options = list(models.ResultTableOption.objects.filter(table_id=table_id).values("name", "value", "value_type"))
        # 如果别名或者索引集有变动，则需要通知到unify-query
        if need_refresh_data_label:
            push_and_publish_es_aliases(data_label=data["data_label"])
        if need_refresh_table_id_detail:
            push_and_publish_es_table_id(
                table_id=table_id,
                index_set=es_storage.index_set,
                source_type=es_storage.source_type,
                cluster_id=es_storage.storage_cluster_id,
                options=options,
            )


class CreateOrUpdateEsRouter(Resource):
    """更新或者创建es路由信息"""

    class RequestSerializer(ParamsSerializer):
        space_type = serializers.CharField(required=False, label="空间类型")
        space_id = serializers.CharField(required=False, label="空间ID")
        table_id = serializers.CharField(required=True, label="ES 结果表 ID")
        data_label = serializers.CharField(required=False, allow_blank=True, label="数据标签")
        cluster_id = serializers.IntegerField(required=False, label="ES 集群 ID")
        index_set = serializers.CharField(required=False, allow_blank=True, label="索引集规则")
        source_type = serializers.CharField(required=False, allow_blank=True, label="数据源类型")
        need_create_index = serializers.BooleanField(required=False, label="是否需要创建索引")

    def perform_request(self, validated_request_data):
        # 根据结果表判断是创建或更新
        tableObj = self.get_table_id(validated_request_data["table_id"])
        # 如果结果表不存在，则进行创建，如果存在，则进行更新
        if not tableObj:
            CreateEsRouter().request(validated_request_data)
        else:
            UpdateEsRouter().request(validated_request_data)

    def get_table_id(self, table_id: str) -> Optional[models.ResultTable]:
        """检测结果表是否存在"""
        try:
            return models.ResultTable.objects.get(table_id=table_id)
        except models.ResultTable.DoesNotExist:
            return None
