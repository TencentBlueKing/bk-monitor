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

import abc

import six
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.cache import CacheType
from core.drf_resource import APIResource


class LogSearchAPIGWResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    base_url_statement = None
    base_url = settings.BKLOGSEARCH_API_BASE_URL or "%s/api/c/compapi/v2/bk_log/" % settings.BK_COMPONENT_API_URL

    # 模块名
    module_name = "bk_log"

    @property
    def label(self):
        return self.__doc__


class ESQuerySearchResource(LogSearchAPIGWResource):
    """
    日志查询接口
    """

    action = "esquery_search/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        # 下面字段，二选一
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

        # 条数（非必填，控制返回条目，默认为500）
        size = serializers.IntegerField(required=False, label="条数")
        aggs = serializers.DictField(required=False, label="ES的聚合条件")
        highlight = serializers.DictField(required=False, label="高亮参数")
        sort_list = serializers.ListField(required=False, label="排序")

        # 默认所有的日志检索查询均不包含end_time那一时刻，避免窗口数据不准
        include_end_time = serializers.BooleanField(required=False, label="end_time__gt or gte", default=False)


class SearchIndexFieldsResource(LogSearchAPIGWResource):
    """
    索引集field
    """

    method = "GET"
    action = ""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")

    def get_request_url(self, validated_request_data):
        """
        重写父类方法,获取最终请求的url
        """
        index_set_id = validated_request_data["index_set_id"]
        return self.base_url.rstrip("/") + "/search_index_set/" + str(index_set_id) + "/fields"


class SearchIndexSetResource(LogSearchAPIGWResource):
    """
    索引集列表
    """

    action = "/search_index_set/"
    method = "GET"
    backend_cache_type = CacheType.LOG_SEARCH

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class OperatorsResource(LogSearchAPIGWResource):
    """
    获取可支持查询方法
    """

    action = "/search_index_set/operators/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")


class ReplaceIndexSetResource(LogSearchAPIGWResource):
    """
    索引集替换
    """

    action = "/index_set/replace/"
    method = "POST"

    class RequestSerializer(serializers.Serializer):
        index_set_name = serializers.CharField(required=True)
        result_table_id = serializers.CharField(required=False)
        storage_cluster_id = serializers.IntegerField(required=False)
        scenario_id = serializers.CharField(required=True)
        project_id = serializers.CharField(required=False)
        bk_biz_id = serializers.IntegerField(required=False)
        category_id = serializers.CharField(required=False)
        indexes = serializers.ListField(allow_empty=True)
        time_field = serializers.CharField(required=False)
        time_field_type = serializers.CharField(required=False)
        time_field_unit = serializers.CharField(required=False)
        view_roles = serializers.ListField(default=[])


class ListCollectorsByHost(LogSearchAPIGWResource):
    """
    获取主机采集项列表
    """

    action = "/databus_collectors/list_collectors_by_host/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        bk_host_innerip = serializers.CharField(required=False, label="主机IP")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID", default=0, allow_null=True)
        bk_host_id = serializers.IntegerField(required=False, label="主机id")
        bk_biz_id = serializers.IntegerField(required=True, help_text="业务ID")


class BkLogSearchGetVariableFieldResource(LogSearchAPIGWResource):
    """
    获取变量名列表
    """

    action = "/grafana/get_variable_field/"
    method = "GET"


class BkLogSearchGetVariableValueResource(LogSearchAPIGWResource):
    """
    获取变量取值列表
    """

    action = "/grafana/get_variable_value/"
    method = "POST"


class BkLogSearchQueryResource(LogSearchAPIGWResource):
    """
    指标数据查询
    """

    action = "/grafana/query/"
    method = "POST"


class BkLogSearchMetricResource(LogSearchAPIGWResource):
    """
    获取指标列表
    """

    action = "/grafana/metric/"
    method = "GET"


class BkLogSearchDimensionResource(LogSearchAPIGWResource):
    """
    获取维度取值列表
    """

    action = "/grafana/dimension/"
    method = "GET"


class BkLogSearchTargetTreeResource(LogSearchAPIGWResource):
    """
    获取拓扑树
    """

    action = "/grafana/target_tree/"
    method = "GET"


class BkLogSearchQueryLogResource(LogSearchAPIGWResource):
    """
    日志数据查询
    """

    action = "/grafana/query_log/"
    method = "POST"


class BkLogSearchClusterGroupsResource(LogSearchAPIGWResource):
    """
    存储集群列表查询
    """

    action = "/databus_storage/cluster_groups/"
    method = "GET"


class CreateIndexSetResource(LogSearchAPIGWResource):
    """
    创建索引集
    """

    action = "/create_index_set/"
    method = "POST"


class UpdateIndexSetResource(LogSearchAPIGWResource):
    """
    更新索引集
    """

    action = "/update_index_set/{index_set_id}/"
    method = "PUT"

    def get_request_url(self, validated_request_data):
        """
        获取最终请求的url，也可以由子类进行重写
        """
        url = self.base_url.rstrip("/") + "/" + self.action.lstrip("/")
        return url.format(index_set_id=validated_request_data.pop("index_set_id"))


class SearchPatternResource(LogSearchAPIGWResource):
    """
    查询索引集模型
    """

    action = "/pattern/{index_set_id}/search/"
    method = "POST"

    def get_request_url(self, validated_request_data):
        """
        获取最终请求的url，也可以由子类进行重写
        """
        url = self.base_url.rstrip("/") + "/" + self.action.lstrip("/")
        return url.format(index_set_id=validated_request_data.pop("index_set_id"))
