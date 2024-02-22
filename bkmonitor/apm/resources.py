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
import datetime
import json
import logging
import traceback

import pytz
from django.conf import settings
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apm.constants import GLOBAL_CONFIG_BK_BIZ_ID, ConfigTypes, VisibleEnum
from apm.core.handlers.application_hepler import ApplicationHelper
from apm.core.handlers.bk_data.helper import FlowHelper
from apm.core.handlers.discover_handler import DiscoverHandler
from apm.core.handlers.instance_handlers import InstanceHandler
from apm.core.handlers.query.define import QueryMode, QueryStatisticsMode
from apm.core.handlers.query.proxy import QueryProxy
from apm.models import (
    ApdexConfig,
    ApmApplication,
    ApmInstanceDiscover,
    ApmMetricDimension,
    ApmTopoDiscoverRule,
    AppConfigBase,
    BkdataFlowConfig,
    CustomServiceConfig,
    Endpoint,
    HostInstance,
    LicenseConfig,
    MetricDataSource,
    NormalTypeValueConfig,
    ProbeConfig,
    ProfileDataSource,
    QpsConfig,
    RemoteServiceRelation,
    RootEndpoint,
    SamplerConfig,
    TopoInstance,
    TopoNode,
    TopoRelation,
    TraceDataSource,
)
from apm.models.profile import ProfileService
from apm.task.tasks import create_or_update_tail_sampling
from apm.models.profile import ProfileService
from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.models import LogServiceRelation
from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.utils.cipher import transform_data_id_to_v1_token
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import (
    DataSamplingLogTypeChoices,
    FlowType,
    TailSamplingSupportMethod,
    TraceListQueryMode,
    TraceWaterFallDisplayKey,
)
from core.drf_resource import Resource, api
from metadata import models
from metadata.models import DataSource

logger = logging.getLogger("apm")


class DatasourceConfigRequestSerializer(serializers.Serializer):
    """应用数据库配置"""

    es_storage_cluster = serializers.IntegerField(label="es存储集群")
    es_retention = serializers.IntegerField(required=False, label="es存储周期", min_value=1)
    es_number_of_replicas = serializers.IntegerField(required=False, label="es副本数量", min_value=0)
    es_shards = serializers.IntegerField(required=False, label="索引分片数量", min_value=1)
    es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500)


class PageListResource(Resource):
    def handle_pagination(self, params, data):
        page = params.get("page", 1)
        page_size = params.get("page_size", 10)
        offset = (page - 1) * page_size
        return data[offset : offset + page_size]


class CreateApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        app_alias = serializers.CharField(label="应用别名", max_length=255)
        # enable profiling as default for debugging
        enabled_profiling = serializers.BooleanField(label="是否开启性能分析", default=False)
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        es_storage_config = DatasourceConfigRequestSerializer(label="数据库配置")

    def perform_request(self, validated_request_data):
        application = ApmApplication.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).first()
        if application:
            raise ValueError(_("应用名称: {}已被创建").format(validated_request_data['app_name']))
        return ApmApplication.create_application(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=validated_request_data["app_alias"],
            description=validated_request_data["description"],
            es_storage_config=validated_request_data["es_storage_config"],
            options={"enabled_profiling": validated_request_data["enabled_profiling"]},
        )


class CreateApplicationSimpleResource(Resource):
    from apm_web.meta.plugin.plugin import DeploymentEnum, LanguageEnum, Opentelemetry

    DEFAULT_PLUGIN_ID = Opentelemetry.id
    DEFAULT_DEPLOYMENT_IDS = [DeploymentEnum.CENTOS.id]
    DEFAULT_LANGUAGE_IDS = [LanguageEnum.PYTHON.id]
    DEFAULT_ES_STORAGE_CLUSTER = settings.APM_APP_DEFAULT_ES_STORAGE_CLUSTER
    DEFAULT_ES_RETENTION = settings.APM_APP_DEFAULT_ES_RETENTION
    DEFAULT_ES_NUMBER_OF_REPLICAS = settings.APM_APP_DEFAULT_ES_REPLICAS
    DEFAULT_ES_SHARDS = settings.APM_APP_DEFAULT_ES_SHARDS
    DEFAULT_ES_SLICE_SIZE = settings.APM_APP_DEFAULT_ES_SLICE_LIMIT

    DEFAULT_CLUSTER = "_default"
    CLUSTER_TYPE = "elasticsearch"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id", required=False)
        app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"^[a-z0-9_-]+$")
        app_alias = serializers.CharField(label="应用别名", max_length=255, required=False)
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        plugin_id = serializers.CharField(label="插件ID", max_length=255, required=False)
        deployment_ids = serializers.ListField(label="环境", child=serializers.CharField(max_length=255), required=False)
        language_ids = serializers.ListField(label="语言", child=serializers.CharField(max_length=255), required=False)
        space_uid = serializers.CharField(label="空间唯一标识", required=False, default="")

    def fill_default(self, validate_data):
        if not validate_data.get("bk_biz_id"):
            validate_data["bk_biz_id"] = api.cmdb.get_blueking_biz()

        if not validate_data.get("app_alias"):
            validate_data["app_alias"] = validate_data["app_name"]

        if not validate_data.get("plugin_id"):
            validate_data["plugin_id"] = self.DEFAULT_PLUGIN_ID

        if not validate_data.get("deployment_ids"):
            validate_data["deployment_ids"] = self.DEFAULT_DEPLOYMENT_IDS

        if not validate_data.get("language_ids"):
            validate_data["language_ids"] = self.DEFAULT_LANGUAGE_IDS

        es_storage_cluster = self.DEFAULT_ES_STORAGE_CLUSTER
        if not es_storage_cluster or es_storage_cluster == -1:
            # 默认集群从集群列表中选择
            default_cluster_id = ApplicationHelper.get_default_cluster_id(validate_data["bk_biz_id"])
            if default_cluster_id:
                es_storage_cluster = default_cluster_id

        # 填充默认存储集群
        validate_data["datasource_option"] = {
            "es_storage_cluster": es_storage_cluster,
            "es_retention": self.DEFAULT_ES_RETENTION,
            "es_number_of_replicas": self.DEFAULT_ES_NUMBER_OF_REPLICAS,
            "es_shards": self.DEFAULT_ES_SHARDS,
            "es_slice_size": self.DEFAULT_ES_SLICE_SIZE,
        }

    def perform_request(self, validated_request_data):
        """api侧创建应用 需要保持和saas侧创建应用接口逻辑一致"""

        if validated_request_data.get("space_uid"):
            validated_request_data["bk_biz_id"] = space_uid_to_bk_biz_id(validated_request_data["space_uid"])

        from apm_web.meta.resources import CreateApplicationResource

        self.fill_default(validated_request_data)
        app = CreateApplicationResource()(**validated_request_data)
        return ApplicationInfoResource()(application_id=app["application_id"])["bk_data_token"]


