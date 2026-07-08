"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.api import SpaceApi
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from core.drf_resource import Resource
from core.drf_resource.exceptions import CustomException
from rum.core.handlers.application_helper import RumApplicationHelper
from rum.models import RumAppConfig, RumApplication
from rum.task.tasks import delete_application_async

logger = logging.getLogger("rum")


class DatasourceConfigRequestSerializer(serializers.Serializer):
    """RUM 应用数据源配置"""

    es_storage_cluster = serializers.IntegerField(label="ES 存储集群")
    es_retention = serializers.IntegerField(required=False, label="ES 存储周期", min_value=1)
    es_number_of_replicas = serializers.IntegerField(required=False, label="ES 副本数量", min_value=0)
    es_shards = serializers.IntegerField(required=False, label="索引分片数量", min_value=1)
    es_slice_size = serializers.IntegerField(label="ES 索引切分大小", default=100)


class CreateApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        app_alias = serializers.CharField(label="应用别名", max_length=255)
        description = serializers.CharField(label="描述", required=False, max_length=255, default="", allow_blank=True)
        es_storage_config = DatasourceConfigRequestSerializer(label="数据源配置", required=False, allow_null=True)

    def perform_request(self, validated_data):
        datasource_options = validated_data.get("es_storage_config")
        if not datasource_options:
            datasource_options = RumApplicationHelper.get_default_storage_config(
                validated_data["bk_biz_id"], validated_data["app_name"]
            )

        bk_tenant_id = validated_data.get("bk_tenant_id")
        if not bk_tenant_id:
            bk_tenant_id = get_request_tenant_id()

        return RumApplication.create_application(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=validated_data["bk_biz_id"],
            app_name=validated_data["app_name"],
            app_alias=validated_data["app_alias"],
            description=validated_data["description"],
            es_storage_config=datasource_options,
        )


class DeleteApplicationResource(Resource):
    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")

    def perform_request(self, validated_request_data):
        application_id = validated_request_data["application_id"]

        try:
            application = RumApplication.objects.get(id=application_id)
        except RumApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

        delete_application_async.delay(
            application.bk_biz_id,
            application.app_name,
            get_request_username(),
        )


class ApplicationRequestSerializer(serializers.Serializer):
    """
    通用应用查找序列化器，支持三种查找方式：
    1. application_id
    2. bk_biz_id + app_name
    3. space_uid + app_name
    """

    application_id = serializers.IntegerField(label="应用ID", required=False)
    bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
    app_name = serializers.CharField(label="应用名称", max_length=50, required=False)
    space_uid = serializers.CharField(label="空间唯一标识", required=False)

    def validate(self, attrs):
        application_id = attrs.get("application_id", None)
        space_uid = attrs.get("space_uid", "")
        bk_biz_id = attrs.get("bk_biz_id", None)
        app_name = attrs.get("app_name", "")

        if application_id:
            app = RumApplication.objects.filter(id=application_id).first()
            if app:
                attrs["bk_biz_id"] = app.bk_biz_id
                attrs["app_name"] = app.app_name
                return attrs
            raise ValidationError(f"the application({application_id}) does not exist")

        if app_name and bk_biz_id:
            app = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            if app:
                attrs["application_id"] = app.id
                return attrs
            raise ValidationError(f"the application({app_name}) does not exist")

        if app_name and space_uid:
            bk_biz_id = SpaceApi.get_space_detail(space_uid=space_uid).bk_biz_id
            if bk_biz_id:
                app = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
                if app:
                    attrs["application_id"] = app.id
                    attrs["bk_biz_id"] = bk_biz_id
                    return attrs
                raise ValidationError(f"the application({app_name}) does not exist")

        raise ValidationError("miss required fields: application_id, or bk_biz_id + app_name, or space_uid + app_name")


class ListApplicationResources(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = RumApplication
            exclude = ("is_deleted", "is_enabled")

        def to_representation(self, instance):
            data = super().to_representation(instance)
            if instance.rum_datasource:
                data["rum_config"] = instance.rum_datasource.to_json()
            if instance.metric_datasource:
                data["metric_config"] = instance.metric_datasource.to_json()
            return data

    many_response_data = True

    def perform_request(self, validated_request_data):
        return RumApplication.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])


