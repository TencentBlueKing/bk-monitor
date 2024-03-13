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
import copy
import datetime
import itertools
import json
import operator
import re
from collections import defaultdict
from dataclasses import asdict
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import Count, Q
from django.db.transaction import atomic
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from rest_framework import serializers

from api.cmdb.define import Business
from apm_web.constants import (
    APM_APPLICATION_DEFAULT_METRIC,
    DB_SYSTEM_TUPLE,
    DEFAULT_DB_CONFIG,
    DEFAULT_DIMENSION_DATA_PERIOD,
    DEFAULT_NO_DATA_PERIOD,
    DEFAULT_SPLIT_SYMBOL,
    NODATA_ERROR_STRATEGY_CONFIG_KEY,
    Apdex,
    BizConfigKey,
    CategoryEnum,
    CustomServiceMatchType,
    CustomServiceType,
    DataStatus,
    DefaultSetupConfig,
    InstanceDiscoverKeys,
    SamplerTypeChoices,
    SceneEventKey,
    ServiceRelationLogTypeChoices,
    TopoNodeKind,
)
from apm_web.handlers.application_handler import ApplicationHandler
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.db_handler import DbComponentHandler
from apm_web.handlers.instance_handler import InstanceHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.handlers.span_handler import SpanHandler
from apm_web.icon import get_icon
from apm_web.meta.handlers.custom_service_handler import Matcher
from apm_web.meta.handlers.sampling_handler import SamplingHelpers
from apm_web.meta.plugin.help import Help
from apm_web.meta.plugin.log_trace_plugin_config import EncodingsEnum
from apm_web.meta.plugin.plugin import (
    LOG_TRACE,
    DeploymentEnum,
    LanguageEnum,
    Opentelemetry,
    PluginEnum,
)
from apm_web.metric_handler import (
    ApdexInstance,
    AvgDurationInstance,
    ErrorCountInstance,
    ErrorRateInstance,
    RequestCountInstance,
)
from apm_web.metrics import APPLICATION_LIST
from apm_web.models import (
    ApmMetaConfig,
    Application,
    ApplicationCustomService,
    ApplicationRelationInfo,
    AppServiceRelation,
    CMDBServiceRelation,
    LogServiceRelation,
    UriServiceRelation,
)
from apm_web.resources import AsyncColumnsListResource
from apm_web.serializers import (
    ApdexConfigSerializer,
    ApplicationCacheSerializer,
    AsyncSerializer,
    CustomServiceConfigSerializer,
    ServiceParamsSerializer,
)
from apm_web.service.resources import CMDBServiceTemplateResource
from apm_web.service.serializers import (
    AppServiceRelationSerializer,
    LogServiceRelationOutputSerializer,
)
from apm_web.trace.service_color import ServiceColorClassifier
from apm_web.utils import group_by, span_time_strft
from bkmonitor.iam import ActionEnum
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.ip import is_v6
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.user import get_global_user, get_request_username
from common.log import logger
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE, EventSeverity
from constants.apm import (
    DataSamplingLogTypeChoices,
    FlowType,
    OtlpKey,
    SpanStandardField,
    TailSamplingSupportMethod,
)
from constants.data_source import (
    ApplicationsResultTableLabel,
    DataSourceLabel,
    DataTypeLabel,
)
from constants.result_table import ResultTableField
from core.drf_resource import Resource, api, resource
from monitor.models import ApplicationConfig
from monitor_web.constants import AlgorithmType
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    LinkListTableFormat,
    LinkTableFormat,
    NumberTableFormat,
    ScopedSlotsFormat,
    StatusTableFormat,
    StringTableFormat,
)
from monitor_web.strategies.user_groups import get_or_create_ops_notice_group


class CreateApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class DatasourceOptionSerializer(serializers.Serializer):
            es_storage_cluster = serializers.IntegerField(label="es存储集群")
            es_retention = serializers.IntegerField(label="es存储周期", min_value=1)
            es_number_of_replicas = serializers.IntegerField(label="es副本数量", min_value=0)
            es_shards = serializers.IntegerField(label="es索引分片数量", min_value=1)
            es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500)

        class PluginConfigSerializer(serializers.Serializer):
            target_node_type = serializers.CharField(label="节点类型", max_length=255)
            target_nodes = serializers.ListField(
                label="目标节点",
                required=False,
            )
            target_object_type = serializers.CharField(label="目标类型", max_length=255)
            data_encoding = serializers.CharField(label="日志字符集", max_length=255)
            paths = serializers.ListSerializer(
                label="语言",
                child=serializers.CharField(max_length=255),
                required=False,
            )

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"^[a-z0-9_-]+$")
        app_alias = serializers.CharField(label="应用别名", max_length=255)
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        plugin_id = serializers.CharField(
            label="插件ID", max_length=255, required=False, allow_blank=True, default=Opentelemetry.id
        )
        deployment_ids = serializers.ListField(
            label="环境",
            child=serializers.CharField(max_length=255),
            required=False,
            allow_empty=True,
            default=[DeploymentEnum.CENTOS.id],
        )
        language_ids = serializers.ListField(
            label="语言",
            child=serializers.CharField(max_length=255),
            required=False,
            allow_empty=True,
            default=[LanguageEnum.PYTHON.id],
        )
        datasource_option = DatasourceOptionSerializer(required=True)
        plugin_config = PluginConfigSerializer(required=False)
        enable_profiling = serializers.BooleanField(label="是否开启 Profiling 功能")
        enable_tracing = serializers.BooleanField(label="是否开启 Tracing 功能")

        def validate(self, attrs):
            res = super(CreateApplicationResource.RequestSerializer, self).validate(attrs)
            if not attrs["enable_tracing"]:
                raise ValueError(_("目前暂不支持关闭 Tracing 功能"))
            return res

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = Application
            fields = "__all__"

        def to_representation(self, instance):
            data = super(CreateApplicationResource.ResponseSerializer, self).to_representation(instance)
            application = Application.objects.filter(application_id=instance.application_id).first()
            data["plugin_config"] = application.plugin_config
            return data

    def perform_request(self, validated_request_data):
        if Application.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).exists():
            raise ValueError(_("应用名称: {}已被创建").format(validated_request_data['app_name']))

        plugin_config = validated_request_data.get("plugin_config")
        app = Application.create_application(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=validated_request_data["app_alias"],
            description=validated_request_data["description"],
            plugin_id=validated_request_data["plugin_id"],
            deployment_ids=validated_request_data["deployment_ids"],
            language_ids=validated_request_data["language_ids"],
            # TODO: enable_profiling vs enabled_profiling, 前后需要完全统一
            enabled_profiling=validated_request_data["enable_profiling"],
            datasource_option=validated_request_data["datasource_option"],
            plugin_config=plugin_config,
        )
        from apm_web.tasks import report_apm_application_event

        report_apm_application_event.delay(validated_request_data["bk_biz_id"], app.application_id)
        return app


class CheckDuplicateNameResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"[0-9a-zA-Z_]")

    class ResponseSerializer(serializers.Serializer):
        exists = serializers.BooleanField(label="是否存在")

    def perform_request(self, validated_request_data):
        if Application.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).exists():
            return {"exists": True}
        return {"exists": False}


class ListApplicationInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")

    many_response_data = True

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            ref_name = "list_application_info"
            model = Application
            fields = "__all__"

    def perform_request(self, validated_request_data):
        return Application.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])


class ApplicationInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            ref_name = "application_info"
            model = Application
            fields = "__all__"

        def handle_instance_name_config(self, instance, data):
            if not data.get("application_instance_name_config"):
                instance.set_init_instance_name_config()
                # 旧应用没有实例名 -> 补充
                data["application_instance_name_config"] = instance.get_config_by_key(
                    Application.INSTANCE_NAME_CONFIG_KEY
                ).config_value

            last_span = SpanHandler.get_lastly_span(instance.bk_biz_id, instance.app_name)
            composition = []
            for item in data["application_instance_name_config"]["instance_name_composition"]:
                composition.append(
                    {
                        "id": item,
                        "name": item,
                        "alias": InstanceDiscoverKeys.get_label_by_key(item),
                        "value": SpanHandler.get_span_field_value(last_span, item),
                    }
                )

            data["application_instance_name_config"]["instance_name_composition"] = composition

        def handle_sampler_config(self, instance, data):
            if "application_sampler_config" not in data:
                # 旧应用没有采样配置 -> 补充
                instance.set_init_sampler_config()
                data["application_sampler_config"] = instance.get_config_by_key(
                    Application.SAMPLER_CONFIG_KEY
                ).config_value

        def handle_dimension_config(self, instance, data):
            if "application_dimension_config" not in data:
                instance.set_init_dimensions_config()
                data["application_dimension_config"] = instance.get_config_by_key(
                    Application.DIMENSION_CONFIG_KEY
                ).config_value

        def handle_apdex_config(self, instance, data):
            # 如果是旧的apdex配置
            if "application_apdex_config" not in data or len(data["application_apdex_config"].keys()) == 2:
                instance.set_init_apdex_config()
                data["application_apdex_config"] = instance.get_config_by_key(Application.APDEX_CONFIG_KEY).config_value

        def handle_es_storage_shards(self, instance, data):
            # 旧应用没有分片数设置 -> 获取当前索引集群分片数
            if "es_shards" not in data["application_datasource_config"]:
                indices_data = IndicesInfoResource()(application_id=instance.application_id)
                if indices_data:
                    shards_count = indices_data[0]["pri"]
                    config_value = {**data["application_datasource_config"], "es_shards": shards_count}
                    ApmMetaConfig.application_config_setup(
                        instance.application_id, Application.APPLICATION_DATASOURCE_CONFIG_KEY, config_value
                    )
                    data["application_datasource_config"] = config_value

        def convert_sampler_config(self, bk_biz_id, app_name, data):
            if data[Application.SamplerConfig.SAMPLER_TYPE] == SamplerTypeChoices.RANDOM:
                # 随机类型配置不需要额外的转换逻辑
                return data

            fields_mapping = group_by(SpanStandardField.flat_list(), get_key=operator.itemgetter("key"))
            for i in data.get("tail_conditions", []):
                item = fields_mapping.get(i["key"])
                if item:
                    i["key_alias"] = item[0]["name"]
                    i["type"] = item[0]["type"]
                else:
                    # 如果为特殊字段elapsed_time 则手动进行修改
                    if i["key"] == "elapsed_time":
                        i["key_alias"] = _("Span耗时")
                        i["type"] = "time"
                    else:
                        # 如果配置字段不在内置字段中 默认为string类型
                        i["key_alias"] = i["key"]
                        i["type"] = "string"

            # 添加尾部采样flow信息帮助排查问题
            flow_detail = api.apm_api.get_bkdata_flow_detail(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                flow_type=FlowType.TAIL_SAMPLING.value,
            )
            data["tail_sampling_info"] = (
                {
                    "last_process_time": flow_detail.get("last_process_time"),
                    "status": flow_detail.get("status"),
                }
                if flow_detail
                else None
            )

            return data

        def to_representation(self, instance):
            data = super(ApplicationInfoResource.ResponseSerializer, self).to_representation(instance)
            data["es_storage_index_name"] = instance.trace_result_table_id.replace(".", "_")
            for config in instance.get_all_config():
                data[config.config_key] = config.config_value

            # 处理apdex配置
            self.handle_apdex_config(instance, data)
            # 处理实例名配置
            self.handle_instance_name_config(instance, data)
            # 处理存储分片数设置
            self.handle_es_storage_shards(instance, data)
            # 处理采样配置
            self.handle_sampler_config(instance, data)
            # 处理维度配置
            # self.handle_dimension_config(instance, data)
            data["plugin_id"] = instance.plugin_id
            data["deployment_ids"] = instance.deployment_ids
            data["language_ids"] = instance.language_ids
            data["no_data_period"] = instance.no_data_period
            # db 类型配置
            data["application_db_system"] = DB_SYSTEM_TUPLE
            # 补充默认配置
            if "application_db_config" not in data:
                data["application_db_config"] = [DEFAULT_DB_CONFIG]
            data["plugin_config"] = instance.plugin_config

            # 转换采样配置显示内容
            data[Application.SAMPLER_CONFIG_KEY] = self.convert_sampler_config(
                instance.bk_biz_id, instance.app_name, data[Application.SAMPLER_CONFIG_KEY]
            )
            return data

    def perform_request(self, validated_request_data):
        try:
            return Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))


class ApplicationInfoByAppNameResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, validated_request_data):
        try:
            application = Application.objects.get(
                app_name=validated_request_data["app_name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")
        data = ApplicationInfoResource().request({"application_id": application.application_id})
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        data["data_status"] = DataStatus.NO_DATA
        if start_time and end_time:
            if ApplicationHandler.have_data(application, start_time, end_time):
                data["data_status"] = DataStatus.NORMAL
        return data


class OperateType(models.TextChoices):
    TRACING = "tracing", _("tracing")
    PROFILING = "profiling", _("profiling")


class StartResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        type = serializers.ChoiceField(label="暂停类型", choices=OperateType.choices, default=OperateType.TRACING.value)

    @atomic
    def perform_request(self, validated_data):
        if validated_data["type"] == OperateType.TRACING.value:
            Application.objects.filter(application_id=validated_data["application_id"]).update(is_enabled=True)
            Application.start_plugin_config(validated_data["application_id"])
            return api.apm_api.start_application(application_id=validated_data["application_id"], type="tracing")

        Application.objects.filter(application_id=validated_data["application_id"]).update(is_enabled_profiling=True)
        return api.apm_api.start_application(application_id=validated_data["application_id"], type="profiling")


class StopResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        type = serializers.ChoiceField(label="暂停类型", choices=OperateType.choices, default=OperateType.TRACING.value)

    @atomic
    def perform_request(self, validated_data):
        if validated_data["type"] == OperateType.TRACING.value:
            Application.objects.filter(application_id=validated_data["application_id"]).update(is_enabled=False)
            Application.stop_plugin_config(validated_data["application_id"])
            return api.apm_api.stop_application(validated_data, type="tracing")

        Application.objects.filter(application_id=validated_data["application_id"]).update(is_enabled_profiling=False)
        return api.apm_api.stop_application(application_id=validated_data["application_id"], type="profiling")


class SamplingOptionsResource(Resource):
    """获取采样配置常量"""

    def perform_request(self, validated_request_data):
        sampling_types = [SamplerTypeChoices.RANDOM, SamplerTypeChoices.EMPTY]
        res = {}
        if settings.IS_ACCESS_BK_DATA:
            # 标准字段常量 + 耗时字段
            sampling_types.append(SamplerTypeChoices.TAIL)
            standard_fields = SpanStandardField.flat_list()
            standard_fields = [{"name": _("Span耗时"), "key": "elapsed_time", "type": "time"}] + standard_fields
            res["tail_sampling_options"] = standard_fields

        return {
            "sampler_types": sampling_types,
            **res,
        }


class SetupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class DatasourceOptionSerializer(serializers.Serializer):
            es_storage_cluster = serializers.IntegerField(label="es存储集群")
            es_retention = serializers.IntegerField(label="es存储周期", min_value=1)
            es_number_of_replicas = serializers.IntegerField(label="es副本数量", min_value=0)
            # 兼容旧应用没有分片数
            es_shards = serializers.IntegerField(label="es索引分片数", min_value=1, default=3)
            es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500)

        class SamplerConfigSerializer(serializers.Serializer):
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

            sampler_type = serializers.ChoiceField(choices=SamplerTypeChoices.choices(), label="采集类型")
            sampler_percentage = serializers.IntegerField(label="采集百分比", required=False)
            tail_trace_session_gap_min = serializers.IntegerField(label="尾部采样-会话过期时间", required=False)
            tail_trace_mark_timeout = serializers.IntegerField(label="尾部采样-标记状态最大存活时间", required=False)
            tail_conditions = serializers.ListSerializer(child=TailConditions(), required=False, allow_empty=True)

            def validate(self, attrs):
                attr = super().validate(attrs)
                if attrs["sampler_type"] == SamplerTypeChoices.RANDOM:
                    if "sampler_percentage" not in attrs:
                        raise ValueError(_("随机采样未配置采集百分比"))
                elif attrs["sampler_type"] == SamplerTypeChoices.TAIL:
                    if "sampler_percentage" not in attrs:
                        raise ValueError("尾部采样未配置采集百分比")

                if attrs.get("tail_conditions"):
                    t = [i for i in attrs["tail_conditions"] if i["key"] and i["method"] and i["value"]]
                    attrs["tail_conditions"] = t

                return attr

        class InstanceNameConfigSerializer(serializers.Serializer):
            instance_name_composition = serializers.ListField(
                child=serializers.CharField(), min_length=1, label="实例名组成"
            )

            def validate_instance_name_composition(self, data):
                if len(set(data)) != len(data):
                    raise ValueError(_("实例名配置含有重复"))

                return data

        class DimensionConfigSerializer(serializers.Serializer):
            class _DimensionSerializer(serializers.Serializer):
                span_kind = serializers.CharField(label="span_kind")
                predicate_key = serializers.CharField(label="predicate_key")
                dimensions = serializers.ListField(child=serializers.CharField(), label="维度")

            dimensions = serializers.ListField(child=_DimensionSerializer(), label="维度配置")

        class DbConfigSerializer(serializers.Serializer):
            db_system = serializers.CharField(label="DB类型", allow_blank=True)
            trace_mode = serializers.CharField(label="追踪模式")
            length = serializers.IntegerField(label="保留长度")
            threshold = serializers.IntegerField(label="阀值")
            enabled_slow_sql = serializers.BooleanField(label="是否启用慢语句")

        class PluginConfigSerializer(serializers.Serializer):
            target_node_type = serializers.CharField(label="节点类型", max_length=255)
            target_nodes = serializers.ListField(
                label=_("目标节点"),
                required=False,
            )
            target_object_type = serializers.CharField(label="目标类型", max_length=255)
            data_encoding = serializers.CharField(label=_("日志字符集"), max_length=255)
            paths = serializers.ListSerializer(
                label="语言",
                child=serializers.CharField(max_length=255),
                required=False,
            )
            bk_biz_id = serializers.IntegerField(label="业务id", required=False)
            subscription_id = serializers.IntegerField(label="订阅任务id", required=False)
            bk_data_id = serializers.IntegerField(label="数据id", required=False)

        application_id = serializers.IntegerField(label="应用id")
        app_alias = serializers.CharField(label="应用别名", max_length=255, required=False)
        description = serializers.CharField(label="应用描述", max_length=255, allow_blank=True, required=False)
        datasource_option = DatasourceOptionSerializer(required=False)
        application_apdex_config = ApdexConfigSerializer(required=False)
        application_sampler_config = SamplerConfigSerializer(required=False)
        application_instance_name_config = InstanceNameConfigSerializer(required=False)
        application_dimension_config = DimensionConfigSerializer(required=False)
        application_db_config = serializers.ListField(label="db配置", child=DbConfigSerializer(), default=[])

        no_data_period = serializers.IntegerField(label="无数据周期", required=False)
        is_enabled = serializers.BooleanField(label="Tracing启/停", required=False)
        profiling_is_enabled = serializers.BooleanField(label="Profiling启/停", required=False)
        plugin_config = PluginConfigSerializer(required=False)

    class SetupProcessor:
        update_key = []
        group_key = None

        def __init__(self, application):
            self._application = application
            self._params = {}

        def set_params(self, key, value):
            self._params[key] = value

        def set_group_params(self, value):
            for k, v in value.items():
                self.set_params(k, v)

        def setup(self):
            pass

    class NoDataPeriodProcessor(SetupProcessor):
        update_key = ["no_data_period"]

        def setup(self):
            for key, value in self._params.items():
                self._application.setup_nodata_config(key, value)

    class DatasourceSetProcessor(SetupProcessor):
        update_key = ["datasource_option"]

        def setup(self):
            for key in self.update_key:
                if key not in self._params:
                    return
            Application.setup_datasource(self._application.application_id, self._params["datasource_option"])

    class ApplicationSetupProcessor(SetupProcessor):
        update_key = ["app_alias", "description"]

        def setup(self):
            Application.objects.filter(application_id=self._application.application_id).update(**self._params)

    class ApdexSetupProcessor(SetupProcessor):
        group_key = "application_apdex_config"
        update_key = ["apdex_default", "apdex_http", "apdex_db", "apdex_messaging", "apdex_backend", "apdex_rpc"]

        def setup(self):
            self._application.setup_config(
                self._application.apdex_config, self._params, self._application.APDEX_CONFIG_KEY, override=True
            )

    class InstanceNameSetupProcessor(SetupProcessor):
        group_key = "application_instance_name_config"
        update_key = ["instance_name_composition"]

        def setup(self):
            self._application.setup_config(
                self._application.instance_config, self._params, self._application.INSTANCE_NAME_CONFIG_KEY
            )

    class DimensionSetupProcessor(SetupProcessor):
        group_key = "application_dimension_config"
        update_key = ["dimensions"]

        def setup(self):
            self._application.setup_config(
                self._application.dimension_config, self._params, self._application.DIMENSION_CONFIG_KEY
            )

    class DbSetupProcessor(SetupProcessor):
        update_key = ["application_db_config"]

        def setup(self):
            self._application.setup_config(
                self._application.db_config,
                self._params["application_db_config"],
                self._application.DB_CONFIG_KEY,
                override=True,
            )

    def perform_request(self, validated_data):
        try:
            application = Application.objects.get(application_id=validated_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        # Step1: 更新应用配置
        processors = [
            processor_cls(application)
            for processor_cls in [
                self.DatasourceSetProcessor,
                self.ApplicationSetupProcessor,
                self.ApdexSetupProcessor,
                self.InstanceNameSetupProcessor,
                # self.DimensionSetupProcessor,
                self.NoDataPeriodProcessor,
                self.DbSetupProcessor,
            ]
        ]

        need_handle_processors = []
        for key, value in validated_data.items():
            for processor in processors:
                if processor.group_key and key == processor.group_key:
                    processor.set_group_params(value)
                    need_handle_processors.append(processor)

                if key in processor.update_key:
                    processor.set_params(key, value)
                    need_handle_processors.append(processor)

        for processor in need_handle_processors:
            processor.setup()

        # Step2: 因为采样配置较复杂所以不走Processor 交给单独Helper处理
        if validated_data.get("application_sampler_config"):
            SamplingHelpers(validated_data['application_id']).setup(validated_data["application_sampler_config"])

        # 判断是否需要启动/停止项目
        if validated_data.get("is_enabled") is not None:
            if application.is_enabled != validated_data["is_enabled"]:
                Application.objects.filter(application_id=application.application_id).update(
                    is_enabled=validated_data["is_enabled"]
                )

                if validated_data["is_enabled"]:
                    Application.start_plugin_config(validated_data["application_id"])
                    api.apm_api.start_application(application_id=validated_data["application_id"], type="tracing")
                else:
                    Application.stop_plugin_config(validated_data["application_id"])
                    api.apm_api.stop_application(application_id=validated_data["application_id"], type="tracing")

        # 判断是否需要启动/暂停 profiling
        if validated_data.get("profiling_is_enabled") is not None:
            if application.is_enabled_profiling != validated_data["profiling_is_enabled"]:
                Application.objects.filter(application_id=application.application_id).update(
                    is_enabled_profiling=validated_data["profiling_is_enabled"]
                )

                if validated_data["profiling_is_enabled"]:
                    api.apm_api.start_application(application_id=validated_data["application_id"], type="profiling")
                else:
                    api.apm_api.stop_application(application_id=validated_data["application_id"], type="profiling")

        Application.objects.filter(application_id=application.application_id).update(update_user=get_global_user())

        # Log-Trace配置更新
        if application.plugin_id == LOG_TRACE:
            Application.update_plugin_config(application.application_id, validated_data["plugin_config"])
        from apm_web.tasks import update_application_config

        update_application_config.delay(application.application_id)


class ListApplicationResource(PageListResource):
    """APM 观测场景应用列表接口"""

    def get_columns(self, column_type=None):
        return [
            ScopedSlotsFormat(
                url_format="/application?filter-app_name={app_name}",
                id="app_alias",
                name=_("应用别名"),
                checked=True,
                action_id=ActionEnum.VIEW_APM_APPLICATION.id,
                disabled=True,
            ),
            StringTableFormat(id="app_name", name=_("应用名"), checked=False),
            StringTableFormat(id="description", name=_("应用描述"), checked=False),
            StringTableFormat(id="retention", name=_("存储计划"), checked=False),
            LinkTableFormat(
                id="service_count",
                name=_("服务数量"),
                url_format="/application?filter-app_name={app_name}&dashboardId=service",
                sortable=True,
                action_id=ActionEnum.VIEW_APM_APPLICATION.id,
                asyncable=True,
            ),
            StatusTableFormat(id="apdex", name="Apdex", status_map_cls=Apdex, filterable=True, asyncable=True),
            NumberTableFormat(id="request_count", name=_("调用次数"), sortable=True, asyncable=True),
            NumberTableFormat(id="avg_duration", name=_("平均响应耗时"), sortable=True, unit="ns", decimal=2, asyncable=True),
            NumberTableFormat(id="error_rate", name=_("错误率"), sortable=True, decimal=2, unit="percent", asyncable=True),
            NumberTableFormat(id="error_count", name=_("错误次数"), checked=False, sortable=True, asyncable=True),
            StringTableFormat(id="is_enabled", name=_("应用是否启用"), checked=False),
            StringTableFormat(id="is_enabled_profiling", name=_("Profiling是否启用"), checked=False),
            StringTableFormat(
                id="profiling_data_status",
                name=_("Profiling数据状态"),
                checked=True,
            ),
            StringTableFormat(
                id="data_status",
                name=_("Trace数据状态"),
                checked=True,
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        filter_dict = serializers.JSONField(required=False, label="筛选字典")
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)

    class ApplicationSerializer(serializers.ModelSerializer):
        class Meta:
            model = Application
            fields = [
                "bk_biz_id",
                "application_id",
                "app_name",
                "app_alias",
                "description",
                "is_enabled",
                "is_enabled_profiling",
                "profiling_data_status",
                "data_status",
            ]

        def to_representation(self, instance):
            data = super(ListApplicationResource.ApplicationSerializer, self).to_representation(instance)
            if not data["is_enabled"]:
                data["data_status"] = DataStatus.STOP
            return data

    def get_filter_fields(self):
        return ["app_name", "app_alias", "description"]

    def perform_request(self, validate_data):
        applications = Application.objects.filter(bk_biz_id=validate_data["bk_biz_id"])
        data = self.ApplicationSerializer(applications, many=True).data
        data = sorted(
            data,
            key=lambda i: (
                1 if i["data_status"] == DataStatus.NORMAL else 0,
                1 if i["profiling_data_status"] == DataStatus.NORMAL else 0,
                i["application_id"],
            ),
            reverse=True,
        )

        return self.get_pagination_data(data, validate_data)


class ListApplicationAsyncResource(AsyncColumnsListResource):
    """
    应用列表页异步接口
    """

    METRIC_MAP = {
        "apdex": ApdexInstance,
        "request_count": RequestCountInstance,
        "avg_duration": AvgDurationInstance,
        "error_rate": ErrorRateInstance,
        "error_count": ErrorCountInstance,
    }
    SERVICE_COUNT = "service_count"

    SyncResource = ListApplicationResource

    @classmethod
    def get_miss_application_and_cache_metric_data(cls, applications):
        """
        获取应用指标缓存数据及miss_application
        :param applications: 应用列表
        :return:
        """

        miss_application = []
        cache_metric_data = {}

        # 获取缓存数据
        cache_key_maps = {str(app.get("application_id")): ServiceHandler.build_cache_key(app) for app in applications}
        cache_data = cache.get_many(cache_key_maps.values())

        for app in applications:
            application_id = str(app.get("application_id"))
            key = cache_key_maps.get(application_id)
            app_cache_data = cache_data.get(key)
            if app_cache_data:
                cache_metric_data[application_id] = app_cache_data
            else:
                miss_application.append(app)
        return miss_application, cache_metric_data

    @classmethod
    def get_metric_data(cls, metric_name: str, applications: list) -> dict:
        """
        获取应用指标数据
        :param metric_name: 指标名称
        :param applications: 应用列表
        :return:
        """

        service_count_mapping = {}
        metric_data = {}
        if metric_name == cls.SERVICE_COUNT:
            service_count_mapping = ServiceHandler.batch_query_service_count(applications)

        if metric_name in cls.METRIC_MAP:
            metric_data = APPLICATION_LIST(applications, metric_handler_cls=[cls.METRIC_MAP.get(metric_name)])

        metric_map = {}
        for app in applications:
            application_id = str(app["application_id"])
            app_metric = metric_data.get(application_id, copy.deepcopy(APM_APPLICATION_DEFAULT_METRIC))
            app_metric["service_count"] = service_count_mapping.get(application_id, 0)
            metric_map[application_id] = app_metric
        return metric_map

    def build_res(self, validate_data, app_mapping, metric_data):
        """
        获取返回数据
        :param validate_data: 参数
        :param app_mapping: 应用MAP
        :param metric_data: 指标数据
        :return:
        """

        res = []

        for application_id in validate_data.get("application_ids"):
            if application_id not in app_mapping:
                continue

            app_metric = metric_data.get(str(application_id), {})
            if validate_data["column"] in app_metric:
                res.append(
                    {
                        "application_id": application_id,
                        "app_name": app_mapping[application_id][0].app_name,
                        **self.get_async_column_item(app_metric, validate_data["column"]),
                    }
                )

        return res

    class RequestSerializer(AsyncSerializer):
        application_ids = serializers.ListSerializer(child=serializers.CharField(), default=[], label="app应用id列表")

    def perform_request(self, validate_data):
        res = []

        application_ids = validate_data.get("application_ids")
        if not application_ids:
            return res

        applications = Application.objects.filter(
            bk_biz_id=validate_data["bk_biz_id"], application_id__in=[int(app_id) for app_id in application_ids]
        )
        application_mapping = group_by(applications, lambda i: str(i.application_id))

        cache_applications = sorted(
            ApplicationCacheSerializer(applications, many=True).data, key=lambda i: i.get("application_id", 0)
        )

        miss_application, cache_metric_data = self.get_miss_application_and_cache_metric_data(
            applications=cache_applications
        )

        # 缓存中缺少部分应用时，补全数据
        if miss_application:
            metric_data = self.get_metric_data(metric_name=validate_data["column"], applications=miss_application)
            cache_metric_data.update(metric_data)

        res = self.build_res(
            validate_data=validate_data, app_mapping=application_mapping, metric_data=cache_metric_data
        )
        return self.get_async_data(res, validate_data["column"])


class ServiceDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称")
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")

    def key_name_map(self):
        return {
            TopoNodeKind.SERVICE: {
                "topo_key": _("服务名称"),
                "category": _("服务分类"),
                "predicate_value": _("分类名称"),
                "service_language": _("语言"),
                "instance_count": _("实例数"),
                "cmdb_template_name": _("关联CMDB服务名称"),
                "cmdb_first_category": _("关联CMDB一级分类名称"),
                "cmdb_second_category": _("关联CMDB二级分类名称"),
                "log_type": _("关联日志类型"),
                "log_related_bk_biz_name": _("关联日志业务名称"),
                "log_value_alias": _("关联日志索引集"),
                "log_value": _("关联日志url"),
                "app_related_bk_biz_name": _("关联应用(业务名称)"),
                "app_related_app_name": _("关联应用(应用名称)"),
            },
            TopoNodeKind.COMPONENT: {
                "topo_key": _("服务名称"),
                "category": _("服务分类"),
                "predicate_value": _("分类名称"),
                "kind": _("服务类型"),
                "belong_service": _("归属服务"),
            },
        }

    def value_map(self):
        return {
            "category": lambda x: CategoryEnum.get_label_by_key(x),
        }

    def get_service_detail(self, data):
        resp = api.apm_api.query_topo_node({"bk_biz_id": data["bk_biz_id"], "app_name": data["app_name"]})
        instance_map = api.apm_api.query_instance(
            {
                "bk_biz_id": data["bk_biz_id"],
                "app_name": data["app_name"],
                "service_name": [data["service_name"]],
                "filters": {
                    "instance_topo_kind": TopoNodeKind.SERVICE,
                },
            }
        )
        instance_count = instance_map.get("total", 0)
        for service in resp:
            if service["topo_key"] == data["service_name"]:
                service.update(service["extra_data"])
                for clean_key in ["extra_data", "kind"]:
                    service.pop(clean_key)

                if service["category"] == CategoryEnum.HTTP:
                    service.pop("predicate_value")

                service["instance_count"] = instance_count

                self.add_service_relation(data["bk_biz_id"], data["app_name"], service)

                return [
                    {
                        "name": self.key_name_map()[TopoNodeKind.SERVICE].get(item, item),
                        "type": "string",
                        "value": self.value_map().get(item, lambda x: str(x))(value),
                    }
                    for item, value in service.items()
                    if item in self.key_name_map()[TopoNodeKind.SERVICE].keys()
                ]

    def get_component_detail(self, data):
        service_params = data["service_params"]

        instance = {
            "topo_key": data.get("service_name"),
            "category": service_params.get("category"),
            "predicate_value": service_params.get("predicate_value"),
            "kind": service_params.get("kind"),
            "belong_service": ComponentHandler.get_component_belong_service(
                data.get("service_name", ""), service_params.get("predicate_value", "")
            ),
        }

        return [
            {
                "name": self.key_name_map()[TopoNodeKind.COMPONENT][k],
                "type": "string",
                "value": v,
            }
            for k, v in instance.items()
        ]

    def perform_request(self, data):
        if ComponentHandler.is_component(data.get("service_params")):
            return self.get_component_detail(data)

        return self.get_service_detail(data)

    def add_service_relation(self, bk_biz_id, app_name, service):
        query_params = {"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service["topo_key"]}
        # -- 添加cmdb关联信息
        cmdb_query = CMDBServiceRelation.objects.filter(**query_params)
        if cmdb_query.exists():
            instance = cmdb_query.first()
            bk_biz_id = instance.bk_biz_id
            template_id = instance.template_id
            template = {t["id"]: t for t in CMDBServiceTemplateResource.get_templates(bk_biz_id)}.get(template_id, {})
            service.update(
                {
                    "cmdb_template_name": template.get("name"),
                    "cmdb_first_category": template.get("first_category", {}).get("name"),
                    "cmdb_second_category": template.get("second_category", {}).get("name"),
                }
            )

        # -- 添加日志关联
        log_query = LogServiceRelation.objects.filter(**query_params)
        if log_query.exists():
            log_data = LogServiceRelationOutputSerializer(instance=log_query.first()).data
            if log_data["log_type"] == ServiceRelationLogTypeChoices.BK_LOG:
                service.update(
                    {
                        "log_type": log_data["log_type_alias"],
                        "log_related_bk_biz_name": log_data["related_bk_biz_name"],
                        "log_value_alias": log_data["value_alias"],
                    }
                )
            else:
                service.update({"log_type": log_data["log_type_alias"], "log_value": log_data["value"]})

        # -- 添加app关联
        app_query = AppServiceRelation.objects.filter(**query_params)
        if app_query.exists():
            instance = app_query.first()
            res = AppServiceRelationSerializer(instance=instance).data
            relate_bk_biz_id = instance.relate_bk_biz_id
            biz = {i.bk_biz_id: i for i in api.cmdb.get_business(bk_biz_ids=[relate_bk_biz_id])}.get(relate_bk_biz_id)
            service.update(
                {
                    "app_related_bk_biz_name": biz.bk_biz_name if isinstance(biz, Business) else None,
                    "app_related_app_name": res["relate_app_name"],
                }
            )


class MetricInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        keyword = serializers.CharField(required=False, label="关键字", allow_blank=True)

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        metric_info = app.metric_info
        keyword = validated_request_data.get("keyword", "")
        return [metric for metric in metric_info if keyword in metric["field_name"] or keyword in metric["description"]]


class ServiceListResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        resp = api.apm_api.query_topo_node(
            {"bk_biz_id": validated_request_data["bk_biz_id"], "app_name": validated_request_data["app_name"]}
        )
        return {
            "conditionList": [],
            "data": [
                {
                    "id": service["topo_key"],
                    "name": service["topo_key"],
                    "service_name": service["topo_key"],
                }
                for service in resp
                if service["extra_data"]["kind"] == "service"
            ],
        }


class QueryExceptionEventResource(PageListResource):
    EXCEPTION_EVENT_TYPE = "exception"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据开始时间")
        filter_dict = serializers.DictField(required=False, label="过滤条件", default={})
        filter_params = serializers.DictField(required=False, label="过滤参数", default={})
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )

    def build_filter_params(self, filter_dict):
        result = []
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append(
                {"key": key, "op": "=", "value": value if isinstance(value, list) else [value], "condition": "and"}
            )
        return result

    def get_operator(self):
        return _("查看")

    def perform_request(self, validated_request_data):
        filter_params = self.build_filter_params(validated_request_data["filter_params"])
        DbComponentHandler.build_component_filter_params(
            validated_request_data["bk_biz_id"],
            validated_request_data["app_name"],
            filter_params,
            validated_request_data.get("service_params"),
            validated_request_data.get("component_instance_id"),
        )
        category = validated_request_data.get("service_params", {}).get("category")
        if category:
            db_system_filter = DbComponentHandler.build_db_system_param(category=category)
            filter_params.extend(db_system_filter)

        events = api.apm_api.query_event(
            {
                "app_name": validated_request_data["app_name"],
                "bk_biz_id": validated_request_data["bk_biz_id"],
                "start_time": validated_request_data["start_time"],
                "end_time": validated_request_data["end_time"],
                "name": [self.EXCEPTION_EVENT_TYPE],
                "filter_params": filter_params,
            }
        )
        res = []
        for index, event in enumerate(events, 1):
            title = (
                f"{datetime.datetime.fromtimestamp(int(event['timestamp']) // 1000000).strftime('%Y-%m-%d %H:%M:%S')}  "
                f"{event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_TYPE, 'unknown')}"
            )
            res.append(
                {
                    "id": index,
                    "title": title,
                    "subtitle": event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_STACKTRACE),
                    "content": event.get(OtlpKey.ATTRIBUTES, {})
                    .get(SpanAttributes.EXCEPTION_STACKTRACE, "")
                    .split("\n"),
                }
            )

        return self.get_pagination_data(res, validated_request_data)


class MetaConfigInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def get_setup_config_value(self, key: str, bk_biz_id, default=None):
        obj = ApplicationConfig.objects.filter(cc_biz_id=bk_biz_id, key=key).first()
        if obj:
            return json.loads(obj.value)["_data"]
        return default

    def setup(self, bk_biz_id):
        return {
            "guide_url": {
                "access_url": settings.APM_ACCESS_URL,
                "best_practice": settings.APM_BEST_PRACTICE_URL,
                "metric_description": settings.APM_METRIC_DESCRIPTION_URL,
            },
            "index_prefix_name": f"{bk_biz_id}_bkapm_",
            "es_retention_days": {
                "default": DefaultSetupConfig.DEFAULT_ES_RETENTION_DAYS,
                "default_es_max": self.get_setup_config_value(
                    BizConfigKey.DEFAULT_ES_RETENTION_DAYS_MAX,
                    bk_biz_id,
                    DefaultSetupConfig.DEFAULT_ES_RETENTION_DAYS_MAX,
                ),
                "private_es_max": self.get_setup_config_value(
                    BizConfigKey.PRIVATE_ES_RETENTION_DAYS_MAX,
                    bk_biz_id,
                    DefaultSetupConfig.PRIVATE_ES_RETENTION_DAYS_MAX,
                ),
            },
            "es_number_of_replicas": {
                "default": DefaultSetupConfig.DEFAULT_ES_NUMBER_OF_REPLICAS,
                "default_es_max": self.get_setup_config_value(
                    BizConfigKey.DEFAULT_ES_NUMBER_OF_REPLICAS_MAX,
                    bk_biz_id,
                    DefaultSetupConfig.DEFAULT_ES_NUMBER_OF_REPLICAS_MAX,
                ),
                "private_es_max": self.get_setup_config_value(
                    BizConfigKey.PRIVATE_ES_NUMBER_OF_REPLICAS_MAX,
                    bk_biz_id,
                    DefaultSetupConfig.PRIVATE_ES_NUMBER_OF_REPLICAS_MAX,
                ),
            },
        }

    def perform_request(self, validated_request_data):
        plugins = []
        popularity_map = {}
        for plugin_id, popularity in (
            ApplicationRelationInfo.objects.filter(relation_key=Application.PLUGING_KEY)
            .values("relation_value")
            .annotate(count=Count("relation_value"))
            .values_list("relation_value", "count")
        ):
            popularity_map[plugin_id] = popularity

        push_urls = PushUrlResource().request({"bk_biz_id": validated_request_data["bk_biz_id"]})
        push_urls_str = "\n".join(
            str(_("云区域 {} {} [{}]").format(push_url['bk_cloud_id'], push_url['push_url'], ','.join(push_url['tags'])))
            for push_url in push_urls
        )
        for plugin in PluginEnum.get_values():
            plugin_json = plugin.to_json()
            plugin_json["access_md"] = str(plugin_json["access_md"]).format(push_url=push_urls_str)
            plugin_json["popularity"] = popularity_map.get(plugin.id, 0)
            plugins.append(plugin_json)

        return {
            "deployments": [asdict(d) for d in DeploymentEnum.get_values()],
            "languages": [asdict(value) for value in LanguageEnum.get_values()],
            "plugins": plugins,
            "help_md": {plugin.id: Help(plugin.id).get_help_md() for plugin in [Opentelemetry]},
            "setup": self.setup(validated_request_data["bk_biz_id"]),
        }


class IndicesInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    class ResponseSerializer(serializers.Serializer):
        health = serializers.CharField(label="健康状态")
        status = serializers.CharField(label="状态")
        index = serializers.CharField(label="索引名称")
        uuid = serializers.CharField(label="索引uuid")
        pri = serializers.IntegerField(label="主分片数量")
        rep = serializers.IntegerField(label="副分片数量")
        docs_count = serializers.IntegerField(label="文档数量")
        docs_deleted = serializers.IntegerField(label="文档数量")
        store_size = serializers.IntegerField(label="存储大小单位bytes")
        pri_store_size = serializers.IntegerField(label="主分片存储大小")

    many_response_data = True

    TIME_FORMAT_LEN = 11

    def perform_request(self, validated_request_data):
        try:
            application = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        es_index_name = application.trace_result_table_id.replace(".", "_")
        data = api.metadata.es_route(
            {
                "es_storage_cluster": application.es_storage_cluster,
                "url": f"_cat/indices/{es_index_name}_*_*?bytes=b&format=json",
            }
        )
        result = []
        for item in data:
            __, index_name = item["index"].split("v2_", 1)
            __, index_name_time = index_name.split(es_index_name)
            if len(index_name_time) != self.TIME_FORMAT_LEN:
                continue
            result.append({k.replace(".", "_"): v for k, v in item.items()})
        return result


class PushUrlResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    class ResponseSerializer(serializers.Serializer):
        push_url = serializers.CharField(label="push_url")
        tags = serializers.ListField(label="地址标签")
        bk_cloud_id = serializers.IntegerField(label="云区域ID")

    many_response_data = True

    PUSH_URL_CONFIGS = [
        {"tags": ["grpc", "opentelemetry"], "port": "4317", "url": ""},
        {"tags": ["http", "opentelemetry"], "port": "4318", "url": "/v1/traces"},
    ]

    def get_proxy_info(self, bk_biz_id):
        proxy_host_info = []
        try:
            proxy_hosts = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
            for host in proxy_hosts:
                bk_cloud_id = int(host["bk_cloud_id"])
                ip = host.get("conn_ip") or host.get("inner_ip")
                proxy_host_info.append({"ip": ip, "bk_cloud_id": bk_cloud_id})
        except Exception as e:
            logger.exception(e)

        default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
            default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN
        for proxy_ip in default_cloud_display:
            proxy_host_info.insert(0, {"ip": proxy_ip, "bk_cloud_id": 0})
        return proxy_host_info

    def perform_request(self, validated_request_data):
        proxy_host_info = self.get_proxy_info(validated_request_data["bk_biz_id"])
        push_urls = []
        for proxy_host, config in itertools.product(proxy_host_info, self.PUSH_URL_CONFIGS):
            ip = proxy_host["ip"]
            if is_v6(ip):
                ip = f"[{ip}]"
            push_urls.append(
                {
                    "push_url": f"http://{ip}:{config['port']}{config['url']}",
                    "tags": config["tags"],
                    "bk_cloud_id": proxy_host["bk_cloud_id"],
                }
            )
        return push_urls


class QueryBkDataToken(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        return api.apm_api.detail_application(validated_request_data)["bk_data_token"]


class DataViewConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return [
            {
                "id": 1,
                "title": _("分钟数据量"),
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "datasource": "time_series",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": "bk_apm",
                                    "data_type_label": "log",
                                    "table": app.trace_result_table_id.replace(".", "_"),
                                    "metrics": [{"field": "span_name", "method": "COUNT", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [],
                                    "interval": 60,
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
            {
                "id": 2,
                "title": _("日数据量"),
                "type": "graph",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "datasource": "time_series",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": "bk_apm",
                                    "data_type_label": "log",
                                    "table": app.trace_result_table_id.replace(".", "_"),
                                    "metrics": [{"field": "span_name", "method": "COUNT", "alias": "A"}],
                                    "group_by": [],
                                    "display": True,
                                    "where": [],
                                    "interval": 60 * 60 * 24,
                                    "interval_unit": "s",
                                    "time_field": "time",
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            },
        ]


class DataSamplingResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        size = serializers.IntegerField(required=False, label="拉取条数", default=10)
        log_type = serializers.ChoiceField(
            label="日志类型",
            choices=DataSamplingLogTypeChoices.choices(),
        )

    def get_sampling_time(self, data: dict, log_type: str):
        if log_type == DataSamplingLogTypeChoices.TRACE:
            return data.get("datetime", "")
        if log_type == DataSamplingLogTypeChoices.METRIC:
            data = data.get("data", [])
            if len(data) == 0:
                return ""
            return datetime.datetime.fromtimestamp(data[0]["timestamp"], timezone.get_current_timezone()).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    def combine_data(self, app: Application, log_type: str, size: int):
        table_id = getattr(app, f"{log_type}_result_table_id")
        resp = api.metadata.kafka_tail({"table_id": table_id, "size": size})
        if resp:
            return [{"raw_log": log, "sampling_time": self.get_sampling_time(log, log_type)} for log in resp]
        return []

    def perform_request(self, validated_request_data):
        # 获取 App
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取数据
        log_type = validated_request_data["log_type"]
        size = validated_request_data["size"]
        return self.combine_data(app, log_type, size)


class StorageFieldInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        # 获取应用
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取字段信息
        field_data = api.apm_api.query_fields({"bk_biz_id": app.bk_biz_id, "app_name": app.app_name})
        # 获取字段描述信息
        table_data = api.metadata.get_result_table({"table_id": app.trace_result_table_id}).get("field_list", [])
        field_desc_data = {field_info["field_name"]: field_info["description"] for field_info in table_data}
        # 构造响应信息
        return [
            {
                "field_name": key,
                "ch_field_name": field_desc_data.get(key, ""),
                "analysis_field": value == "text",
                "field_type": value,
                "time_field": value == "date",
            }
            for key, value in field_data.items()
        ]


class NoDataStrategyInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(required=True, label="应用ID")

    def get_strategy(self, bk_biz_id: int, app: Application):
        """检测策略存在与否，不存在则创建"""
        # 不分页获取所有已注册的策略
        strategies = resource.strategies.get_strategy_list_v2(bk_biz_id=bk_biz_id, page=0, page_size=0).get(
            "strategy_config_list", []
        )
        strategy_map = {strategy["id"]: strategy for strategy in strategies}
        # 获取数据库存储的策略
        strategy_config, is_created = ApmMetaConfig.objects.get_or_create(
            config_level=ApmMetaConfig.APPLICATION_LEVEL,
            level_key=app.application_id,
            config_key=NODATA_ERROR_STRATEGY_CONFIG_KEY,
            defaults={"config_value": {"id": -1, "notice_group_id": -1}},
        )
        strategy_id = strategy_config.config_value["id"]
        # 匹配则返回
        if strategy_id in strategy_map.keys():
            return strategy_map[strategy_id]
        # 不匹配则创建新策略
        return self.registry_strategy(bk_biz_id, app, strategy_config)

    @classmethod
    def get_notice_group(cls, bk_biz_id: int, app: Application, strategy_config: ApmMetaConfig):
        """获取告警组ID"""
        # 获取告警用户
        notice_receiver = [{"type": "user", "id": get_request_username()}]
        if app.create_user:
            notice_receiver.append({"type": "user", "id": app.create_user})

        # 默认用户组设置为运维组
        strategy_config.config_value["notice_group_id"] = get_or_create_ops_notice_group(bk_biz_id)
        strategy_config.save()
        return strategy_config.config_value["notice_group_id"]

    @classmethod
    def registry_strategy(cls, bk_biz_id: int, app: Application, strategy_config: ApmMetaConfig):
        """创建策略并返回ID"""
        # 获取告警组
        group_id = cls.get_notice_group(bk_biz_id, app, strategy_config)
        metric_table_id = app.metric_result_table_id
        # 初始化策略配置
        metric_id = f"custom.{metric_table_id}.bk_apm_count"
        config = {
            "bk_biz_id": bk_biz_id,
            # 默认关闭
            "is_enabled": False,
            "name": "BKAPM-{}-{}".format(_("无数据告警"), app.app_name),
            "labels": ["BKAPM"],
            "scenario": ApplicationsResultTableLabel.application_check,
            "detects": [
                {
                    "expression": "",
                    "connector": "and",
                    "level": EventSeverity.WARNING,
                    "trigger_config": {
                        "count": 1,
                        "check_window": 5,
                    },
                    "recovery_config": {
                        "check_window": 5,
                    },
                }
            ],
            "items": [
                {
                    "name": "BK_APM_COUNT",
                    "no_data_config": {
                        "is_enabled": False,
                        "continuous": DEFAULT_NO_DATA_PERIOD,
                        "level": EventSeverity.WARNING,
                    },
                    "algorithms": [
                        {
                            "level": EventSeverity.WARNING,
                            "config": [[{"method": "eq", "threshold": "0"}]],
                            "type": AlgorithmType.Threshold,
                            "unit_prefix": "",
                        }
                    ],
                    # TODO result_table_id / metric_id
                    "query_configs": [
                        {
                            "data_source_label": DataSourceLabel.CUSTOM,
                            "data_type_label": DataTypeLabel.TIME_SERIES,
                            "alias": "a",
                            "result_table_id": f"{metric_table_id}",
                            "agg_method": "SUM",
                            "agg_interval": 60,
                            "agg_dimension": [],
                            "agg_condition": [],
                            "metric_field": "bk_apm_count",
                            "unit": "ns",
                            "metric_id": metric_id,
                            "index_set_id": "",
                            "query_string": "*",
                            "custom_event_name": "bk_apm_count",
                            "functions": [],
                            "time_field": "time",
                            "bkmonitor_strategy_id": "bk_apm_count",
                            "alert_name": "bk_apm_count",
                        }
                    ],
                    "target": [],
                }
            ],
            "notice": {
                "user_groups": [group_id],
                "signal": [],
                "options": {
                    "converge_config": {
                        "need_biz_converge": True,
                    },
                    "start_time": "00:00:00",
                    "end_time": "23:59:59",
                },
                "config": {
                    "interval_notify_mode": "standard",
                    "notify_interval": 2 * 60 * 60,
                    "template": DEFAULT_NOTICE_MESSAGE_TEMPLATE,
                },
            },
            "actions": [],
        }
        # 保存策略
        resp = resource.strategies.save_strategy_v2(**config)
        # 存储信息
        strategy_config.config_value = {"id": resp["id"], "notice_group_id": group_id}
        strategy_config.save()
        return resp

    def perform_request(self, validated_request_data):
        # 获取请求信息
        application_id = validated_request_data["application_id"]
        # 获取应用
        try:
            app = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取策略
        strategy = self.get_strategy(app.bk_biz_id, app)
        # 获取告警图表
        alert_graph = {
            "id": 1,
            "title": _("告警数量"),
            "type": "apdex-chart",
            "targets": [
                {
                    "dataType": "event",
                    "datasource": "time_series",
                    "api": "apm_metric.alertQuery",
                    "data": {
                        "bk_biz_id": app.bk_biz_id,
                        "app_name": app.app_name,
                        "strategy_id": strategy["id"],
                    },
                }
            ],
        }
        alert_count = strategy.get("alert_count", 0)
        # 获取告警信息
        strategy_detail = resource.strategies.get_strategy_v2(id=strategy["id"], bk_biz_id=app.bk_biz_id)

        # 响应信息
        return {
            "id": strategy["id"],
            "name": strategy["name"],
            "alert_status": 2 if alert_count > 0 else 1,
            "alert_count": alert_count,
            "alert_graph": alert_graph,
            "is_enabled": strategy["is_enabled"],
            "notice_group": [
                {"id": group["id"], "name": group["name"]}
                for group in strategy_detail["notice"].get("user_group_list", [])
            ],
        }


class NoDataStrategyStatusResource(Resource):
    is_enabled = None

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")

    def perform_request(self, validated_request_data):
        # 获取请求信息
        application_id = validated_request_data["application_id"]
        # 获取应用及配置信息
        try:
            app = Application.objects.get(application_id=application_id)
            config = ApmMetaConfig.objects.get(
                config_level=ApmMetaConfig.APPLICATION_LEVEL,
                level_key=app.application_id,
                config_key=NODATA_ERROR_STRATEGY_CONFIG_KEY,
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        except ApmMetaConfig.DoesNotExist:
            raise ValueError(_("配置信息不存在"))
        strategy_id = config.config_value["id"]
        # 已注册的策略
        strategies = resource.strategies.get_strategy_list_v2(bk_biz_id=app.bk_biz_id).get("strategy_config_list", [])
        strategy_ids = [strategy["id"] for strategy in strategies]
        # 检测策略存在情况，不存在则创建
        if strategy_id not in strategy_ids:
            strategy_id = NoDataStrategyInfoResource.registry_strategy(app.bk_biz_id, app, config)["id"]
        # 更新策略状态
        resource.strategies.update_partial_strategy_v2(
            bk_biz_id=app.bk_biz_id,
            ids=[strategy_id],
            edit_data={"is_enabled": self.is_enabled},
        )
        return


class NoDataStrategyEnableResource(NoDataStrategyStatusResource):
    is_enabled = True


class NoDataStrategyDisableResource(NoDataStrategyStatusResource):
    is_enabled = False


class DimensionDataResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(required=True, label="应用ID")
        table_id = serializers.CharField(required=True, label="表ID")
        metric_id = serializers.CharField(required=True, label="指标ID")
        dimension_fields = serializers.ListField(required=True, label="维度字段")

    def dimension_count(self, dimension_field: str, app: Application, metric_id: str, table_id: str, data_map: dict):
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(minutes=DEFAULT_DIMENSION_DATA_PERIOD)
        query_dict = {
            "dimension_field": dimension_field,
            "bk_biz_id": app.bk_biz_id,
            "start_time": int(start_time.timestamp()),
            "end_time": int(end_time.timestamp()),
            "query_configs": [
                {
                    "data_source_label": "custom",
                    "metrics": [{"field": metric_id, "method": "COUNT", "alias": "A"}],
                    "table": table_id,
                    "group_by": [],
                    "where": [],
                }
            ],
        }
        resp = resource.grafana.dimension_count_unify_query(query_dict)
        data_map[dimension_field] = resp

    def perform_request(self, validated_request_data):
        # 获取请求
        application_id = validated_request_data["application_id"]
        table_id = validated_request_data["table_id"]
        dimension_fields = validated_request_data["dimension_fields"]
        metric_id = validated_request_data["metric_id"]
        try:
            app = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取维度
        dimension_data = resource.custom_report.get_custom_time_series_latest_data_by_fields(
            result_table_id=table_id, fields_list=dimension_fields + [metric_id]
        ).get("fields_value", {})
        count_map = {}
        th_list = [
            InheritParentThread(target=self.dimension_count, args=(field, app, metric_id, table_id, count_map))
            for field in dimension_data.keys()
        ]
        run_threads(th_list)
        # 响应
        return {"data": dimension_data, "count": count_map}


class ModifyMetricResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class DimensionSerializer(serializers.Serializer):
            field = serializers.CharField(label="维度字段")
            description = serializers.CharField(label="维度描述", allow_blank=True)

        application_id = serializers.IntegerField(required=True, label="应用ID")
        metric_id = serializers.CharField(label="指标ID")
        metric_description = serializers.CharField(label="指标描述", allow_blank=True)
        metric_unit = serializers.CharField(label="指标单位", allow_blank=True)
        dimensions = serializers.ListField(label="维度", child=DimensionSerializer(), allow_empty=True)

    def get_query_config(self, app: Application, metric_id: str, metric_desc: str, metric_unit: str, dimensions: list):
        query_config = {
            "bk_biz_id": app.bk_biz_id,
            "app_name": app.app_name,
            "field_list": [
                {
                    "field_name": metric_id,
                    "field_type": ResultTableField.FIELD_TYPE_FLOAT,
                    "tag": ResultTableField.FIELD_TAG_METRIC,
                    "description": metric_desc,
                    "unit": metric_unit,
                }
            ],
        }
        query_config["field_list"].extend(
            [
                {
                    "field_name": dimension["field"],
                    "field_type": ResultTableField.FIELD_TYPE_STRING,
                    "tag": ResultTableField.FIELD_TAG_DIMENSION,
                    "description": dimension["description"],
                    "unit": "",
                }
                for dimension in dimensions
            ]
        )
        return query_config

    def perform_request(self, validated_request_data):
        # 获取请求
        application_id = validated_request_data["application_id"]
        metric_id = validated_request_data["metric_id"]
        metric_description = validated_request_data["metric_description"]
        metric_unit = validated_request_data["metric_unit"]
        dimensions = validated_request_data["dimensions"]
        # 获取应用
        try:
            app = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 更新
        query_config = self.get_query_config(app, metric_id, metric_description, metric_unit, dimensions)
        api.apm_api.update_metric_fields(query_config)
        return


class QueryEndpointStatisticsResource(PageListResource):
    span_keys = ["db.system", "http.url", "messaging.system", "rpc.system"]

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="summary", name=_("请求内容"), min_width=120),
            StringTableFormat(id="request_count", name=_("请求次数"), sortable=True, width=110),
            NumberTableFormat(
                id="average", name=_("平均耗时"), checked=True, unit="ms", decimal=0, sortable=True, width=110
            ),
            NumberTableFormat(
                id="max_elapsed", name=_("最大耗时"), checked=True, unit="ms", decimal=0, sortable=True, width=110
            ),
            NumberTableFormat(
                id="min_elapsed", name=_("最小耗时"), checked=True, unit="ms", decimal=0, sortable=True, width=110
            ),
            LinkListTableFormat(
                id="operation",
                name=_("操作"),
                checked=True,
                disabled=True,
                width=90,
                links=[
                    LinkTableFormat(
                        id="trace",
                        name=_("调用链"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_tiem={start_time}&end_tiem={end_time}'
                        + '&listType=span',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                    LinkTableFormat(
                        id="statistics",
                        name=_("统计"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_tiem={start_time}&end_tiem={end_time}'
                        + '&listType=interfaceStatistics',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                ],
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        filter_params = serializers.DictField(required=False, label="过滤参数", default={})
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )
        span_keys = serializers.ListSerializer(child=serializers.CharField(), required=False, label="分类过滤")

    def build_filter_params(self, filters):
        res = []
        for k, v in filters.items():
            if v == "undefined":
                continue

            res.append({"key": k, "op": "=", "value": v if isinstance(v, list) else [v]})

        return res

    def group_by(self, data, get_key):
        res = {}
        for item in data:
            key = get_key(item)
            if not key:
                continue

            if key in res:
                res[key].append(item)
            else:
                res[key] = [item]

        return res

    def add_extra_params(self, params):
        return {
            "bk_biz_id": params.get("bk_biz_id"),
            "app_name": params.get("app_name"),
            "start_time": datetime.datetime.fromtimestamp(params.get("start_time")).strftime("%Y-%m-%d+%H:%M:%S"),
            "end_time": datetime.datetime.fromtimestamp(params.get("end_time")).strftime("%Y-%m-%d+%H:%M:%S"),
        }

    def get_pagination_data(self, data, params, column_type=None, skip_sorted=False):
        items = super(QueryEndpointStatisticsResource, self).get_pagination_data(data, params, column_type)

        # url 拼接
        for item in items["data"]:
            tmp = {}
            filter_http_url = ""
            if item["filter_key"] in ["attributes.http.url"]:
                filter_http_url = f'&query=attributes.http.url:"{item["summary"]}"'
            else:
                tmp[item.get("filter_key")] = {
                    "selectedCondition": {"label": "=", "value": "equal"},
                    "isInclude": True,
                    "selectedConditionValue": [item.get("summary")],
                }
            service_name = params.get("filter_params", {}).get(
                OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)
            )
            if service_name:
                tmp[OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)] = {
                    "selectedCondition": {"label": "=", "value": "equal"},
                    "isInclude": True,
                    "selectedConditionValue": [service_name],
                }

            for i in item["operation"]:
                i["url"] = i["url"] + '&conditionList=' + json.dumps(tmp)
                if filter_http_url:
                    i["url"] += filter_http_url

        return items

    def perform_request(self, validated_data):
        """
        根据app_name service_name查询span 遍历span然后取db.system,http.method..等等这些字段 没有就为空
        """
        if validated_data.get("span_keys", []):
            self.span_keys = validated_data.get("span_keys")
        filter_params = self.build_filter_params(validated_data["filter_params"])
        ComponentHandler.build_component_filter_params(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            filter_params,
            validated_data.get("service_params"),
            validated_data.get("component_instance_id"),
        )

        spans = api.apm_api.query_span(
            {
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "start_time": validated_data["start_time"],
                "end_time": validated_data["end_time"],
                "filter_params": filter_params,
            }
        )

        is_component = ComponentHandler.is_component(validated_data.get("service_params"))

        uri_configs_mappings = None
        if not is_component:
            # http类服务可以设置uri归类
            uri_configs_mappings = self.group_by(
                UriServiceRelation.objects.filter(
                    bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
                ),
                lambda i: i.service_name,
            )

        summary_mappings = defaultdict(list)
        for span in spans:
            summary = None
            filter_key = None
            if not is_component:
                # http 类服务summary处理
                if (
                    SpanAttributes.HTTP_URL in span[OtlpKey.ATTRIBUTES]
                    and ResourceAttributes.SERVICE_NAME in span[OtlpKey.RESOURCE]
                ):
                    # http span需要根据服务配置uri进行汇总
                    url = span["attributes"][SpanAttributes.HTTP_URL]

                    # 取此服务的uri配置
                    uri_configs = uri_configs_mappings.get(span[OtlpKey.RESOURCE][ResourceAttributes.SERVICE_NAME], [])
                    for uri_config in uri_configs:
                        if re.match(uri_config.uri, url):
                            summary = SpanHandler.generate_uri(urlparse(url))
                            filter_key = "http.url"

                if not summary:
                    # 否则取span的分析字段
                    summary = next(
                        iter(
                            span[OtlpKey.ATTRIBUTES][attr]
                            for attr in self.span_keys
                            if attr in span[OtlpKey.ATTRIBUTES]
                        ),
                        None,
                    )

                if not summary:
                    continue
            else:
                # 组件类服务summary处理
                summary = span[OtlpKey.SPAN_NAME]
            if not filter_key:
                filter_key = next(
                    iter(
                        attr
                        for attr in self.span_keys
                        if attr in span[OtlpKey.ATTRIBUTES] and span[OtlpKey.ATTRIBUTES][attr]
                    ),
                    None,
                )
            if filter_key:
                filter_key = OtlpKey.ATTRIBUTES + "." + filter_key
                summary = DEFAULT_SPLIT_SYMBOL.join([filter_key, summary])
            summary_mappings[summary].append(span)

        res = []
        for summary, items in summary_mappings.items():
            intervals = [int(str(i["end_time"])[:-3]) - int(str(i["start_time"])[:-3]) for i in items]
            tmp = str(summary).split(DEFAULT_SPLIT_SYMBOL, maxsplit=1)
            filter_key = OtlpKey.SPAN_NAME
            if len(tmp) == 2:
                summary = tmp[-1]
                filter_key = tmp[0]
            res.append(
                {
                    "summary": summary,
                    "filter_key": filter_key,
                    "request_count": len(items),
                    "average": round(sum(intervals) / len(intervals), 2),
                    "max_elapsed": max(intervals),
                    "min_elapsed": min(intervals),
                    "operation": {"trace": _("调用链"), "statistics": _("统计")},
                }
            )
        return self.get_pagination_data(res, validated_data)


class QueryExceptionDetailEventResource(PageListResource):
    UNKNOWN = "unknown"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        exception_type = serializers.CharField(label="异常类型", required=False, default="")
        filter_params = serializers.DictField(required=False, label="过滤参数", default={})
        keyword = serializers.CharField(required=False, default="", label="关键词", allow_blank=True)
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]

        for key, value in filter_dict.items():
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})

        return result

    def perform_request(self, validated_data):
        filter_params = self.build_filter_params(validated_data["filter_params"])
        ComponentHandler.build_component_filter_params(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            filter_params,
            validated_data.get("service_params"),
            validated_data.get("component_instance_id"),
        )

        query_dict = {
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
            "name": ["exception"],
            "filter_params": filter_params,
        }
        exception_spans = api.apm_api.query_span(query_dict)
        res = []
        for span in exception_spans:
            # 异常信息有两个来源: events.attributes.exception_stacktrace or status.message
            subtitle = span.get("status", {}).get("message")
            if span["events"]:
                for event in span["events"]:
                    exception_type = event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN)
                    stacktrace = (
                        event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_STACKTRACE, "").split("\n")
                    )
                    if validated_data["exception_type"]:
                        if exception_type == validated_data["exception_type"]:
                            res.append(
                                {
                                    "title": f"{span_time_strft(event['timestamp'])}  {exception_type}",
                                    "subtitle": subtitle,
                                    "content": stacktrace,
                                }
                            )
                    else:
                        # 无过滤条件 -> 显示全部
                        res.append(
                            {
                                "title": f"{span_time_strft(event['timestamp'])}  {exception_type}",
                                "subtitle": subtitle,
                                "content": stacktrace,
                            }
                        )
            else:
                if subtitle:
                    res.append(
                        {
                            "title": f"{span_time_strft(span['start_time'])}  {self.UNKNOWN}",
                            "subtitle": subtitle,
                            "content": [],
                        }
                    )

        for index, r in enumerate(res, 1):
            r["id"] = index

        return self.get_pagination_data(res, validated_data)


class QueryExceptionEndpointResource(Resource):
    EXCEPTION_NAME = "exception"
    UNKNOWN_EXCEPTION = "unknown"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        exception_type = serializers.CharField(label="异常类型", required=False, default="")
        filter_params = serializers.DictField(required=False, label="过滤条件", default={})
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})
        return result

    def perform_request(self, validated_data):
        filter_params = self.build_filter_params(validated_data["filter_params"])
        ComponentHandler.build_component_filter_params(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            filter_params,
            validated_data.get("service_params"),
            validated_data.get("component_instance_id"),
        )

        query_dict = {
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
            "filter_params": filter_params,
        }

        exception_spans = api.apm_api.query_span(query_dict)
        has_event_trace_id = [i["trace_id"] for i in exception_spans if i["events"]]
        indentify_mapping = {}
        colors = ServiceColorClassifier()

        for span in exception_spans:
            service_name = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, self.UNKNOWN_EXCEPTION)
            span_name = span[OtlpKey.SPAN_NAME]

            if span["events"]:
                for event in span["events"]:
                    exception_type = event[OtlpKey.ATTRIBUTES].get(
                        SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN_EXCEPTION
                    )
                    if (
                        validated_data["exception_type"] and exception_type == validated_data["exception_type"]
                    ) or not validated_data["exception_type"]:
                        indentify = f"{service_name}: {span_name}"
                        if indentify in indentify_mapping:
                            indentify_mapping[indentify]["value"] += 1
                        else:
                            color = colors.next(indentify)

                            indentify_mapping[indentify] = {
                                "name": indentify,
                                "service_name": service_name,
                                "value": 1,
                                "color": color,
                                "borderColor": color,
                            }
            else:
                exception_type = self.UNKNOWN_EXCEPTION
                if (
                    validated_data["exception_type"]
                    and exception_type == validated_data["exception_type"]
                    and span["trace_id"] not in has_event_trace_id
                ) or not validated_data["exception_type"]:
                    indentify = f"{service_name}: {span_name}"
                    if indentify in indentify_mapping:
                        indentify_mapping[indentify]["value"] += 1
                    else:
                        color = colors.next(indentify)

                        indentify_mapping[indentify] = {
                            "name": indentify,
                            "service_name": service_name,
                            "value": 1,
                            "color": color,
                            "borderColor": color,
                        }

        return {"name": _("服务+接口"), "data": list(indentify_mapping.values())}


