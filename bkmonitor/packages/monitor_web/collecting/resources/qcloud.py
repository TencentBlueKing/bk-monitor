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
import logging

from core.drf_resource.base import Resource
from core.drf_resource import api
from monitor_web.models.qcloud import CloudProduct

logger = logging.getLogger(__name__)


class CloudProductMappingResource(Resource):
    """
    腾讯云产品映射接口
    获取所有可用的云产品信息
    """

    class RequestSerializer(serializers.Serializer):
        search = serializers.CharField(required=False, help_text=_("搜索关键词"))

    class ResponseSerializer(serializers.Serializer):
        total = serializers.IntegerField(help_text=_("产品总数"))
        products = serializers.ListField(child=serializers.DictField(), help_text=_("产品列表"))

    def perform_request(self, validated_request_data):
        search = validated_request_data.get("search")

        # 基础查询
        queryset = CloudProduct.objects.filter(is_deleted=False)

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


class CloudProductInstanceQueryResource(Resource):
    """
    腾讯云产品实例查询接口
    调用外部腾讯云监控接口查询实例信息
    """

    class RequestSerializer(serializers.Serializer):
        namespace = serializers.CharField(required=True, help_text=_("产品命名空间，如：QCE/LB_PRIVATE"))
        region = serializers.CharField(required=True, help_text=_("地域代码，如：ap-beijing"))

        # 可选的凭证信息，如果不提供则从task_id获取
        secret_id = serializers.CharField(required=False, help_text=_("腾讯云SecretId"))
        secret_key = serializers.CharField(required=False, help_text=_("腾讯云SecretKey"))
        task_id = serializers.CharField(required=False, help_text=_("任务ID，用于获取凭证信息"))

        # 标签过滤条件
        tags = serializers.ListField(
            child=serializers.DictField(), required=False, default=list, help_text=_("标签选择器，支持fuzzy匹配")
        )

        # 字段过滤器
        filters = serializers.ListField(
            child=serializers.DictField(), required=False, default=list, help_text=_("字段过滤器")
        )

    class ResponseSerializer(serializers.Serializer):
        total = serializers.IntegerField(help_text=_("实例总数"))
        data = serializers.ListField(
            child=serializers.DictField(), help_text=_("过滤后的实例列表，每个字段包含value、display_name、description")
        )

    def perform_request(self, validated_request_data):
        """
        调用外部腾讯云监控接口查询实例
        """
        # 直接从请求数据中获取namespace
        namespace = validated_request_data["namespace"]
        region = validated_request_data["region"]

        # 获取凭证信息
        secret_id = validated_request_data.get("secret_id")
        secret_key = validated_request_data.get("secret_key")
        task_id = validated_request_data.get("task_id")

        if not region:
            raise ValueError("必须提供region")
        # 如果没有提供凭证信息，从数据库中获取
        if not secret_id or not secret_key:
            if not task_id:
                raise ValueError("必须提供secret_id和secret_key，或者提供task_id")

            from monitor_web.models.qcloud import CloudMonitoringTask

            try:
                task = CloudMonitoringTask.objects.get(task_id=task_id)
                secret_id = task.secret_id
                secret_key = task.secret_key
                logger.info(f"从任务{task_id}获取到凭证信息")
            except CloudMonitoringTask.DoesNotExist:
                raise ValueError(f"未找到任务ID为{task_id}的配置")

        # 构建请求数据
        request_data = {
            "secretId": secret_id,
            "secretKey": secret_key,
            "namespace": namespace,
            "region": region,
            "tags": validated_request_data.get("tags", []),
            "filters": validated_request_data.get("filters", []),
        }

        # 调用外部API
        try:
            logger.info(f"调用腾讯云实例查询接口: namespace={namespace}, region={region}")

            # 使用API资源调用腾讯云监控接口
            result = api.qcloud_monitor.query_instances(request_data)

            # 获取该产品需要展示的字段配置
            filtered_data = self._filter_instance_data(namespace, result.get("data", []))

            return {"total": result.get("total", 0), "data": filtered_data}

        except Exception as e:
            logger.error(f"腾讯云实例查询失败: {str(e)}")
            raise RuntimeError(f"实例查询失败: {str(e)}")

    def _filter_instance_data(self, namespace, raw_data):
        """
        根据CloudProductInstanceField配置过滤实例数据

        Args:
            namespace: 产品命名空间
            raw_data: 原始实例数据列表

        Returns:
            过滤后的实例数据列表
        """
        from monitor_web.models.qcloud import CloudProductInstanceField

        # 获取该产品配置的字段
        field_configs = CloudProductInstanceField.objects.filter(
            namespace=namespace, is_active=True, is_deleted=False
        ).values("field_name", "display_name", "description")

        if not field_configs:
            logger.warning(f"产品 {namespace} 未配置实例字段，返回原始数据")
            return raw_data

        # 构建字段映射
        field_mapping = {}
        for config in field_configs:
            field_name = config["field_name"]
            display_name = config["display_name"] or field_name
            field_mapping[field_name] = {"display_name": display_name, "description": config["description"]}

        logger.info(f"产品 {namespace} 配置的展示字段: {list(field_mapping.keys())}")

        # 过滤数据
        filtered_instances = []
        for instance in raw_data:
            filtered_instance = {}
            for field_name, field_config in field_mapping.items():
                if field_name in instance:
                    # 使用原字段名作为key，但可以通过display_name获取展示名称
                    filtered_instance[field_name] = {
                        "value": instance[field_name],
                        "display_name": field_config["display_name"],
                        "description": field_config["description"],
                    }

            # 如果过滤后有数据，才添加到结果中
            if filtered_instance:
                filtered_instances.append(filtered_instance)

        logger.info(f"原始实例数量: {len(raw_data)}, 过滤后数量: {len(filtered_instances)}")
        return filtered_instances


