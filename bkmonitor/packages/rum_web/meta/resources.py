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
import copy
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.user import get_global_user, get_backend_username
from bkmonitor.utils import group_by
from common.log import logger
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE, EventSeverity
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import ApplicationsResultTableLabel
from constants.rum import TelemetryDataType
from core.drf_resource import Resource, api, resource
from monitor.models import ApplicationConfig
from monitor_web.constants import AlgorithmType
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import StringTableFormat
from monitor_web.strategies.user_groups import get_or_create_ops_notice_group
from rum_web.constants import (
    ASYNC_COLUMN_CHOICES,
    BizConfigKey,
    DEFAULT_NO_DATA_PERIOD,
    DefaultSetupConfig,
    NODATA_ERROR_STRATEGY_CONFIG_KEY,
    DataStatus,
    RUM_APPLICATION_DEFAULT_METRIC,
    RUM_WEB_CLIENT_CHOICES,
)
from rum_web.handlers.service_handler import ServiceHandler
from rum_web.handlers.backend_data_handler import telemetry_handler_registry
from rum_web.models.application import Application, RumAppConfig
from rum_web.metric_handler import (
    LcpP75Instance,
    JsErrorRateInstance,
    ApiFailRateInstance,
)
from rum_web.metrics import APPLICATION_LIST
from rum_web.resources import AsyncColumnsListResource
from rum_web.serializers import ApplicationCacheSerializer


class CreateApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class DatasourceOptionSerializer(serializers.Serializer):
            es_storage_cluster = serializers.IntegerField(label="es存储集群")
            es_retention = serializers.IntegerField(label="es存储周期", min_value=1)
            es_number_of_replicas = serializers.IntegerField(label="es副本数量", min_value=0)
            es_shards = serializers.IntegerField(label="es索引分片数量", min_value=1)
            es_slice_size = serializers.IntegerField(label="es索引切分大小", default=500)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.RegexField(label="应用名称", max_length=50, regex=r"^[a-z0-9_.-]+$")
        app_alias = serializers.CharField(label="应用别名", max_length=255, required=False, default="")
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        client_type = serializers.CharField(label="前端类型", required=False, default="web")
        datasource_option = DatasourceOptionSerializer(label="数据源配置", required=False, allow_null=True)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = Application
            fields = "__all__"

    def perform_request(self, validated_request_data):
        if Application.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).exists():
            raise ValueError(_("应用名称: {}已被创建").format(validated_request_data["app_name"]))

        if settings.ENABLE_MULTI_TENANT_MODE:
            from bkmonitor.utils.request import get_request_tenant_id

            bk_tenant_id = get_request_tenant_id()
        else:
            bk_tenant_id = DEFAULT_TENANT_ID

        # app_alias 未提供时默认使用 app_name，对齐 APM 行为
        app_alias = validated_request_data.get("app_alias") or validated_request_data["app_name"]

        app = Application.create_application(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            app_alias=app_alias,
            description=validated_request_data["description"],
            storage_options=validated_request_data.get("datasource_option"),
        )

        from rum_web.tasks import RUMEvent, report_rum_application_event

        report_rum_application_event.delay(
            validated_request_data["bk_biz_id"],
            app.application_id,
            rum_event=RUMEvent.APP_CREATE,
        )
        return app


class CheckDuplicateAppNameResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    class ResponseSerializer(serializers.Serializer):
        exists = serializers.BooleanField(label="是否存在")

    def perform_request(self, validated_request_data):
        if Application.origin_objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).exists():
            return {"exists": True}
        return {"exists": False}


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    @atomic
    def perform_request(self, data):
        app = Application.objects.filter(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"]).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(data["app_name"]))

        RumAppConfig.delete_application_config(app.application_id)
        api.rum_api.delete_application(application_id=app.application_id)
        app.delete()
        return True


class StartDataSourceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    @classmethod
    def translate_data_status_when_start(cls, data_status):
        return DataStatus.NO_DATA if data_status == DataStatus.DISABLED else data_status

    @atomic
    def perform_request(self, validated_request_data):
        app = Application.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用不存在"))

        app.data_status = self.translate_data_status_when_start(app.data_status)
        res = api.rum_api.start_application(application_id=app.application_id)
        app.is_enabled = True
        app.save()

        from rum_web.tasks import RUMEvent, report_rum_application_event

        report_rum_application_event.delay(
            app.bk_biz_id,
            app.application_id,
            rum_event=RUMEvent.APP_UPDATE,
        )
        return res


class StopDataSourceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    @atomic
    def perform_request(self, validated_request_data):
        app = Application.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用不存在"))

        app.data_status = DataStatus.DISABLED
        res = api.rum_api.stop_application(application_id=app.application_id)
        app.is_enabled = False
        app.save()

        from rum_web.tasks import RUMEvent, report_rum_application_event

        report_rum_application_event.delay(
            app.bk_biz_id,
            app.application_id,
            rum_event=RUMEvent.APP_UPDATE,
        )
        return res


class GetApplicationInfoByAppNameResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            ref_name = "rum_application_info"
            model = Application
            fields = "__all__"

        def handle_apdex_config(self, instance, data):
            if Application.APDEX_CONFIG_KEY not in data:
                instance.set_init_apdex_config()
                data[Application.APDEX_CONFIG_KEY] = instance.get_config_by_key(
                    Application.APDEX_CONFIG_KEY
                ).config_value

        def handle_qps_config(self, instance, data):
            if Application.QPS_CONFIG_KEY not in data:
                instance.set_init_qps_config()
                data[Application.QPS_CONFIG_KEY] = instance.get_config_by_key(Application.QPS_CONFIG_KEY).config_value

        def handle_datasource_config(self, instance, data):
            if Application.APPLICATION_DATASOURCE_CONFIG_KEY not in data:
                instance.set_init_datasource_config()
                data[Application.APPLICATION_DATASOURCE_CONFIG_KEY] = instance.get_config_by_key(
                    Application.APPLICATION_DATASOURCE_CONFIG_KEY
                ).config_value

        def to_representation(self, instance):
            data = super().to_representation(instance)
            data["es_storage_index_name"] = instance.span_result_table_id.replace(".", "_")
            data["is_create_finished"] = bool(instance.span_result_table_id and instance.metric_result_table_id)
            # 将所有配置写入响应
            for config in instance.get_all_config():
                data[config.config_key] = config.config_value

            # 各配置项独立处理
            self.handle_apdex_config(instance, data)
            self.handle_qps_config(instance, data)
            self.handle_datasource_config(instance, data)
            return data

    def perform_request(self, validated_request_data):
        try:
            application = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return application


class QueryRumTokenInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        app_name = serializers.CharField(label="应用名称", max_length=50, required=False)

    def perform_request(self, validated_request_data):
        return api.rum_api.query_bk_data_token_info(validated_request_data)


class SetupApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class SpanDatasourceConfigSerializer(serializers.Serializer):
            es_storage_cluster = serializers.IntegerField(label="存储集群", required=False)
            es_retention = serializers.IntegerField(label="保留天数", required=False)
            es_number_of_replicas = serializers.IntegerField(label="副本数", required=False)
            es_shards = serializers.IntegerField(label="分片数", required=False)
            es_slice_size = serializers.IntegerField(label="切分大小", required=False)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        app_alias = serializers.CharField(label="展示名称", required=False, allow_blank=True)
        description = serializers.CharField(label="描述", required=False, allow_blank=True)
        span_datasource_config = SpanDatasourceConfigSerializer(required=False)
        application_apdex_config = serializers.DictField(label="Apdex配置", required=False)
        application_qps_config = serializers.IntegerField(label="QPS限制", required=False)

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            ref_name = "rum_setup_application"
            model = Application
            fields = "__all__"

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

    class ApplicationSetupProcessor(SetupProcessor):
        update_key = ["app_alias", "description"]

        def setup(self):
            Application.objects.filter(application_id=self._application.application_id).update(**self._params)

    class DatasourceSetupProcessor(SetupProcessor):
        group_key = "span_datasource_config"

        def setup(self):
            if not self._params:
                return
            api.rum_api.apply_datasource(
                application_id=self._application.application_id,
                rum_datasource_option=self._params,
            )
            RumAppConfig.application_config_setup(
                self._application.application_id,
                Application.APPLICATION_DATASOURCE_CONFIG_KEY,
                self._params,
            )

    class ApdexSetupProcessor(SetupProcessor):
        group_key = "application_apdex_config"

        def setup(self):
            if not self._params:
                return
            configs = [{"config_type": f"apdex:{k}", "config_value": v} for k, v in self._params.items()]
            if configs:
                api.rum_api.release_app_config(
                    bk_biz_id=self._application.bk_biz_id,
                    app_name=self._application.app_name,
                    configs=configs,
                )
            RumAppConfig.application_config_setup(
                self._application.application_id,
                Application.APDEX_CONFIG_KEY,
                self._params,
            )

    class QPSSetupProcessor(SetupProcessor):
        update_key = ["application_qps_config"]

        def setup(self):
            if "application_qps_config" not in self._params:
                return
            qps = self._params["application_qps_config"]
            api.rum_api.release_app_config(
                bk_biz_id=self._application.bk_biz_id,
                app_name=self._application.app_name,
                configs=[{"config_type": "qps:default", "config_value": qps}],
            )
            RumAppConfig.application_config_setup(
                self._application.application_id,
                Application.QPS_CONFIG_KEY,
                qps,
            )

    @atomic
    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        processors = [
            processor_cls(app)
            for processor_cls in [
                self.ApplicationSetupProcessor,
                self.DatasourceSetupProcessor,
                self.ApdexSetupProcessor,
                self.QPSSetupProcessor,
            ]
        ]
        need_handle_processors = []
        for key, value in validated_request_data.items():
            if key in ("bk_biz_id", "app_name"):
                continue
            for processor in processors:
                if processor.group_key and key == processor.group_key:
                    processor.set_group_params(value)
                    need_handle_processors.append(processor)
                if key in processor.update_key:
                    processor.set_params(key, value)
                    need_handle_processors.append(processor)

        for processor in need_handle_processors:
            processor.setup()
        Application.objects.filter(application_id=app.application_id).update(update_user=get_global_user())

        from rum_web.tasks import RUMEvent, report_rum_application_event

        report_rum_application_event.delay(
            app.bk_biz_id,
            app.application_id,
            rum_event=RUMEvent.APP_UPDATE,
        )
        return Application.objects.get(application_id=app.application_id)


class ListApplicationResource(PageListResource):
    """RUM 应用列表接口"""

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="app_name", name=_("应用名称"), checked=True, disabled=True, min_width=200),
            StringTableFormat(id="app_alias", name=_("应用别名"), checked=True, min_width=120),
            StringTableFormat(id="description", name=_("描述"), checked=True, min_width=120),
            StringTableFormat(id="lcp_p75", name="LCP P75", checked=True, asyncable=True, sortable=True, width=130),
            StringTableFormat(
                id="js_error_rate", name=_("JS 错误率"), checked=True, asyncable=True, sortable=True, width=130
            ),
            StringTableFormat(
                id="api_fail_rate", name=_("API 失败率"), checked=True, asyncable=True, sortable=True, width=130
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        filter_dict = serializers.JSONField(required=False, label="筛选字典")
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)

    class ApplicationSerializer(serializers.ModelSerializer):
        is_create_finished = serializers.SerializerMethodField()

        def get_is_create_finished(self, instance):
            return bool(instance.span_result_table_id and instance.metric_result_table_id)

        class Meta:
            model = Application
            fields = [
                "application_id",
                "bk_biz_id",
                "app_name",
                "app_alias",
                "description",
                "client_type",
                "is_enabled",
                "data_status",
                "span_result_table_id",
                "metric_result_table_id",
                "is_create_finished",
            ]

    def get_filter_fields(self):
        return ["app_name", "app_alias", "description"]

    def perform_request(self, validate_data):
        applications = Application.objects.filter(bk_biz_id=validate_data["bk_biz_id"])

        def sort_rule(app):
            """排序：有数据的优先，其次按名称"""
            first = 0 if app.get("data_status") == DataStatus.NORMAL else 1
            return first, app.get("app_name", "")

        data = sorted(self.ApplicationSerializer(applications, many=True).data, key=sort_rule)

        # 不分页
        validate_data["page_size"] = len(data)
        return self.get_pagination_data(data, validate_data)


