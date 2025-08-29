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
    "CloudMonitoringConfigResource",
    "CloudMonitoringTaskListResource",
    "CloudMonitoringTaskStatusResource",
    "CloudMonitoringTaskDetailResource",
    "CloudMonitoringStopTaskResource",
    "CloudMonitoringDeleteTaskResource",
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


class CloudMonitoringConfigResource(Resource):
    """
    保存及更新云监控采集任务配置并部署
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        task_id = serializers.CharField(required=False, allow_blank=True, help_text=_("任务ID，更新时需要提供"))

        # 基本信息
        namespace = serializers.CharField(required=False, help_text=_("产品命名空间"))
        collect_name = serializers.CharField(required=False, help_text=_("采集任务名称"))
        collect_interval = serializers.CharField(required=False, help_text=_("采集间隔，如：1m"))
        collect_timeout = serializers.CharField(required=False, help_text=_("采集超时时间，如：30s"))

        # 凭证信息
        secret_id = serializers.CharField(required=False, help_text=_("腾讯云SecretId"))
        secret_key = serializers.CharField(required=False, help_text=_("腾讯云SecretKey"))

        # 地域配置
        regions = serializers.ListField(child=serializers.DictField(), required=False, help_text=_("地域配置列表"))

        # 环境配置
        is_internal = serializers.BooleanField(required=False, help_text=_("是否内部环境"))
        is_international = serializers.BooleanField(required=False, help_text=_("是否国际版"))

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(help_text=_("任务ID"))
        message = serializers.CharField(help_text=_("返回消息"))

    def perform_request(self, validated_request_data):
        task_id = validated_request_data.get("task_id")

        if task_id:
            # 更新逻辑
            return self._update_task(task_id, validated_request_data)
        else:
            # 创建逻辑
            return self._create_task(validated_request_data)

    def _create_task(self, data):
        """
        创建新的采集任务
        """
        # 校验创建任务所需参数
        required_fields = [
            "bk_biz_id",
            "namespace",
            "collect_name",
            "collect_interval",
            "collect_timeout",
            "secret_id",
            "secret_key",
            "regions",
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"创建任务时缺少必要参数: {field}")

        try:
            # 1. 验证凭证信息
            self._validate_credentials(data["secret_id"], data["secret_key"])
            # 2. 验证产品命名空间
            self._validate_namespace(data["namespace"])
            # 3. 验证地域配置
            self._validate_regions(data["regions"])
            # 4. 生成任务ID
            task_id = self._generate_task_id(data["bk_biz_id"], data["namespace"])
            # 5. 保存主任务配置
            self._save_monitoring_task(task_id, data)
            # 6. 保存地域配置
            self._save_region_configs(task_id, data["regions"])
            # 7. 下发采集任务
            self._deploy_monitoring_task(task_id)

            return {"message": "监控采集任务创建成功", "task_id": task_id}

        except Exception as e:
            logger.error(f"创建云监控配置失败: {str(e)}")
            raise

    def _update_task(self, task_id, data):
        """
        更新现有的采集任务
        """
        try:
            # 1. 验证任务是否存在
            task = self._get_task(data["bk_biz_id"], task_id)

            # 2. 处理可能需要更新的凭证
            if "secret_id" in data and "secret_key" in data:
                self._validate_credentials(data["secret_id"], data["secret_key"])

            # 3. 更新主任务配置
            updated_fields = self._update_monitoring_task(task, data)

            # 4. 如果有地域配置更新，处理地域配置
            if "regions" in data and data["regions"]:
                self._validate_regions(data["regions"])
                self._update_region_configs(task_id, data["regions"])
                updated_fields.append("regions")

                # 如果只更新了地域配置，也需要更新主任务以更新时间戳
                if len(updated_fields) == 1:
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
            raise

    def _validate_credentials(self, secret_id, secret_key):
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

    def _save_monitoring_task(self, task_id, data):
        from monitor_web.models.qcloud import CloudMonitoringTask

        # 检查任务ID是否已存在
        if CloudMonitoringTask.objects.filter(task_id=task_id).exists():
            raise ValueError(f"任务ID {task_id} 已存在")

        # 创建任务
        task = CloudMonitoringTask.objects.create(
            task_id=task_id,
            bk_biz_id=data["bk_biz_id"],
            namespace=data["namespace"],
            collect_name=data["collect_name"],
            collect_interval=data["collect_interval"],
            collect_timeout=data["collect_timeout"],
            secret_id=data["secret_id"],
            secret_key=data["secret_key"],
            is_internal=data.get("is_internal", False),
            is_international=data.get("is_international", True),
            status=CloudMonitoringTask.STATUS_CONNECTING,
        )
        logger.info(f"创建云监控任务成功: task_id={task_id}, namespace={data['namespace']}")
        return task

    def _save_region_configs(self, task_id, regions):
        from monitor_web.models.qcloud import CloudMonitoringTaskRegion

        for region_config in regions:
            tags_config = region_config.get("instance_selection", {}).get("tags", [])
            filters_config = region_config.get("instance_selection", {}).get("filters", [])
            dimensions_config = region_config.get("dimensions", [])

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

    def _get_task(self, bk_biz_id, task_id):
        from monitor_web.models.qcloud import CloudMonitoringTask

        try:
            return CloudMonitoringTask.objects.get(bk_biz_id=bk_biz_id, task_id=task_id, is_deleted=False)
        except CloudMonitoringTask.DoesNotExist:
            raise ValueError(f"任务不存在: task_id={task_id}, bk_biz_id={bk_biz_id}")

    def _update_monitoring_task(self, task, data):
        updated_fields = []
        update_mapping = {
            "collect_name": "collect_name",
            "collect_interval": "collect_interval",
            "collect_timeout": "collect_timeout",
            "is_internal": "is_internal",
            "is_international": "is_international",
        }
        for field, attr in update_mapping.items():
            if field in data and data[field] != getattr(task, attr):
                setattr(task, attr, data[field])
                updated_fields.append(field)

        if "secret_id" in data and "secret_key" in data:
            task.secret_id = data["secret_id"]
            task.secret_key = data["secret_key"]
            updated_fields.append("credentials")

        if updated_fields:
            task.save()
            logger.info(f"更新云监控任务成功: task_id={task.task_id}, 更新字段: {updated_fields}")
        return updated_fields

    def _update_region_configs(self, task_id, regions):
        from monitor_web.models.qcloud import CloudMonitoringTaskRegion

        existing_regions = {
            region.region_id: region
            for region in CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False)
        }
        processed_region_ids = set()

        for region_config in regions:
            region_id = region_config["id"]
            processed_region_ids.add(region_id)

            tags_config = region_config.get("instance_selection", {}).get("tags", [])
            filters_config = region_config.get("instance_selection", {}).get("filters", [])
            dimensions_config = region_config.get("dimensions", [])

            if region_id in existing_regions:
                region_obj = existing_regions[region_id]
                region_obj.region_code = region_config["region"]
                region_obj.tags_config = tags_config
                region_obj.filters_config = filters_config
                region_obj.selected_metrics = region_config.get("selected_metrics", [])
                region_obj.dimensions_config = dimensions_config
                region_obj.save()
            else:
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

        for region_id, region_obj in existing_regions.items():
            if region_id not in processed_region_ids:
                region_obj.delete()

    def _deploy_monitoring_task(self, task_id):
        try:
            from monitor_web.collecting.deploy.qcloud import QCloudMonitoringTaskDeployer

            deployer = QCloudMonitoringTaskDeployer(task_id)
            deployer.deploy()
            logger.info(f"腾讯云监控任务部署/更新成功: task_id={task_id}")
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


class K8sOperationsMixin:
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


class CloudMonitoringTaskStatusResource(K8sOperationsMixin, Resource):
    """
    查询云监控任务状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        task_id = serializers.CharField(required=True, label="任务ID")

    def perform_request(self, validated_data):
        from monitor_web.models.qcloud import CloudMonitoringTask, CloudMonitoringTaskRegion

        task_id = validated_data["task_id"]
        bk_biz_id = validated_data["bk_biz_id"]

        # 1. 检查任务是否在数据库中标记为“已停用”
        try:
            task = CloudMonitoringTask.objects.get(task_id=task_id, bk_biz_id=bk_biz_id)
            if task.status == CloudMonitoringTask.STATUS_STOPPED:
                regions = CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False)
                return [
                    {
                        "region": region.region_code,
                        "id": region.region_id,
                        "status": "SUCCESS",
                        "log": _("任务已停用"),
                    }
                    for region in regions
                ]
        except CloudMonitoringTask.DoesNotExist:
            raise ValueError(f"任务不存在: {task_id}")

        # 2. 准备 K8s 客户端
        cluster_id, namespace = self._get_default_cluster()
        results = []
        region_configs = CloudMonitoringTaskRegion.objects.filter(task_id=task_id, is_deleted=False)

        if not region_configs:
            return []

        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            apps_v1 = k8s_client.AppsV1Api(api_client)

            # 3. 遍历每个地域并检查其 Deployment 状态
            for region in region_configs:
                resource_name = f"qcloud-{task_id}-{region.region_code}".lower().replace("_", "-")
                status = "UNKNOWN"
                log = ""

                try:
                    # 4. 查询 Deployment
                    deployment = apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)

                    # 5. 检查 Deployment 状态
                    dep_status = deployment.status
                    spec_replicas = deployment.spec.replicas
                    ready_replicas = dep_status.ready_replicas or 0

                    if spec_replicas is None or spec_replicas == 0:
                        status = "SUCCESS"
                        log = _("采集任务的副本数设置为0，视作已停止")
                    elif ready_replicas >= spec_replicas:
                        status = "SUCCESS"
                        log = _("采集任务运行正常 ({ready_replicas}/{spec_replicas})").format(
                            ready_replicas=ready_replicas, spec_replicas=spec_replicas
                        )
                    else:
                        # 检查是否有部署失败的迹象
                        if dep_status.conditions:
                            for condition in dep_status.conditions:
                                if condition.type == "Progressing" and condition.status == "False":
                                    status = "FAILED"
                                    log = condition.message or _("部署失败，请检查配置或查看日志")
                                    break
                        if status != "FAILED":
                            status = "RUNNING"
                            log = _("采集任务部署中 ({ready_replicas}/{spec_replicas} 就绪)").format(
                                ready_replicas=ready_replicas, spec_replicas=spec_replicas
                            )

                except k8s_client.exceptions.ApiException as e:
                    if e.status == 404:
                        status = "FAILED"
                        log = _("采集任务的部署资源 ({resource_name}) 未找到").format(resource_name=resource_name)
                    else:
                        status = "FAILED"
                        log = _("查询部署状态失败: {reason}").format(reason=e.reason)

                except Exception as e:
                    status = "FAILED"
                    log = _("发生未知错误: {error}").format(error=str(e))

                results.append({"region": region.region_code, "id": region.region_id, "status": status, "log": log})

        return results


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


