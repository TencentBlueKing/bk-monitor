"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import (
    APM_IS_SLOW_ATTR_KEY,
    DEFAULT_APM_APP_EVENT_CONFIG,
    DEFAULT_APM_APP_QPS,
    DEFAULT_DB_CONFIG,
    DEFAULT_DB_CONFIG_CUT_KEY,
    DEFAULT_DB_CONFIG_IS_SLOW_QUERY_THRESHOLD,
    DEFAULT_DB_CONFIG_PREDICATE_KEY,
    DEFAULT_NO_DATA_PERIOD,
    ApdexConfigEnum,
    ApmCacheKey,
    CustomServiceMatchType,
    CustomServiceType,
    DataStatus,
    DefaultApdex,
    DefaultDimensionConfig,
    DefaultInstanceNameConfig,
    DefaultSamplerConfig,
    TraceMode,
)
from apm_web.meta.plugin.log_trace_plugin_config import LogTracePluginConfig
from apm_web.meta.plugin.plugin import LOG_TRACE
from apm_web.metric_handler import RequestCountInstance
from bkm_space.api import SpaceApi
from bkmonitor.iam import Permission, ResourceEnum
from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.utils import group_by
from bkmonitor.utils.cache import lru_cache_with_ttl
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.time_tools import get_datetime_range
from common.log import logger
from constants.apm import OtlpKey, SpanKindKey, TelemetryDataType
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api, resource

tracer = trace.get_tracer(__name__)