class QueryExceptionTypeGraphResource(Resource):
    EXCEPTION_NAME = "exception"
    INTERVAL_COUNT = 15
    UNKNOWN_EXCEPTION_TYPE = "unknown"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        exception_type = serializers.CharField(label="异常类型", required=False, default="")
        filter_params = serializers.DictField(required=False, label="过滤条件", default={})
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})
        return result

    def perform_request(self, validated_data):
        filter_params = self.build_filter_params(validated_data["filter_params"])
        ComponentHandler.build_component_filter_params(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            filter_params,
            validated_data.get("service_params"),
            validated_data.get("component_instance_id"),
        )

        query_dict = {
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
            "filter_params": filter_params,
        }

        exception_spans = api.apm_api.query_span(query_dict)
        timestamp_mapping = {}
        has_event_trace_id = [i["trace_id"] for i in exception_spans if i["events"]]

        for span in exception_spans:
            if span["events"]:
                for event in span["events"]:
                    exception_type = event[OtlpKey.ATTRIBUTES].get(
                        SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN_EXCEPTION_TYPE
                    )
                    if validated_data["exception_type"]:
                        if exception_type == validated_data["exception_type"]:
                            timestamp = self.convert_timestamp(span["start_time"])
                            if timestamp in timestamp_mapping:
                                timestamp_mapping[timestamp][0] += 1
                            else:
                                timestamp_mapping[timestamp] = [1, timestamp]
                    else:
                        timestamp = self.convert_timestamp(span["start_time"])
                        if timestamp in timestamp_mapping:
                            timestamp_mapping[timestamp][0] += 1
                        else:
                            timestamp_mapping[timestamp] = [1, timestamp]
            else:
                exception_type = self.UNKNOWN_EXCEPTION_TYPE
                if validated_data["exception_type"]:
                    if (
                        exception_type == validated_data["exception_type"]
                        and span["trace_id"] not in has_event_trace_id
                    ):
                        timestamp = self.convert_timestamp(span["start_time"])
                        if timestamp in timestamp_mapping:
                            timestamp_mapping[timestamp][0] += 1
                        else:
                            timestamp_mapping[timestamp] = [1, timestamp]
                else:
                    if span["trace_id"] not in has_event_trace_id:
                        timestamp = self.convert_timestamp(span["start_time"])
                        if timestamp in timestamp_mapping:
                            timestamp_mapping[timestamp][0] += 1
                        else:
                            timestamp_mapping[timestamp] = [1, timestamp]

        return {
            "metrics": [],
            "series": [
                {
                    "alias": "_result_",
                    "datapoints": sorted(timestamp_mapping.values(), key=lambda i: i[-1]),
                    "dimensions": {},
                    "metric_field": "_result_",
                    "target": "",
                    "type": "line",
                    "unit": "",
                }
            ]
            if timestamp_mapping
            else [],
        }

    def convert_timestamp(self, timestamp):
        # 16位时间戳转13位&忽略秒数
        timestamp = int(str(timestamp)[:-3])
        return int(str(timestamp)[:-4] + "0000")


class InstanceDiscoverKeysResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, data):
        app = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not app:
            raise ValueError(_("应用不存在"))

        # 固定字段
        know_fixed_fields = InstanceDiscoverKeys.get_list()
        # 用户所有上报字段
        user_fields = InstanceHandler.get_span_fields(app)

        last_span = SpanHandler.get_lastly_span(data["bk_biz_id"], data["app_name"])

        return [
            {**i, "value": SpanHandler.get_span_field_value(last_span, i["name"])}
            for i in list({v["id"]: v for v in (know_fixed_fields + user_fields)}.values())
        ]


class CustomServiceListResource(PageListResource):
    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="name", name=_("服务名称")),
            StringTableFormat(id="type", name=_("远程服务类型")),
            NumberTableFormat(id="host_match_count", name=_("域名匹配"), sortable=True),
            NumberTableFormat(id="uri_match_count", name=_("URI匹配"), sortable=True),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        page = serializers.IntegerField(required=False)
        page_size = serializers.IntegerField(required=False)
        sort = serializers.CharField(required=False)

    class CustomServiceResponseSerializer(serializers.ModelSerializer):
        rule = serializers.JSONField()

        class Meta:
            model = ApplicationCustomService
            fields = "__all__"

    def perform_request(self, validated_data):
        query = ApplicationCustomService.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        )
        data = self.CustomServiceResponseSerializer(instance=query, many=True).data

        # 默认获取最近一天数据
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=1)

        spans = api.apm_api.query_span(
            bk_biz_id=validated_data["bk_biz_id"],
            app_name=validated_data["app_name"],
            start_time=int(start_time.timestamp()),
            end_time=int(end_time.timestamp()),
            filter_params=[{"key": "attributes.peer.service", "op": "exists"}],
        )

        for item in data:
            if item["match_type"] == CustomServiceMatchType.AUTO:
                count_mapping = defaultdict(lambda: 0)
                for i in spans:
                    url = i.get("attributes", {}).get(SpanAttributes.HTTP_URL)
                    if Matcher.match_auto(item["rule"], url):
                        count_mapping[url] += 1

                uri_match_count = len(count_mapping.keys())
                host_match_count = len(count_mapping.keys())
            else:
                count_mapping = defaultdict(lambda: {"host": 0, "uri": 0})
                for i in spans:
                    http_url = i.get("attributes", {}).get(SpanAttributes.HTTP_URL)
                    if not http_url:
                        continue

                    url = urlparse(http_url)
                    host_match = Matcher.manual_match_host(item["rule"].get("host"), url.hostname)
                    uri_match = Matcher.manual_match_uri(item["rule"].get("path"), url.path)
                    if host_match:
                        count_mapping[http_url]["host"] += 1
                    if uri_match:
                        count_mapping[http_url]["uri"] += 1

                host_match_count = sum(1 for i in count_mapping.values() if i["host"])
                uri_match_count = sum(1 for i in count_mapping.values() if i["uri"])

            item["icon"] = get_icon(item["type"])
            item["uri_match_count"] = uri_match_count
            item["host_match_count"] = host_match_count

        return self.get_pagination_data(data, validated_data)


