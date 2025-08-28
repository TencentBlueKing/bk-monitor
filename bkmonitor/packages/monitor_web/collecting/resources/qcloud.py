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
from django.conf import settings
from kubernetes import client as k8s_client
from urllib.parse import urljoin

from core.drf_resource.base import Resource
from core.drf_resource import api
from monitor_web.models.qcloud import CloudProduct

logger = logging.getLogger(__name__)

__all__ = [
    "CloudProductMappingResource",
    "CloudProductInstanceQueryResource",
    "CloudProductConfigResource",
    "CloudMonitoringSaveConfigResource",
    "CloudMonitoringTaskListResource",
    "CloudMonitoringTaskStatusResource",
    "CloudMonitoringTaskDetailResource",
    "CloudMonitoringUpdateConfigResource",
    "CloudMonitoringTaskLogResource",
]


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


class CloudMonitoringSaveConfigResource(Resource):
    """
    保存配置并下发采集接口
    保存云监控采集任务配置并开始部署
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        namespace = serializers.CharField(required=True, help_text=_("产品命名空间"))
        collect_name = serializers.CharField(required=True, help_text=_("采集任务名称"))
        collect_interval = serializers.CharField(required=True, help_text=_("采集间隔，如：1m"))
        collect_timeout = serializers.CharField(required=True, help_text=_("采集超时时间，如：30s"))

        # 直接的凭证信息
        secret_id = serializers.CharField(required=True, help_text=_("腾讯云SecretId"))
        secret_key = serializers.CharField(required=True, help_text=_("腾讯云SecretKey"))

        # 地域配置
        regions = serializers.ListField(child=serializers.DictField(), required=True, help_text=_("地域配置列表"))

        # 环境配置
        is_internal = serializers.BooleanField(required=False, default=False, help_text=_("是否内部环境"))
        is_international = serializers.BooleanField(required=False, default=True, help_text=_("是否国际版"))

    class ResponseSerializer(serializers.Serializer):
        result = serializers.BooleanField(help_text=_("操作结果"))
        code = serializers.IntegerField(help_text=_("状态码"))
        message = serializers.CharField(help_text=_("返回消息"))
        task_id = serializers.CharField(help_text=_("任务ID"))

    def perform_request(self, validated_request_data):
        """
        保存配置并下发采集任务
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        namespace = validated_request_data["namespace"]
        collect_name = validated_request_data["collect_name"]
        collect_interval = validated_request_data["collect_interval"]
        collect_timeout = validated_request_data["collect_timeout"]
        secret_id = validated_request_data["secret_id"]
        secret_key = validated_request_data["secret_key"]
        regions = validated_request_data["regions"]
        is_internal = validated_request_data["is_internal"]
        is_international = validated_request_data["is_international"]

        try:
            # 1. 验证凭证信息
            self._validate_credentials(secret_id, secret_key)

            # 2. 验证产品命名空间
            self._validate_namespace(namespace)

            # 3. 验证地域配置
            self._validate_regions(regions)

            # 4. 生成任务ID
            task_id = self._generate_task_id(bk_biz_id, namespace)

            # 5. 保存主任务配置
            self._save_monitoring_task(
                task_id=task_id,
                bk_biz_id=bk_biz_id,
                namespace=namespace,
                collect_name=collect_name,
                collect_interval=collect_interval,
                collect_timeout=collect_timeout,
                secret_id=secret_id,
                secret_key=secret_key,
                is_internal=is_internal,
                is_international=is_international,
            )

            # 6. 保存地域配置
            self._save_region_configs(task_id, regions)

            # 7. 下发采集任务
            self._deploy_monitoring_task(task_id)

            return {"message": "监控采集任务创建成功", "task_id": task_id}

        except Exception as e:
            logger.error(f"保存云监控配置失败: {str(e)}")
            return {"message": f"保存配置失败: {str(e)}", "task_id": ""}

    def _validate_credentials(self, secret_id, secret_key):
        """
        验证凭证信息

        Args:
            secret_id: 腾讯云SecretId
            secret_key: 腾讯云SecretKey
        """
        if not secret_id or not secret_key:
            raise ValueError("secret_id和secret_key不能为空")

    def _validate_namespace(self, namespace):
        """
        验证产品命名空间

        Args:
            namespace: 产品命名空间
        """
        from monitor_web.models.qcloud import CloudProduct

        if not CloudProduct.objects.filter(namespace=namespace, is_deleted=False).exists():
            raise ValueError(f"不支持的产品命名空间: {namespace}")

    def _validate_regions(self, regions):
        """
        验证地域配置

        Args:
            regions: 地域配置列表
        """
        if not regions:
            raise ValueError("地域配置不能为空")

        for i, region in enumerate(regions):
            # 验证必要字段
            if "region" not in region:
                raise ValueError(f"地域配置[{i}]缺少region字段")

            if "id" not in region:
                raise ValueError(f"地域配置[{i}]缺少id字段")

            # 验证实例选择配置
            instance_selection = region.get("instance_selection", {})
            tags = instance_selection.get("tags", [])
            filters = instance_selection.get("filters", [])
            dimensions = region.get("dimensions", [])

            # 验证标签配置格式
            for tag in tags:
                if "name" not in tag or "value" not in tag:
                    raise ValueError(f"地域配置[{i}]标签格式不正确，缺少name或value字段")

            # 验证过滤器配置格式
            for filter_item in filters:
                if "name" not in filter_item or "value" not in filter_item:
                    raise ValueError(f"地域配置[{i}]过滤器格式不正确，缺少name或value字段")

            # 验证维度配置格式
            for dimension in dimensions:
                if "name" not in dimension or "value" not in dimension:
                    raise ValueError(f"地域配置[{i}]维度格式不正确，缺少name或value字段")

            # 验证选择的指标
            selected_metrics = region.get("selected_metrics", [])
            if not selected_metrics:
                logger.warning(f"地域配置[{i}]未选择任何指标")

    def _generate_task_id(self, bk_biz_id, namespace):
        """
        生成任务ID

        Args:
            bk_biz_id: 业务ID
            namespace: 产品命名空间

        Returns:
            str: 任务ID
        """
        import uuid
        import time

        # 使用时间戳和UUID生成唯一任务ID
        timestamp = int(time.time())
        uuid_str = str(uuid.uuid4()).replace("-", "")[:8]

        # 格式：qcloud_{namespace}_{bk_biz_id}_{timestamp}_{uuid}
        namespace_short = namespace.replace("QCE/", "").replace("/", "_")
        task_id = f"qcloud_{namespace_short}_{bk_biz_id}_{timestamp}_{uuid_str}"

        return task_id

    def _save_monitoring_task(
        self,
        task_id,
        bk_biz_id,
        namespace,
        collect_name,
        collect_interval,
        collect_timeout,
        secret_id,
        secret_key,
        is_internal,
        is_international,
    ):
        """
        保存主任务配置

        Args:
            task_id: 任务ID
            bk_biz_id: 业务ID
            namespace: 产品命名空间
            collect_name: 采集名称
            collect_interval: 采集间隔
            collect_timeout: 采集超时时间
            secret_id: 腾讯云SecretId
            secret_key: 腾讯云SecretKey
            is_internal: 是否内部环境
            is_international: 是否国际版

        Returns:
            CloudMonitoringTask: 保存的任务对象
        """
        from monitor_web.models.qcloud import CloudMonitoringTask

        # 检查任务ID是否已存在
        if CloudMonitoringTask.objects.filter(task_id=task_id).exists():
            raise ValueError(f"任务ID {task_id} 已存在")

        # 创建任务
        task = CloudMonitoringTask.objects.create(
            task_id=task_id,
            bk_biz_id=bk_biz_id,
            namespace=namespace,
            collect_name=collect_name,
            collect_interval=collect_interval,
            collect_timeout=collect_timeout,
            secret_id=secret_id,
            secret_key=secret_key,
            is_internal=is_internal,
            is_international=is_international,
            status=CloudMonitoringTask.STATUS_CONNECTING,
        )

        logger.info(f"创建云监控任务成功: task_id={task_id}, namespace={namespace}")
        return task

    def _save_region_configs(self, task_id, regions):
        """
        保存地域配置

        Args:
            task_id: 任务ID
            regions: 地域配置列表
        """
        from monitor_web.models.qcloud import CloudMonitoringTaskRegion

        for region_config in regions:
            # 构建标签配置
            tags_config = []
            instance_selection = region_config.get("instance_selection", {})
            for tag in instance_selection.get("tags", []):
                tags_config.append(
                    {
                        "name": tag["name"],
                        "value": tag["value"],
                        "fuzzy": tag.get("fuzzy", False),  # 默认精确匹配
                    }
                )

            # 构建过滤器配置
            filters_config = []
            for filter_item in instance_selection.get("filters", []):
                filters_config.append({"name": filter_item["name"], "value": filter_item["value"]})

            # 构建维度配置
            dimensions_config = []
            for dimension in region_config.get("dimensions", []):
                dimensions_config.append({"name": dimension["name"], "value": dimension["value"]})

            # 创建地域配置
            CloudMonitoringTaskRegion.objects.create(
                task_id=task_id,
                region_id=region_config["id"],
                region_code=region_config["region"],
                tags_config=tags_config,
                filters_config=filters_config,
                selected_metrics=region_config.get("selected_metrics", []),
                dimensions_config=dimensions_config,
                status=CloudMonitoringTaskRegion.STATUS_CONNECTING,
            )

            logger.info(f"保存地域配置成功: task_id={task_id}, region={region_config['region']}")

    def _deploy_monitoring_task(self, task_id):
        """
        部署腾讯云监控采集任务

        Args:
            task_id: 任务ID
        """
        try:
            from monitor_web.collecting.deploy.qcloud import QCloudMonitoringTaskDeployer

            deployer = QCloudMonitoringTaskDeployer(task_id)
            deployer.deploy()

            logger.info(f"腾讯云监控任务部署启动成功: task_id={task_id}")
        except Exception as e:
            logger.error(f"腾讯云监控任务部署失败: task_id={task_id}, error={str(e)}")
            # 更新任务状态为失败
            from monitor_web.models.qcloud import CloudMonitoringTask

            try:
                task = CloudMonitoringTask.objects.get(task_id=task_id)
                task.status = CloudMonitoringTask.STATUS_FAILED
                task.save()
            except CloudMonitoringTask.DoesNotExist:
                logger.error(f"未找到任务: task_id={task_id}")
            raise


