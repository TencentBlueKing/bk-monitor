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

from rest_framework import serializers

from core.drf_resource import Resource
from metadata import models
from metadata.service.space_redis import (
    push_and_publish_es_aliases,
    push_and_publish_es_space_router,
    push_and_publish_es_table_id,
)


class EsRouter(Resource):
    """同步es路由信息"""

    class RequestSerializer(serializers.Serializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间ID")
        table_id = serializers.CharField(required=True, label="ES 结果表 ID")
        data_label = serializers.CharField(required=True, label="数据标签")
        cluster_id = serializers.CharField(required=True, label="ES 集群 ID")
        index_set = serializers.CharField(required=False, label="索引集规则")
        source_type = serializers.CharField(required=False, label="数据源类型")

    def perform_request(self, data: OrderedDict):
        # 创建结果表和ES存储记录
        biz_id = models.Space.objects.get_biz_id_by_space(space_type=data["space_type"], space_id=data["space_id"])
        # 创建结果表
        models.ResultTable.objects.create(
            table_id=data["table_id"],
            table_name_zh=data["table_id"],
            is_custom_table=True,
            default_storage=models.ClusterInfo.TYPE_ES,
            creator="system",
            bk_biz_id=biz_id,
        )
        # 创建es存储记录
        models.ESStorage.create_table(
            data["table_id"],
            is_sync_db=False,
            cluster_id=data["cluster_id"],
            enable_create_index=False,
            source_type=data["source_type"],
            index_set=data["index_set"],
        )
        # 推送空间数据
        push_and_publish_es_space_router(space_type=data["space_type"], space_id=data["space_id"])
        # 推送别名到结果表数据
        push_and_publish_es_aliases(data_label=data["data_label"], table_id=data["table_id"])
        # 推送结果表ID详情数据
        push_and_publish_es_table_id(
            table_id=data["table_id"],
            index_set=data.get("index_set"),
            source_type=data.get("source_type"),
            cluster_id=data["cluster_id"],
        )