class ListApplicationAsyncResource(AsyncColumnsListResource):
    """
    应用列表异步指标查询接口。
    参考 APM 的 ListApplicationAsyncResource 实现。
    """

    METRIC_MAP = {
        "lcp_p75": LcpP75Instance,
        "js_error_rate": JsErrorRateInstance,
        "api_fail_rate": ApiFailRateInstance,
    }
    METRIC_UNIT = {
        "lcp_p75": "s",
        "js_error_rate": "%",
        "api_fail_rate": "%",
    }

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
    def get_metric_data(
        cls, metric_name: str, applications: list, start_time: int | None = None, end_time: int | None = None
    ) -> dict:
        """
        获取应用指标数据
        :param metric_name: 指标名称
        :param applications: 应用列表
        :param start_time: 开始时间戳（秒），可选
        :param end_time: 结束时间戳（秒），可选
        :return: 应用 ID 到指标数据的映射字典
        """

        metric_data = APPLICATION_LIST(
            applications, metric_handler_cls=[cls.METRIC_MAP.get(metric_name)], start_time=start_time, end_time=end_time
        )

        metric_map = {}
        for app in applications:
            application_id = str(app["application_id"])
            app_metric = metric_data.get(application_id, copy.deepcopy(RUM_APPLICATION_DEFAULT_METRIC))
            metric_map[application_id] = app_metric
        return metric_map

    @classmethod
    def get_async_column_item(cls, data, column, **kwargs):
        column_dict: dict[str, float] = super().get_async_column_item(data, column, **kwargs)
        metric_dict: dict[str, dict[str, Any]] = {}
        for metric_name, metric_value in column_dict.items():
            if metric_name == "lcp_p75":
                metric_value = round(metric_value / 1000, 1)
            elif metric_name in {"js_error_rate", "api_fail_rate"}:
                metric_value = round(metric_value * 100, 1)
            metric_dict[metric_name] = {
                "id": metric_name,
                "value": metric_value,
                "unit": cls.METRIC_UNIT.get(metric_name, ""),
            }
        return metric_dict

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

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        column = serializers.ChoiceField(label="列名", choices=ASYNC_COLUMN_CHOICES)
        application_ids = serializers.ListField(label="应用ID列表", child=serializers.CharField())
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    many_response_data = True

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
            metric_data = self.get_metric_data(
                metric_name=validate_data["column"],
                applications=miss_application,
                start_time=validate_data["start_time"],
                end_time=validate_data["end_time"],
            )
            cache_metric_data.update(metric_data)

        res = self.build_res(
            validate_data=validate_data, app_mapping=application_mapping, metric_data=cache_metric_data
        )
        return self.get_async_data(res, validate_data["column"])