class CustomServiceConfigResource(Resource):
    class RequestSerializer(CustomServiceConfigSerializer):
        id = serializers.IntegerField(required=False)

    def perform_request(self, validated_data):
        if not validated_data.get("id"):
            # 新增
            self.validate_name(validated_data)
            ApplicationCustomService.objects.create(**validated_data)
        else:
            # 更新
            _id = validated_data.pop("id")
            self.validate_name(validated_data, _id)
            ApplicationCustomService.objects.filter(id=_id).update(**validated_data)

        from apm_web.tasks import update_application_config

        application = Application.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        ).first()
        update_application_config.delay(application.application_id)

    def validate_name(self, validated_data, config_id=None):
        if validated_data["match_type"] == CustomServiceMatchType.AUTO:
            validated_data["name"] = None
            q = Q()
            if config_id:
                q = Q(id=config_id)

            if (
                ApplicationCustomService.objects.filter(~q)
                .filter(
                    rule=validated_data["rule"],
                    bk_biz_id=validated_data["bk_biz_id"],
                    app_name=validated_data["app_name"],
                )
                .exists()
            ):
                raise ValueError(_("匹配规则已存在"))

        else:
            if not validated_data.get("name"):
                raise ValueError(_("没有传递服务名称"))
            q = Q()
            if config_id:
                q = Q(id=config_id)

            if (
                ApplicationCustomService.objects.filter(~q)
                .filter(
                    name=validated_data["name"],
                    bk_biz_id=validated_data["bk_biz_id"],
                    app_name=validated_data["app_name"],
                )
                .exists()
            ):
                raise ValueError(_("服务名称已存在"))


class DeleteCustomSeriviceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField()

    def perform_request(self, validated_data):
        query = ApplicationCustomService.objects.filter(id=validated_data["id"])
        instance = query.first()
        query.delete()

        from apm_web.tasks import update_application_config

        application = Application.objects.filter(bk_biz_id=instance.bk_biz_id, app_name=instance.app_name).first()
        update_application_config.delay(application.application_id)


class CustomServiceMatchListResource(Resource):
    TIME_DELTA = 1

    class RequestSerializer(CustomServiceConfigSerializer):
        urls_source = serializers.ListSerializer(child=serializers.CharField())

    def perform_request(self, validated_data):
        urls = validated_data["urls_source"]
        res = set()
        for item in urls:
            if not item:
                continue
            url = urlparse(item)
            if validated_data["match_type"] == CustomServiceMatchType.AUTO:
                is_match = Matcher.match_auto(validated_data["rule"], item)
                if is_match:
                    res.add(f"{item}")
            else:
                predicates = []
                if url.hostname and "host" in validated_data["rule"]:
                    predicates.append(Matcher.manual_match_host(validated_data["rule"].get("host"), url.hostname))
                if url.path and "path" in validated_data["rule"]:
                    predicates.append(Matcher.manual_match_uri(validated_data["rule"].get("path"), url.path))
                if url.query and "params" in validated_data["rule"]:
                    predicates.append(Matcher.manual_match_params(validated_data["rule"].get("params"), url.query))
                if predicates and all(predicates):
                    res.add(f"{item}")

        return list(res)


class CustomServiceDataViewResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        database = app.metric_result_table_id.split(".")[0]
        return [
            {
                "id": 1,
                "title": _("分钟数据量"),
                "type": "graph",
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 6},
                "targets": [
                    {
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                        "datasource": "time_series",
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "data_source_label": "custom",
                                    "data_type_label": "time_series",
                                    "table": f"{database}.__default__",
                                    "metrics": [{"field": "bk_apm_duration", "method": "COUNT", "alias": "A"}],
                                    "group_by": ["peer_service"],
                                    "display": True,
                                    "where": [{"key": "peer_service", "method": "neq", "value": [""]}],
                                    "interval": "auto",
                                    "interval_unit": "s",
                                    "time_field": None,
                                    "filter_dict": {},
                                    "functions": [],
                                }
                            ],
                        },
                    }
                ],
                "options": {"time_series": {"type": "bar"}},
            }
        ]


class CustomServiceDataSourceResource(Resource):
    TIME_DELTA = 1

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        type = serializers.ChoiceField(choices=CustomServiceType.choices())

    def perform_request(self, data):
        app = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not app:
            raise ValueError(_("应用不存在"))

        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=self.TIME_DELTA)

        if data["type"] == CustomServiceType.HTTP:
            return SpanHandler.get_span_urls(app, start_time, end_time)

        return None


class ListEsClusterGroupsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")

    def perform_request(self, data):
        cluster_groups = api.log_search.bk_log_search_cluster_groups(bk_biz_id=data["bk_biz_id"])
        return cluster_groups


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, data):
        app = Application.objects.filter(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"]).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(data['app_name']))
        Application.delete_plugin_config(app.application_id)
        api.apm_api.delete_application(application_id=app.application_id)
        app.delete()
        return True


class GETDataEncodingResource(Resource):
    def perform_request(self, data):
        data = EncodingsEnum.get_choices_list_dict()
        return data
