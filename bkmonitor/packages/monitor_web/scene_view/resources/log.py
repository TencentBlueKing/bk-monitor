# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.utils.translation import ugettext as _
from rest_framework import serializers

from apm_web.utils import get_interval
from core.drf_resource import Resource, api
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import StringTableFormat, TimestampTableFormat


class HostIndexQueryMixin:
    @classmethod
    def query_indexes(cls, validated_data):
        params = {"bk_biz_id": validated_data["bk_biz_id"]}

        if validated_data.get("bk_host_id"):
            params["bk_host_id"] = validated_data["bk_host_id"]
        else:
            if not validated_data.get("bk_host_innerip") or validated_data.get("bk_cloud_id", None) is None:
                raise ValueError(_("没有传递IP信息"))

            params.update(
                {"bk_host_innerip": validated_data["bk_host_innerip"], "bk_cloud_id": validated_data["bk_cloud_id"]}
            )

        infos = api.log_search.list_collectors_by_host(params)

        return infos


class IndexSetQueryMixin:
    @classmethod
    def get_index_time_field(cls, bk_biz_id, index_set_id):
        index_set_info = api.log_search.search_index_fields(bk_biz_id=bk_biz_id, index_set_id=index_set_id)
        return index_set_info.get("time_field", "dtEventTimeStamp")


class GetIndexSetLogSeries(Resource, IndexSetQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        index_set_id = serializers.IntegerField(label="索引集ID")
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        interval = serializers.CharField(default="auto")
        keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        interval = validated_request_data["interval"]

        time_field = self.get_index_time_field(bk_biz_id, index_set_id)
        interval = get_interval(start_time, end_time, interval)

        params = {}
        if validated_request_data.get("keyword"):
            params["query_string"] = validated_request_data["keyword"]

        response = api.log_search.es_query_search(
            index_set_id=index_set_id,
            aggs={"log_count": {"date_histogram": {"field": time_field, "interval": interval}}},
            start_time=start_time,
            end_time=end_time,
            **params
        )

        buckets = response.get("aggregations", {}).get("log_count", {}).get("buckets", [])

        return {
            "metrics": [],
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": [[i["key"], i["doc_count"]] for i in buckets if i["doc_count"]],
                    "dimensions": {},
                    "metric_field": "_result_",
                    "target": "",
                    "type": "line",
                    "unit": "",
                }
            ],
        }


class ListIndexSetLog(PageListResource, IndexSetQueryMixin):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        index_set_id = serializers.IntegerField(label="索引集ID")

        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        offset = serializers.IntegerField(default=0)
        limit = serializers.IntegerField(default=10)
        keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def get_filter_fields(self):
        return ["log"]

    def get_columns(self, column_type=None):
        return [
            TimestampTableFormat(id="date", name=_("时间"), digits=1000, width=200),
            StringTableFormat(id="log", name=_("日志内容"), show_over_flow_tool_tip=False),
        ]

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]

        time_field = self.get_index_time_field(bk_biz_id, index_set_id)

        params = {}
        if validated_request_data.get("keyword"):
            params["query_string"] = validated_request_data["keyword"]

        response = api.log_search.es_query_search(
            index_set_id=index_set_id,
            start_time=start_time,
            end_time=end_time,
            size=validated_request_data["limit"],
            start=validated_request_data["offset"],
            sort_list=[[time_field, "desc"]],
            **params
        )

        res = []
        total = response["hits"]["total"]
        for item in response.get("hits", {}).get("hits", []):
            source = item["_source"]
            res.append(
                {
                    "date": source.get(time_field),
                    "source": source,
                    "log": str(source),
                }
            )

        c_f = self.get_columns_config(res, None)[0]

        # 格式化数据
        res = self.handle_format(res, c_f, validated_request_data)

        return {"columns": [column.column() for column in c_f], "total": total, "data": res}
