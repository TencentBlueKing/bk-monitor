# -*- coding: utf-8 -*-
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

from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from core.drf_resource import Resource, api

logger = logging.getLogger(__name__)


class GetIndexSetListResource(Resource):
    """
    日志查询服务 -- 获取索引集列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info("SearchIndexSetListResource: try to search index set list, bk_biz_id->[%s]", bk_biz_id)
        result = api.log_search.search_index_set(bk_biz_id=bk_biz_id)
        return result


class GetIndexSetFieldListResource(Resource):
    """
    日志查询服务 -- 获取索引集字段列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info("GetIndexSetFieldListResource: try to get index set field list, index_set_id->[%s], bk_biz_id->[%s]"
                    , index_set_id, bk_biz_id)
        result = api.log_search.log_search_index_set(index_set_id=index_set_id)
        return result


class SearchLogResource(Resource):
    """
    日志查询服务 -- 日志查询
    """
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        # index_set_id 和 indices,scenario_id,storage_cluster_id,time_field 任选一种
        index_set_id = serializers.IntegerField(required=False, label="索引集ID")

        indices = serializers.CharField(required=False, label="索引列表")
        # ES接入场景(非必填） 默认为log，蓝鲸计算平台：bkdata 原生ES：es 日志采集：log
        scenario_id = serializers.CharField(required=False, label="ES接入场景")
        # 当scenario_id为es或log时候需要传入
        storage_cluster_id = serializers.IntegerField(required=False, label="存储集群")
        time_field = serializers.CharField(required=False, label="时间字段")

        start_time = serializers.CharField(required=False, label="开始时间")
        end_time = serializers.CharField(required=False, label="结束时间")

        #  时间标识符符["15m", "30m", "1h", "4h", "12h", "1d", "customized"]
        # （非必填，默认15m）
        time_range = serializers.CharField(required=False, label="时间标识符")

        # 搜索语句query_string(非必填，默认为*)
        query_string = serializers.CharField(required=False, label="搜索语句")

        # 搜索过滤条件（非必填，默认为没有过滤，默认的操作符是is） 操作符支持 is、is one of、is not、is not one of
        filter = serializers.ListField(required=False, label="搜索过滤条件")

        # 起始位置（非必填，类似数组切片，默认为0）
        start = serializers.IntegerField(required=False, label="起始位置")

        # 条数（非必填，控制返回条目，默认为10）
        size = serializers.IntegerField(required=False, label="条数",)
        aggs = serializers.DictField(required=False, label="ES的聚合条件")
        highlight = serializers.DictField(required=False, label="高亮参数")
        sort_list = serializers.ListField(required=False, label="排序")

        # 默认所有的日志检索查询均不包含end_time那一时刻，避免窗口数据不准
        include_end_time = serializers.BooleanField(required=False, label="end_time__gt or gte", default=False)

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.pop("bk_biz_id")
        logger.info("SearchLogResource: try to search log, index_set_id->[%s], bk_biz_id->[%s]"
                    , index_set_id, bk_biz_id)
        result = api.log_search.es_query_search(**validated_request_data)
        return result