class GetMetaConfigInfoResource(Resource):
    """RUM 元信息配置"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def get_setup_config_value(self, key: str, bk_biz_id, default=None):
        """从 ApplicationConfig 表查询业务级配置"""
        obj = ApplicationConfig.objects.filter(cc_biz_id=bk_biz_id, key=key).first()
        if obj:
            return json.loads(obj.value)["_data"]
        return default

    def setup(self, bk_biz_id):
        return {
            "guide_url": {
                "access_url": settings.RUM_ACCESS_URL,
                "best_practice": settings.RUM_BEST_PRACTICE_URL,
                "metric_description": settings.RUM_METRIC_DESCRIPTION_URL,
            },
            "index_prefix_name": f"{bk_biz_id}_bkrum_",  # 需要按实际确认
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
        return {
            "client_type_options": RUM_WEB_CLIENT_CHOICES,
            "setup": self.setup(validated_request_data["bk_biz_id"]),
        }


class GetStorageInfoResource(Resource):
    """查询存储配置信息"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).storage_info()


class GetIndicesInfoResource(Resource):
    """查询 ES 索引信息"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).indices_info()


class GetDataSamplingResource(Resource):
    """查询采样数据"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        size = serializers.IntegerField(label="拉取条数", required=False, default=10)

    many_response_data = True

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).data_sampling(
            size=validated_request_data["size"]
        )


class StorageFieldInfoResource(Resource):
    """查询存储字段信息"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).storage_field_info()


class GetDataViewConfigResource(Resource):
    """获取数据视图查询配置"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    many_response_data = True

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).get_data_view_config()