class ApplicationInfoResource(Resource):
    RequestSerializer = ApplicationRequestSerializer

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = RumApplication
            exclude = ("is_deleted", "is_enabled")

        def to_representation(self, instance):
            data = super().to_representation(instance)
            data["token"] = instance.get_bk_data_token()
            if instance.rum_datasource:
                data["rum_config"] = instance.rum_datasource.to_json()
            if instance.metric_datasource:
                data["metric_config"] = instance.metric_datasource.to_json()
            return data

    def perform_request(self, validated_request_data):
        application_id = validated_request_data.get("application_id", None)
        return RumApplication.objects.get(id=application_id)


class StartApplicationResource(Resource):
    """整体启动 RUM 应用"""

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")

    def perform_request(self, validated_request_data):
        try:
            application = RumApplication.objects.get(id=validated_request_data["application_id"])
        except RumApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return application.start_rum()


class StopApplicationResource(Resource):
    """整体停止 RUM 应用"""

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")

    def perform_request(self, validated_request_data):
        try:
            application = RumApplication.objects.get(id=validated_request_data["application_id"])
        except RumApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

        return application.stop_rum()


class ApplyDatasourceResource(Resource):
    """更改数据源配置"""

    class RequestSerializer(serializers.Serializer):
        application_id = serializers.IntegerField(label="应用ID")
        rum_datasource_option = DatasourceConfigRequestSerializer(required=False, label="RUM 存储配置")

    def perform_request(self, validated_request_data):
        try:
            application = RumApplication.objects.get(id=validated_request_data["application_id"])
        except RumApplication.DoesNotExist:
            raise ValueError(_("应用不存在"))

        rum_datasource_option = validated_request_data.get("rum_datasource_option")
        if rum_datasource_option:
            return application.apply_datasource(rum_datasource_option)


class QueryBkDataTokenInfoResource(Resource):
    RequestSerializer = ApplicationRequestSerializer

    def perform_request(self, validated_request_data):
        return ApplicationInfoResource()(**validated_request_data)["token"]


class AppConfigResource(Resource):
    """获取应用配置"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]

        configs = RumAppConfig.application_configs(bk_biz_id, app_name)

        # 按大类分组返回
        result = {}
        for config in configs:
            config_json = config.to_json()
            config_type = config_json["config_type"]
            # config_type 格式为 "category:subcategory"
            category = config_type.split(":")[0] if ":" in config_type else config_type
            if category not in result:
                result[category] = []
            result[category].append(config_json)

        return result


class ReleaseAppConfigResource(Resource):
    """发布应用配置"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        config_type = serializers.CharField(label="配置大类", required=False, default="", allow_blank=True)
        configs = serializers.ListField(label="配置列表", child=serializers.DictField())

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        configs = validated_request_data["configs"]

        application = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not application:
            raise CustomException(_("业务下的应用: {} 不存在").format(app_name))

        RumAppConfig.refresh_config(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            scope_type=RumAppConfig.APPLICATION_LEVEL,
            scope_key="",
            refresh_configs=configs,
            refresh_categories=[
                config["config_type"].split(":", 1)[0] for config in configs if "config_type" in config
            ],
        )

        from rum.task.tasks import refresh_rum_application_config

        refresh_rum_application_config.delay(bk_biz_id, app_name)


class DeleteAppConfigResource(Resource):
    """删除应用配置"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称", max_length=50)
        configs = serializers.ListField(label="待删除配置列表", child=serializers.DictField())

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        configs = validated_request_data["configs"]

        application = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not application:
            raise CustomException(_("业务下的应用: {} 不存在").format(app_name))

        RumAppConfig.delete_config(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            delete_configs=configs,
        )

        from rum.task.tasks import refresh_rum_application_config

        refresh_rum_application_config.delay(bk_biz_id, app_name)