class CloudMonitoringStopTaskResource(Resource):
    """
    停用云监控采集任务接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(help_text=_("任务ID"))
        message = serializers.CharField(help_text=_("返回消息"))

    def perform_request(self, validated_request_data):
        """
        停用云监控采集任务
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        task_id = validated_request_data["task_id"]

        try:
            from monitor_web.models.qcloud import CloudMonitoringTask
            from monitor_web.collecting.deploy.qcloud import QCloudMonitoringTaskDeployer

            # 1. 验证任务是否存在
            try:
                task = CloudMonitoringTask.objects.get(bk_biz_id=bk_biz_id, task_id=task_id, is_deleted=False)
            except CloudMonitoringTask.DoesNotExist:
                raise ValueError(f"任务不存在: task_id={task_id}, bk_biz_id={bk_biz_id}")

            # 2. 调用Deployer进行卸载
            deployer = QCloudMonitoringTaskDeployer(task_id)
            deployer.undeploy()

            # 3. 更新任务状态为已停用
            task.status = CloudMonitoringTask.STATUS_STOPPED
            task.save()

            logger.info(f"云监控任务已停用: task_id={task_id}")
            return {"task_id": task_id, "message": "任务已成功停用"}

        except Exception as e:
            logger.error(f"停用云监控任务失败: {str(e)}")
            raise RuntimeError(f"停用任务失败: {str(e)}")