class CloudMonitoringTaskListResource(Resource):
    """
    获取采集配置列表接口
    查询指定业务下的云监控采集任务列表，支持分页和搜索
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        page = serializers.IntegerField(required=False, default=1, help_text=_("页码，默认1"))
        page_size = serializers.IntegerField(required=False, default=20, help_text=_("每页数量，默认20"))
        search = serializers.CharField(required=False, help_text=_("搜索关键词，搜索采集名称、产品名、最近更新人"))

    class ResponseSerializer(serializers.Serializer):
        total = serializers.IntegerField(help_text=_("任务总数"))
        page = serializers.IntegerField(help_text=_("当前页码"))
        page_size = serializers.IntegerField(help_text=_("每页数量"))
        tasks = serializers.ListField(child=serializers.DictField(), help_text=_("任务列表"))

    def perform_request(self, validated_request_data):
        """
        查询云监控采集任务列表
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        page = validated_request_data.get("page", 1)
        page_size = validated_request_data.get("page_size", 20)
        search = validated_request_data.get("search")

        try:
            # 1. 基础查询
            queryset = self._build_base_queryset(bk_biz_id)

            # 2. 搜索过滤
            if search:
                queryset = self._apply_search_filter(queryset, search)

            # 3. 获取总数
            total = queryset.count()

            # 4. 分页处理
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_queryset = queryset[start_index:end_index]

            # 5. 构建任务列表
            tasks = self._build_task_list(paginated_queryset)

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "tasks": tasks,
            }

        except Exception as e:
            logger.error(f"查询云监控任务列表失败: {str(e)}")
            raise RuntimeError(f"查询任务列表失败: {str(e)}")

    def _build_base_queryset(self, bk_biz_id):
        """
        构建基础查询集

        Args:
            bk_biz_id: 业务ID

        Returns:
            QuerySet: 基础查询集
        """
        from monitor_web.models.qcloud import CloudMonitoringTask

        return (
            CloudMonitoringTask.objects.filter(bk_biz_id=bk_biz_id, is_deleted=False)
            .select_related()
            .order_by("-update_time")
        )

    def _apply_search_filter(self, queryset, search):
        """
        应用搜索过滤

        Args:
            queryset: 查询集
            search: 搜索关键词

        Returns:
            QuerySet: 过滤后的查询集
        """
        from monitor_web.models.qcloud import CloudProduct

        # 获取符合条件的产品命名空间列表
        product_namespaces = list(
            CloudProduct.objects.filter(product_name__icontains=search, is_deleted=False).values_list(
                "namespace", flat=True
            )
        )

        return queryset.filter(
            models.Q(collect_name__icontains=search)
            | models.Q(update_user__icontains=search)
            | models.Q(namespace__in=product_namespaces)
        )

    def _build_task_list(self, queryset):
        """
        构建任务列表

        Args:
            queryset: 查询集

        Returns:
            list: 任务列表
        """
        from monitor_web.models.qcloud import CloudProduct

        tasks = []

        # 批量获取产品信息以提高性能
        namespaces = [task.namespace for task in queryset]
        product_mapping = {
            product.namespace: product.product_name
            for product in CloudProduct.objects.filter(namespace__in=namespaces, is_deleted=False)
        }

        for task in queryset:
            # 获取产品名称
            product_name = product_mapping.get(task.namespace, task.namespace)

            # 获取地域信息列表
            regions = self._get_main_region(task.task_id)

            # 格式化时间
            latest_datapoint = task.latest_datapoint.strftime("%Y-%m-%d %H:%M:%S %z") if task.latest_datapoint else None
            latest_update_time = task.update_time.strftime("%Y-%m-%d %H:%M:%S %z") if task.update_time else None

            task_info = {
                "task_id": task.task_id,
                "collect_name": task.collect_name,
                "product_name": product_name,
                "latest_datapoint": latest_datapoint,
                "regions": regions,  # 返回地域列表
                "latest_updater": task.update_user,
                "latest_update_time": latest_update_time,
            }

            tasks.append(task_info)

        return tasks

    def _get_main_region(self, task_id):
        """
        获取任务的地域信息列表

        Args:
            task_id: 任务ID

        Returns:
            list: 地域信息列表，格式为 [{"id": "...", "region": "..."}]
        """
        from monitor_web.models.qcloud import CloudMonitoringTaskRegion

        try:
            # 获取所有地域配置
            region_configs = CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False).order_by(
                "region_id"
            )

            # 构建地域信息列表
            regions_list = []
            for region in region_configs:
                regions_list.append({"id": region.region_id, "region": region.region_code})
            return regions_list

        except Exception as e:
            logger.warning(f"获取任务{task_id}地域信息失败: {str(e)}")
            return []