class GetNoDataStrategyInfoResource(Resource):
    """
    RUM 无数据告警策略查询，对齐 apm_web.meta.resources.NoDataStrategyInfoResource。
    查不到策略时自动创建。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")

    def _get_strategy(self, app):
        """获取已存储的策略，不存在则创建"""
        strategy_config, _ = RumAppConfig.objects.get_or_create(
            config_level=RumAppConfig.APPLICATION_LEVEL,
            level_key=app.application_id,
            config_key=NODATA_ERROR_STRATEGY_CONFIG_KEY,
            defaults={"config_value": {"id": -1, "notice_group_id": -1}},
        )
        strategy_id = strategy_config.config_value.get("id", -1)

        # 已有有效策略则查询返回
        if strategy_id > 0:
            try:
                strategies = resource.strategies.get_strategy_list_v2(
                    bk_biz_id=app.bk_biz_id,
                    conditions=[{"key": "id", "value": [strategy_id]}],
                    page=0,
                    page_size=0,
                ).get("strategy_config_list", [])
                if strategies:
                    return strategies[0]
            except Exception as e:
                logger.warning(f"[GetNoDataStrategyInfo] query strategy({strategy_id}) failed: {e}")

        # 不存在则创建
        return self.registry_strategy(app, strategy_config)

    @classmethod
    def _get_notice_group(cls, bk_biz_id, strategy_config):
        """获取告警组ID"""
        group_id = get_or_create_ops_notice_group(bk_biz_id)
        strategy_config.config_value["notice_group_id"] = group_id
        strategy_config.save()
        return group_id

    @classmethod
    def registry_strategy(cls, app, strategy_config):
        """创建无数据告警策略"""
        group_id = cls._get_notice_group(app.bk_biz_id, strategy_config)
        if not group_id:
            return None

        if not app.metric_result_table_id:
            return None

        register_config = telemetry_handler_registry(TelemetryDataType.RUM.value, app=app).get_no_data_strategy_config()

        config = {
            "bk_biz_id": app.bk_biz_id,
            "is_enabled": False,
            "name": register_config["name"],
            "labels": ["BKRUM"],
            "scenario": ApplicationsResultTableLabel.application_check,
            "detects": [
                {
                    "expression": "",
                    "connector": "and",
                    "level": EventSeverity.WARNING,
                    "trigger_config": {"count": 1, "check_window": 5},
                    "recovery_config": {"check_window": 5},
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
                    "converge_config": {"need_biz_converge": True},
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

        try:
            resp = resource.strategies.save_strategy_v2(**config)
            strategy_config.config_value = {"id": resp["id"], "notice_group_id": group_id}
            strategy_config.save()
            return resp
        except Exception as e:
            logger.exception(f"[GetNoDataStrategyInfo] create strategy failed: {e}")
            return None

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))

        strategy = self._get_strategy(app)
        if not strategy:
            return {}

        alert_graph = {
            "id": 1,
            "title": _("告警数量"),
            "type": "apdex-chart",
            "gridPos": {"x": 0, "y": 0, "w": 24, "h": 6},
            "targets": [],
            "options": {},
        }

        return {
            "id": strategy.get("id"),
            "name": strategy.get("name"),
            "is_enabled": strategy.get("is_enabled", False),
            "alert_graph": alert_graph,
            "strategy_id": strategy.get("id"),
        }


class NoDataStrategyStatusResource(Resource):
    is_enabled = None

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label=_("应用ID"))

    def perform_request(self, validated_request_data):
        # 获取请求信息
        application_id = validated_request_data["application_id"]

        # 获取应用及配置信息
        try:
            app = Application.objects.get(application_id=application_id)
            config = RumAppConfig.objects.get(
                config_level=RumAppConfig.APPLICATION_LEVEL,
                level_key=app.application_id,
                config_key=NODATA_ERROR_STRATEGY_CONFIG_KEY,
            )
        except Application.DoesNotExist:
            raise ValueError(_("应用不存在"))
        except RumAppConfig.DoesNotExist:
            raise ValueError(_("配置信息不存在"))
        strategy_id = config.config_value["id"]
        conditions = [{"key": "id", "value": [strategy_id]}]
        # 已注册的策略
        strategies = resource.strategies.get_strategy_list_v2(bk_biz_id=app.bk_biz_id, conditions=conditions).get(
            "strategy_config_list", []
        )
        # 检测策略存在情况，不存在则创建
        if not strategies:
            new_strategy = GetNoDataStrategyInfoResource.registry_strategy(app, config)
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