class CloudProductConfigResource(Resource):
    """
    查询产品标签和过滤器配置接口
    获取指定云产品的标签和过滤器配置信息
    """

    class RequestSerializer(serializers.Serializer):
        namespace = serializers.CharField(required=True, help_text=_("监控命名空间"))

    class ResponseSerializer(serializers.Serializer):
        tags = serializers.DictField(help_text=_("标签配置"))
        filters = serializers.DictField(help_text=_("过滤器配置"))
        metrics = serializers.ListField(child=serializers.DictField(), help_text=_("指标配置列表"))

    def perform_request(self, validated_request_data):
        """
        查询产品标签和过滤器配置
        """
        namespace = validated_request_data["namespace"]

        # 1. 从ORM获取标签配置
        tags = self._get_tags_from_orm(namespace)

        # 2. 调用API获取过滤器配置
        filters = self._get_filters_from_api(namespace)

        # 3. 从ORM获取指标配置
        metrics = self._get_metrics_from_orm(namespace)

        return {"tags": tags, "filters": filters, "metrics": metrics}

    def _get_tags_from_orm(self, namespace):
        """
        从CloudProductTagField模型获取标签配置

        Args:
            namespace: 产品命名空间

        Returns:
            dict: 标签配置字典，格式为 {tag_name: display_name}
        """
        from monitor_web.models.qcloud import CloudProductTagField

        # 查询该产品的标签字段配置
        tag_fields = CloudProductTagField.objects.filter(namespace=namespace, is_active=True, is_deleted=False).values(
            "tag_name", "display_name"
        )

        # 使用字典推导式构建标签配置字典
        tags = {tag_field["tag_name"]: tag_field["display_name"] or tag_field["tag_name"] for tag_field in tag_fields}

        return tags

    def _get_filters_from_api(self, namespace):
        """
        通过API获取过滤器配置

        Args:
            namespace: 产品命名空间

        Returns:
            dict: 过滤器配置字典，格式为 {filter_name: filter_name}
        """
        try:
            # 构建请求数据
            request_data = {"namespace": namespace}

            # 调用腾讯云监控API获取过滤器
            result = api.qcloud_monitor.query_instance_filters(request_data)

            # 提取过滤器列表
            filter_list = result.get("filters", [])

            # 使用字典推导式构建过滤器配置字典 (key和value相同，因为API只返回过滤器名称)
            filters = {filter_name: filter_name for filter_name in filter_list}

            return filters

        except Exception as e:
            logger.error(f"获取过滤器配置失败: {str(e)}")
            # 如果API调用失败，返回空字典
            return {}

    def _get_metrics_from_orm(self, namespace):
        """
        从CloudProductMetric模型获取指标配置

        Args:
            namespace: 产品命名空间

        Returns:
            list: 指标配置列表，格式为 [{"metric_name": "", "display_name": "", "description": "", "unit": "", "dimensions": []}]
        """
        from monitor_web.models.qcloud import CloudProductMetric

        # 查询该产品的指标配置并使用列表推导式构建结果
        metric_fields = CloudProductMetric.objects.filter(namespace=namespace, is_active=True, is_deleted=False).values(
            "metric_name", "display_name", "description", "unit", "dimensions"
        )

        # 使用列表推导式批量构建指标配置列表
        metrics = [
            {
                "metric_name": metric["metric_name"],
                "display_name": metric["display_name"] or metric["metric_name"],
                "description": metric["description"] or "",
                "unit": metric["unit"] or "",
                "dimensions": metric["dimensions"] or [],
            }
            for metric in metric_fields
        ]

        return metrics
