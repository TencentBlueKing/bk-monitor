"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.paginator import Paginator
from django.db import models
from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource.base import Resource, logger
from metadata.models import DataSource, TimeSeriesGroup


class TimeSeriesGroupListResource(Resource):
    """时序分组列表查询接口"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", default=0)
        search_key = serializers.CharField(label="名称", required=False, allow_blank=True)
        page_size = serializers.IntegerField(default=10, label="获取的条数")
        page = serializers.IntegerField(default=1, label="页数")
        is_platform = serializers.BooleanField(required=False, label="是否查询平台级数据")

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info("TimeSeriesGroupListResource: try to get time series group list, bk_biz_id->[%s]", bk_biz_id)

        # 查询平台级数据源ID
        platform_data_ids = set(
            DataSource.objects.filter(bk_tenant_id=bk_tenant_id, is_platform_data_id=True).values_list(
                "bk_data_id", flat=True
            )
        )

        # 构建查询
        queryset = TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            is_delete=False,
        ).order_by("-last_modify_time")

        # 过滤
        if validated_request_data.get("is_platform"):
            queryset = queryset.filter(bk_data_id__in=platform_data_ids)
        elif validated_request_data.get("bk_biz_id"):
            queryset = queryset.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        # 搜索
        if validated_request_data.get("search_key"):
            search_key = validated_request_data["search_key"]
            conditions = models.Q(time_series_group_name__contains=search_key)
            try:
                search_key_int = int(search_key)
                conditions |= models.Q(time_series_group_id=search_key_int) | models.Q(bk_data_id=search_key_int)
            except ValueError:
                pass
            queryset = queryset.filter(conditions)

        # 分页
        total = queryset.count()
        paginator = Paginator(queryset, validated_request_data["page_size"])
        page_data = paginator.page(validated_request_data["page"])

        # 转换数据
        result_list = []
        for obj in page_data:
            result_list.append(
                {
                    "time_series_group_id": obj.time_series_group_id,
                    "bk_data_id": obj.bk_data_id,
                    "bk_biz_id": obj.bk_biz_id,
                    "bk_tenant_id": obj.bk_tenant_id,
                    "table_id": obj.table_id,
                    "time_series_group_name": obj.time_series_group_name,
                    "label": obj.label,
                    "is_enable": obj.is_enable,
                    "is_delete": obj.is_delete,
                    "creator": obj.creator,
                    "create_time": obj.create_time.strftime("%Y-%m-%d %H:%M:%S%z"),
                    "last_modify_user": obj.last_modify_user,
                    "last_modify_time": obj.last_modify_time.strftime("%Y-%m-%d %H:%M:%S%z"),
                    "is_split_measurement": obj.is_split_measurement,
                    "is_platform": obj.bk_data_id in platform_data_ids,
                }
            )

        return {"list": result_list, "total": total}