class CloudMonitoringDeleteTaskResource(Resource):
    """
    删除云监控采集任务接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, help_text=_("业务ID"))
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))

    class ResponseSerializer(serializers.Serializer):
        task_id = serializers.CharField(help_text=_("任务ID"))
        message = serializers.CharField(help_text=_("返回消息"))

    def perform_request(self, validated_request_data):
        """
        删除云监控采集任务
        """
        bk_biz_id = validated_request_data["bk_biz_id"]
        task_id = validated_request_data["task_id"]

        try:
            from monitor_web.models.qcloud import CloudMonitoringTask, CloudMonitoringTaskRegion

            # 1. 验证任务是否存在
            try:
                task = CloudMonitoringTask.objects.get(bk_biz_id=bk_biz_id, task_id=task_id, is_deleted=False)
            except CloudMonitoringTask.DoesNotExist:
                # 如果任务已经不存在，也认为是成功的
                logger.info(f"尝试删除的任务已不存在: task_id={task_id}")
                return {"task_id": task_id, "message": "任务已删除"}

            # 2. 检查任务是否已停用
            if task.status != CloudMonitoringTask.STATUS_STOPPED:
                raise ValueError("任务必须先停用才能删除")

            # 3. 软删除主任务和相关的地域配置
            task.is_deleted = True
            task.save()

            CloudMonitoringTaskRegion.objects.filter(task_id=task_id).update(is_deleted=True)

            logger.info(f"云监控任务已删除: task_id={task_id}")
            return {"task_id": task_id, "message": "任务已成功删除"}

        except Exception as e:
            logger.error(f"删除云监控任务失败: {str(e)}")
            raise RuntimeError(f"删除任务失败: {str(e)}")


class CloudMonitoringTaskLogResource(K8sOperationsMixin, Resource):
    """
    获取腾讯云监控任务采集日志接口
    """

    class RequestSerializer(serializers.Serializer):
        task_id = serializers.CharField(required=True, help_text=_("任务ID"))
        region = serializers.CharField(required=True, help_text=_("地域代码, e.g., ap-guangzhou"))
        id = serializers.CharField(required=True, help_text=_("地域配置的唯一ID"))

    class ResponseSerializer(serializers.Serializer):
        log_content = serializers.CharField(help_text=_("日志内容"))

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