class CloudMonitoringTaskStatusResource(Resource):
    """
    异步获取任务状态接口
    查询指定任务的当前状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(help_text=_("任务ID"))
        status = serializers.CharField(help_text=_("任务状态"))

    def perform_request(self, validated_request_data):
        """
        查询任务状态
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        task_id = validated_request_data["task_id"]

        try:
            from monitor_web.models.qcloud import CloudMonitoringTask

            # 查询任务
            task = CloudMonitoringTask.objects.get(task_id=task_id, bk_biz_id=bk_biz_id, is_deleted=False)

            return {
                "task_id": task.task_id,
                "status": task.status,
            }

        except CloudMonitoringTask.DoesNotExist:
            logger.error(f"任务不存在: task_id={task_id}, bk_biz_id={bk_biz_id}")
            raise ValueError(f"任务不存在: {task_id}")
        except Exception as e:
            logger.error(f"查询任务状态失败: {str(e)}")
            raise RuntimeError(f"查询任务状态失败: {str(e)}")


class CloudMonitoringTaskDetailResource(Resource):
    """
    获取采集配置详情接口
    查询指定任务的详细配置信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(help_text=_("任务ID"))
        bk_biz_id = serializers.IntegerField(help_text=_("业务ID"))
        collect_interval = serializers.CharField(help_text=_("采集间隔"))
        collect_timeout = serializers.CharField(help_text=_("采集超时时间"))
        resource_name = serializers.CharField(help_text=_("资源名称"))
        secret_id = serializers.CharField(help_text=_("腾讯云SecretId"))
        regions = serializers.ListField(child=serializers.DictField(), help_text=_("地域配置列表"))

    def perform_request(self, validated_request_data, task_id=None):
        """
        查询任务详细配置
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        # 从URL参数获取task_id
        task_id = task_id or validated_request_data.get("task_id")

        if not task_id:
            raise ValueError("必须提供task_id参数")

        try:
            from monitor_web.models.qcloud import CloudMonitoringTask, CloudMonitoringTaskRegion

            # 查询主任务
            task = CloudMonitoringTask.objects.get(task_id=task_id, bk_biz_id=bk_biz_id, is_deleted=False)

            # 查询地域配置
            region_configs = CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False).order_by(
                "region_id"
            )

            # 构建地域配置列表
            regions = []
            for region_config in region_configs:
                region_data = {
                    "region": region_config.region_code,
                    "id": region_config.region_id,
                    "instance_selection": {
                        "tags": region_config.tags_config or [],
                        "filters": region_config.filters_config or [],
                    },
                    "selected_metrics": region_config.selected_metrics or [],
                    "dimensions": region_config.dimensions_config or [],
                }
                regions.append(region_data)

            # 构建响应数据
            return {
                "task_id": task.task_id,
                "bk_biz_id": task.bk_biz_id,
                "collect_interval": task.collect_interval,
                "collect_timeout": task.collect_timeout,
                "resource_name": task.collect_name,
                "secret_id": self._mask_secret_id(task.secret_id),
                "regions": regions,
            }

        except CloudMonitoringTask.DoesNotExist:
            logger.error(f"任务不存在: task_id={task_id}, bk_biz_id={bk_biz_id}")
            raise ValueError(f"任务不存在: {task_id}")
        except Exception as e:
            logger.error(f"查询任务详情失败: {str(e)}")
            raise RuntimeError(f"查询任务详情失败: {str(e)}")

    def _mask_secret_id(self, secret_id):
        """
        对 secret_id 进行脱敏处理，只显示前后各3个字符，中间用*号填充

        Args:
            secret_id: 原始的 secret_id

        Returns:
            str: 脱敏后的 secret_id
        """
        if not secret_id:
            return ""

        secret_id_str = str(secret_id)
        if len(secret_id_str) <= 6:
            # 如果长度小于等于6，则全部用*号替换
            return "*" * len(secret_id_str)
        else:
            # 显示前3个和后3个字符，中间用*号填充
            prefix = secret_id_str[:3]
            suffix = secret_id_str[-3:]
            middle_length = len(secret_id_str) - 6
            return f"{prefix}{'*' * middle_length}{suffix}"


