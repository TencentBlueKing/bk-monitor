"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _
from django.db import models
from rest_framework import serializers

from core.drf_resource.base import Resource
from monitor_web.models.qcloud import CloudProduct


class CloudProductMappingResource(Resource):
    """
    腾讯云产品映射接口
    获取所有可用的云产品信息
    """

    class RequestSerializer(serializers.Serializer):
        category = serializers.CharField(
            required=False, help_text=_("产品分类过滤，如：compute、network、storage、database")
        )
        search = serializers.CharField(required=False, help_text=_("搜索关键词"))

    class ResponseSerializer(serializers.Serializer):
        total = serializers.IntegerField(help_text=_("产品总数"))
        products = serializers.ListField(child=serializers.DictField(), help_text=_("产品列表"))

    def perform_request(self, validated_request_data):
        category = validated_request_data.get("category")
        search = validated_request_data.get("search")

        # 基础查询
        queryset = CloudProduct.objects.filter(is_deleted=False)

        # 分类过滤 - 这里可以根据实际需求扩展分类逻辑
        # 目前根据namespace前缀或者description内容进行粗略分类
        if category:
            category_mapping = {
                "compute": ["CVM", "CDB", "REDIS"],
                "network": ["CLB", "VPC", "CDN"],
                "storage": ["COS", "CBS"],
                "database": ["CDB", "REDIS", "MONGODB"],
            }
            if category in category_mapping:
                category_keywords = category_mapping[category]
                # 使用namespace中包含的关键词进行过滤
                category_filter = None
                for keyword in category_keywords:
                    if category_filter is None:
                        category_filter = models.Q(namespace__icontains=keyword)
                    else:
                        category_filter |= models.Q(namespace__icontains=keyword)

                if category_filter:
                    queryset = queryset.filter(category_filter)

        # 搜索过滤
        if search:
            queryset = queryset.filter(
                models.Q(namespace__icontains=search)
                | models.Q(product_name__icontains=search)
                | models.Q(description__icontains=search)
            )

        # 获取产品列表
        products = []
        for product in queryset:
            products.append(
                {
                    "namespace": product.namespace,
                    "product_name": product.product_name,
                    "description": product.description,
                }
            )

        return {"total": len(products), "products": products}