class ApplyDatasourceResource(Resource):
    class RequestSerializer(DatasourceConfigRequestSerializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        try:
            application = ApmApplication.objects.get(id=validated_request_data["application_id"])
        except ApmApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

        storage_config = {
            "es_storage_cluster": validated_request_data["es_storage_cluster"],
            "es_retention": validated_request_data.get("es_retention", 15),
            "es_number_of_replicas": validated_request_data.get("es_number_of_replicas", 1),
            "es_shards": validated_request_data.get("es_shards", 3),
            "es_slice_size": validated_request_data.get("es_slice_size", 500),
        }

        return ApmApplication.apply_datasource(
            bk_biz_id=application.bk_biz_id, app_name=application.app_name, es_storage_config=storage_config
        )


class StartApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        try:
            application = ApmApplication.objects.get(id=validated_request_data["application_id"])
        except ApmApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return application.start()


class StopApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        try:
            application = ApmApplication.objects.get(id=validated_request_data["application_id"])
        except ApmApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return application.stop()


class ListApplicationResources(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = ApmApplication
            exclude = ("is_deleted", "is_enabled")

        def to_representation(self, instance):
            data = super(ListApplicationResources.ResponseSerializer, self).to_representation(instance)
            if instance.metric_datasource:
                data["metric_config"] = instance.metric_datasource.to_json()
            if instance.trace_datasource:
                data["trace_config"] = instance.trace_datasource.to_json()
            if instance.profile_datasource:
                data["profiling_config"] = instance.profile_datasource.to_json()
            return data

    many_response_data = True

    def perform_request(self, validated_request_data):
        return ApmApplication.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])


class ApplicationInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = ApmApplication
            exclude = ("is_deleted", "is_enabled")

        def to_representation(self, instance):
            data = super(ApplicationInfoResource.ResponseSerializer, self).to_representation(instance)
            data["bk_data_token"] = instance.get_bk_data_token()
            if instance.metric_datasource:
                data["metric_config"] = instance.metric_datasource.to_json()
            if instance.trace_datasource:
                data["trace_config"] = instance.trace_datasource.to_json()
            if instance.profile_datasource:
                data["profiling_config"] = instance.profile_datasource.to_json()
            return data

    def perform_request(self, validated_request_data):
        return ApmApplication.objects.get(id=validated_request_data["application_id"])


class ApdexSerializer(serializers.Serializer):
    apdex_t = serializers.IntegerField(label="apdex_t", min_value=0)
    span_kind = serializers.CharField(label="span_kind", allow_blank=True)
    predicate_key = serializers.CharField(label="predicate_key", allow_blank=True)


class SampleSerializer(serializers.Serializer):
    sampler_type = serializers.CharField(label="采集类型")
    sampling_percentage = serializers.IntegerField(
        label="采集百分比", required=False, default=100, min_value=0, max_value=100
    )


class DimensionConfigSerializer(serializers.Serializer):
    span_kind = serializers.CharField(label="span_kind")
    predicate_key = serializers.CharField(label="predicate_key", allow_blank=True)
    dimensions = serializers.ListField(child=serializers.CharField())


class ReleaseAppConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ServiceConfigSerializer(serializers.Serializer):
            service_name = serializers.CharField(label="service_name")
            apdex_config = serializers.ListField(label="Apdex配置规则", child=ApdexSerializer(), required=False)

        class InstanceConfigSerializer(serializers.Serializer):
            id = serializers.IntegerField(label="instance_id")
            apdex_config = serializers.ListField(label="Apdex配置规则", child=ApdexSerializer(), required=False)
            sampler_config = SampleSerializer(label="采样配置", required=False)

        class CustomServiceSerializer(serializers.Serializer):
            rule = serializers.JSONField()
            name = serializers.CharField(allow_null=True)
            type = serializers.CharField()
            match_type = serializers.CharField()

        class LicenseConfigSerializer(serializers.Serializer):
            enabled = serializers.BooleanField(label="是否开启license检查", default=True)
            expire_time = serializers.IntegerField(label="license 过期时间")
            tolerable_expire = serializers.CharField(label="容忍过期时间")
            number_nodes = serializers.IntegerField(label="可接受探针实例数量")
            tolerable_num_ratio = serializers.FloatField(label="可接受探针实例数量倍率", default=1.0)

        class DbConfigSerializer(serializers.Serializer):
            cut = serializers.ListSerializer(label="剪辑配置", child=serializers.DictField(), default=[])
            drop = serializers.ListSerializer(label="丢弃配置", child=serializers.DictField(), default=[])

        class ProbeConfigSerializer(serializers.Serializer):
            sn = serializers.CharField(label="配置变更标识")
            rules = serializers.ListSerializer(label="配置项", child=serializers.DictField(), allow_empty=False)

        class DbSlowCommandConfigSerializer(serializers.Serializer):
            destination = serializers.CharField(label="目标字段")
            rules = serializers.ListSerializer(label="配置项", child=serializers.DictField(), default=[])

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

        apdex_config = serializers.ListField(label="应用Apdex配置规则", child=ApdexSerializer(), required=False)
        sampler_config = SampleSerializer(label="应用采样配置", required=False)
        instance_name_config = serializers.ListField(child=serializers.CharField(), label="实例名称")
        dimension_config = serializers.ListField(
            child=DimensionConfigSerializer(label="应用维度配置"), required=False, allow_empty=True, allow_null=True
        )
        custom_service_config = serializers.ListField(
            child=CustomServiceSerializer(), required=False, allow_empty=True, allow_null=True
        )

        instance_configs = serializers.ListField(
            label="实例配置", child=InstanceConfigSerializer(), required=False, allow_null=True, allow_empty=True
        )
        service_configs = serializers.ListField(
            label="服务配置", child=ServiceConfigSerializer(), required=False, allow_null=True, allow_empty=True
        )
        license_config = LicenseConfigSerializer(label="license 配置", required=False, default={})

        db_config = DbConfigSerializer(label="sql/nosql配置", default={})

        probe_config = ProbeConfigSerializer(label="探针配置", default={})

        db_slow_command_config = DbSlowCommandConfigSerializer(label="慢命令配置", default={})

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]

        ApmApplication.get_application(bk_biz_id, app_name)

        service_configs = validated_request_data.get("service_configs", [])
        instance_configs = validated_request_data.get("instance_configs", [])
        self.set_config(bk_biz_id, app_name, app_name, ApdexConfig.APP_LEVEL, validated_request_data)
        self.set_custom_service_config(bk_biz_id, app_name, validated_request_data["custom_service_config"])

        for service_config in service_configs:
            self.set_config(bk_biz_id, app_name, app_name, ApdexConfig.SERVICE_LEVEL, service_config)

        # 目前暂无实例配置
        for instance_config in instance_configs:
            self.set_config(bk_biz_id, app_name, instance_config["id"], ApdexConfig.INSTANCE_LEVEL, instance_config)

        from apm.task.tasks import refresh_apm_application_config

        refresh_apm_application_config.delay(bk_biz_id, app_name)

    def set_custom_service_config(self, bk_biz_id, app_name, custom_services):
        CustomServiceConfig.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, config_level=ApdexConfig.APP_LEVEL, config_key=app_name
        ).delete()
        CustomServiceConfig.refresh_config(bk_biz_id, app_name, ApdexConfig.APP_LEVEL, app_name, custom_services)

    def set_config(self, bk_biz_id, app_name, config_key, config_level, config):
        if config_level == AppConfigBase.APP_LEVEL:
            # 如果是app级别配置 -> 保存实例名配置&维度配置&采样配置
            instance_name_config = config.get("instance_name_config", [])
            dimension_config = config.get("dimension_config", [])
            sampler_config = config.get("sampler_config", {})
            apdex_configs = config.get("apdex_config", [])
            license_config = config.get("license_config", {})
            db_config = config.get("db_config", {})
            probe_config = config.get("probe_config", {})
            db_slow_command_config = config.get("db_slow_command_config", {})

            self.set_apdex_configs(bk_biz_id, app_name, config_key, config_level, apdex_configs)
            self.set_sampler_configs(bk_biz_id, app_name, config_key, config_level, sampler_config)
            self.set_instance_name_config(bk_biz_id, app_name, instance_name_config)
            self.set_dimension_config(bk_biz_id, app_name, dimension_config)
            self.set_license_config(bk_biz_id, app_name, config_key, config_level, license_config)
            self.set_db_config(bk_biz_id, app_name, config_key, config_level, db_config)
            self.set_probe_config(bk_biz_id, app_name, config_key, config_level, probe_config)
            self.set_db_slow_command_config(bk_biz_id, app_name, config_key, config_level, db_slow_command_config)
        elif config_level == AppConfigBase.SERVICE_LEVEL:
            self.set_apdex_configs(
                bk_biz_id, app_name, config["service_name"], AppConfigBase.SERVICE_LEVEL, config["apdex_config"]
            )

    def set_instance_name_config(self, bk_biz_id, app_name, instance_name_config):
        ApmInstanceDiscover.refresh_config(bk_biz_id, app_name, instance_name_config)

    def set_dimension_config(self, bk_biz_id, app_name, dimension_configs):
        ApmMetricDimension.refresh_config(bk_biz_id, app_name, dimension_configs)

    def set_apdex_configs(self, bk_biz_id, app_name, config_key, config_level, apdex_configs):
        ApdexConfig.refresh_config(bk_biz_id, app_name, config_level, config_key, apdex_configs)

    def set_sampler_configs(self, bk_biz_id, app_name, config_key, config_level, sampler_config):
        if not sampler_config:
            return
        SamplerConfig.refresh_config(bk_biz_id, app_name, config_level, config_key, [sampler_config])

    def set_license_config(self, bk_biz_id, app_name, config_key, config_level, license_config):
        if not license_config:
            return
        LicenseConfig.refresh_config(bk_biz_id, app_name, config_level, config_key, [license_config])

    def set_db_config(self, bk_biz_id, app_name, config_key, config_level, db_config):
        if not db_config:
            return
        type_value_config = {"type": ConfigTypes.DB_CONFIG, "value": json.dumps(db_config)}
        NormalTypeValueConfig.refresh_config(
            bk_biz_id, app_name, config_level, config_key, [type_value_config], need_delete_config=False
        )

    def set_probe_config(self, bk_biz_id, app_name, config_key, config_level, probe_config):
        if not probe_config:
            return
        ProbeConfig.refresh_config(bk_biz_id, app_name, config_level, config_key, [probe_config])

    def set_db_slow_command_config(self, bk_biz_id, app_name, config_key, config_level, db_slow_command_config):
        if not db_slow_command_config:
            return
        type_value_config = {"type": ConfigTypes.DB_SLOW_COMMAND_CONFIG, "value": json.dumps(db_slow_command_config)}
        NormalTypeValueConfig.refresh_config(
            bk_biz_id, app_name, config_level, config_key, [type_value_config], need_delete_config=False
        )


class DeleteAppConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ServiceConfigSerializer(serializers.Serializer):
            service_name = serializers.CharField(label="service_name")
            apdex_config = serializers.ListField(label="Apdex配置规则", child=ApdexSerializer(), required=False)

        class InstanceConfigSerializer(serializers.Serializer):
            id = serializers.IntegerField(label="instance_id")
            apdex_config = serializers.ListField(label="Apdex配置规则", child=ApdexSerializer(), required=False)
            sampler_config = SampleSerializer(label="采样配置", required=False)

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

        apdex_config = serializers.ListField(label="Apdex配置规则", child=ApdexSerializer(), required=False)
        sampler_config = SampleSerializer(label="采样配置", required=False)
        instance_name_config = serializers.ListField(child=serializers.CharField(), label="实例名称")
        dimension_config = serializers.ListField(child=DimensionConfigSerializer(label="应用维度配置"), required=False)

        service_configs = serializers.ListField(label="服务配置", child=ServiceConfigSerializer(), required=False)
        instance_configs = serializers.ListField(label="实例配置", child=InstanceConfigSerializer(), required=False)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]

        ApmApplication.get_application(bk_biz_id, app_name)

        service_configs = validated_request_data.get("service_configs", [])
        instance_configs = validated_request_data.get("instance_configs", [])
        self.delete_config(bk_biz_id, app_name, app_name, ApdexConfig.APP_LEVEL, validated_request_data)

        for service_config in service_configs:
            self.delete_config(bk_biz_id, app_name, app_name, ApdexConfig.SERVICE_LEVEL, service_config)

        for instance_config in instance_configs:
            self.delete_config(bk_biz_id, app_name, instance_config["id"], ApdexConfig.INSTANCE_LEVEL, instance_config)
        from apm.task.tasks import refresh_apm_application_config

        refresh_apm_application_config.delay(bk_biz_id, app_name)

    def delete_config(self, bk_biz_id, app_name, config_key, config_level, config):
        apdex_configs = config.get("apdex_config", [])
        self.delete_apdex_configs(bk_biz_id, app_name, config_key, config_level, apdex_configs)

        if config_level == ApdexConfig.APP_LEVEL:
            # 应用配置需要删除采样配置&维度配置&实例名配置
            sampler_config = config.get("sampler_config")
            self.delete_sampler_configs(bk_biz_id, app_name, config_key, config_level, sampler_config)
            self.delete_instance_name_configs(bk_biz_id, app_name)
            self.delete_dimension_configs(bk_biz_id, app_name)

    def delete_instance_name_configs(self, bk_biz_id, app_name):
        ApmInstanceDiscover.delete_config(bk_biz_id, app_name)

    def delete_dimension_configs(self, bk_biz_id, app_name):
        ApmMetricDimension.delete_config(bk_biz_id, app_name)

    def delete_apdex_configs(self, bk_biz_id, app_name, config_key, config_level, apdex_configs):
        delete_configs = []
        for apdex_config in apdex_configs:
            delete_configs.append({"config_key": config_key, "config_level": config_level, **apdex_config})
        ApdexConfig.delete_config(bk_biz_id, app_name, delete_configs)

    def delete_sampler_configs(self, bk_biz_id, app_name, config_key, config_level, sampler_config):
        if not sampler_config:
            return
        SamplerConfig.delete_config(
            bk_biz_id, app_name, [{"config_key": config_key, "config_level": config_level, **sampler_config}]
        )


class AppConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    def perform_request(self, validated_request_data):
        return {
            "apdex_config_rules": [
                apdex_config.to_json()
                for apdex_config in ApdexConfig.objects.filter(
                    bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
                )
            ],
            "sampler_config": [
                sampler_config.to_json()
                for sampler_config in SamplerConfig.objects.filter(
                    bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
                )
            ],
            "instance_id_config": [
                instance.to_json()
                for instance in ApmInstanceDiscover.get_biz_config(validated_request_data["bk_biz_id"])
            ],
            "metric_dimension_config": [
                metric.to_json() for metric in ApmMetricDimension.get_biz_config(validated_request_data["bk_biz_id"])
            ],
        }


class QueryTopoNodeResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        topo_key = serializers.CharField(label="Topo Key", required=False, allow_null=True)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = TopoNode
            fields = ("extra_data", "topo_key")

        def to_representation(self, instance):
            data = super(QueryTopoNodeResource.ResponseSerializer, self).to_representation(instance)
            data["extra_data"] = instance.extra_data
            return data

    many_response_data = True

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        if data.get("topo_key"):
            filter_params["topo_key"] = data["topo_key"]

        return TopoNode.objects.filter(**filter_params)


class QueryTopoRelationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        from_topo_key = serializers.CharField(label="调用方Topo Key", allow_null=True, required=False)
        to_topo_key = serializers.CharField(label="被调方Topo Key", allow_null=True, required=False)
        filters = serializers.DictField(label="查询条件", allow_null=True, required=False, default={})

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = TopoRelation
            exclude = ["created_at", "updated_at"]

    many_response_data = True

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        if data.get("from_topo_key"):
            filter_params["from_topo_key"] = data["from_topo_key"]
        if data.get("to_topo_key"):
            filter_params["to_topo_key"] = data["to_topo_key"]

        return TopoRelation.objects.filter(**filter_params, **data["filters"])


class QueryTopoInstanceResource(PageListResource):
    UNIQUE_UPDATED_AT = "updated_at"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        service_name = serializers.ListField(label="服务列表", required=False, default=[])
        filters = serializers.DictField(label="查询条件", required=False)
        page = serializers.IntegerField(required=False, label="页码", min_value=1)
        page_size = serializers.IntegerField(required=False, label="每页条数", min_value=1)
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)

    class TopoInstanceSerializer(serializers.ModelSerializer):
        class Meta:
            model = TopoInstance
            fields = "__all__"

    def sort_data(self, queryset, sort_field: str):
        """
        updated_at 字段排序
        :param queryset: 结果集
        :param sort_field: 排序字段
        :return:
        """
        if sort_field in (self.UNIQUE_UPDATED_AT,):
            return sorted(queryset, key=lambda item: item.updated_at)
        return sorted(queryset, key=lambda item: item.updated_at, reverse=True)

    def filter_data(self, queryset, filter_flag):
        """
        updated_at 字段过滤
        :param queryset: 结果集
        :param filter_flag: 过滤字段
        :return:
        """
        if "updated_at__gte" in filter_flag:
            queryset = [i for i in queryset if i.updated_at >= filter_flag.get("updated_at__gte")]
        if "updated_at__gt" in filter_flag:
            queryset = [i for i in queryset if i.updated_at > filter_flag.get("updated_at__gt")]
        if "updated_at__lte" in filter_flag:
            queryset = [i for i in queryset if i.updated_at <= filter_flag.get("updated_at__lte")]
        if "updated_at__lt" in filter_flag:
            queryset = [i for i in queryset if i.updated_at < filter_flag.get("updated_at__lt")]
        if self.UNIQUE_UPDATED_AT in filter_flag:
            queryset = [i for i in queryset if i.updated_at == filter_flag.get("updated_at")]
        return queryset

    def pre_process(self, filter_params, validated_request_data):
        # 去除 updated_at 过滤条件
        filter_flag = {}
        for k in list(filter_params.keys()):
            if self.UNIQUE_UPDATED_AT in k:
                filter_flag[k] = filter_params.pop(k)

        sort_flag = ""
        sort = validated_request_data.get("sort")
        if sort and self.UNIQUE_UPDATED_AT in sort:
            sort_flag = sort
        return {"filter_flag": filter_flag, "sort_flag": sort_flag}

    def post_process(self, unique_params, data):
        if unique_params.get("sort_flag"):
            data = self.sort_data(data, unique_params.get("sort_flag"))
        if unique_params.get("filter_flag"):
            data = self.filter_data(data, unique_params.get("filter_flag"))
        return data

    def merge_data(self, instance_list, validated_request_data):
        merge_data = []
        name = InstanceHandler.get_topo_instance_cache_key(
            validated_request_data["bk_biz_id"], validated_request_data["app_name"]
        )
        cache_data = InstanceHandler().get_cache_data(name)
        # 更新 updated_at 字段
        for instance in instance_list:
            key = str(instance.id) + ":" + instance.instance_id
            if key in cache_data:
                instance.updated_at = datetime.datetime.fromtimestamp(cache_data.get(key), tz=pytz.UTC)
            merge_data.append(instance)
        return merge_data

    def perform_request(self, validated_request_data):
        filter_params = DiscoverHandler.get_retention_utc_filter_params(
            validated_request_data["bk_biz_id"], validated_request_data["app_name"]
        )
        service_name = validated_request_data["service_name"]
        if service_name:
            filter_params["topo_node_key__in"] = service_name

        if validated_request_data.get("filters"):
            filter_params.update(validated_request_data["filters"])

        unique_params = self.pre_process(filter_params, validated_request_data)

        queryset = TopoInstance.objects.filter(**filter_params)
        sort_field = validated_request_data.get("sort")
        if sort_field and self.UNIQUE_UPDATED_AT not in sort_field:
            queryset = queryset.order_by(sort_field)

        total = queryset.count()

        merge_data = self.merge_data(list(queryset), validated_request_data)

        data = self.post_process(unique_params, merge_data)

        if validated_request_data.get("page") and validated_request_data.get("page_size"):
            # 分页
            page_data = self.handle_pagination(data=data, params=validated_request_data)
            res = self.TopoInstanceSerializer(page_data, many=True).data
            return {"total": total, "data": res}

        return {"total": total, "data": self.TopoInstanceSerializer(data, many=True).data}


class QueryRootEndpointResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = RootEndpoint
            fields = ("endpoint_name", "category_id", "service_name")

    many_response_data = True

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        return RootEndpoint.objects.filter(**filter_params)


class FilterSerializer(serializers.Serializer):
    key = serializers.CharField(label="key", max_length=50)
    value = serializers.ListField(label="value", required=False, default=[])
    op = serializers.CharField(label="op", max_length=50)
    condition = serializers.CharField(label="condition", max_length=50, required=False)


class QuerySpanResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据开始时间")
        filter_params = serializers.ListField(required=False, label="过滤条件", child=FilterSerializer())
        fields = serializers.ListField(required=False, label="过滤字段")
        category = serializers.CharField(required=False, label="类别")

    def perform_request(self, validated_request_data):
        application = ApmApplication.get_application(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        )
        return application.trace_datasource.query_span(
            validated_request_data["start_time"],
            validated_request_data["end_time"],
            validated_request_data.get("filter_params"),
            validated_request_data.get("fields"),
            validated_request_data.get("category"),
        )


class QueryEndpointResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        # start_time = serializers.IntegerField(required=True, label="数据开始时间")
        # end_time = serializers.IntegerField(required=True, label="数据开始时间")
        category = serializers.CharField(required=False, label="类别", default="")
        category_kind_value = serializers.CharField(required=False, label="类型具体值", default="")
        service_name = serializers.CharField(required=False, label="服务名称", allow_blank=True, default="")
        bk_instance_id = serializers.CharField(required=False, label="实例id", allow_blank=True, default="")

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        endpoints = Endpoint.objects.filter(**filter_params).order_by("-updated_at")
        if data["category"]:
            endpoints = endpoints.filter(category_id=data["category"])
        if data["category_kind_value"]:
            endpoints = endpoints.filter(category_kind_value=data["category_kind_value"])
        if data["service_name"]:
            endpoints = endpoints.filter(service_name=data["service_name"])
        if data["bk_instance_id"]:
            instance = TopoInstance.objects.filter(
                instance_id=data["bk_instance_id"],
                bk_biz_id=data["bk_biz_id"],
                app_name=data["app_name"],
            ).first()
            endpoints = endpoints.filter(service_name=instance.topo_node_key)
        return [
            {
                "endpoint_name": endpoint.endpoint_name,
                "kind": endpoint.span_kind,
                "service_name": endpoint.service_name,
                "category_kind": {"key": endpoint.category_kind_key, "value": endpoint.category_kind_value},
                "category": endpoint.category_id,
                "extra_data": endpoint.extra_data,
            }
            for endpoint in endpoints
        ]


class QueryEventResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据开始时间")
        filter_params = serializers.ListField(required=False, label="过滤条件", child=FilterSerializer())
        name = serializers.ListField(required=False, label="事件名称", default=[])
        category = serializers.CharField(required=False, label="类别")

    def perform_request(self, validated_request_data):
        application = ApmApplication.get_application(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        )

        return application.trace_datasource.query_event(
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            name=validated_request_data["name"],
            filter_params=validated_request_data.get("filter_params"),
            category=validated_request_data.get("category"),
        )


class QuerySerializer(serializers.Serializer):
    class FilterSerializer(serializers.Serializer):
        key = serializers.CharField(label="查询键")
        operator = serializers.CharField(label="操作符")
        value = serializers.ListSerializer(label="查询值", child=serializers.CharField(allow_blank=True), allow_empty=True)

    bk_biz_id = serializers.IntegerField(label="业务id")
    app_name = serializers.CharField(label="应用名称", max_length=50)
    start_time = serializers.IntegerField(required=True, label="数据开始时间")
    end_time = serializers.IntegerField(required=True, label="数据开始时间")
    offset = serializers.IntegerField(required=False, label="偏移量", default=0)
    limit = serializers.IntegerField(required=False, label="每页数量", default=10)
    es_dsl = serializers.DictField(required=False, label="DSL语句")
    filters = serializers.ListSerializer(required=False, label="查询条件", child=FilterSerializer())
    exclude_field = serializers.ListSerializer(required=False, label="排除字段", child=serializers.CharField())
    query_mode = serializers.ChoiceField(
        required=False,
        label="查询模式",
        choices=TraceListQueryMode.choices(),
        default=TraceListQueryMode.PRE_CALCULATION,
    )


class QueryTraceListResource(Resource):
    """查询Trace概览信息列表"""

    RequestSerializer = QuerySerializer

    def perform_request(self, validated_data):
        if validated_data["query_mode"] == TraceListQueryMode.PRE_CALCULATION:
            qm = QueryMode.TRACE
        else:
            qm = QueryMode.ORIGIN_TRACE

        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_list(
            qm,
            validated_data["start_time"],
            validated_data["end_time"],
            validated_data["limit"],
            validated_data["offset"],
            validated_data.get("filters"),
            validated_data.get("es_dsl"),
        )


class QuerySpanListResource(Resource):
    """查询Span概览信息列表"""

    RequestSerializer = QuerySerializer

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_list(
            QueryMode.SPAN,
            validated_data["start_time"],
            validated_data["end_time"],
            validated_data["limit"],
            validated_data["offset"],
            validated_data.get("filters"),
            validated_data.get("es_dsl"),
            validated_data.get("exclude_field"),
        )


class QueryOptionValuesSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务id")
    app_name = serializers.CharField(label="应用名称", max_length=50)
    start_time = serializers.IntegerField(required=True, label="数据开始时间")
    end_time = serializers.IntegerField(required=True, label="数据开始时间")
    fields = serializers.ListField(child=serializers.CharField(), label="查询字段")


