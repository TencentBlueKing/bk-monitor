"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import StatusCode
from rest_framework import serializers

from api.cmdb.define import Business
from apm_web.constants import (
    APM_APPLICATION_DEFAULT_METRIC,
    DB_SYSTEM_TUPLE,
    DEFAULT_APM_APP_QPS,
    DEFAULT_DB_CONFIG,
    DEFAULT_DIMENSION_DATA_PERIOD,
    DEFAULT_NO_DATA_PERIOD,
    DEFAULT_TRACE_VIEW_CONFIG,
    NODATA_ERROR_STRATEGY_CONFIG_KEY,
    TRPC_TRACE_VIEW_CONFIG,
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
    StorageStatus,
    TopoNodeKind,
    nodata_error_strategy_config_mapping,
)
from apm_web.db.db_utils import build_filter_params, get_service_from_params
from apm_web.handlers import metric_group
from apm_web.handlers.application_handler import ApplicationHandler
from apm_web.handlers.backend_data_handler import telemetry_handler_registry
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.db_handler import DbComponentHandler
from apm_web.handlers.endpoint_handler import EndpointHandler
from apm_web.handlers.instance_handler import InstanceHandler
from apm_web.handlers.metric_group import MetricHelper
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.handlers.span_handler import SpanHandler
from apm_web.handlers.strategy_group import (
    BaseStrategyGroup,
    GroupType,
    StrategyGroupRegistry,
)
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
)
from apm_web.service.resources import CMDBServiceTemplateResource
from apm_web.service.serializers import (
    AppServiceRelationSerializer,
    LogServiceRelationOutputSerializer,
)
from apm_web.topo.handle.relation.relation_metric import RelationMetricHandler
from apm_web.trace.service_color import ServiceColorClassifier
from apm_web.utils import get_interval_number, span_time_strft
from bkm_space.api import SpaceApi
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils import group_by
from bkmonitor.utils.ip import is_v6
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.user import (
    get_backend_username,
    get_global_user,
    get_request_username,
)
from common.log import logger
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE, EventSeverity
from constants.apm import (
    FlowType,
    FormatType,
    OtlpKey,
    OtlpProtocol,
    SpanStandardField,
    StandardFieldCategory,
    TailSamplingSupportMethod,
    TelemetryDataType,
)
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import ApplicationsResultTableLabel, DataSourceLabel, DataTypeLabel
from constants.result_table import ResultTableField
from core.drf_resource import Resource, api, resource
from monitor.models import ApplicationConfig
from monitor_web.constants import AlgorithmType
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    LinkListTableFormat,
    LinkTableFormat,
    NumberTableFormat,
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
        # ↓ datasource_option 在创建时 Trace / Log 都使用这个集群配置
        datasource_option = DatasourceOptionSerializer(required=False)
        # ↓ Log-Trace 配置 目前页面上没有开放
        plugin_config = PluginConfigSerializer(required=False)
        # ↓ 四个 Module 的开关
        enabled_profiling = serializers.BooleanField(label="是否开启 Profiling 功能", required=True)
        enabled_trace = serializers.BooleanField(label="是否开启 Trace 功能", required=True)
        enabled_metric = serializers.BooleanField(label="是否开启 Metric 功能", required=True)
        enabled_log = serializers.BooleanField(label="是否开启 Log 功能", required=True)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = Application
            fields = "__all__"

        def to_representation(self, instance):
            data = super().to_representation(instance)
            application = Application.objects.filter(application_id=instance.application_id).first()
            data["plugin_config"] = application.plugin_config
            return data

    def perform_request(self, validated_request_data):
        if Application.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).exists():
            raise ValueError(_("应用名称: {}已被创建").format(validated_request_data["app_name"]))

        if settings.ENABLE_MULTI_TENANT_MODE:
            bk_tenant_id = get_request_tenant_id()
        else:
            bk_tenant_id = DEFAULT_TENANT_ID
        app = Application.create_application(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=validated_request_data["app_alias"],
            description=validated_request_data["description"],
            plugin_id=validated_request_data["plugin_id"],
            deployment_ids=validated_request_data["deployment_ids"],
            language_ids=validated_request_data["language_ids"],
            enabled_profiling=validated_request_data["enabled_profiling"],
            enabled_trace=validated_request_data["enabled_trace"],
            enabled_metric=validated_request_data["enabled_metric"],
            enabled_log=validated_request_data["enabled_log"],
            # ↓ 两个可选项
            storage_options=validated_request_data.get("datasource_option"),
            plugin_config=validated_request_data.get("plugin_config"),
        )

        from apm_web.tasks import APMEvent, report_apm_application_event

        switch_on_data_sources = app.get_data_sources()
        report_apm_application_event.delay(
            validated_request_data["bk_biz_id"],
            app.application_id,
            apm_event=APMEvent.APP_CREATE,
            data_sources=switch_on_data_sources,
        )
        return app


class CheckDuplicateNameResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称", max_length=50)

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

    class ApplicationInfoResponseSerializer(serializers.ModelSerializer):
        class Meta:
            ref_name = "list_application_info"
            model = Application
            fields = "__all__"

    def perform_request(self, validated_request_data):
        # 过滤掉没有 metricTable 和 traceTable 的应用(接入中应用)
        bk_biz_id = validated_request_data["bk_biz_id"]
        qs = Application.objects.filter(bk_biz_id=bk_biz_id).filter(Application.q_filter_create_finished())
        apps = self.ApplicationInfoResponseSerializer(instance=qs, many=True).data
        app_ids = [str(app["application_id"]) for app in apps]
        amc_dict = dict(
            ApmMetaConfig.objects.filter(
                config_level=ApmMetaConfig.APPLICATION_LEVEL,
                level_key__in=app_ids,
                config_key=Application.TRACE_VIEW_CONFIG_KEY,
            ).values_list("level_key", "config_value")
        )
        biz_trpc_apps = settings.APM_TRPC_APPS.get(str(bk_biz_id)) or []
        for app in apps:
            app_name = app["app_name"]
            app_id_str = str(app["application_id"])
            if app_id_str in amc_dict:
                app["view_config"] = amc_dict[app_id_str]
            else:
                app["view_config"] = TRPC_TRACE_VIEW_CONFIG if app_name in biz_trpc_apps else DEFAULT_TRACE_VIEW_CONFIG
        return apps


class ApplicationInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.CharField(
            label="数据源类型", max_length=255, default=TelemetryDataType.TRACE.value
        )

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

        def handle_event_config(self, instance, data):
            if Application.EVENT_CONFIG_KEY not in data:
                instance.set_init_event_config()
                data[Application.EVENT_CONFIG_KEY] = instance.event_config

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
            data = super().to_representation(instance)
            data["es_storage_index_name"] = instance.trace_result_table_id.replace(".", "_")
            for config in instance.get_all_config():
                data[config.config_key] = config.config_value

            # 处理apdex配置
            self.handle_apdex_config(instance, data)
            # 处理实例名配置
            self.handle_instance_name_config(instance, data)
            # 处理存储信息配置
            # self.handle_es_storage_shards(instance, data)
            # 处理采样配置
            self.handle_sampler_config(instance, data)
            # 处理维度配置
            # self.handle_dimension_config(instance, data)
            self.handle_event_config(instance, data)
            data["plugin_id"] = instance.plugin_id
            data["deployment_ids"] = instance.deployment_ids
            data["language_ids"] = instance.language_ids
            data["no_data_period"] = instance.no_data_period
            # db 类型配置
            data["application_db_system"] = DB_SYSTEM_TUPLE
            # 补充 db 默认配置
            if Application.DB_CONFIG_KEY not in data:
                data[Application.DB_CONFIG_KEY] = [DEFAULT_DB_CONFIG]
            # 补充 QPS 默认配置
            if Application.QPS_CONFIG_KEY not in data:
                data[Application.QPS_CONFIG_KEY] = DEFAULT_APM_APP_QPS
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
        if start_time and end_time:
            data["trace_data_status"] = DataStatus.NO_DATA
            if ApplicationHandler.have_data(application, start_time, end_time):
                data["trace_data_status"] = DataStatus.NORMAL

        # 增加一个信息给到页面，是否需要提供尾部采样的选项。
        # 如果没有 bk base 等相关配置，则不提供尾部采样选项
        data["is_enabled_tail_sampling"] = bool(settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID)
        return data


class OperateDataSourceSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(label="应用id")
    type = serializers.ChoiceField(label="开启/暂停类型", choices=TelemetryDataType.choices(), required=True)


class StartResource(Resource):
    RequestSerializer = OperateDataSourceSerializer

    @classmethod
    def translate_data_status_when_start(cls, data_status):
        return DataStatus.NO_DATA if data_status == DataStatus.DISABLED else data_status

    @atomic
    def perform_request(self, validated_data):
        try:
            application = Application.objects.get(application_id=validated_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        if validated_data["type"] == TelemetryDataType.TRACE.value:
            application.is_enabled_trace = True
            application.trace_data_status = self.translate_data_status_when_start(application.trace_data_status)
            Application.start_plugin_config(validated_data["application_id"])
        elif validated_data["type"] == TelemetryDataType.PROFILING.value:
            application.is_enabled_profiling = True
            application.profiling_data_status = self.translate_data_status_when_start(application.profiling_data_status)
        elif validated_data["type"] == TelemetryDataType.METRIC.value:
            application.is_enabled_metric = True
            application.metric_data_status = self.translate_data_status_when_start(application.metric_data_status)
        elif validated_data["type"] == TelemetryDataType.LOG.value:
            application.is_enabled_log = True
            application.log_data_status = self.translate_data_status_when_start(application.log_data_status)
        else:
            raise ValueError(_("不支持的data_source: {}").format(validated_data["type"]))

        res = api.apm_api.start_application(
            application_id=validated_data["application_id"], type=validated_data["type"]
        )

        application.is_enabled = True
        application.save()

        from apm_web.tasks import APMEvent, report_apm_application_event

        switch_on_data_sources = application.get_data_sources()
        report_apm_application_event.delay(
            application.bk_biz_id,
            application.application_id,
            apm_event=APMEvent.APP_UPDATE,
            data_sources=switch_on_data_sources,
            updated_telemetry_types=[validated_data["type"]],
        )
        return res


class StopResource(Resource):
    RequestSerializer = OperateDataSourceSerializer

    @atomic
    def perform_request(self, validated_data):
        try:
            application = Application.objects.get(application_id=validated_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        if validated_data["type"] == TelemetryDataType.TRACE.value:
            application.is_enabled_trace = False
            application.trace_data_status = DataStatus.DISABLED
            Application.stop_plugin_config(validated_data["application_id"])
        elif validated_data["type"] == TelemetryDataType.PROFILING.value:
            application.is_enabled_profiling = False
            application.profiling_data_status = DataStatus.DISABLED
        elif validated_data["type"] == TelemetryDataType.METRIC.value:
            application.is_enabled_metric = False
            application.metric_data_status = DataStatus.DISABLED
        elif validated_data["type"] == TelemetryDataType.LOG.value:
            application.is_enabled_log = False
            application.log_data_status = DataStatus.DISABLED

        res = api.apm_api.stop_application(application_id=validated_data["application_id"], type=validated_data["type"])
        application.save()

        from apm_web.tasks import APMEvent, report_apm_application_event

        switch_on_data_sources = application.get_data_sources()
        report_apm_application_event.delay(
            application.bk_biz_id,
            application.application_id,
            apm_event=APMEvent.APP_UPDATE,
            data_sources=switch_on_data_sources,
            updated_telemetry_types=[validated_data["type"]],
        )
        return res


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
            # 旧应用没有分片数
            es_shards = serializers.IntegerField(label="es索引分片数", min_value=1, default=3)
            es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500, required=False)

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
            bk_biz_id = serializers.IntegerField(label="业务id", required=False)
            subscription_id = serializers.IntegerField(label="订阅任务id", required=False)
            bk_data_id = serializers.IntegerField(label="数据id", required=False)

        application_id = serializers.IntegerField(label="应用id")
        app_alias = serializers.CharField(label="应用别名", max_length=255, required=False)
        description = serializers.CharField(label="应用描述", max_length=255, allow_blank=True, required=False)
        trace_datasource_option = DatasourceOptionSerializer(required=False, label="trace ES 配置")
        log_datasource_option = DatasourceOptionSerializer(required=False, label="log ES 配置")
        application_apdex_config = ApdexConfigSerializer(required=False)
        application_sampler_config = SamplerConfigSerializer(required=False)
        application_instance_name_config = InstanceNameConfigSerializer(required=False)
        application_dimension_config = DimensionConfigSerializer(required=False)
        application_db_config = serializers.ListField(label="db配置", child=DbConfigSerializer(), default=[])

        no_data_period = serializers.IntegerField(label="无数据周期", required=False)
        plugin_config = PluginConfigSerializer(required=False)
        application_qps_config = serializers.IntegerField(label="qps", required=False)

        def validate(self, attrs):
            res = super().validate(attrs)
            if attrs.get("trace_datasource_option") and not attrs.get("trace_datasource_option", {}).get(
                "es_slice_size"
            ):
                # 更新 trace 数据源时 需要传递切分大小
                raise ValueError("更新 Trace 数据源时需要指定切分大小")
            return res

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

        def get_transfer_config(self):
            return {}

    class NoDataPeriodProcessor(SetupProcessor):
        update_key = ["no_data_period"]

        def setup(self):
            for key, value in self._params.items():
                self._application.setup_nodata_config(key, value)

    class TraceDatasourceSetProcessor(SetupProcessor):
        update_key = ["trace_datasource_option"]

        def setup(self):
            for key in self.update_key:
                if key not in self._params:
                    return
            Application.setup_datasource(
                self._application.application_id,
                {"trace_datasource_option": self._params["trace_datasource_option"]},
            )

    class LogDatasourceSetProcessor(SetupProcessor):
        update_key = ["log_datasource_option"]

        def setup(self):
            for key in self.update_key:
                if key not in self._params:
                    return
            Application.setup_datasource(
                self._application.application_id,
                {"log_datasource_option": self._params["log_datasource_option"]},
            )

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
            self._application.apdex_config = self._params

        def get_transfer_config(self):
            return self._application.get_apdex_config()

    class InstanceNameSetupProcessor(SetupProcessor):
        group_key = "application_instance_name_config"
        update_key = ["instance_name_composition"]

        def setup(self):
            self._application.setup_config(
                self._application.instance_config, self._params, self._application.INSTANCE_NAME_CONFIG_KEY
            )
            self._application.instance_name_config = self._params

        def get_transfer_config(self):
            return self._application.get_instance_name_config()

    class DimensionSetupProcessor(SetupProcessor):
        group_key = "application_dimension_config"
        update_key = ["dimensions"]

        def setup(self):
            self._application.setup_config(
                self._application.dimension_config, self._params, self._application.DIMENSION_CONFIG_KEY
            )
            self._application.dimension_config = self._params

        def get_transfer_config(self):
            return self._application.get_dimension_config()

    class DbSetupProcessor(SetupProcessor):
        update_key = ["application_db_config"]

        def setup(self):
            self._application.setup_config(
                self._application.db_config,
                self._params["application_db_config"],
                self._application.DB_CONFIG_KEY,
                override=True,
            )
            self._application.db_config = self._params["application_db_config"]

        def get_transfer_config(self):
            return self._application.get_db_configs()

    class QPSSetupProcessor(SetupProcessor):
        update_key = ["application_qps_config"]

        def setup(self):
            self._application.setup_config(
                self._application.qps_config,
                self._params["application_qps_config"],
                self._application.QPS_CONFIG_KEY,
                override=True,
            )
            self._application.qps_config = self._params["application_qps_config"]

        def get_transfer_config(self):
            return self._application.get_qps_config()

    class EventSetupProcessor(SetupProcessor):
        update_key = [Application.EVENT_CONFIG_KEY]

        def setup(self):
            self._application.setup_config(
                self._application.event_config,
                self._params[Application.EVENT_CONFIG_KEY],
                self._application.EVENT_CONFIG_KEY,
                override=True,
            )
            self._application.event_config = self._params[Application.EVENT_CONFIG_KEY]

    def perform_request(self, validated_data):
        try:
            application = Application.objects.get(application_id=validated_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        # Step1: 更新应用配置
        processors = [
            processor_cls(application)
            for processor_cls in [
                self.TraceDatasourceSetProcessor,
                self.LogDatasourceSetProcessor,
                self.ApplicationSetupProcessor,
                self.ApdexSetupProcessor,
                self.InstanceNameSetupProcessor,
                # self.DimensionSetupProcessor,
                self.NoDataPeriodProcessor,
                self.DbSetupProcessor,
                self.QPSSetupProcessor,
            ]
        ]

        need_handle_processors = []
        need_transfer_configs = {}
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
            need_transfer_configs.update(processor.get_transfer_config())

        # Step2: 因为采样配置较复杂所以不走Processor 交给单独Helper处理
        if validated_data.get("application_sampler_config"):
            sampling_helpers = SamplingHelpers(validated_data["application_id"])
            sampling_helpers.setup(validated_data["application_sampler_config"])
            need_transfer_configs.update(sampling_helpers.get_transfer_config())

        Application.objects.filter(application_id=application.application_id).update(update_user=get_global_user())

        # Log-Trace配置更新
        if application.plugin_id == LOG_TRACE and validated_data.get("plugin_config"):
            Application.update_plugin_config(application.application_id, validated_data["plugin_config"])

        from apm_web.tasks import update_application_config

        update_application_config.delay(application.bk_biz_id, application.app_name, need_transfer_configs)


class ListApplicationResource(PageListResource):
    """APM 观测场景应用列表接口"""

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="app_alias", name=_("应用别名"), checked=True),
            StringTableFormat(id="app_name", name=_("应用名"), checked=True),
            StringTableFormat(id="description", name=_("应用描述"), checked=True),
            StringTableFormat(id="retention", name=_("存储计划"), checked=True),
            StringTableFormat(id="service_count", name=_("服务数量")),
            StringTableFormat(id="is_enabled", name=_("应用是否启用"), checked=True),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        filter_dict = serializers.JSONField(required=False, label="筛选字典")
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)

    class ApplicationSerializer(serializers.ModelSerializer):
        is_create_finished = serializers.SerializerMethodField()

        def get_is_create_finished(self, instance):
            return instance.is_create_finished

        class Meta:
            model = Application
            fields = [
                "bk_biz_id",
                "application_id",
                "app_name",
                "app_alias",
                "description",
                "is_enabled",
                "trace_data_status",
                "profiling_data_status",
                "metric_data_status",
                "log_data_status",
                "service_count",
                "trace_result_table_id",
                "metric_result_table_id",
                "is_create_finished",
            ]

    def get_filter_fields(self):
        return ["app_name", "app_alias", "description"]

    def perform_request(self, validate_data):
        applications = Application.objects.filter(bk_biz_id=validate_data["bk_biz_id"])

        def sort_rule(app):
            """
            排序规则
            1. 有数据的优先
            2. 有服务的其次
            3. 分组内按名称排序
            """
            first, second, third = 1, 1, app.get("app_name", "")
            if (
                app.get("trace_data_status") == DataStatus.NORMAL
                or app.get("profiling_data_status") == DataStatus.NORMAL
                or app.get("metric_data_status") == DataStatus.NORMAL
                or app.get("log_data_status") == DataStatus.NORMAL
            ):
                first = 0

            if app.get("service_count", 0) > 0:
                second = 0

            return first, second, third

        # 排序
        data = sorted(self.ApplicationSerializer(applications, many=True).data, key=sort_rule)
        # 不分页
        validate_data["page_size"] = len(data)
        return self.get_pagination_data(data, validate_data)