class CloudMonitoringUpdateConfigResource(Resource):
    """
    更新采集配置接口
    只更新前端传递的参数，前端未传递的参数不会被更新
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))

        # 可选参数，如果不传则不更新
        collect_name = serializers.CharField(required=False, help_text=_("采集任务名称"))
        collect_interval = serializers.CharField(required=False, help_text=_("采集间隔，如：1m"))
        collect_timeout = serializers.CharField(required=False, help_text=_("采集超时时间，如：30s"))

        # 凭证信息，如果不传则不更新
        secret_id = serializers.CharField(required=False, help_text=_("腾讯云SecretId"))
        secret_key = serializers.CharField(required=False, help_text=_("腾讯云SecretKey"))

        # 地域配置，如果不传则不更新
        regions = serializers.ListField(child=serializers.DictField(), required=False, help_text=_("地域配置列表"))

        # 环境配置
        is_internal = serializers.BooleanField(required=False, help_text=_("是否内部环境"))
        is_international = serializers.BooleanField(required=False, help_text=_("是否国际版"))

    class ResponseSerializer(serializers.Serializer):
        result = serializers.BooleanField(help_text=_("操作结果"))
        code = serializers.IntegerField(help_text=_("状态码"))
        message = serializers.CharField(help_text=_("返回消息"))
        task_id = serializers.CharField(help_text=_("任务ID"))

    def perform_request(self, validated_request_data):
        """
        更新采集配置
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        task_id = validated_request_data["task_id"]

        try:
            # 1. 验证任务是否存在
            task = self._get_task(bk_biz_id, task_id)

            # 2. 处理可能需要更新的凭证
            if "secret_id" in validated_request_data and "secret_key" in validated_request_data:
                self._validate_credentials(validated_request_data["secret_id"], validated_request_data["secret_key"])

            # 3. 更新主任务配置
            updated_fields = self._update_monitoring_task(task, validated_request_data)

            # 4. 如果有地域配置更新，处理地域配置
            if "regions" in validated_request_data and validated_request_data["regions"]:
                self._validate_regions(validated_request_data["regions"])
                self._update_region_configs(task_id, validated_request_data["regions"])
                updated_fields.append("regions")

                # 如果只更新了地域配置，也需要更新主任务以更新时间戳
                if len(updated_fields) == 1 and updated_fields[0] == "regions":  # 如果只更新了地域配置
                    task.save()

            # 5. 如果更新了配置，需要重新下发采集任务
            if updated_fields:
                self._deploy_monitoring_task(task_id)

                return {
                    "message": f"监控采集任务更新成功 (更新字段: {', '.join(updated_fields)})",
                    "task_id": task_id,
                }
            else:
                return {"message": "没有需要更新的字段", "task_id": task_id}

        except Exception as e:
            logger.error(f"更新云监控配置失败: {str(e)}")
            return {"message": f"更新配置失败: {str(e)}", "task_id": task_id}

    def _get_task(self, bk_biz_id, task_id):
        """
        获取任务对象

        Args:
            bk_biz_id: 业务ID
            task_id: 任务ID

        Returns:
            CloudMonitoringTask: 任务对象
        """
        from monitor_web.models.qcloud import CloudMonitoringTask

        try:
            task = CloudMonitoringTask.objects.get(bk_biz_id=bk_biz_id, task_id=task_id, is_deleted=False)
            return task
        except CloudMonitoringTask.DoesNotExist:
            raise ValueError(f"任务不存在: task_id={task_id}, bk_biz_id={bk_biz_id}")

    def _validate_credentials(self, secret_id, secret_key):
        """
        验证凭证信息

        Args:
            secret_id: 腾讯云SecretId
            secret_key: 腾讯云SecretKey
        """
        if not secret_id or not secret_key:
            raise ValueError("secret_id和secret_key不能为空")

    def _update_monitoring_task(self, task, validated_request_data):
        """
        更新主任务配置

        Args:
            task: 任务对象
            validated_request_data: 验证后的请求数据

        Returns:
            list: 已更新的字段列表
        """
        updated_fields = []

        # 更新采集名称
        if "collect_name" in validated_request_data and validated_request_data["collect_name"] != task.collect_name:
            task.collect_name = validated_request_data["collect_name"]
            updated_fields.append("collect_name")

        # 更新采集间隔
        if (
            "collect_interval" in validated_request_data
            and validated_request_data["collect_interval"] != task.collect_interval
        ):
            task.collect_interval = validated_request_data["collect_interval"]
            updated_fields.append("collect_interval")

        # 更新采集超时时间
        if (
            "collect_timeout" in validated_request_data
            and validated_request_data["collect_timeout"] != task.collect_timeout
        ):
            task.collect_timeout = validated_request_data["collect_timeout"]
            updated_fields.append("collect_timeout")

        # 更新凭证信息
        if "secret_id" in validated_request_data and "secret_key" in validated_request_data:
            # 对于加密字段，我们不能直接比较，只能直接更新
            task.secret_id = validated_request_data["secret_id"]
            task.secret_key = validated_request_data["secret_key"]
            updated_fields.append("credentials")

        # 更新环境配置
        if "is_internal" in validated_request_data and validated_request_data["is_internal"] != task.is_internal:
            task.is_internal = validated_request_data["is_internal"]
            updated_fields.append("is_internal")

        if (
            "is_international" in validated_request_data
            and validated_request_data["is_international"] != task.is_international
        ):
            task.is_international = validated_request_data["is_international"]
            updated_fields.append("is_international")

        # 如果有更新字段，保存任务
        if updated_fields:
            task.save()
            logger.info(f"更新云监控任务成功: task_id={task.task_id}, 更新字段: {updated_fields}")

        return updated_fields

    def _update_region_configs(self, task_id, regions):
        """
        更新地域配置

        Args:
            task_id: 任务ID
            regions: 地域配置列表
        """
        from monitor_web.models.qcloud import CloudMonitoringTaskRegion

        # 先获取所有现有地域配置
        existing_regions = {
            region.region_id: region
            for region in CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False)
        }

        # 记录处理过的地域ID
        processed_region_ids = set()

        for region_config in regions:
            region_id = region_config["id"]
            processed_region_ids.add(region_id)

            # 构建标签配置
            tags_config = []
            instance_selection = region_config.get("instance_selection", {})
            for tag in instance_selection.get("tags", []):
                tags_config.append(
                    {
                        "name": tag["name"],
                        "value": tag["value"],
                        "fuzzy": tag.get("fuzzy", False),  # 默认精确匹配
                    }
                )

            # 构建过滤器配置
            filters_config = []
            for filter_item in instance_selection.get("filters", []):
                filters_config.append({"name": filter_item["name"], "value": filter_item["value"]})

            # 构建维度配置
            dimensions_config = []
            for dimension in region_config.get("dimensions", []):
                dimensions_config.append({"name": dimension["name"], "value": dimension["value"]})

            # 检查是否存在该地域配置
            if region_id in existing_regions:
                # 更新现有地域配置
                region_obj = existing_regions[region_id]
                region_obj.region_code = region_config["region"]
                region_obj.tags_config = tags_config
                region_obj.filters_config = filters_config
                region_obj.selected_metrics = region_config.get("selected_metrics", [])
                region_obj.dimensions_config = dimensions_config
                region_obj.save()
                logger.info(f"更新地域配置成功: task_id={task_id}, region_id={region_id}")
            else:
                # 创建新的地域配置
                CloudMonitoringTaskRegion.objects.create(
                    task_id=task_id,
                    region_id=region_id,
                    region_code=region_config["region"],
                    tags_config=tags_config,
                    filters_config=filters_config,
                    selected_metrics=region_config.get("selected_metrics", []),
                    dimensions_config=dimensions_config,
                    status=CloudMonitoringTaskRegion.STATUS_CONNECTING,
                )
                logger.info(f"创建新地域配置成功: task_id={task_id}, region_id={region_id}")

        # 检查是否有需要删除的地域配置
        for region_id, region_obj in existing_regions.items():
            if region_id not in processed_region_ids:
                # 标记为删除
                region_obj.delete()
                logger.info(f"删除地域配置成功: task_id={task_id}, region_id={region_id}")

    def _deploy_monitoring_task(self, task_id):
        """
        部署腾讯云监控采集任务

        Args:
            task_id: 任务ID
        """
        try:
            from monitor_web.collecting.deploy.qcloud import QCloudMonitoringTaskDeployer

            deployer = QCloudMonitoringTaskDeployer(task_id)
            deployer.deploy()

            logger.info(f"腾讯云监控任务重新部署启动成功: task_id={task_id}")
        except Exception as e:
            logger.error(f"腾讯云监控任务重新部署失败: task_id={task_id}, error={str(e)}")
            # 更新任务状态为失败
            from monitor_web.models.qcloud import CloudMonitoringTask

            try:
                task = CloudMonitoringTask.objects.get(task_id=task_id)
                task.status = CloudMonitoringTask.STATUS_FAILED
                task.save()
            except CloudMonitoringTask.DoesNotExist:
                logger.error(f"未找到任务: task_id={task_id}")
            raise