class QueryTraceOptionValues(Resource):
    """获取Trace候选值"""

    RequestSerializer = QueryOptionValuesSerializer

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_option_values(
            QueryMode.TRACE, validated_data["start_time"], validated_data["end_time"], validated_data["fields"]
        )


class QuerySpanOptionValues(Resource):
    """获取Span候选值"""

    RequestSerializer = QueryOptionValuesSerializer

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_option_values(
            QueryMode.SPAN, validated_data["start_time"], validated_data["end_time"], validated_data["fields"]
        )


class QueryTraceDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        trace_id = serializers.CharField(label="trace_id")
        displays = serializers.ListField(
            child=serializers.ChoiceField(
                choices=TraceWaterFallDisplayKey.choices(),
                default=TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY,
            ),
            default=list,
            allow_empty=True,
            required=False,
        )
        query_trace_relation_app = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_data):
        # otel data must be in displays choice
        displays = validated_data.get("displays")
        if TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY not in displays:
            displays.append(TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY)

        trace, relation_mapping = QueryProxy(
            validated_data["bk_biz_id"], validated_data["app_name"]
        ).query_trace_detail(
            trace_id=validated_data["trace_id"],
            displays=validated_data["displays"],
            bk_biz_id=validated_data["bk_biz_id"],
            query_trace_relation_app=validated_data["query_trace_relation_app"],
        )

        return {"trace_data": trace, "relation_mapping": relation_mapping}


class QuerySpanDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        span_id = serializers.CharField(label="span_id")

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_span_detail(
            validated_data["span_id"]
        )


class QueryFieldsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    def perform_request(self, validated_request_data):
        application = ApmApplication.get_application(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        )
        return application.trace_datasource.fields()


class UpdateMetricFieldsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        field_list = serializers.ListField(label="字段列表")

    def perform_request(self, validated_request_data):
        application = ApmApplication.get_application(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        )
        return application.metric_datasource.update_fields(validated_request_data["field_list"])


class QueryEsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=True, label="结果表ID")
        query_body = serializers.DictField(required=True, label="查询内容")

    def perform_request(self, validated_request_data):
        table_id = validated_request_data["table_id"].replace(".", "_")
        datasource = None
        try:
            datasource = TraceDataSource.objects.get(result_table_id=validated_request_data["table_id"])
        except TraceDataSource.DoesNotExist:
            logger.info(f"trace data source not found [{validated_request_data['table_id']}]")
        if not datasource:
            for trace_datasource in TraceDataSource.objects.all():
                if trace_datasource.result_table_id.replace(".", "_") == table_id:
                    datasource = trace_datasource

        if datasource:
            return datasource.es_client.search(index=datasource.index_name, body=validated_request_data["query_body"])

        raise ValueError(_("未找到对应的结果表"))


class QueryEsMappingResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()

    def perform_request(self, data):
        datasource = TraceDataSource.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not datasource:
            return None

        return datasource.es_client.indices.get_mapping(datasource.index_name)


class ListEsClusterInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")

    def can_visible(self, bk_biz_id, visible_bk_biz) -> bool:
        if bk_biz_id == str(GLOBAL_CONFIG_BK_BIZ_ID):
            return True
        return bk_biz_id in visible_bk_biz

    def perform_request(self, validated_request_data):
        bk_biz_id = str(validated_request_data["bk_biz_id"])
        query_result = models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_ES)
        result = []
        for cluster in query_result:
            cluster_info = cluster.consul_config
            cluster_info.pop("auth_info", None)
            custom_option = cluster_info["cluster_config"].get("custom_option", {})
            try:
                custom_option = json.loads(custom_option) if custom_option else {"bk_biz_id": ""}
                cluster_info["cluster_config"]["custom_option"] = custom_option

                # 兼容日志平台可见业务
                cluster_create_biz_id = custom_option["bk_biz_id"]
                if str(bk_biz_id) == str(cluster_create_biz_id):
                    result.append(cluster_info)
                    continue

                visible_config = custom_option.get("visible_config", {})
                if visible_config:
                    # 1. 可见范围配置是使用visible_config字段控制
                    # {'visible_type': 'multi_biz', 'visible_bk_biz': [481], 'bk_biz_labels': {}}
                    visible_type = str(visible_config.get("visible_type"))
                    if visible_type == VisibleEnum.ALL_BIZ:
                        result.append(cluster_info)
                    elif visible_type == VisibleEnum.CURRENT_BIZ:
                        if str(bk_biz_id) == str(cluster_create_biz_id):
                            result.append(cluster_info)
                    elif visible_type == VisibleEnum.MULTI_BIZ:
                        if str(bk_biz_id) in [str(i) for i in visible_config.get("visible_bk_biz", [])]:
                            result.append(cluster_info)
                    elif visible_type == VisibleEnum.BIZ_ATTR:
                        # 如果CMDB的属性一致，则集群可见
                        bk_biz_labels = visible_config.get("bk_biz_labels", {})
                        bizs = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
                        if bizs and bizs[0]:
                            biz_obj = bizs[0]
                            if all(
                                [
                                    getattr(biz_obj, label_key) in label_val
                                    for label_key, label_val in bk_biz_labels.items()
                                ]
                            ):
                                result.append(cluster_info)
                else:
                    # 2. 老的可见范围配置是使用visible_bk_biz控制
                    custom_visible_bk_biz = custom_option.get("visible_bk_biz", [])
                    custom_visible_bk_biz = {str(item) for item in custom_visible_bk_biz} & {str(bk_biz_id)}
                    if (
                        self.can_visible(bk_biz_id, custom_visible_bk_biz)
                        or cluster_info["cluster_config"]["registered_system"]
                        == models.ClusterInfo.DEFAULT_REGISTERED_SYSTEM
                    ):
                        result.append(cluster_info)

            except ValueError:
                continue
        return result


class QueryAppByHostInstanceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class IpSerializer(serializers.Serializer):
            ip = serializers.CharField()
            bk_cloud_id = serializers.CharField()

        ips = serializers.ListField(child=IpSerializer(), allow_empty=True)

    def perform_request(self, validated_data):
        if not validated_data["ips"]:
            return {}

        res = {}
        for item in validated_data["ips"]:
            query = HostInstance.objects.filter(bk_cloud_id=item["bk_cloud_id"], ip=item["ip"])
            if not query.exists():
                continue
            for instance in query:
                key = f"{item['ip']}|{item['bk_cloud_id']}"
                if key in res:
                    res[key]["relations"].append(
                        {
                            "bk_biz_id": instance.bk_biz_id,
                            "app_name": instance.app_name,
                            "topo_node_key": instance.topo_node_key,
                        }
                    )
                else:
                    res[key] = {
                        "relations": [
                            {
                                "bk_biz_id": instance.bk_biz_id,
                                "app_name": instance.app_name,
                                "topo_node_key": instance.topo_node_key,
                            }
                        ]
                    }

        return res


class QueryTraceByIdsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        trace_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()

    def perform_request(self, validated_request_data):
        """根据trace_id列表查询trace信息"""
        trace_ids = list(set(validated_request_data["trace_ids"]))
        if len(trace_ids) > settings.APM_APP_QUERY_TRACE_MAX_COUNT:
            logger.warning(
                "QueryTraceByIdsResource len of trace_ids({}) has exceeded the maximum number({})".format(
                    len(trace_ids), settings.APM_APP_QUERY_TRACE_MAX_COUNT
                )
            )
            validated_request_data["trace_ids"] = trace_ids[: settings.APM_APP_QUERY_TRACE_MAX_COUNT]

        return QueryProxy.query_trace_by_ids(**validated_request_data)


class QueryTraceByHostInstanceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        ip = serializers.CharField()
        bk_cloud_id = serializers.CharField()
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()
        offset = serializers.IntegerField(default=0)
        limit = serializers.IntegerField(default=10)

    def perform_request(self, data):
        host_instance = DiscoverHandler.get_host_instance(data["bk_biz_id"], data["ip"], data["bk_cloud_id"])

        if not host_instance:
            return None

        trace_mapping, total = QueryProxy(host_instance.bk_biz_id, host_instance.app_name).query_simple_info(
            data["start_time"], data["end_time"], data["offset"], data["limit"]
        )

        return {
            "app_info": {"bk_biz_id": host_instance.bk_biz_id, "app_name": host_instance.app_name},
            "data": {"total": total, "data": trace_mapping},
        }


class QueryAppByTraceResource(Resource):
    CONCURRENT_NUMBER = 5

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        trace_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)
        start_time = serializers.IntegerField()
        end_time = serializers.IntegerField()

    def perform_request(self, validated_request_data):
        """根据trace_id列表查询对应app信息"""
        trace_ids = validated_request_data["trace_ids"]
        if len(trace_ids) > settings.APM_APP_QUERY_TRACE_MAX_COUNT:
            logger.warning(
                "QueryTraceByIdsResource len of trace_ids({}) has exceeded the maximum number({})".format(
                    len(trace_ids), settings.APM_APP_QUERY_TRACE_MAX_COUNT
                )
            )
            trace_ids = trace_ids[: settings.APM_APP_QUERY_TRACE_MAX_COUNT]

        apps = ApmApplication.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])
        params = []
        for app in apps:
            params.append([app, trace_ids, validated_request_data["start_time"], validated_request_data["end_time"]])

        pool = ThreadPool(self.CONCURRENT_NUMBER)
        results = pool.map_ignore_exception(TraceDataSource.exists_by_trace_ids, params)
        res = {}
        for result in results:
            res.update(result)

        return res


class QueryHostInstanceResource(Resource):
    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField(required=False)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = HostInstance
            fields = ["bk_cloud_id", "ip", "bk_host_id"]

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        q = Q()
        if data.get("service_name"):
            q &= Q(topo_node_key=data["service_name"])

        return HostInstance.objects.filter(**filter_params).filter(q)


class QueryRemoteServiceRelationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        topo_node_key = serializers.CharField()
        category = serializers.CharField(allow_null=True, required=False)

    many_response_data = True

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = RemoteServiceRelation
            fields = ["topo_node_key", "from_endpoint_name", "category"]

    def perform_request(self, data):
        filter_params = DiscoverHandler.get_retention_filter_params(data["bk_biz_id"], data["app_name"])

        q = Q(topo_node_key=data["topo_node_key"])
        if data.get("category"):
            q &= Q(category=data["category"])

        return RemoteServiceRelation.objects.filter(**filter_params).filter(q)


class QueryLogRelationByIndexSetIdResource(Resource):
    class RequestSerializer(serializers.Serializer):
        index_set_id = serializers.IntegerField()

    def perform_request(self, data):
        log_relation = (
            LogServiceRelation.objects.filter(log_type=ServiceRelationLogTypeChoices.BK_LOG, value=data["index_set_id"])
            .order_by("created_at")
            .first()
        )

        if not log_relation:
            return None

        return {
            "bk_biz_id": log_relation.bk_biz_id,
            "app_name": log_relation.app_name,
            "service_name": log_relation.service_name,
        }


class QueryDiscoverRulesResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False)
        app_name = serializers.CharField(required=False)
        filters = serializers.DictField(required=False, default={})
        global_guarantee = serializers.BooleanField(required=False, default=True)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = ApmTopoDiscoverRule
            fields = "__all__"

    many_response_data = True

    def perform_request(self, data):
        filter_params = {}
        custom = False
        if data.get("bk_biz_id") and data.get("app_name"):
            filter_params["bk_biz_id"] = data["bk_biz_id"]
            filter_params["app_name"] = data["app_name"]
            custom = True
        else:
            filter_params["bk_biz_id"] = GLOBAL_CONFIG_BK_BIZ_ID

        filter_params.update(data["filters"])
        rules = ApmTopoDiscoverRule.objects.filter(**filter_params)

        if not rules.exists() and custom and data["global_guarantee"]:
            filter_params["bk_biz_id"] = GLOBAL_CONFIG_BK_BIZ_ID
            filter_params["app_name"] = ""
            rules = ApmTopoDiscoverRule.objects.filter(**filter_params)

        return rules


class QueryMetricDimensionsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField(allow_null=True, required=False)

    def perform_request(self, data):
        q = Q(bk_biz_id=data["bk_biz_id"])
        if data.get("app_name"):
            q &= Q(app_name=data["app_name"])

        dimensions = ApmMetricDimension.objects.filter(q)
        metric_dimensions = {}
        for q in dimensions:
            metric_dimensions.setdefault(q.span_kind, {}).setdefault(q.predicate_key, []).append(q.dimension_key)

        return [
            {"kind": kind, "predicate_key": predicate_key, "dimensions": dimensions}
            for kind, kind_configs in metric_dimensions.items()
            for predicate_key, dimensions in kind_configs.items()
        ]


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, data):
        app = ApmApplication.objects.filter(id=data["application_id"]).first()
        if not app:
            raise ValueError(_("应用不存在"))

        QpsConfig.refresh_config(
            app.bk_biz_id,
            app.app_name,
            AppConfigBase.APP_LEVEL,
            app.app_name,
            [{"qps": -1}],
        )

        from apm.task.tasks import refresh_apm_application_config

        refresh_apm_application_config(app.bk_biz_id, app.app_name)
        try:
            app.stop()
        except Exception as e:  # noqa
            logger.exception(
                f"[DeleteApplication] stop app: {app.bk_biz_id}-{app.app_name} failed {e} " f"{traceback.format_exc()}"
            )
        app.delete()


class QuerySpanStatisticsListResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_statistics(
            QueryStatisticsMode.SPAN_NAME,
            validated_data["start_time"],
            validated_data["end_time"],
            validated_data["limit"],
            validated_data["offset"],
            validated_data.get("filters"),
            validated_data.get("es_dsl"),
        )


class QueryServiceStatisticsListResource(Resource):
    RequestSerializer = QuerySerializer

    def perform_request(self, validated_data):
        return QueryProxy(validated_data["bk_biz_id"], validated_data["app_name"]).query_statistics(
            QueryStatisticsMode.SERVICE,
            validated_data["start_time"],
            validated_data["end_time"],
            validated_data["limit"],
            validated_data["offset"],
            validated_data.get("filters"),
            validated_data.get("es_dsl"),
        )


class QueryBuiltinProfileDatasourceResource(Resource):
    """Query builtin profile datasource"""

    class ProfileDataSourceSerializer(serializers.ModelSerializer):
        bk_data_token = serializers.SerializerMethodField()

        def get_bk_data_token(self, obj: ProfileDataSource):
            params = {"bk_biz_id": obj.bk_biz_id, "app_name": obj.app_name, "profile_data_id": obj.bk_data_id}
            return transform_data_id_to_v1_token(**params)

        class Meta:
            model = ProfileDataSource
            fields = "__all__"

    def perform_request(self, validated_request_data: dict):
        builtin_source = ProfileDataSource.get_builtin_source()
        if builtin_source is None:
            raise ValueError(_("未找到内置数据源，请联系管理员创建"))

        return self.ProfileDataSourceSerializer(builtin_source).data


class GetBkDataFlowDetailResource(Resource):
    """获取APM在计算平台中创建的Flow列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        flow_type = serializers.ChoiceField(label="数据开始时间", choices=FlowType.choices)

    class FlowResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = BkdataFlowConfig
            fields = "__all__"

    def perform_request(self, validated_request_data):
        instance = FlowHelper.get_detail(**validated_request_data)
        if instance:
            return self.FlowResponseSerializer(instance=instance).data

        return None


class CreateOrUpdateBkdataFlowResource(Resource):
    """创建/更新计算平台Flow"""

    class RequestSerializer(serializers.Serializer):
        class TailSamplingConfigSerializer(serializers.Serializer):
            class TailConditions(serializers.Serializer):
                """尾部采样-采样规则数据格式"""

                condition_choices = (
                    ("and", "and"),
                    ("or", "or"),
                )

                condition = serializers.ChoiceField(label="Condition", choices=condition_choices, required=False)
                key = serializers.CharField(label="Key")
                method = serializers.ChoiceField(label="Method", choices=TailSamplingSupportMethod.choices)
                value = serializers.ListSerializer(label="Value", child=serializers.CharField())

            tail_percentage = serializers.IntegerField(label="尾部采样-采集百分比", required=False)
            tail_trace_session_gap_min = serializers.IntegerField(label="尾部采样-会话过期时间", required=False)
            tail_trace_mark_timeout = serializers.IntegerField(label="尾部采样-标记状态最大存活时间", required=False)
            tail_conditions = serializers.ListSerializer(child=TailConditions(), required=False, allow_empty=True)

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        flow_type = serializers.ChoiceField(label="Flow类型", choices=FlowType.choices)
        config = serializers.DictField(label="Flow配置", allow_empty=True)

    def perform_request(self, validated_data):
        bk_biz_id = validated_data["bk_biz_id"]
        app_name = validated_data["app_name"]

        # 目前仅支持创建尾部采样Flow
        if validated_data["flow_type"] == FlowType.TAIL_SAMPLING.value:
            ser = self.RequestSerializer.TailSamplingConfigSerializer(data=validated_data["config"])
            ser.is_valid(raise_exception=True)

            logger.info(
                f"[create_trace_tail_sampling] start create tail sampling, bk_biz_id: {bk_biz_id} app_name: {app_name}"
            )
            trace = TraceDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if not trace:
                raise ValueError(f"没有找到app_name: {app_name}的Trace数据表")

            if settings.IS_ACCESS_BK_DATA:
                create_or_update_tail_sampling.delay(trace, ser.data)
                return

            raise ValueError("环境中未开启计算平台，无法创建")

        raise ValueError(f"不支持的Flow类型: {validated_data['flow_type']}")


class OperateApmDataIdResource(Resource):
    """操作APM Dataid的链路"""

    class RequestSerializer(serializers.Serializer):
        datalink_operate = (("stop", "暂停"), ("recover", "恢复"))

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        datasource_type = serializers.ChoiceField(label="采样类型", choices=DataSamplingLogTypeChoices.choices())
        operate = serializers.ChoiceField(choices=datalink_operate, label="操作")

    def perform_request(self, validated_data):
        if validated_data["datasource_type"] == DataSamplingLogTypeChoices.TRACE:
            data_id = TraceDataSource.objects.get(
                bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
            ).bk_data_id
        else:
            data_id = MetricDataSource.objects.get(
                bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
            ).bk_data_id

        ds = DataSource.objects.filter(bk_data_id=data_id).first()
        if not ds:
            raise ValueError(f"data_id: {data_id} not found in metadata.DataSource")

        logger.info(f"[OPERATE_APM_DATA_ID] --> {validated_data['operate']} dataId: {data_id}")
        if validated_data["operate"] == "stop":
            ds.is_enable = False
            ds.save()
            ds.delete_consul_config()
            return data_id

        ds.is_enable = True
        ds.save()
        ds.refresh_consul_config()
        return data_id


class QueryProfileServiceDetailResource(Resource):
    """查询Profile服务详情信息"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
        data_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class ResponseSerializer(serializers.ModelSerializer):
        last_check_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
        created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
        updated_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

        class Meta:
            model = ProfileService
            fields = "__all__"

    many_response_data = True

    def perform_request(self, validated_data):
        params = {
            "bk_biz_id": validated_data["bk_biz_id"],
            "app_name": validated_data["app_name"],
        }
        if validated_data.get("service_name"):
            params["name"] = validated_data["service_name"]
        if validated_data.get("data_type"):
            params["data_type"] = validated_data["data_type"]

        return ProfileService.objects.filter(**params).order_by("created_at")