class Application(AbstractRecordModel):
    DEPLOYMENT_KEY = "deployment"
    LANGUAGE_KEY = "language"
    PLUGING_KEY = "plugin"

    # trace 存储配置 KEY
    APPLICATION_DATASOURCE_CONFIG_KEY = "application_datasource_config"
    # log 存储配置 KEY
    APPLICATION_LOG_DATASOURCE_CONFIG_KEY = "application_log_datasource_config"

    class DatasourceConfig:
        ES_RETENTION = "es_retention"
        ES_STORAGE_CLUSTER = "es_storage_cluster"
        ES_NUMBER_OF_REPLICAS = "es_number_of_replicas"

    EVENT_CONFIG_KEY = "application_event_config"
    APDEX_CONFIG_KEY = "application_apdex_config"
    SAMPLER_CONFIG_KEY = "application_sampler_config"
    INSTANCE_NAME_CONFIG_KEY = "application_instance_name_config"
    DIMENSION_CONFIG_KEY = "application_dimension_config"
    DB_CONFIG_KEY = "application_db_config"
    QPS_CONFIG_KEY = "application_qps_config"
    TRACE_VIEW_CONFIG_KEY = "application_trace_view_config"

    class ApdexConfig:
        """Apdex配置项"""

        APDEX_DEFAULT = ApdexConfigEnum.DEFAULT
        APDEX_HTTP = ApdexConfigEnum.HTTP
        APDEX_DB = ApdexConfigEnum.DB
        APDEX_MESSAGING = ApdexConfigEnum.MESSAGING
        APDEX_BACKEND = ApdexConfigEnum.BACKEND
        APDEX_RPC = ApdexConfigEnum.RPC

    class SamplerConfig:
        """采样配置项"""

        SAMPLER_TYPE = "sampler_type"
        SAMPLER_PERCENTAGE = "sampler_percentage"

    class InstanceNameConfig:
        """实例名配置项"""

        INSTANCE_NAME_COMPOSITION = "instance_name_composition"

    class DimensionConfig:
        """维度配置项"""

        DIMENSIONS = "dimensions"

    # 不同Apdex配置的规则对应关系
    APDEX_RULE_MAPPING = {
        ApdexConfig.APDEX_HTTP: [
            {"span_kind": SpanKindKey.CLIENT, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD)},
            {"span_kind": SpanKindKey.SERVER, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD)},
        ],
        ApdexConfig.APDEX_DEFAULT: [
            {"span_kind": SpanKindKey.UNSPECIFIED, "predicate_key": ""},
            {"span_kind": SpanKindKey.INTERNAL, "predicate_key": ""},
            {"span_kind": SpanKindKey.SERVER, "predicate_key": ""},
            {"span_kind": SpanKindKey.CLIENT, "predicate_key": ""},
            {"span_kind": SpanKindKey.PRODUCER, "predicate_key": ""},
            {"span_kind": SpanKindKey.CONSUMER, "predicate_key": ""},
        ],
        ApdexConfig.APDEX_DB: [
            {"span_kind": SpanKindKey.CLIENT, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM)}
        ],
        ApdexConfig.APDEX_RPC: [
            {"span_kind": SpanKindKey.CLIENT, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)},
            {"span_kind": SpanKindKey.SERVER, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)},
            {"span_kind": SpanKindKey.PRODUCER, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)},
            {"span_kind": SpanKindKey.CONSUMER, "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)},
        ],
        ApdexConfig.APDEX_MESSAGING: [
            {
                "span_kind": SpanKindKey.PRODUCER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            },
            {
                "span_kind": SpanKindKey.CONSUMER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            },
            {
                "span_kind": SpanKindKey.PRODUCER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION),
            },
            {
                "span_kind": SpanKindKey.CONSUMER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION),
            },
        ],
        ApdexConfig.APDEX_BACKEND: [
            {
                "span_kind": SpanKindKey.PRODUCER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            },
            {
                "span_kind": SpanKindKey.CONSUMER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            },
            {
                "span_kind": SpanKindKey.PRODUCER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION),
            },
            {
                "span_kind": SpanKindKey.CONSUMER,
                "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION),
            },
        ],
    }

    NO_DATA_CONFIG_KEY = "no_data_config"

    class NoDataConfig:
        no_data_period = "no_data_period"

    application_id = models.IntegerField("应用Id", primary_key=True)
    bk_biz_id = models.IntegerField("业务id", db_index=True)
    app_name = models.CharField("应用名称", max_length=50)
    app_alias = models.CharField("应用别名", max_length=128)
    description = models.CharField("应用描述", max_length=255)
    metric_result_table_id = models.CharField("指标结果表", max_length=255, default="")
    trace_result_table_id = models.CharField("Trace结果表", max_length=255, default="")
    time_series_group_id = models.IntegerField("时序分组ID", default=0)
    source = models.CharField("来源系统", default=get_source_app_code, max_length=32)
    plugin_config = JsonField("log-trace 插件配置", null=True, blank=True)
    # ↓ 4 个 Module 功能开关 (这四个字段在 api 侧 model 同样有记录 需要保持同步)
    is_enabled_profiling = models.BooleanField("是否开启 Profiling 功能", default=False)
    is_enabled_metric = models.BooleanField("是否开启 Metric 功能", default=True)
    is_enabled_log = models.BooleanField("是否开启 Log 功能", default=False)
    is_enabled_trace = models.BooleanField("是否开启 Trace 功能", default=True)
    # ↓ 4 个 Module 数据状态开关 (这四个字段由定时任务刷新)
    trace_data_status = models.CharField("数据状态", default=DataStatus.NO_DATA, max_length=50)
    profiling_data_status = models.CharField("Profiling 数据状态", default=DataStatus.DISABLED, max_length=50)
    metric_data_status = models.CharField("Metric 数据状态", default=DataStatus.NO_DATA, max_length=50)
    log_data_status = models.CharField("Log 数据状态", default=DataStatus.DISABLED, max_length=50)
    # ↓ 1 个数据字段 (由定时任务刷新)
    service_count = models.IntegerField("服务个数", default=0)
    # 租户id
    bk_tenant_id = models.CharField("租户ID", max_length=64, default=DEFAULT_TENANT_ID)

    class Meta:
        ordering = ["-update_time", "-application_id"]
        index_together = [["bk_biz_id", "app_name"], ["update_time", "application_id"]]

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"<Application {self.application_id} {self.app_name}>"

    @cached_property
    def storage_plan(self):
        es_storage_config = self.get_config_by_key(self.APPLICATION_DATASOURCE_CONFIG_KEY).config_value
        return _("{}天").format(es_storage_config[self.DatasourceConfig.ES_RETENTION])

    @cached_property
    def es_storage_cluster(self):
        es_storage_config = self.get_config_by_key(self.APPLICATION_DATASOURCE_CONFIG_KEY).config_value
        return es_storage_config[self.DatasourceConfig.ES_STORAGE_CLUSTER]

    @cached_property
    def es_retention(self):
        es_storage_config = self.get_config_by_key(self.APPLICATION_DATASOURCE_CONFIG_KEY).config_value
        return es_storage_config[self.DatasourceConfig.ES_RETENTION]

    @cached_property
    def plugin_id(self):
        return (
            ApplicationRelationInfo.objects.filter(application_id=self.application_id, relation_key=self.PLUGING_KEY)
            .first()
            .relation_value
        )

    @cached_property
    def metric_info(self):
        metric_info = api.metadata.get_time_series_group({"time_series_group_id": self.time_series_group_id})
        result = []
        for metric_item in metric_info:
            metric_list = metric_item.get("metric_info_list", [])
            database_name, __ = metric_item["table_id"].split(".")
            for metric in metric_list:
                __, table_name = metric["table_id"].split(".")
                metric["table_id"] = f"{database_name}.{table_name}"
                metric["tags"] = []
                metric["data_source_label"] = _("自定义数据源")
                metric["result_table_label"] = "application_check"
                metric["result_table_label_name"] = _("业务应用")
                result.append(metric)
        return result

    @cached_property
    def deployment_ids(self):
        return list(
            ApplicationRelationInfo.objects.filter(
                application_id=self.application_id, relation_key=self.DEPLOYMENT_KEY
            ).values_list("relation_value", flat=True)
        )

    @cached_property
    def event_config(self):
        config = self.get_config_by_key(self.EVENT_CONFIG_KEY)
        if not config:
            return DEFAULT_APM_APP_EVENT_CONFIG
        return config.config_value

    @cached_property
    def apdex_config(self):
        # 兼容旧版无此配置
        config = self.get_config_by_key(self.APDEX_CONFIG_KEY)
        if not config:
            return {}
        return config.config_value

    @cached_property
    def sampler_config(self):
        config = self.get_config_by_key(self.SAMPLER_CONFIG_KEY)
        if not config:
            return {}
        return config.config_value

    @cached_property
    def instance_config(self):
        config = self.get_config_by_key(self.INSTANCE_NAME_CONFIG_KEY)
        if not config:
            return {}
        return config.config_value

    @cached_property
    def db_config(self):
        config = self.get_config_by_key(self.DB_CONFIG_KEY)
        if not config:
            return []
        return config.config_value

    @cached_property
    def qps_config(self):
        config = self.get_config_by_key(self.QPS_CONFIG_KEY)
        if not config:
            return DEFAULT_APM_APP_QPS
        return config.config_value

    @cached_property
    def dimension_config(self):
        config = self.get_config_by_key(self.DIMENSION_CONFIG_KEY)
        if not config:
            return {}
        return config.config_value

    @cached_property
    def no_data_period(self):
        no_data_config = self.get_config_by_key(self.NO_DATA_CONFIG_KEY)
        if no_data_config:
            return no_data_config.config_value[self.NoDataConfig.no_data_period]
        return DEFAULT_NO_DATA_PERIOD

    @cached_property
    def doc_count(self):
        """应用过期时间内的文档数量"""
        start_time, end_time = get_datetime_range("day", self.es_retention)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        return RequestCountInstance(self, start_time, end_time).query_instance()

    def set_service_count_and_data_status(self):
        """刷新应用的服务数量和各个数据源的状态"""
        from apm_web.handlers.service_handler import ServiceHandler

        # 刷新服务数量
        services = ServiceHandler.list_services(self)

        # 这里通过update方式，指定字段更新，是为了不自动变更 update_user， update_time 字段
        Application.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).update(service_count=len(services))

        # 刷新数据状态
        start_time, end_time = get_datetime_range("minute", self.no_data_period)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        service_status_mapping = ServiceHandler.get_service_data_status_mapping(self, start_time, end_time, services)
        key = ApmCacheKey.APP_SERVICE_STATUS_KEY.format(application_id=self.application_id)
        cache.set(key, json.dumps(service_status_mapping))

    def set_data_status(self):
        from apm_web.handlers.backend_data_handler import telemetry_handler_registry

        start_time, end_time = get_datetime_range("minute", self.no_data_period)
        start_time, end_time = int(start_time.timestamp()), int(end_time.timestamp())
        # NOTICE: data_status / profile_data_status 目前暂无接口用到只在指标中使用考虑指标处换成实时查询

        update_field_values = {}
        for data_type in TelemetryDataType:
            # 未定义的telemetry类型数据状态
            if not getattr(self, f"{data_type.datasource_type}_data_status", False):
                continue

            # 未打开开关，无需检查
            if not getattr(self, f"is_enabled_{data_type.datasource_type}", False):
                data_status = DataStatus.DISABLED
            else:
                try:
                    count = telemetry_handler_registry(data_type.value, app=self).get_data_count(start_time, end_time)
                    if count:
                        logger.info(
                            f"[Application] set_data_status ->  "
                            f"bk_biz_id: {self.bk_biz_id} app: {self.app_name} | {data_type.value} "
                            f"have data in {self.no_data_period} period"
                        )

                        data_status = DataStatus.NORMAL
                    else:
                        data_status = DataStatus.NO_DATA
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        f"[Application] set app: {self.app_name} | {data_type.value} data_status failed: {e}"
                    )
                    data_status = DataStatus.NO_DATA
            update_field_values[f"{data_type.datasource_type}_data_status"] = data_status

        # 这里通过update方式，指定字段更新，是为了不自动变更 update_user， update_time 字段
        Application.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).update(**update_field_values)

    @property
    def language_ids(self):
        return list(
            ApplicationRelationInfo.objects.filter(
                application_id=self.application_id, relation_key=self.LANGUAGE_KEY
            ).values_list("relation_value", flat=True)
        )

    def list_retention_time_range(self):
        """获取应用的过期时间范围"""
        s, e = get_datetime_range(period="day", distance=self.es_retention, rounding=False)
        return int(s.timestamp()), int(e.timestamp())

    def get_all_config(self):
        return ApmMetaConfig.get_all_application_config_value(self.application_id)

    def get_config_by_key(self, key: str):
        return ApmMetaConfig.get_application_config_value(self.application_id, key)

    @classmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 10, decision_to_drop_func=lambda v: v is None)
    def get_metric_table_id(cls, bk_biz_id, app_name):
        try:
            return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).values_list(
                "metric_result_table_id", flat=True
            )[0]
        except IndexError:
            return None

    @classmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 10, decision_to_drop_func=lambda v: v is None)
    def get_trace_table_id(cls, bk_biz_id, app_name):
        try:
            return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).values_list(
                "trace_result_table_id", flat=True
            )[0]
        except IndexError:
            return None

    @classmethod
    def get_application_id_by_app_name(cls, app_name: str):
        request = get_request()
        biz_id: int | None = request.biz_id

        if biz_id is None:
            try:
                data = json.loads(request.body.decode("utf-8"))
            except (TypeError, json.JSONDecodeError):
                raise ValueError(f"application({app_name}) not found")

            # space_uid to biz_id
            if "space_uid" in data:
                biz_id = SpaceApi.get_space_detail(space_uid=data["space_uid"]).bk_biz_id

        try:
            return cls.objects.filter(bk_biz_id=biz_id, app_name=app_name).values_list("application_id", flat=True)[0]
        except IndexError:
            raise ValueError(f"application({app_name}) not found")

    @classmethod
    def get_application_by_app_id(cls, application_id):
        instance = cls.objects.filter(application_id=application_id).first()
        if not instance:
            raise ValueError(f"application(id: {application_id}) not found.")

        return instance

    @classmethod
    @atomic
    def create_application(
        cls,
        bk_tenant_id,
        bk_biz_id,
        app_name,
        app_alias,
        description,
        plugin_id,
        deployment_ids,
        language_ids,
        enabled_profiling,
        enabled_trace,
        enabled_metric,
        enabled_log,
        storage_options=None,
        plugin_config=None,
    ):
        create_params = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "app_alias": app_alias,
            "description": description,
            "enabled_profiling": enabled_profiling,
            "enabled_trace": enabled_trace,
            "enabled_metric": enabled_metric,
            "enabled_log": enabled_log,
            "es_storage_config": storage_options,
        }

        application_info = api.apm_api.create_application(create_params)

        application = cls.objects.create(
            bk_tenant_id=bk_tenant_id,
            application_id=application_info["application_id"],
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            app_alias=app_alias,
            description=description,
        )

        # 初始化应用配置信息: 插件、环境、语言、数据源配置
        application.add_relation(cls.PLUGING_KEY, plugin_id)
        for deployment_id in deployment_ids:
            application.add_relation(cls.DEPLOYMENT_KEY, deployment_id)
        for language_id in language_ids:
            application.add_relation(cls.LANGUAGE_KEY, language_id)
        application.set_init_datasource(
            application_info["datasource_option"],
            enabled_profiling,
            enabled_trace,
            enabled_metric,
            enabled_log,
        )

        # 初始化配置：apdex、采样、实例名、db 慢语句、qps
        application.set_init_apdex_config()
        application.set_init_sampler_config()
        application.set_init_instance_name_config()
        application.set_init_db_config()
        application.set_init_qps_config()

        # todo 暂时不做维度配置
        # obj.set_init_dimensions_config()
        application.authorization()

        # log-trace 功能单独更新
        if plugin_config:
            Application.objects.filter(application_id=application.application_id).update(plugin_config=plugin_config)

        return Application.objects.get(application_id=application.application_id)

    def sync_datasource(self):
        """同步数据源到 saas 中"""

        detail = api.apm_api.detail_application(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

        trace_ds_info = detail.get("trace_config")
        metric_ds_info = detail.get("metric_config")
        if not trace_ds_info or not metric_ds_info:
            # trace/metric 任意一个没有 说明 api 侧创建失败了 此时应用已由 api 侧发送告警事件 这里直接返回等待下一次检查
            logger.warning(f"[SyncDatasource] apm-api create failed(id: {self.application_id}), skip")
            return

        self.trace_result_table_id = trace_ds_info["result_table_id"]
        self.metric_result_table_id = metric_ds_info["result_table_id"]
        self.time_series_group_id = metric_ds_info["time_series_group_id"]

        self.save()

        # 如果此应用走的是 log-trace 功能
        if self.get_relation(self.PLUGING_KEY) == LOG_TRACE:
            self.refresh_log_trace_plugin()

        # 下发配置
        from apm_web.tasks import update_application_config

        update_application_config.delay(self.bk_biz_id, self.app_name, self.get_transfer_config())

    def refresh_log_trace_plugin(self, plugin_config=None):
        if not plugin_config:
            plugin_config = self.plugin_config

        output_param = self.get_output_param(self.bk_biz_id, self.app_name)
        if not output_param.get("host"):
            return
        plugin_config = LogTracePluginConfig().release_log_trace_config(plugin_config, output_param)
        Application.objects.filter(application_id=self.application_id).update(plugin_config=plugin_config)
        return plugin_config

    @classmethod
    def update_plugin_config(cls, application_id, plugin_config):
        old_application = Application.objects.filter(application_id=application_id).first()
        if old_application.plugin_config != plugin_config:
            old_application.refresh_log_trace_plugin(plugin_config)
        return plugin_config

    @classmethod
    def get_output_param(cls, bk_biz_id, app_name):
        token = api.apm_api.detail_application({"bk_biz_id": bk_biz_id, "app_name": app_name})["token"]
        # 获取上报地址
        if settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN:
            host = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN[0]
        elif settings.CUSTOM_REPORT_DEFAULT_PROXY_IP:
            host = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP[0]
        else:
            return {}
        return {"token": token, "host": host}

    @classmethod
    def stop_plugin_config(cls, application_id):
        app = Application.objects.filter(application_id=application_id).first()
        if app.plugin_id == LOG_TRACE:
            # 停止节点管理采集任务
            api.node_man.switch_subscription(
                {"subscription_id": app.plugin_config["subscription_id"], "action": "disable"}
            )
            return LogTracePluginConfig().run_subscription_task(app.plugin_config["subscription_id"], "STOP")

    @classmethod
    def start_plugin_config(cls, application_id):
        app = Application.objects.filter(application_id=application_id).first()
        if app.plugin_id == LOG_TRACE:
            # 开始节点管理采集任务
            api.node_man.switch_subscription(
                {"subscription_id": app.plugin_config["subscription_id"], "action": "enable"}
            )
            return LogTracePluginConfig().run_subscription_task(app.plugin_config["subscription_id"], "START")

    @classmethod
    def delete_plugin_config(cls, application_id):
        app = Application.objects.filter(application_id=application_id).first()
        if app.plugin_id == LOG_TRACE:
            # 停止节点管理采集任务
            api.node_man.switch_subscription(
                {"subscription_id": app.plugin_config["subscription_id"], "action": "disable"}
            )
            # 删除节点管理采集订阅任务
            return LogTracePluginConfig().run_subscription_task(
                app.plugin_config["subscription_id"], "UNINSTALL_AND_DELETE"
            )

    def set_init_datasource(self, datasource_option, enabled_profiling, enabled_trace, enabled_metric, enabled_log):
        # 更新数据源开关
        # profiling
        self.is_enabled_profiling = enabled_profiling
        self.profiling_data_status = DataStatus.NO_DATA if enabled_profiling else DataStatus.DISABLED
        # trace
        self.is_enabled_trace = enabled_trace
        self.trace_data_status = DataStatus.NO_DATA if enabled_trace else DataStatus.DISABLED
        # metric
        self.is_enabled_metric = enabled_metric
        self.metric_data_status = DataStatus.NO_DATA if enabled_metric else DataStatus.DISABLED
        # log
        self.is_enabled_log = enabled_log
        self.log_data_status = DataStatus.NO_DATA if enabled_log else DataStatus.DISABLED

        self.save()

        ApmMetaConfig.application_config_setup(
            self.application_id, self.APPLICATION_DATASOURCE_CONFIG_KEY, datasource_option
        )
        ApmMetaConfig.application_config_setup(
            self.application_id, self.APPLICATION_LOG_DATASOURCE_CONFIG_KEY, datasource_option
        )

    def get_data_sources(self):
        return {
            TelemetryDataType.TRACE.value: self.is_enabled_trace,
            TelemetryDataType.PROFILING.value: self.is_enabled_profiling,
            TelemetryDataType.METRIC.value: self.is_enabled_metric,
            TelemetryDataType.LOG.value: self.is_enabled_log,
        }

    def set_init_dimensions_config(self):
        dimensions_value = {self.DimensionConfig.DIMENSIONS: DefaultDimensionConfig.DEFAULT_DIMENSIONS}
        ApmMetaConfig.application_config_setup(self.application_id, self.DIMENSION_CONFIG_KEY, dimensions_value)

    def set_init_instance_name_config(self):
        default_instance_name = DefaultInstanceNameConfig.DEFAULT_INSTANCE_NAME_COMPOSITION

        instance_value = {self.InstanceNameConfig.INSTANCE_NAME_COMPOSITION: default_instance_name}
        ApmMetaConfig.application_config_setup(self.application_id, self.INSTANCE_NAME_CONFIG_KEY, instance_value)

    def set_init_db_config(self):
        db_value = [DEFAULT_DB_CONFIG]

        ApmMetaConfig.application_config_setup(self.application_id, self.DB_CONFIG_KEY, db_value)

    def set_init_qps_config(self):
        qps_value = DEFAULT_APM_APP_QPS

        ApmMetaConfig.application_config_setup(self.application_id, self.QPS_CONFIG_KEY, qps_value)

    def set_init_sampler_config(self):
        sampler_value = {
            self.SamplerConfig.SAMPLER_TYPE: DefaultSamplerConfig.TYPE,
            self.SamplerConfig.SAMPLER_PERCENTAGE: DefaultSamplerConfig.PERCENTAGE,
        }
        ApmMetaConfig.application_config_setup(self.application_id, self.SAMPLER_CONFIG_KEY, sampler_value)

    def set_init_event_config(self):
        ApmMetaConfig.application_config_setup(self.application_id, self.EVENT_CONFIG_KEY, DEFAULT_APM_APP_EVENT_CONFIG)

    def fetch_datasource_info(self, datasource_type: str, attr_name: str):
        if getattr(self, f"{datasource_type}_{attr_name}", None):
            return getattr(self, f"{datasource_type}_{attr_name}")
        datasource_config = api.apm_api.detail_application({"bk_biz_id": self.bk_biz_id, "app_name": self.app_name})
        return datasource_config.get(f"{datasource_type}_config", {}).get(attr_name)

    def authorization(self):
        try:
            permission = Permission()
            permission.grant_creator_action(
                ResourceEnum.APM_APPLICATION.create_simple_instance(self.application_id, {"bk_biz_id": self.bk_biz_id}),
                creator=self.update_user,
            )
            Application.authorization_to_maintainers.delay(self.update_user, self.application_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"application->({self.application_id}) grant creator action failed, reason: {e}")

    @property
    def is_create_finished(self):
        return bool(self.trace_result_table_id and self.metric_result_table_id)

    @classmethod
    def q_filter_create_finished(cls):
        """
        获取过滤应用未开启 Trace 或 未创建完成的过滤条件 (是否有 trace_table_id 和 metric_table_id)
        """
        return (
            Q(is_enabled_trace=True)
            & Q(
                trace_result_table_id__isnull=False,
                metric_result_table_id__isnull=False,
            )
            & ~(Q(trace_result_table_id="") | Q(metric_result_table_id=""))
        )

    @staticmethod
    @shared_task()
    def authorization_to_maintainers(creator, app_id):
        """给业务的负责人授权"""
        logger.info(f"[authorization_to_maintainers] grant app_id: {app_id}")
        application = Application.get_application_by_app_id(app_id)

        try:
            maintainers = resource.cc.get_app_by_id(application.bk_biz_id).maintainers
        except Exception as e:
            raise ValueError("get maintainers failed with error: %s", e)

        permission = Permission(username=creator, bk_tenant_id=get_request_tenant_id())
        for user in list(maintainers):
            permission.grant_creator_action(
                ResourceEnum.APM_APPLICATION.create_simple_instance(app_id, {"bk_biz_id": application.bk_biz_id}),
                creator=user,
            )

        logger.info(f"[authorization_to_maintainers] grant app_id: {app_id} to maintainers: {maintainers} finished")

    @classmethod
    def setup_datasource(cls, application_id, datasource_option: dict):
        """
        更新存储配置
        datasource_option 格式: {"trace_datasource_option": {...}, "log_datasource_option": {...}}
        """
        application = cls.objects.filter(application_id=application_id).first()
        if not application:
            raise ValueError(_("应用不存在"))
        api.apm_api.apply_datasource({"application_id": application.application_id, **datasource_option})
        detail = api.apm_api.detail_application(bk_biz_id=application.bk_biz_id, app_name=application.app_name)
        application.trace_result_table_id = detail["trace_config"]["result_table_id"]
        application.metric_result_table_id = detail["metric_config"]["result_table_id"]
        application.time_series_group_id = detail["metric_config"]["time_series_group_id"]
        application.save()
        if datasource_option.get("trace_datasource_option"):
            ApmMetaConfig.application_config_setup(
                application_id,
                cls.APPLICATION_DATASOURCE_CONFIG_KEY,
                datasource_option["trace_datasource_option"],
            )
        if datasource_option.get("log_datasource_option"):
            ApmMetaConfig.application_config_setup(
                application_id,
                cls.APPLICATION_LOG_DATASOURCE_CONFIG_KEY,
                datasource_option["log_datasource_option"],
            )

    def set_init_apdex_config(self):
        apdex_value = {
            self.ApdexConfig.APDEX_DEFAULT: DefaultApdex.DEFAULT,
            self.ApdexConfig.APDEX_HTTP: DefaultApdex.HTTP,
            self.ApdexConfig.APDEX_DB: DefaultApdex.DB,
            self.ApdexConfig.APDEX_RPC: DefaultApdex.RPC,
            self.ApdexConfig.APDEX_BACKEND: DefaultApdex.BACKEND,
            self.ApdexConfig.APDEX_MESSAGING: DefaultApdex.MESSAGE,
        }
        ApmMetaConfig.application_config_setup(self.application_id, self.APDEX_CONFIG_KEY, apdex_value)

    def setup_config(self, config, new_config, config_key, override=False):
        if not override and isinstance(config, dict):
            config.update(new_config)
        else:
            config = new_config
        ApmMetaConfig.application_config_setup(self.application_id, config_key, config)

    def setup_apdex_config(self, key, value):
        apdex_value = self.apdex_config
        apdex_value[key] = value
        ApmMetaConfig.application_config_setup(self.application_id, self.APDEX_CONFIG_KEY, apdex_value)

    def setup_nodata_config(self, key, value):
        no_data_config = self.get_config_by_key(self.NO_DATA_CONFIG_KEY)
        if no_data_config:
            no_data_value = no_data_config.config_value
            no_data_value[key] = value
            ApmMetaConfig.application_config_setup(self.application_id, self.NO_DATA_CONFIG_KEY, no_data_value)
            return
        no_data_value = {key: value}
        ApmMetaConfig.application_config_setup(self.application_id, self.NO_DATA_CONFIG_KEY, no_data_value)

    def add_relation(self, relation_key: str, relation_value: str):
        ApplicationRelationInfo.add_relation(self.application_id, relation_key, relation_value)

    def get_relation(self, relation_key):
        return ApplicationRelationInfo.get_relation(self.application_id, relation_key)

    def get_transfer_config(self):
        """获取传递给API侧的数据"""
        application_config = self.get_application_transfer_config()
        service_config = self.get_service_transfer_config()

        return {"service_configs": service_config, **application_config}

    def get_application_transfer_config(self):
        res = {}
        # 依次获取各个配置
        config_parts = [
            self.get_apdex_config(),
            self.get_sampler_config(),
            self.get_instance_name_config(),
            self.get_dimension_config(),
            self.get_db_configs(),
            self.get_custom_service_config(),
            self.get_qps_config(),
        ]

        for part in config_parts:
            res.update(part)

        return res

    def get_apdex_config(self):
        apdex_config = self.apdex_config
        apdex_list = []
        for key, value in self.APDEX_RULE_MAPPING.items():
            for item in value:
                apdex_list.append({"apdex_t": apdex_config[key], **item})
        return {"apdex_config": apdex_list}

    def get_sampler_config(self):
        return {
            "sampler_config": {
                "sampling_percentage": self.sampler_config["sampler_percentage"],
                "sampler_type": self.sampler_config["sampler_type"],
            }
        }

    def get_instance_name_config(self):
        return {"instance_name_config": self.instance_config.get("instance_name_composition", [])}

    def get_dimension_config(self):
        return {"dimension_config": self.dimension_config.get("dimensions")}

    def get_db_configs(self):
        db_configs = self.db_config
        # 首字母大写
        for item in db_configs:
            item["db_system"] = str(item.get("db_system", "")).capitalize()
        return {
            "db_config": self.get_db_cut_drop_config(db_configs),
            "db_slow_command_config": self.get_db_slow_command_config(db_configs),
        }

    def get_custom_service_config(self):
        query = ApplicationCustomService.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        from apm_web.serializers import CustomServiceSerializer

        return {"custom_service_config": CustomServiceSerializer(instance=query, many=True).data}

    def get_qps_config(self):
        return {"qps": self.qps_config}

    @staticmethod
    def get_db_slow_command_config(configs: list):
        """
        组装db慢命令配置
        :param configs: 配置
        :return:
        """

        rules = []
        for config in configs:
            if config.get("enabled_slow_sql"):
                rules.append(
                    {
                        "match": config.get("db_system", ""),
                        "threshold": config.get("threshold", DEFAULT_DB_CONFIG_IS_SLOW_QUERY_THRESHOLD),
                    }
                )
        rules.sort(key=lambda rule: rule["match"], reverse=True)
        return {"destination": APM_IS_SLOW_ATTR_KEY, "rules": rules}

    @staticmethod
    def get_db_cut_drop_config(configs: list):
        """
        组装db配置
        :param configs: 配置
        :return:
        """

        cut_mapping = group_by(configs, lambda i: str(i["length"]))
        drop_mapping = group_by(configs, lambda i: str(i["trace_mode"]))

        cut = []
        drop = []

        for k, values in cut_mapping.items():
            cut_match = [v.get("db_system") for v in values if v.get("db_system")]
            cut.append(
                {
                    "max_length": int(k),
                    "keys": [DEFAULT_DB_CONFIG_CUT_KEY],
                    "predicate_key": DEFAULT_DB_CONFIG_PREDICATE_KEY,
                    "match": cut_match,
                }
            )

        for k, values in drop_mapping.items():
            drop_keys = []
            if k == TraceMode.NO_PARAMETERS:
                drop_keys = TraceMode.APM_DROP_KEYS_MAPPING[k]
            elif k == TraceMode.CLOSED:
                drop_keys = TraceMode.APM_DROP_KEYS_MAPPING[k]
            drop_match = [v.get("db_system") for v in values if v.get("db_system")]
            drop.append({"keys": drop_keys, "predicate_key": DEFAULT_DB_CONFIG_PREDICATE_KEY, "match": drop_match})

        cut.sort(key=lambda item: item["match"], reverse=True)
        drop.sort(key=lambda item: item["match"], reverse=True)

        return {"cut": cut, "drop": drop}

    def get_service_transfer_config(self):
        res = []

        # 1. 获取服务Apdex配置
        from apm_web.models import ApdexServiceRelation

        apdexs = ApdexServiceRelation.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
        for apdex in apdexs:
            # 服务需要额外携带一个UNSPECIFIED类型的配置
            apdex_config = [{"span_kind": SpanKindKey.UNSPECIFIED, "predicate_key": "", "apdex_t": apdex.apdex_value}]
            apdex_kind_config = self.APDEX_RULE_MAPPING.get(apdex.apdex_key)

            for item in apdex_kind_config:
                apdex_config.append({"apdex_t": apdex.apdex_value, **item})
            res.append({"service_name": apdex.service_name, "apdex_config": apdex_config})

        return res


class ApplicationRelationInfo(models.Model):
    application_id = models.IntegerField("应用Id", db_index=True)
    relation_key = models.CharField("关联Key", max_length=255, db_index=True)
    relation_value = models.CharField("关联值", max_length=255)

    class Meta:
        index_together = [["application_id", "relation_key"]]

    @classmethod
    def add_relation(cls, application_id: int, relation_key: str, relation_value: str):
        cls.objects.create(application_id=application_id, relation_key=relation_key, relation_value=relation_value)

    @classmethod
    def get_relation(cls, application_id, relation_key):
        instance = cls.objects.filter(application_id=application_id, relation_key=relation_key).first()
        if not instance:
            return None

        return instance.relation_value


class ApmMetaConfig(models.Model):
    """业务/应用/服务通用配置"""

    BK_BIZ_LEVEL = "bk_biz_level"
    APPLICATION_LEVEL = "application_level"
    SERVICE_LEVEL = "service_level"

    config_level = models.CharField("配置级别", max_length=128)
    level_key = models.CharField("配置目标key", max_length=512)
    config_key = models.CharField("config key", max_length=255)
    config_value = JsonField("配置信息")

    class Meta:
        unique_together = [["config_level", "level_key", "config_key"]]
        app_label = "apm_web"

    @classmethod
    def get_all_application_config_value(cls, application_id):
        return cls.objects.filter(config_level=cls.APPLICATION_LEVEL, level_key=application_id)

    @classmethod
    def get_application_config_value(cls, application_id, config_key: str):
        return cls.objects.filter(
            config_key=config_key, config_level=cls.APPLICATION_LEVEL, level_key=application_id
        ).first()

    @classmethod
    def get_service_level_key(cls, bk_biz_id, app_name, service_name):
        """因服务可能没有 id 所以 service_id 约定为 {bk_biz_id}-{app_name}-{service_name} 格式"""
        return f"{bk_biz_id}-{app_name}-{service_name}"

    @classmethod
    def get_service_config_value(cls, bk_biz_id, app_name, service_name, config_key):
        return cls.objects.filter(
            config_level=cls.SERVICE_LEVEL,
            level_key=cls.get_service_level_key(bk_biz_id, app_name, service_name),
            config_key=config_key,
        ).first()

    @classmethod
    def list_service_config_values(cls, bk_biz_id, app_name, service_names, config_key):
        level_keys = [cls.get_service_level_key(bk_biz_id, app_name, i) for i in service_names]
        return cls.objects.filter(
            config_level=cls.SERVICE_LEVEL,
            level_key__in=level_keys,
            config_key=config_key,
        )

    @classmethod
    def application_config_setup(cls, application_id, config_key, config_value):
        return cls._setup(cls.APPLICATION_LEVEL, application_id, config_key, config_value)

    @classmethod
    def bk_biz_config_setup(cls, bk_biz_id, config_key, config_value):
        return cls._setup(cls.BK_BIZ_LEVEL, bk_biz_id, config_key, config_value)

    @classmethod
    def service_config_setup(cls, bk_biz_id, app_name, service_name, config_key, config_value):
        """
        服务的元数据配置
        """
        return cls._setup(
            cls.SERVICE_LEVEL,
            cls.get_service_level_key(bk_biz_id, app_name, service_name),
            config_key,
            config_value,
        )

    @classmethod
    def _setup(cls, config_level, level_key, config_key, config_value):
        qs = cls.objects.filter(config_level=config_level, level_key=level_key, config_key=config_key)
        if qs.exists():
            qs.update(config_value=config_value)
            return

        cls.objects.create(
            config_level=config_level, level_key=level_key, config_key=config_key, config_value=config_value
        )


class ApplicationCustomService(AbstractRecordModel):
    bk_biz_id = models.IntegerField(verbose_name="业务id")
    app_name = models.CharField(verbose_name="应用名称", max_length=50)
    name = models.CharField(max_length=128, verbose_name="名称", null=True)
    type = models.CharField(max_length=32, choices=CustomServiceType.choices(), verbose_name="服务类型")
    match_type = models.CharField(max_length=32, choices=CustomServiceMatchType.choices(), verbose_name="匹配类型")
    rule = JsonField(verbose_name="匹配规则")

    class Meta:
        index_together = [["bk_biz_id", "app_name"]]