class ListApplicationAsyncResource(AsyncColumnsListResource):
    """
    应用列表页异步接口
    (目前新版应用列表 前端没有使用这个接口)
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
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="开始时间")

    def key_name_map(self):
        return {
            TopoNodeKind.SERVICE: {
                "category": _("服务分类"),
                "predicate_value": _("分类名称"),
                "service_language": _("语言"),
                "instance_count": _("实例数量"),
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
                "category": _("服务分类"),
                "predicate_value": _("分类名称"),
                "kind": _("服务类型"),
                "belong_service": _("归属服务"),
                "instance_count": _("实例数量"),
            },
        }

    def perform_request(self, data):
        node_info = ServiceHandler.get_node(
            data["bk_biz_id"],
            data["app_name"],
            data["service_name"],
            raise_exception=False,
        )
        if not node_info:
            return [
                {
                    "name": _("数据状态"),
                    "type": "string",
                    "value": _("无数据（暂未发现此服务）"),
                }
            ]

        instances = RelationMetricHandler.list_instances(
            data["bk_biz_id"],
            data["app_name"],
            data["start_time"],
            data["end_time"],
            service_name=data["service_name"],
        )

        extra_data = node_info.get("extra_data", {})
        if extra_data.get("kind") == TopoNodeKind.COMPONENT:
            return [
                {
                    "name": self.key_name_map()[TopoNodeKind.COMPONENT][k],
                    "type": "string",
                    "value": v or "--",
                }
                for k, v in {
                    "category": StandardFieldCategory.get_label_by_key(extra_data.get("category")),
                    "predicate_value": extra_data.get("predicate_value"),
                    "kind": TopoNodeKind.get_label_by_key(extra_data.get("kind")),
                    "belong_service": ComponentHandler.get_component_belong_service(data["service_name"]),
                    "instance_count": len(instances),
                }.items()
            ]

        # 暂时用不上，并需注意方法体逻辑已过时
        # self.add_service_relation(data["bk_biz_id"], data["app_name"], node_info)

        return [
            {
                "name": self.key_name_map()[TopoNodeKind.SERVICE].get(item, item),
                "type": "string",
                "value": str(value) if value else "--",
            }
            for item, value in {
                "category": StandardFieldCategory.get_label_by_key(extra_data.get("category")),
                "predicate_value": extra_data.get("predicate_value"),
                "service_language": extra_data.get("service_language") or _("其他语言"),
                "instance_count": len(instances),
            }.items()
            if item in self.key_name_map()[TopoNodeKind.SERVICE].keys()
        ]

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


class EndpointDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称")
        endpoint_name = serializers.CharField(label="接口名称")

    def perform_request(self, validated_data):
        endpoint_info = EndpointHandler.get_endpoint(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            validated_data["service_name"],
            validated_data["endpoint_name"],
        )

        if not endpoint_info:
            return [
                {
                    "name": _("数据状态"),
                    "type": "string",
                    "value": _("无数据（暂未发现此接口）"),
                }
            ]

        return [
            {
                "name": _("接口类型"),
                "type": "string",
                "value": CategoryEnum.get_label_by_key(endpoint_info.get("category"))
                if endpoint_info.get("category")
                else "--",
            },
            {"name": _("所属服务"), "type": "string", "value": endpoint_info.get("service_name", "--")},
        ]


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
        resp = ServiceHandler.list_nodes(validated_request_data["bk_biz_id"], validated_request_data["app_name"])

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
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )
        category = serializers.CharField(label="分类", required=False)

    def get_operator(self):
        return _("查看")

    def perform_request(self, validated_data):
        filter_params = build_filter_params(validated_data["filter_params"])
        service_name = get_service_from_params(filter_params)
        params = {
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "name": [self.EXCEPTION_EVENT_TYPE],
        }
        if validated_data.get("category"):
            params["category"] = validated_data["category"]
        if service_name:
            node = ServiceHandler.get_node(
                validated_data["bk_biz_id"],
                validated_data["app_name"],
                service_name,
                raise_exception=False,
            )
            # 如果是组件 增加查询参数
            if ComponentHandler.is_component_by_node(node):
                DbComponentHandler.build_component_filter_params(
                    validated_data["bk_biz_id"],
                    validated_data["app_name"],
                    service_name,
                    filter_params,
                    validated_data.get("component_instance_id"),
                )
                db_system_filter = DbComponentHandler.build_db_system_param(category=node["extra_data"]["category"])
                filter_params.extend(db_system_filter)
            else:
                if ServiceHandler.is_remote_service_by_node(node):
                    filter_params = ServiceHandler.build_remote_service_filter_params(service_name, filter_params)

        params["filter_params"] = filter_params
        events = api.apm_api.query_event(params)
        res = []
        for event in events:
            exception_type = event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_TYPE, "unknown")
            res.append(
                {
                    "title": f"{span_time_strft(event['timestamp'])}  {exception_type}",
                    "subtitle": event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_MESSAGE, ""),
                    "content": event.get(OtlpKey.ATTRIBUTES, {})
                    .get(SpanAttributes.EXCEPTION_STACKTRACE, "")
                    .split("\n"),
                    "timestamp": int(event["timestamp"]),
                    "trace_id": event.get("trace_id", ""),
                }
            )
        # 对 res 基于 timestamp 字段排序 (倒序)
        res = sorted(res, key=lambda x: x["timestamp"], reverse=True)
        for index, r in enumerate(res, 1):
            r["id"] = index
        return self.get_pagination_data(res, validated_data)


class MetaInstrumentGuides(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        base_endpoint = serializers.URLField(label="接收端地址")

        languages = serializers.ListSerializer(
            label="语言列表",
            child=serializers.ChoiceField(label="语言", choices=[lang.lower() for lang in LanguageEnum.get_keys()]),
        )
        deployments = serializers.ListSerializer(
            label="环境列表",
            required=False,
            default=[DeploymentEnum.CENTOS.id],
            child=serializers.ChoiceField(
                label="环境", choices=[deploy.lower() for deploy in DeploymentEnum.get_keys()]
            ),
        )
        plugins = serializers.ListSerializer(
            label="场景列表",
            required=False,
            default=[PluginEnum.OPENTELEMETRY.id],
            child=serializers.ChoiceField(label="场景", choices=[plugin.lower() for plugin in PluginEnum.get_keys()]),
        )
        access_config = serializers.DictField(label="接入配置", required=False)

        OTLP_EXPORTER_GRPC_PORT = 4317
        OTLP_EXPORTER_HTTP_PORT = 4318

        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            app = Application.objects.filter(bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]).first()
            if app is None:
                raise ValueError(_(f"应用({attrs['app_name']})不存在"))

            data_token: str = QueryBkDataToken().request({"application_id": app.application_id})

            attrs["access_config"] = {
                "token": data_token,
                "otlp": {
                    # 语意参考：https://opentelemetry.io/docs/specs/otel/protocol/exporter/#configuration-options
                    # 默认通过 gRPC 上报
                    "protocol": OtlpProtocol.GRPC,
                    "endpoint": f"{attrs['base_endpoint']}:{self.OTLP_EXPORTER_GRPC_PORT}",
                    "http_endpoint": f"{attrs['base_endpoint']}:{self.OTLP_EXPORTER_HTTP_PORT}",
                    "enable_metrics": app.is_enabled_metric,
                    "enable_logs": app.is_enabled_log,
                    "enable_traces": app.is_enabled_trace,
                },
                "profiling": {
                    # 语意参考：https://grafana.com/docs/pyroscope/latest/configure-client/
                    "enabled": app.is_enabled_profiling,
                    "endpoint": f"{attrs['base_endpoint']}:{self.OTLP_EXPORTER_HTTP_PORT}/pyroscope",
                },
            }
            return attrs

    def perform_request(self, validated_request_data):
        access_config = validated_request_data["access_config"]
        for field in ["enable_metrics", "enable_logs", "enable_traces"]:
            access_config["otlp"][field] = str(access_config["otlp"][field]).lower()
        access_config["profiling"]["enabled"] = str(access_config["profiling"]["enabled"]).lower()

        context: dict[str, str] = {
            "ECOSYSTEM_REPOSITORY_URL": settings.ECOSYSTEM_REPOSITORY_URL,
            "ECOSYSTEM_CODE_ROOT_URL": settings.ECOSYSTEM_CODE_ROOT_URL,
            "APM_ACCESS_URL": settings.APM_ACCESS_URL,
            "access_config": access_config,
            "service_name": "{{service_name}}",
        }

        helper: Help = Help(context)

        guides: list[dict[str, Any]] = []
        for language, deployment, plugin in itertools.product(
            validated_request_data["languages"],
            validated_request_data["deployments"],
            validated_request_data["plugins"],
        ):
            guides.append(
                {
                    "plugin": plugin,
                    "deployment": deployment,
                    "language": language,
                    "content": helper.get_help_md(plugin, language, deployment),
                }
            )

        return guides


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
                "data_push_url_all": settings.APM_DATA_PUSH_URL,
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
            str(
                _("云区域 {} {} [{}]").format(push_url["bk_cloud_id"], push_url["push_url"], ",".join(push_url["tags"]))
            )
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
            # "help_md": {plugin.id: Help(plugin.id).get_help_md() for plugin in [Opentelemetry]},
            "setup": self.setup(validated_request_data["bk_biz_id"]),
        }


class IndicesInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(label="采集类型", choices=TelemetryDataType.values())

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

    def perform_request(self, validated_request_data):
        try:
            telemetry_data_type = validated_request_data["telemetry_data_type"]
            application = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        result = telemetry_handler_registry(telemetry_data_type, app=application).indices_info()
        return result


class PushUrlResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        format_type = serializers.ChoiceField(
            label="返回格式",
            required=False,
            default=FormatType.DEFAULT,
            choices=FormatType.choices(),
        )

    class ResponseSerializer(serializers.Serializer):
        push_url = serializers.CharField(label="push_url")
        tags = serializers.ListField(label="地址标签")
        bk_cloud_id = serializers.IntegerField(label="云区域ID")
        bk_cloud_alias = serializers.CharField(label="云区域别名", required=False, allow_blank=True)

    many_response_data = True

    PUSH_URL_CONFIGS = [
        {"tags": ["grpc", "opentelemetry"], "port": "4317", "path": ""},
        {"tags": ["http", "opentelemetry"], "port": "4318", "path": "/v1/traces"},
    ]
    CLOUD_AREA_ZERO_ALIAS = "内网"
    CLUSTER_PUSH_URL_ALIAS = "集群内服务"

    @classmethod
    def get_proxy_infos(cls, bk_biz_id):
        proxy_host_infos = []
        try:
            proxy_hosts = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
            for host in proxy_hosts:
                bk_cloud_id = int(host["bk_cloud_id"])
                ip = host.get("conn_ip") or host.get("inner_ip")
                proxy_host_infos.append({"ip": ip, "bk_cloud_id": bk_cloud_id})
        except Exception as e:
            logger.exception(e)

        default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
            default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN
        for proxy_ip in default_cloud_display:
            proxy_host_infos.insert(0, {"ip": proxy_ip, "bk_cloud_id": 0})

        # 添加集群内上报域名（在默认区域0之后）
        cluster_domain = getattr(settings, "CUSTOM_REPORT_DEFAULT_K8S_CLUSTER_SERVICE", "")
        if cluster_domain:
            proxy_host_infos.insert(
                len(default_cloud_display) if default_cloud_display else 0, {"ip": cluster_domain, "bk_cloud_id": 0}
            )

        return proxy_host_infos

    @classmethod
    def generate_endpoint(cls, ip: str, port: int | str | None = None, path: str | None = None) -> str:
        if is_v6(ip):
            ip = f"[{ip}]"

        base_endpoint: str = f"http://{ip}"
        if port:
            base_endpoint = f"{base_endpoint}:{port}"

        if path:
            if not path.startswith("/"):
                path = f"/{path}"
            return f"{base_endpoint}{path}"

        return base_endpoint

    def _get_cloud_alias_map(self) -> dict[int, str]:
        """获取云区域别名映射"""
        bk_tenant_id = get_request_tenant_id()
        clouds = api.cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        return {int(c.get("bk_cloud_id", 0)): c.get("bk_cloud_name", "") for c in clouds}

    def _generate_alias(self, ip: str, bk_cloud_id: int, cloud_alias_map: dict[int, str]) -> str:
        """生成别名"""
        # 判断是否为中心化域名
        default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
            default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN

        if ip in (default_cloud_display or []):
            return self.CLOUD_AREA_ZERO_ALIAS

        # 判断是否为集群内域名
        cluster_domain = getattr(settings, "CUSTOM_REPORT_DEFAULT_K8S_CLUSTER_SERVICE", "")
        if cluster_domain and ip == cluster_domain:
            return self.CLUSTER_PUSH_URL_ALIAS

        # 其他代理：使用云区域名称
        if bk_cloud_id == 0:
            return self.CLOUD_AREA_ZERO_ALIAS
        else:
            return cloud_alias_map.get(bk_cloud_id, "")

    def _get_default_endpoints(self, proxy_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        # 获取云区域别名映射
        cloud_alias_map = self._get_cloud_alias_map()

        for proxy_info, config in itertools.product(proxy_infos, self.PUSH_URL_CONFIGS):
            bk_cloud_id = proxy_info["bk_cloud_id"]
            ip = proxy_info["ip"]

            # 生成别名
            alias = self._generate_alias(ip, bk_cloud_id, cloud_alias_map)

            endpoints.append(
                {
                    "push_url": self.generate_endpoint(ip, config["port"], config["path"]),
                    "tags": config["tags"],
                    "bk_cloud_id": bk_cloud_id,
                    "bk_cloud_alias": alias,
                }
            )
        return endpoints

    def _get_simple_endpoints(self, proxy_infos: list[dict[str, Any]]):
        deplicate_keys: set[str] = set()
        endpoints: list[dict[str, Any]] = []
        # 获取云区域别名映射
        cloud_alias_map = self._get_cloud_alias_map()

        for proxy_info in proxy_infos:
            deplicate_key: str = f"{proxy_info['bk_cloud_id']}-{proxy_info['ip']}"
            if deplicate_key in deplicate_keys:
                continue
            deplicate_keys.add(deplicate_key)

            bk_cloud_id = proxy_info["bk_cloud_id"]
            ip = proxy_info["ip"]

            # 生成别名
            alias = self._generate_alias(ip, bk_cloud_id, cloud_alias_map)

            endpoints.append(
                {
                    "push_url": self.generate_endpoint(ip),
                    "tags": [PluginEnum.OPENTELEMETRY.id],
                    "bk_cloud_id": bk_cloud_id,
                    "bk_cloud_alias": alias,
                }
            )
        return endpoints

    def perform_request(self, validated_request_data):
        proxy_infos: list[dict[str, Any]] = self.get_proxy_infos(validated_request_data["bk_biz_id"])
        return {FormatType.DEFAULT: self._get_default_endpoints, FormatType.SIMPLE: self._get_simple_endpoints}[
            validated_request_data["format_type"]
        ](proxy_infos)


class QueryBkDataToken(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        return api.apm_api.query_bk_data_token_info(validated_request_data)


class DataViewConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(label="采集类型", choices=TelemetryDataType.values())

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            telemetry_data_type = validated_request_data["telemetry_data_type"]
            data_view_config = telemetry_handler_registry(telemetry_data_type, app=app).get_data_view_config()
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return data_view_config


class DataHistogramResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(label="采集类型", choices=TelemetryDataType.values())
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        data_view_config = serializers.JSONField(label="数据视图查询配置")

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            telemetry_data_type = validated_request_data["telemetry_data_type"]
            start_time = validated_request_data["start_time"]
            end_time = validated_request_data["end_time"]
            data_view_config = validated_request_data["data_view_config"]
            view_data = telemetry_handler_registry(telemetry_data_type, app=app).get_data_histogram(
                start_time=start_time, end_time=end_time, **data_view_config
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return view_data


class DataSamplingResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(
            label="采集类型", choices=TelemetryDataType.values(), default=TelemetryDataType.TRACE.name
        )
        size = serializers.IntegerField(required=False, label="拉取条数", default=10)

    @classmethod
    def combine_data(cls, telemetry_data_type: str, app: Application, **kwargs):
        try:
            resp = telemetry_handler_registry(telemetry_data_type, app=app).data_sampling(**kwargs)
        except Exception as e:  # pylint: disable=broad-except
            # APM 应用详情数据状态采样示例接口, 采样为空无需暴露底层具体错误信息给用户, 日志后台记录即可
            logger.warning(
                _("获取app: {app_id} {data_type} 采样数据失败, 详情: {detail}").format(
                    app_id=app.application_id, data_type=telemetry_data_type, detail=e
                )
            )
            return []
        return resp if resp else []

    def perform_request(self, validated_request_data):
        # 获取 App
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取数据
        size = validated_request_data["size"]
        telemetry_data_type = validated_request_data["telemetry_data_type"]
        return self.combine_data(telemetry_data_type, app, size=size)


class StorageInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(label="采集类型", choices=TelemetryDataType.values())

    def perform_request(self, validated_request_data):
        # 获取应用
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            telemetry_data_type = validated_request_data["telemetry_data_type"]
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        resp = telemetry_handler_registry(telemetry_data_type, app=app).storage_info()
        return resp


class StorageFieldInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        telemetry_data_type = serializers.ChoiceField(label="采集类型", choices=TelemetryDataType.values())

    def perform_request(self, validated_request_data):
        # 获取应用
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            telemetry_data_type = validated_request_data["telemetry_data_type"]
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        resp = telemetry_handler_registry(telemetry_data_type, app=app).storage_field_info()
        return resp


class StorageStatusResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")

    def perform_request(self, validated_request_data):
        # 获取应用
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            status_mapping = {}
            for data_type in TelemetryDataType:
                if not getattr(app, f"is_enabled_{data_type.datasource_type}"):
                    status_mapping[data_type.value] = StorageStatus.DISABLED
                    continue
                try:
                    status_mapping[data_type.value] = (
                        StorageStatus.NORMAL
                        if telemetry_handler_registry(data_type.value, app=app).storage_status
                        else StorageStatus.ERROR
                    )
                except Exception as e:  # pylint: disable=broad-except
                    status_mapping[data_type.value] = StorageStatus.ERROR
                    logger.warning(_("获取{type}存储状态失败,详情: {detail}").format(type=data_type.value, detail=e))
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return status_mapping


class DataStatusResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用id")
        start_time = serializers.IntegerField(label="检查开始时间")
        end_time = serializers.IntegerField(label="检查结束时间")

    def perform_request(self, validated_request_data):
        # 获取应用
        try:
            app = Application.objects.get(application_id=validated_request_data["application_id"])
            start_time = validated_request_data["start_time"]
            end_time = validated_request_data["end_time"]
            status_mapping = {}
            for data_type in TelemetryDataType:
                if not getattr(app, f"is_enabled_{data_type.datasource_type}"):
                    status_mapping[data_type.value] = DataStatus.DISABLED
                    continue
                try:
                    status_mapping[data_type.value] = (
                        DataStatus.NORMAL
                        if telemetry_handler_registry(data_type.value, app=app).get_data_count(start_time, end_time)
                        else DataStatus.NO_DATA
                    )
                except Exception as e:  # pylint: disable=broad-except
                    status_mapping[data_type.value] = getattr(
                        app, f"{data_type.datasource_type}_data_status", DataStatus.NO_DATA
                    )
                    logger.warning(_("获取{type}存储状态失败,详情: {detail}").format(type=data_type.value, detail=e))
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        return status_mapping


class NoDataStrategyInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(required=True, label="应用ID")
        telemetry_data_type = serializers.ChoiceField(
            label="采集类型", choices=TelemetryDataType.values(), required=False, default=TelemetryDataType.TRACE.value
        )

    @classmethod
    def get_config_key(cls, telemetry_data_type: str):
        return nodata_error_strategy_config_mapping.get(telemetry_data_type, NODATA_ERROR_STRATEGY_CONFIG_KEY)

    def get_strategy(self, bk_biz_id: int, app: Application, telemetry_data_type: str):
        """检测策略存在与否，不存在则创建"""
        # 获取数据库存储的策略
        strategy_config, is_created = ApmMetaConfig.objects.get_or_create(
            config_level=ApmMetaConfig.APPLICATION_LEVEL,
            level_key=app.application_id,
            config_key=self.get_config_key(telemetry_data_type),
            defaults={"config_value": {"id": -1, "notice_group_id": -1}},
        )
        strategy_id = strategy_config.config_value["id"]
        # 获取已注册的策略
        if strategy_id > 0:
            conditions = [{"key": "id", "value": [strategy_id]}]
            strategies = resource.strategies.get_strategy_list_v2(
                bk_biz_id=bk_biz_id, conditions=conditions, page=0, page_size=0
            ).get("strategy_config_list", [])
            # 匹配则返回
            if strategies:
                return strategies[0]
        # 不匹配则创建新策略
        return self.registry_strategy(bk_biz_id, app, strategy_config, telemetry_data_type)

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
    def registry_strategy(
        cls, bk_biz_id: int, app: Application, strategy_config: ApmMetaConfig, telemetry_data_type: str = None
    ):
        """创建策略并返回ID"""
        # 获取告警组
        group_id = cls.get_notice_group(bk_biz_id, app, strategy_config)
        register_config = telemetry_handler_registry(telemetry_data_type, app=app).get_no_data_strategy_config()
        if not register_config:
            return

        config = {
            "bk_biz_id": bk_biz_id,
            # 默认关闭
            "is_enabled": False,
            "name": register_config["name"],
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
                    "name": register_config["name"],
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
                    "query_configs": register_config["query_configs"],
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

    def gen_strategy_config(self, app: Application, telemetry_data_type: str):
        strategy = self.get_strategy(app.bk_biz_id, app, telemetry_data_type)
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
            "telemetry_data_type": telemetry_data_type,
        }

    def perform_request(self, validated_request_data):
        # 获取请求信息
        application_id = validated_request_data["application_id"]
        telemetry_data_type = validated_request_data["telemetry_data_type"]

        if telemetry_data_type == TelemetryDataType.PROFILING.value:
            return {}

        # 获取应用
        try:
            app = Application.objects.get(application_id=application_id)
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        # 获取策略
        strategy_config = self.gen_strategy_config(app, telemetry_data_type=telemetry_data_type)
        return strategy_config


class NoDataStrategyStatusResource(Resource):
    is_enabled = None

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")
        telemetry_data_type = serializers.ChoiceField(
            label="数据类型", choices=TelemetryDataType.values(), default=TelemetryDataType.TRACE.value
        )

    def get_config_key(self, telemetry_data_type: str):
        return nodata_error_strategy_config_mapping.get(telemetry_data_type, NODATA_ERROR_STRATEGY_CONFIG_KEY)

    def perform_request(self, validated_request_data):
        # 获取请求信息
        application_id = validated_request_data["application_id"]
        telemetry_data_type = validated_request_data["telemetry_data_type"]
        # 不支持无数据告警
        if not TelemetryDataType(telemetry_data_type).no_data_strategy_enabled:
            return
        # 获取应用及配置信息
        try:
            app = Application.objects.get(application_id=application_id)
            config = ApmMetaConfig.objects.get(
                config_level=ApmMetaConfig.APPLICATION_LEVEL,
                level_key=app.application_id,
                config_key=self.get_config_key(telemetry_data_type),
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        except ApmMetaConfig.DoesNotExist:
            raise ValueError(_("配置信息不存在"))
        strategy_id = config.config_value["id"]
        conditions = [{"key": "id", "value": [strategy_id]}]
        # 已注册的策略
        strategies = resource.strategies.get_strategy_list_v2(bk_biz_id=app.bk_biz_id, conditions=conditions).get(
            "strategy_config_list", []
        )
        # 检测策略存在情况，不存在则创建
        if not strategies:
            new_strategy = NoDataStrategyInfoResource.registry_strategy(app.bk_biz_id, app, config, telemetry_data_type)
            if new_strategy:
                strategy_id = new_strategy["id"]
        # 更新策略状态
        if strategy_id and self.is_enabled is not None:
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


class ApplyStrategiesToServicesResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id", required=False)
        space_uid = serializers.CharField(label="空间唯一标识", required=False)
        app_name = serializers.CharField(label="应用名称", max_length=50)
        group_type = serializers.ChoiceField(label="策略组类型", choices=GroupType.choices())
        apply_types = serializers.ListSerializer(
            label="策略类型列表", child=serializers.CharField(label="策略类型"), required=False, default=[]
        )
        apply_services = serializers.ListSerializer(
            label="服务列表", child=serializers.CharField(label="服务"), required=False, default=[]
        )
        notice_group_ids = serializers.ListSerializer(
            label="告警组 ID 列表", child=serializers.IntegerField(label="告警组 ID"), required=False, default=[]
        )
        config = serializers.CharField(label="配置文本", default="{}")
        options = serializers.DictField(label="配置", required=False)

        def validate(self, attrs):
            bk_biz_id: int | None = attrs.get("bk_biz_id")
            space_uid: str | None = attrs.get("space_uid")
            if not (bk_biz_id or space_uid):
                raise ValueError(_("bk_biz_id、space_uid 至少需要传其中一个"))

            # space_uid to bk_biz_id
            if space_uid:
                attrs["bk_biz_id"] = SpaceApi.get_space_detail(space_uid=space_uid).bk_biz_id

            try:
                attrs["options"] = json.loads(attrs.get("config") or "{}")
            except (TypeError, json.JSONDecodeError):
                raise ValueError(_("配置解析错误，必须是合法 JSON 字符串"))
            return attrs

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]

        group: BaseStrategyGroup = StrategyGroupRegistry.get(
            GroupType.RPC.value,
            bk_biz_id,
            app_name,
            metric_helper=MetricHelper(bk_biz_id, app_name),
            notice_group_ids=validated_request_data.get("notice_group_ids") or [],
            apply_types=validated_request_data["apply_types"],
            apply_services=validated_request_data["apply_services"],
            options=validated_request_data["options"],
        )
        group.apply()

        return {}


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
    span_keys = ["db.system", "http.url", "messaging.system", "rpc.system", "trpc.callee_method"]

    default_sort = "-request_count"

    GROUP_KEY_ATT_CONFIG = {
        "db_system": "attributes.db.system",
        "http_url": "attributes.http.url",
        "messaging_system": "attributes.messaging.system",
        "rpc_system": "attributes.rpc.system",
        "trpc_callee_method": "attributes.trpc.callee_method",
    }

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
                        url_format="/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}"
                        + "&search_type=scope"
                        + "&start_time={start_time}&end_time={end_time}"
                        + "&sceneMode=span&filterMode=ui",
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
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )
        span_keys = serializers.ListSerializer(child=serializers.CharField(), required=False, label="分类过滤")
        keyword = serializers.CharField(required=False, label="过滤条件", allow_blank=True)

    def get_filter_fields(self):
        return ["summary"]

    def build_filter_params(self, filters):
        res = []
        for k, v in filters.items():
            if v == "undefined":
                continue

            res.append({"key": k, "op": "=", "value": v if isinstance(v, list) else [v]})

        return res

    def add_extra_params(self, params):
        return {
            "start_time": int(params["start_time"]) * 1000,
            "end_time": int(params["end_time"]) * 1000,
            "bk_biz_id": params["bk_biz_id"],
            "app_name": params["app_name"],
        }

    def get_pagination_data(self, data, params, column_type=None, skip_sorted=False):
        items = super().get_pagination_data(data, params, column_type)
        service_name_key = OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)
        service_name = params.get("filter_params", {}).get(service_name_key)

        # url 拼接
        for item in items["data"]:
            filters: list[dict[str, Any]] = [
                {"key": item.get("filter_key"), "operator": "equal", "value": [item.get("summary")]}
            ]
            if service_name:
                filters.append({"key": service_name_key, "operator": "equal", "value": [service_name]})

            for i in item["operation"]:
                i["url"] = i["url"] + "&where=" + json.dumps(filters)

        return items

    @classmethod
    def add_url_classify_data(cls, summary_mappings):
        """
        添加 url 归类统计数据
        """
        match_res = []
        no_match_res = []
        for summary, items in summary_mappings.items():
            request_count = sum(i.get("doc_count", 0) for i in items)
            sum_duration = sum(i["sum_duration"]["value"] for i in items)

            (no_match_res, match_res)[summary[-1]].append(
                {
                    "summary": summary[0],
                    "filter_key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL),
                    "request_count": request_count,
                    "average": round(sum_duration / request_count / 1000, 2),
                    "max_elapsed": round(max([item["max_duration"]["value"] for item in items]) / 1000, 2),
                    "min_elapsed": round(min([item["min_duration"]["value"] for item in items]) / 1000, 2),
                    "operation": {"trace": _("调用链"), "statistics": _("统计")},
                }
            )

        # 匹配到正则的结果优先展示
        return match_res + no_match_res

    def perform_request(self, validated_data):
        """
        根据app_name service_name查询span 遍历span然后取db.system,http.method..等等这些字段 没有就为空
        """
        if validated_data.get("span_keys", []):
            self.span_keys = validated_data.get("span_keys")
        # 设置默认排序
        if not validated_data.get("sort"):
            validated_data["sort"] = self.default_sort
        filter_params = self.build_filter_params(validated_data["filter_params"])
        service_name = get_service_from_params(filter_params)
        is_component = False
        uri_queryset = UriServiceRelation.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        )

        if service_name:
            node = ServiceHandler.get_node(
                validated_data["bk_biz_id"],
                validated_data["app_name"],
                service_name,
                raise_exception=False,
            )
            if ComponentHandler.is_component_by_node(node):
                ComponentHandler.build_component_filter_params(
                    validated_data["bk_biz_id"],
                    validated_data["app_name"],
                    service_name,
                    filter_params,
                    validated_data.get("component_instance_id"),
                )
                is_component = True
            else:
                uri_queryset.filter(service_name=service_name)
                if ServiceHandler.is_remote_service_by_node(node):
                    filter_params = ServiceHandler.build_remote_service_filter_params(service_name, filter_params)

        buckets = api.apm_api.query_span(
            {
                "bk_biz_id": validated_data["bk_biz_id"],
                "app_name": validated_data["app_name"],
                "start_time": validated_data["start_time"],
                "end_time": validated_data["end_time"],
                "filter_params": filter_params,
                "group_keys": [key.replace(".", "_") for key in self.span_keys],
            }
        )

        res = []
        summary_mappings = defaultdict(list)
        uri_list = uri_queryset.values_list("uri", flat=True).distinct()
        for bucket in buckets:
            display_values = [(k, v) for k, v in bucket["key"].items() if v]
            if not display_values:
                continue
            tmp_filter_key, summary = display_values[0]
            filter_key = self.GROUP_KEY_ATT_CONFIG.get(tmp_filter_key, "span_name")
            # http_url 归类处理
            if not is_component and filter_key in [OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL)]:
                http_summary_is_match = False
                for uri in uri_list:
                    pure_http_url = SpanHandler.generate_uri(urlparse(summary))
                    if re.match(uri, pure_http_url):
                        summary_mappings[(uri, True)].append(bucket)
                        http_summary_is_match = True

                if not http_summary_is_match:
                    summary_mappings[(summary, False)].append(bucket)

                continue

            res.append(
                {
                    "summary": summary,
                    "filter_key": filter_key,
                    "request_count": bucket["doc_count"],
                    "average": round(bucket["avg_duration"]["value"] / 1000, 2),
                    "min_elapsed": round(bucket["min_duration"]["value"] / 1000, 2),
                    "max_elapsed": round(bucket["max_duration"]["value"] / 1000, 2),
                    "operation": {"trace": _("调用链"), "statistics": _("统计")},
                }
            )
        # 添加 http_url 统计数据
        url_classify_data = self.add_url_classify_data(summary_mappings)
        res += url_classify_data
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
        service_name = get_service_from_params(filter_params)
        if service_name:
            node = ServiceHandler.get_node(
                validated_data["bk_biz_id"],
                validated_data["app_name"],
                service_name,
                raise_exception=False,
            )
            if ComponentHandler.is_component_by_node(node):
                ComponentHandler.build_component_filter_params(
                    validated_data["bk_biz_id"],
                    validated_data["app_name"],
                    service_name,
                    filter_params,
                    validated_data.get("component_instance_id"),
                )
            else:
                if ServiceHandler.is_remote_service_by_node(node):
                    filter_params = ServiceHandler.build_remote_service_filter_params(service_name, filter_params)

        query_dict = {
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
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
                    if not subtitle:
                        exception_message = event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_MESSAGE, "")
                        subtitle = f"{exception_type}: {exception_message}"
                    # 无过滤条件 -> 显示全部
                    res.append(
                        {
                            "title": f"{span_time_strft(event['timestamp'])}  {exception_type}",
                            "subtitle": subtitle,
                            "content": stacktrace,
                            "timestamp": int(event["timestamp"]),
                            "exception_type": exception_type,
                            "trace_id": span.get("trace_id", ""),
                        }
                    )
            else:
                res.append(
                    {
                        "title": f"{span_time_strft(span['start_time'])}  {self.UNKNOWN}",
                        "subtitle": subtitle,
                        "content": [],
                        "timestamp": int(span["start_time"]),
                        "exception_type": self.UNKNOWN,
                        "trace_id": span.get("trace_id", ""),
                    }
                )

        # exception_type 过滤
        if validated_data["exception_type"]:
            res = [i for i in res if i["exception_type"] == validated_data["exception_type"]]

        # 对 res 基于 timestamp 字段排序 (倒序)
        res = sorted(res, key=lambda x: x["timestamp"], reverse=True)
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
        service_name = get_service_from_params(filter_params)
        if service_name:
            node = ServiceHandler.get_node(
                validated_data["bk_biz_id"],
                validated_data["app_name"],
                service_name,
                raise_exception=False,
            )
            if ComponentHandler.is_component_by_node(node):
                ComponentHandler.build_component_filter_params(
                    validated_data["bk_biz_id"],
                    validated_data["app_name"],
                    service_name,
                    filter_params,
                    validated_data.get("component_instance_id"),
                )
            else:
                if ServiceHandler.is_remote_service_by_node(node):
                    filter_params = ServiceHandler.build_remote_service_filter_params(service_name, filter_params)

        query_dict = {
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
            "app_name": validated_data["app_name"],
            "bk_biz_id": validated_data["bk_biz_id"],
            "filter_params": filter_params,
            "fields": ["resource.service.name", "span_name", "trace_id", "events.attributes.exception.type"],
        }

        exception_spans = api.apm_api.query_span(query_dict)
        indentify_mapping = {}
        colors = ServiceColorClassifier()

        for span in exception_spans:
            service_name = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME, self.UNKNOWN_EXCEPTION)
            span_name = span[OtlpKey.SPAN_NAME]

            if span.get("events"):
                for event in span["events"]:
                    exception_type = event.get(OtlpKey.ATTRIBUTES, {}).get(
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
        component_instance_id = serializers.ListSerializer(
            child=serializers.CharField(), required=False, label="组件实例id(组件页面下有效)"
        )

    def build_filter_params(self, filter_dict):
        result = []
        service_name = None
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            if key == OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME):
                service_name = value
            else:
                result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})
        return result, service_name

    def perform_request(self, validated_data):
        app = Application.objects.get(bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"])
        q: QueryConfigBuilder = (
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM))
            .metric(method="COUNT", field="_index", alias="a")
            .table(app.trace_result_table_id)
            .filter(**{OtlpKey.STATUS_CODE: StatusCode.ERROR.value})
            .interval(get_interval_number(validated_data["start_time"], validated_data["end_time"]))
        )

        # Step1: 根据错误类型过滤
        if validated_data["exception_type"] and validated_data["exception_type"] != "unknown":
            q = q.filter(
                **{
                    f"{OtlpKey.EVENTS}.name": "exception",
                    f"{OtlpKey.EVENTS}.attributes.exception.type": validated_data["exception_type"],
                }
            )

        # Step2: 区分服务和组件，生成对应查询条件
        filter_params, service_name = self.build_filter_params(validated_data["filter_params"])
        if service_name:
            node = ServiceHandler.get_node(
                validated_data["bk_biz_id"], validated_data["app_name"], service_name, raise_exception=False
            )
            if ComponentHandler.is_component_by_node(node):
                q = q.filter(
                    ComponentHandler.build_component_filter(
                        validated_data["bk_biz_id"],
                        validated_data["app_name"],
                        service_name,
                        filter_params,
                        validated_data.get("component_instance_id"),
                    )
                )
            else:
                if ServiceHandler.is_remote_service_by_node(node):
                    q = q.filter(ServiceHandler.build_remote_service_filter(service_name, filter_params))
                else:
                    q = q.filter(ServiceHandler.build_service_filter(service_name, filter_params))

        qs: UnifyQuerySet = (
            UnifyQuerySet()
            .scope(app.bk_biz_id)
            .add_query(q)
            .start_time(validated_data["start_time"])
            .end_time(validated_data["end_time"])
        )
        return resource.grafana.graph_unify_query(
            **{**qs.config, "time_alignment": False, "null_as_zero": True, "query_method": "query_reference"}
        )


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
                count_mapping = defaultdict(int)
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
        update_application_config.delay(
            application.bk_biz_id, application.app_name, application.get_custom_service_config()
        )

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
        update_application_config.delay(
            application.bk_biz_id, application.app_name, application.get_custom_service_config()
        )


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
                host_rule = validated_data["rule"].get("host", {})
                path_rule = validated_data["rule"].get("path", {})
                param_rules = validated_data["rule"].get("params", [])

                if host_rule.get("value"):
                    if not Matcher.operator_match(host_rule["value"], str(url.hostname), host_rule["operator"]):
                        continue

                if path_rule.get("value"):
                    if not Matcher.operator_match(path_rule["value"], str(url.path), path_rule["operator"]):
                        continue

                url_param_paris = {}
                for i in url.query.split("&"):
                    if not i:
                        continue
                    k, v = str(i).split("=")
                    url_param_paris[k] = v

                param_filter = True
                for param in param_rules:
                    val = url_param_paris.get(param["name"])
                    if not val:
                        param_filter = False
                        break
                    if not Matcher.operator_match(val, param["value"], param["operator"]):
                        param_filter = False
                        break
                if param_filter:
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
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        type = serializers.ChoiceField(choices=CustomServiceType.choices())

    def perform_request(self, data):
        app = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not app:
            raise ValueError(_("应用不存在"))

        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(hours=2)

        if data["type"] == CustomServiceType.HTTP:
            return SpanHandler.get_span_urls(app, start_time, end_time)

        return None


class ListEsClusterGroupsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")

    def perform_request(self, data):
        # 在 APM 处获取集群信息 使用后台用户权限获取 避免当前用户无权限报错
        cluster_groups = api.log_search.bk_log_search_cluster_groups(
            bk_biz_id=data["bk_biz_id"],
            bk_username=get_backend_username(),
        )
        return cluster_groups


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, data):
        app = Application.objects.filter(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"]).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(data["app_name"]))
        Application.delete_plugin_config(app.application_id)
        api.apm_api.delete_application(application_id=app.application_id)
        app.delete()
        return True


class GETDataEncodingResource(Resource):
    def perform_request(self, data):
        data = EncodingsEnum.get_choices_list_dict()
        return data


class SimpleServiceList(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validate_data):
        app = Application.objects.filter(
            bk_biz_id=validate_data["bk_biz_id"], app_name=validate_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(validate_data["app_name"]))

        services = ServiceHandler.list_services(app)

        return [
            {
                "bk_biz_id": validate_data["bk_biz_id"],
                "app_name": validate_data["app_name"],
                "service_name": service["topo_key"],
                "category": service.get("extra_data", {}).get("category"),
                "kind": service.get("extra_data", {}).get("kind"),
                "predicate_value": service.get("extra_data", {}).get("predicate_value"),
                "language": service.get("extra_data", {}).get("service_language", ""),
            }
            for service in services
        ]


class ServiceConfigResource(Resource):
    bk_biz_id = serializers.IntegerField(label="业务id")
    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="应用名称")
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, validate_data):
        group: metric_group.TrpcMetricGroup = metric_group.MetricGroupRegistry.get(
            metric_group.GroupEnum.TRPC, validate_data["bk_biz_id"], validate_data["app_name"]
        )
        return group.get_server_config(
            server=validate_data["service_name"],
            start_time=validate_data.get("start_time"),
            end_time=validate_data.get("end_time"),
        )