class CloudMonitoringTaskLogResource(Resource):
    """
    获取腾讯云监控任务采集日志接口
    """

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))
        region = serializers.CharField(required=True, help_text=_("地域代码, e.g., ap-guangzhou"))
        id = serializers.CharField(required=True, help_text=_("地域配置的唯一ID"))

    class ResponseSerializer(serializers.Serializer):
        log_content = serializers.CharField(help_text=_("日志内容"))

    def _get_k8s_config(self, cluster_id: str) -> k8s_client.Configuration:
        # 构建并返回用于访问 K8S API 的配置
        if not all(
            [
                settings.BCS_API_GATEWAY_SCHEMA,
                settings.BCS_API_GATEWAY_HOST,
                settings.BCS_API_GATEWAY_PORT,
                settings.BCS_API_GATEWAY_TOKEN,
            ]
        ):
            # 如果网关配置不全，抛出中文错误提示
            raise ValueError("BCS API 网关配置不完整，请联系管理员")

        host = urljoin(
            f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
            f"/clusters/{cluster_id}",
        )
        config = k8s_client.Configuration(
            host=host,
            api_key={"authorization": settings.BCS_API_GATEWAY_TOKEN},
            api_key_prefix={"authorization": "Bearer"},
        )
        return config

    def _get_default_cluster(self) -> tuple[str, str]:
        # 获取默认的集群ID和命名空间 (从配置项读取，格式为 cluster_id:namespace)
        if not settings.K8S_PLUGIN_COLLECT_CLUSTER_ID:
            raise ValueError("需要配置 K8S_PLUGIN_COLLECT_CLUSTER_ID，请联系管理员")

        try:
            cluster_id, namespace = settings.K8S_PLUGIN_COLLECT_CLUSTER_ID.split(":")
            return cluster_id, namespace
        except ValueError:
            raise ValueError(
                f"K8S_PLUGIN_COLLECT_CLUSTER_ID 格式不正确: {settings.K8S_PLUGIN_COLLECT_CLUSTER_ID}，期望格式为 'cluster_id:namespace'"
            )

    def perform_request(self, validated_request_data):
        """
        获取腾讯云监控任务采集日志
        """
        task_id = validated_request_data["task_id"]
        region_code = validated_request_data["region"]

        # 构建部署资源名称，遵循之前的命名约定
        resource_name = f"qcloud-{task_id}-{region_code}".lower().replace("_", "-")

        try:
            # 获取默认集群和命名空间
            cluster_id, namespace = self._get_default_cluster()

            # 使用 K8S API 客户端读取 Deployment -> Pod -> 日志
            with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
                core_v1 = k8s_client.CoreV1Api(api_client)
                apps_v1 = k8s_client.AppsV1Api(api_client)

                try:
                    # 读取 Deployment，获取 label selector 用于查找 Pod
                    deployment = apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
                    selector = deployment.spec.selector.match_labels
                    label_selector_str = ",".join([f"{k}={v}" for k, v in selector.items()])
                except k8s_client.exceptions.ApiException as e:
                    # Deployment 未找到或其他错误，均返回中文友好提示
                    if e.status == 404:
                        logger.warning(
                            f"在命名空间 '{namespace}' 中未找到 Deployment '{resource_name}'，无法获取日志。"
                        )
                        return {"log_content": _("采集任务的部署资源未找到，可能尚未创建或已被删除。")}
                    logger.error(f"读取 Deployment '{resource_name}' 时发生错误: {e}")
                    raise RuntimeError(f"获取采集部署信息失败: {e.reason}")

                # 列出符合 selector 的 Pod
                pod_list = core_v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector_str)

                if not pod_list.items:
                    # 没有找到 Pod 实例
                    return {"log_content": _("未找到采集任务运行的Pod实例。")}

                log_content = ""
                # 尝试找到正在运行的 Pod 并读取日志
                for pod in pod_list.items:
                    if pod.status.phase == "Running":
                        pod_name = pod.metadata.name
                        try:
                            # 读取最近的 500 行日志
                            log_content = core_v1.read_namespaced_pod_log(
                                name=pod_name, namespace=namespace, tail_lines=500
                            )
                            break
                        except k8s_client.exceptions.ApiException as e:
                            # 无法读取某个 Pod 的日志，记录警告并继续尝试其他 Pod
                            logger.warning(f"无法读取 Pod {pod_name} 的日志: {e}")
                            log_content = _("无法读取Pod ({pod_name}) 的日志: {error}").format(
                                pod_name=pod_name, error=e.reason
                            )

                if not log_content:
                    log_content = _("未找到正在运行的Pod实例来获取日志。")

                return {"log_content": log_content}

        except k8s_client.exceptions.ApiException as e:
            logger.error(f"从 Kubernetes 获取任务 {task_id}（地域 {region_code}）的日志失败: {e}")
            return {"log_content": _("从Kubernetes获取日志失败: {error}").format(error=e.body)}
        except Exception as e:
            logger.error(f"获取任务 {task_id}（地域 {region_code}）日志时发生错误: {e}")
            raise RuntimeError(_("获取日志失败: {error}").format(error=str(e)))
