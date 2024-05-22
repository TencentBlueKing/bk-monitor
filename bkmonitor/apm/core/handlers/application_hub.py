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
import json
import logging

from django.conf import settings
from django.utils.translation import ugettext as _
from opentelemetry import trace

from apm.core.handlers.application_hepler import ApplicationHelper
from apm.models import ApmApplication, ApplicationHub
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("apm")

tracer = trace.get_tracer(__name__)


class DataHubHandler:
    @classmethod
    def create_data_hub(cls, bk_biz_id, bcs_cluster_id, apm_application=None, custom_report=None, storage=None):
        """
        一键创建应用
        包含:
        1. APM 应用
        2. 日志平台自定义上报
        """

        with tracer.start_as_current_span("create_data_hub") as span:
            logger.info(f"[DataHub] ({bk_biz_id}){bcs_cluster_id} start create app-hub")

            # Step1: 创建 application_hub
            hub, is_created = ApplicationHub.objects.get_or_create(
                defaults={"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id},
                bk_biz_id=bk_biz_id,
                bcs_cluster_id=bcs_cluster_id,
            )

            # 检查是否已经完成创建
            if hub.is_finished:
                logger.info(f"[DataHub] ({bk_biz_id}){bcs_cluster_id} was created")
                res = ApplicationHub.to_json(bk_biz_id, bcs_cluster_id)
                span.add_event("retrieve_exist", attributes={"data": res})
                return res

            if is_created:
                logger.info(f"[DataHub] ({bk_biz_id}){bcs_cluster_id} create new app-hub, id: {hub.id}")
                span.add_event("handle_hub_instance", attributes={"id": hub.id, "is_created": True})
            else:
                logger.info(f"[DataHub] ({bk_biz_id}){bcs_cluster_id} retrieve exist app-hub, id: {hub.id}")
                span.add_event("handle_hub_instance", attributes={"id": hub.id, "is_created": False})

            # Step2: 获取指定/默认 ES 存储集群
            storage_config = cls.get_es_storage(bk_biz_id, storage)
            # Step3: 创建 APM 应用
            cls.create_apm_application(hub.id, bk_biz_id, bcs_cluster_id, storage_config, apm_application)
            # Step4: 创建自定义上报
            cls.create_log_custom_report(hub.id, bk_biz_id, bcs_cluster_id, storage_config, custom_report)

            ApplicationHub.objects.filter(id=hub.id).update(is_finished=True)
            res = ApplicationHub.to_json(bk_biz_id, bcs_cluster_id)
            span.add_event("create_finished", attributes={"data": res})
            return res

    @classmethod
    def create_apm_application(cls, hub_id, bk_biz_id, bcs_cluster_id, storage_config, data):
        """创建 APM 应用"""
        with tracer.start_as_current_span("create_apm_application") as span:
            # Step1: 检查默认应用是否已经存在
            cluster_default_app = ApplicationHub.get_hub(bk_biz_id, bcs_cluster_id)
            if cluster_default_app and cluster_default_app.app_id:
                logger.info(
                    f"[DataHub] retrieve exist application: "
                    f"({cluster_default_app.app_id}){cluster_default_app.app_name}"
                )
                # 如果应用已存在 则不再进行创建
                span.add_event("retrieve_application", attributes={"id": cluster_default_app.app_id})
                return

            # Step2: 补充基本信息
            app_name = data["app_name"].lower() if data.get("app_name") else cls._cluster_apm_name(bcs_cluster_id)
            app_alias = data["app_alias"].lower() if data.get("app_alias") else cls._cluster_apm_alias(bcs_cluster_id)
            description = data["description"].lower() if data.get("description") else _("系统创建")

            params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "app_alias": app_alias,
                "description": description,
                "datasource_option": storage_config,
                "plugin_id": data["plugin_id"] if data.get("plugin_id") else "opentelemetry",
                "deployment_ids": data["deployment_ids"] if data.get("deployment_ids") else ["centos"],
                "language_ids": data["language_ids"] if data.get("language_ids") else ["python"],
                "enable_profiling": data["enable_profiling"] if data.get("enable_profiling") else True,
                "enable_tracing": data["enable_tracing"] if data.get("enable_tracing") else True,
            }
            # Step4: 获取 Log-Trace 配置
            plugin_config = data["plugin_config"] if data.get("plugin_config") else {}
            if plugin_config:
                params.update({"plugin_config": plugin_config})

            span.add_event("create-start", attributes={"params": params})
            from apm_web.meta.resources import CreateApplicationResource

            response = CreateApplicationResource()(**params)
            span.add_event("create-end", attributes={"response": response})

            # Final: 更新数据
            app = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not app:
                raise ValueError(f"[DataHub] 创建失败，查询应用({bk_biz_id}-{app_name})为空，接口返回：{response}")
            ApplicationHub.objects.filter(id=hub_id).update(
                app_name=app_name,
                app_id=app.id,
                metric_data_id=app.metric_datasource.bk_data_id if app.metric_datasource else None,
                trace_data_id=app.trace_datasource.bk_data_id if app.trace_datasource else None,
                profile_data_id=app.profile_datasource.bk_data_id if app.profile_datasource else None,
            )
            logger.info(f"[DataHub] create application successfully! id: {app.id}")

    @classmethod
    def get_es_storage(cls, bk_biz_id, data):
        """获取配置的集群 如果没有配置则从默认集群中选择"""
        storage_cluster_id = cls._default_es_storage_id(bk_biz_id)
        if not storage_cluster_id:
            raise ValueError(f"[DataHub] 获取应用存储集群失败，未配置默认集群或者当前{bk_biz_id}业务下无默认存储集群")

        es_retention = data["es_retention"] if data.get("es_retention") else settings.APM_APP_DEFAULT_ES_RETENTION
        es_number_of_replicas = (
            data["es_number_of_replicas"] if data.get("es_number_of_replicas") else settings.APM_APP_DEFAULT_ES_REPLICAS
        )
        es_shards = data["es_shards"] if data.get("es_shards") else settings.APM_APP_DEFAULT_ES_SHARDS
        es_slice_size = data["es_slice_size"] if data.get("es_slice_size") else settings.APM_APP_DEFAULT_ES_SLICE_LIMIT

        logger.info(
            f"[DataHub] retrieve es storage, "
            f"id: {storage_cluster_id} retention: {es_retention} slice_size: {es_slice_size} shards: {es_shards}"
        )
        return {
            "es_storage_cluster": storage_cluster_id,
            "es_retention": es_retention,
            "es_number_of_replicas": es_number_of_replicas,
            "es_shards": es_shards,
            "es_slice_size": es_slice_size,
        }

    @classmethod
    def create_log_custom_report(cls, hub_id, bk_biz_id, bcs_cluster_id, storage_config, data):
        """创建 OT 自定义上报"""
        with tracer.start_as_current_span("create_log_custom_report") as span:
            # 检查是否已经创建自定义上报
            cluster_default_app = ApplicationHub.get_hub(bk_biz_id, bcs_cluster_id)
            if cluster_default_app and cluster_default_app.log_data_id:
                logger.info(
                    f"[DataHub] retrieve exist custom_report: "
                    f"dataId: {cluster_default_app.log_data_id} configId: {cluster_default_app.custom_report_id}"
                )
                span.add_event("retrieve_custom_report", attributes={"id": cluster_default_app.log_data_id})
                return

            # 指定了存储集群会有默认的清洗规则所以这里不需要配置规则
            params = {
                "bk_biz_id": bk_biz_id,
                "collector_config_name_en": data["name"] if data.get("name") else cls._cluster_log_name(bcs_cluster_id),
                "collector_config_name": data["alias"] if data.get("alias") else cls._cluster_log_alias(bcs_cluster_id),
                "custom_type": "otlp_log",
                "category_id": "application_check",
                "storage_cluster_id": storage_config["es_storage_cluster"],
                "retention": storage_config["es_retention"],
                # 兼容集群不支持冷热配置
                "allocation_min_days": 0,
                "storage_replies": storage_config["es_number_of_replicas"],
                "es_shards": storage_config["es_shards"],
                "description": data["description"] if data.get("description") else _("系统创建"),
            }

            try:
                span.add_event("create-start", attributes={"params": params})
                response = api.log_search.create_custom_report(**params)
                span.add_event("create-end", attributes={"response": response})
            except BKAPIError as e:
                raise ValueError(f"创建日志自定义上报失败，参数： {json.dumps(params)}，错误：{e}")

            ApplicationHub.objects.filter(id=hub_id).update(
                custom_report_id=response["collector_config_id"],
                log_data_id=response["bk_data_id"],
                custom_report_index_set_id=response["index_set_id"],
            )

    @classmethod
    def _default_es_storage_id(cls, bk_biz_id):
        es_storage_cluster = settings.APM_APP_DEFAULT_ES_STORAGE_CLUSTER
        if not es_storage_cluster or es_storage_cluster == -1:
            # 没有配置则从集群列表中选择
            default_cluster_id = ApplicationHelper.get_default_cluster_id(bk_biz_id)
            if default_cluster_id:
                es_storage_cluster = default_cluster_id
            else:
                return None

        return es_storage_cluster

    @classmethod
    def _cluster_apm_name(cls, cluster_id):
        """获取集群默认应用名称"""
        return f"{cluster_id.replace('-', '_')}_default_apm".lower()

    @classmethod
    def _cluster_apm_alias(cls, cluster_id):
        """获取集群默认应用别名"""
        return _("集群") + cluster_id + _("默认应用")

    @classmethod
    def _cluster_log_name(cls, cluster_id):
        return f"{cluster_id.replace('-', '_')}_default_log".lower()

    @classmethod
    def _cluster_log_alias(cls, cluster_id):
        return _("集群") + cluster_id + _("默认日志自定义上报")
