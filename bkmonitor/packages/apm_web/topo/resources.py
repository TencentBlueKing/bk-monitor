# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from apm_web.icon import get_icon
from apm_web.models import Application
from apm_web.topo.handle.topo import TopoHandler, TopoSizeCategory
from django.utils.translation import gettext_lazy as _
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    DictSearchColumnTableFormat,
    LinkTableFormat,
    NumberTableFormat,
    StringTableFormat,
)
from rest_framework import serializers


class TopoViewResource(PageListResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        query_type = serializers.ChoiceField(required=True, label="查询类型", choices=["topo", "list"])
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序方式", allow_blank=True)
        filter = serializers.CharField(required=False, label="筛选条件", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选字典", default={})
        size_category = serializers.ChoiceField(
            required=False,
            label="节点大小分类类型",
            choices=[TopoSizeCategory.REQUEST_COUNT, TopoSizeCategory.DURATION],
            default=TopoSizeCategory.REQUEST_COUNT,
        )
        service_name = serializers.CharField(required=False, label="服务名称", allow_blank=True)

    def get_columns(self, column_type=None):
        return [
            LinkTableFormat(
                id="service_name",
                name=_("服务名称"),
                url_format="/service/?filter-service_name={service_name}&filter-app_name={app_name}",
                icon_get=lambda x: get_icon(x["category"]),
                width=200,
                sortable=True,
            ),
            DictSearchColumnTableFormat(
                id="relation",
                name=_("关系调用"),
                column_type="relation",
                get_filter_value=lambda d: "*".join(i["name"] for i in d),
            ),
            StringTableFormat(id="kind", name=_("调用类型"), width=100, filterable=True),
            NumberTableFormat(id="request_count", name=_("调用次数"), width=100, sortable=True),
            NumberTableFormat(id="error_rate", name=_("错误率"), unit="%", decimal=2, width=100, sortable=True),
            NumberTableFormat(id="avg_duration", name=_("平均响应耗时"), unit="ns", decimal=2, width=140, sortable=True),
        ]

    def get_filter_fields(self):
        return ["service_name", "relation"]

    def get_sort_fields(self):
        return ["-error_rate", "-avg_duration", "-request_count"]

    def perform_request(self, validated_request_data):
        # 获取应用
        app = Application.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用不存在"))

        topo_handler = TopoHandler(
            app,
            validated_request_data["start_time"],
            validated_request_data["end_time"],
        )

        if validated_request_data["query_type"] == "topo":
            return topo_handler.get_topo_view(
                validated_request_data.get("filter"),
                validated_request_data.get("service_name"),
                # validated_request_data.get("show_nodata", False),
                validated_request_data.get("keyword", ""),
                validated_request_data.get("size_category"),
            )

        data = topo_handler.get_topo_list(validated_request_data.get("filter"))
        return self.get_pagination_data(data, validated_request_data)
