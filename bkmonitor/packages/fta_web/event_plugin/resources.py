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
import abc
import logging
import time
import traceback
import urllib.parse
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.event_plugin import EventPluginSerializer, get_manager, get_serializer
from bkmonitor.event_plugin.constant import EVENT_NORMAL_FIELDS, CollectType
from bkmonitor.event_plugin.serializers import (
    AlertConfigSerializer,
    CleanConfigSerializer,
    HttpPullInstOptionSerializer,
    NormalizationConfig,
)
from bkmonitor.models import EventPluginInstance
from bkmonitor.models import EventPluginV2
from bkmonitor.models import EventPluginV2 as EventPlugin
from bkmonitor.models import PluginMainType, PluginType, Scenario
from bkmonitor.models.fta import PluginStatus
from bkmonitor.utils.cipher import transform_data_id_to_token
from bkmonitor.utils.serializers import StringSplitListField
from bkmonitor.utils.template import jinja_render
from bkmonitor.utils.time_tools import utc2biz_str
from core.drf_resource import Resource, api, resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.tools import format_serializer_errors
from core.errors.event_plugin import (
    DataIDNotSetError,
    GetKafkaConfigError,
    PluginIDExistError,
)
from fta_web.event_plugin.handler import PackageHandler
from fta_web.event_plugin.kafka import KafkaManager
from monitor_web.custom_report.resources import ProxyHostInfo

logger = logging.getLogger("kernel_api")


class BaseEventPluginResource(Resource, metaclass=abc.ABCMeta):
    @staticmethod
    def clean_data(instance, data):
        fields = []
        for field in EVENT_NORMAL_FIELDS:
            new_field = {
                "field": field["field"],
                "display_name": field["display_name"],
                "type": field["field_type"],
                "description": field["description"],
                "expr": "",
                "option": {},
            }
            for config in data.get("normalization_config", []):
                if config["field"] == new_field["field"]:
                    new_field.update(config)
            fields.append(new_field)

        data.update(
            {
                "alert_config": AlertConfigSerializer(instance.list_alert_config(), many=True).data,
                "normalization_config": fields,
                "is_official": True,  # TODO 需要实现具体逻辑
                "category": "event",  # TODO 需要进行抽象
                "category_display": _("事件插件"),  # TODO 需要进行抽象
                "logo": instance.logo_base64,
                "plugin_display_name": instance.plugin_display_name or instance.plugin_id,
                "author": instance.author or instance.create_user,
                "plugin_type_display": instance.get_plugin_type_display(),
                "scenario_display": instance.get_scenario_display(),
                "main_type": instance.main_type,
                "main_type_display": instance.get_main_type_display(),
                "is_installed": False,
                "updatable": False,
                "plugin_instance_id": None,
            }
        )
        return data


class CreateEventPluginResource(BaseEventPluginResource):
    """
    创建事件插件
    """

    RequestSerializer = EventPluginSerializer

    def validate_request_data(self, request_data):
        if EventPluginV2.objects.filter(
            plugin_id=request_data["plugin_id"], version=request_data.get("version")
        ).exists():
            raise PluginIDExistError({"plugin_id": request_data["plugin_id"], "version": request_data["version"]})
        return super(CreateEventPluginResource, self).validate_request_data(request_data)

    def perform_request(self, validated_data):
        serializer = get_serializer(validated_data["plugin_type"], data=validated_data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            instance = serializer.save()

        return self.clean_data(instance, serializer.data)


class UpdateEventPluginResource(BaseEventPluginResource):
    """
    更新事件插件
    """

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.RegexField(required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=64, label="插件ID")
        version = serializers.CharField(required=False, default="", allow_blank=True, label="插件版本号")

    def validate_request_data(self, request_data):
        """
        更新请求，仅清洗id和版本号
        :param request_data:
        :return:
        """
        plugin_info = super(UpdateEventPluginResource, self).validate_request_data(request_data)
        request_data.update(plugin_info)
        return request_data

    def perform_request(self, validated_data):
        instance = EventPlugin.objects.get(plugin_id=validated_data["plugin_id"], version=validated_data["version"])
        serializer = get_serializer(instance.plugin_type, instance, data=validated_data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            instance = serializer.save()

        return self.clean_data(instance, serializer.data)


class GetEventPluginResource(BaseEventPluginResource):
    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(label="插件ID", required=True)
        version = serializers.CharField(label="版本号", required=True)

    def perform_request(self, validated_data):
        instance = EventPlugin.objects.get(plugin_id=validated_data["plugin_id"], version=validated_data["version"])
        serializer = get_serializer(instance.plugin_type, instance)
        return self.clean_data(instance, serializer.data)


class DeleteEventPluginResource(BaseEventPluginResource):
    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(label="插件ID")

    def perform_request(self, validated_data):
        instance = EventPlugin.objects.get(plugin_id=validated_data["plugin_id"])
        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            manager = get_manager(instance)
            manager.switch(is_enabled=False)
            # instance.status = PluginStatus.REMOVED
            # instance.save(update_fields=["status"])
            # AlertConfig.objects.filter(plugin_id=instance.plugin_id).delete()
            # instance.delete()
        return None


class ImportEventPluginResource(BaseEventPluginResource):
    """
    插件包导入
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        file_data = serializers.FileField(required=True)
        force_update = serializers.BooleanField(default=False)

    def perform_request(self, validated_data):
        handler = PackageHandler.from_tar_file(validated_data["file_data"])
        plugin_info = handler.parse()
        plugin_info["bk_biz_id"] = validated_data["bk_biz_id"]

        try:
            data = resource.event_plugin.create_event_plugin(plugin_info)
        except PluginIDExistError as e:
            if validated_data["force_update"]:
                data = resource.event_plugin.update_event_plugin(plugin_info)
            else:
                raise e

        # 更新一波包路径
        EventPlugin.objects.filter(plugin_id=data["plugin_id"]).update(package_dir=handler.get_package_dir())
        data["package_dir"] = handler.get_package_dir()

        return data


class DeployEventPluginResource(BaseEventPluginResource):
    def perform_request(self, validated_data):
        forced_update = validated_data.get("forced_update") or False
        try:
            data = resource.event_plugin.create_event_plugin(validated_data)
        except PluginIDExistError:
            data = resource.event_plugin.update_event_plugin(validated_data)

        if not forced_update and str(data["bk_biz_id"]) not in ["0", ""]:
            # 如果没有强制刷新并且当前不存在全局插件
            return data
        need_updated_instances = EventPluginInstance.objects.filter(plugin_id=data["plugin_id"])
        if not forced_update and str(data["bk_biz_id"]) in ["0", ""]:
            need_updated_instances = need_updated_instances.filter(bk_biz_id=0)

        if not need_updated_instances:
            return data
        normalization_config = [
            {'expr': config["expr"], 'field': config["field"], 'option': config["option"]}
            for config in data["normalization_config"]
        ]

        need_updated_instances.update(
            plugin_id=data["plugin_id"], version=data["version"], normalization_config=normalization_config
        )
        succeed_instances = []
        failed_instances = []
        for instance in need_updated_instances:
            try:
                manager = get_manager(instance)
                manager.access()
                succeed_instances.append(instance.id)
            except Exception as error:  # noqa
                logger.info(
                    "[deploy_event_plugin]update plugin instance(%s) failed, %s", instance.id, traceback.format_exc()
                )
                failed_instances.append(instance.id)
        data["updated_instances"] = {"succeed_instances": succeed_instances, "failed_instances": failed_instances}

        logger.info(
            "[deploy_event_plugin] update plugin instance succeed_instances(%s) failed_instances(%s)",
            len(succeed_instances),
            len(failed_instances),
        )
        return data


class ListEventPluginResource(BaseEventPluginResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID", default=0)
        page = serializers.IntegerField(default=1, label="页数", min_value=1)
        page_size = serializers.IntegerField(default=10, label="页长")
        search_key = serializers.CharField(required=False, label="搜索关键字", default="")
        plugin_type = StringSplitListField(
            sep=",",
            required=False,
            default=[],
            child=serializers.ChoiceField(choices=PluginType.to_choice(), label="插件类型"),
        )
        status = StringSplitListField(
            sep=",",
            required=False,
            default=[],
            child=serializers.ChoiceField(choices=PluginStatus.to_choice(), label="状态"),
        )
        scenario = StringSplitListField(
            sep=",",
            required=False,
            default=[],
            child=serializers.ChoiceField(choices=Scenario.to_choice(), label="场景"),
        )

    def calculate_each_dimension(self, count_map, choices):
        count_tree = {
            "id": "event",
            "name": _("事件插件"),
            "count": 0,
            "child": [],
        }

        for id, name in choices:
            count_tree["child"].append({"id": id, "name": name, "count": count_map[id]})
        count_tree["count"] = sum([item["count"] for item in count_tree["child"]])
        return count_tree

    def calculate_count(self, queryset):
        status_count = defaultdict(int)
        main_type_count = defaultdict(int)
        scenario_count = defaultdict(int)
        tags_count = defaultdict(int)

        for plugin in queryset.only("status", "plugin_type", "scenario", "tags"):
            status_count[plugin.status] += 1
            main_type_count[plugin.main_type] += 1
            scenario_count[plugin.scenario] += 1

            for tag in plugin.tags:
                tags_count[tag] += 1

        count = {
            "scenario": [self.calculate_each_dimension(scenario_count, Scenario.to_choice())],
            "main_type": [self.calculate_each_dimension(main_type_count, PluginMainType.to_choice())],
            "status": [{"id": id, "name": name, "count": status_count[id]} for id, name in PluginStatus.to_choice()],
            "tags": [
                {"id": tag, "name": tag, "count": count}
                for tag, count in sorted(tags_count.items(), key=lambda item: item[1], reverse=True)
            ],
        }

        return count

    def perform_request(self, validated_data):
        bk_biz_id = validated_data["bk_biz_id"]
        plugin_instances = {
            inst.plugin_id: inst
            for inst in EventPluginInstance.objects.filter(bk_biz_id__in=[bk_biz_id, 0]).order_by("-update_time")
        }
        latest_plugin_queryset = EventPlugin.objects.filter(is_latest=True, bk_biz_id__in=[bk_biz_id, 0])
        count = self.calculate_count(latest_plugin_queryset)

        for field in ["plugin_type", "status", "scenario"]:
            if validated_data[field]:
                latest_plugin_queryset = latest_plugin_queryset.filter(**{f"{field}__in": validated_data[field]})

        if validated_data["search_key"]:
            latest_plugin_queryset = latest_plugin_queryset.filter(
                Q(plugin_id__icontains=validated_data["search_key"])
                | Q(plugin_display_name__icontains=validated_data["search_key"])
            )

        if validated_data["page_size"] > 0:
            # page_size > 0 才分页
            limit = validated_data["page_size"]
            offset = (validated_data["page"] - 1) * validated_data["page_size"]
            latest_plugin_queryset = latest_plugin_queryset[offset : offset + limit]

        data = []
        for plugin in latest_plugin_queryset:
            plugin_instance = plugin_instances.get(plugin.plugin_id)
            plugin_info = {
                "id": plugin.id,
                "version": plugin.version,
                "plugin_id": plugin.plugin_id,
                "plugin_display_name": plugin.plugin_display_name or plugin.plugin_id,
                "plugin_type": plugin.plugin_type,
                "plugin_type_display": plugin.get_plugin_type_display(),
                "summary": plugin.summary,
                "tags": plugin.tags,
                "scenario": plugin.scenario,
                "scenario_display": plugin.get_scenario_display(),
                "popularity": plugin.popularity,
                "status": plugin.status,
                "logo": plugin.logo_base64,
                "author": plugin.author or plugin.create_user,
                "is_official": True,  # TODO
                "category": "event",  # TODO
                "category_display": _("事件插件"),  # TODO 需要进行抽象
                "create_user": plugin.create_user,
                "create_time": utc2biz_str(plugin.create_time),
                "update_user": plugin.update_user,
                "update_time": utc2biz_str(plugin.update_time),
                "main_type": plugin.main_type,
                "main_type_display": plugin.get_main_type_display(),
                "is_installed": False,
                "updatable": False,
                "plugin_instance_id": None,
            }
            if plugin_instance:
                plugin_info.update(
                    {
                        "is_installed": True,
                        "updatable": plugin_instance.version != plugin.version,
                        "plugin_instance_id": plugin_instance.id,
                    }
                )
            data.append(plugin_info)
        result = {
            "count": count,
            "list": data,
        }
        return result


class EventPluginInstanceBaseResource(Resource):
    def __init__(self, context=None):
        super(EventPluginInstanceBaseResource, self).__init__(context)
        self.event_plugin = None

    def validate_poller_data(self, validated_data):
        config_context = {
            param["field"]: param["value"] or param["default_value"] for param in validated_data["config_params"]
        }
        ingest_config_data = jinja_render(self.event_plugin.ingest_config, config_context)
        ingest_serializer = HttpPullInstOptionSerializer(data=ingest_config_data)
        if not ingest_serializer.is_valid():
            raise CustomException(
                _("Resource[{}] 请求参数格式错误：{}").format(
                    self.get_resource_name(), format_serializer_errors(ingest_serializer)
                )
            )

    def format_normalization_config(self, validated_data):
        config_params_schema = {param["field"]: param for param in self.event_plugin.config_params}
        for field, value in validated_data["config_params"].items():
            if field not in config_params_schema:
                continue
            config_params_schema[field].update({"value": value})
        validated_data["config_params"] = list(config_params_schema.values())

        config_context = {
            param["field"]: param["value"] or param["default_value"] for param in validated_data["config_params"]
        }
        config_context["plugin_inst_biz_id"] = validated_data["bk_biz_id"]
        if not validated_data.get("normalization_config"):
            validated_data["normalization_config"] = jinja_render(
                self.event_plugin.normalization_config, config_context
            )
        if not validated_data.get("clean_configs"):
            validated_data["clean_configs"] = jinja_render(self.event_plugin.clean_configs, config_context)

        if self.event_plugin.plugin_type == PluginType.HTTP_PULL:
            self.validate_poller_data(validated_data)


class CreateEventPluginInstanceResource(EventPluginInstanceBaseResource):
    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=False, label="配置别名")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        plugin_id = serializers.RegexField(required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=64, label="插件ID")
        version = serializers.CharField(required=True, label="插件版本号")
        config_params = serializers.DictField(label="配置输入, kv格式")
        normalization_config = NormalizationConfig(many=True, label="字段清洗规则", required=False)
        clean_configs = CleanConfigSerializer(many=True, required=False)

    def validate_request_data(self, request_data):
        validated_data = super(CreateEventPluginInstanceResource, self).validate_request_data(request_data)
        try:
            self.event_plugin = EventPlugin.objects.get(
                plugin_id=validated_data["plugin_id"],
                version=validated_data["version"],
                status__in=[PluginStatus.AVAILABLE, PluginStatus.REMOVE_SOON],
            )
        except EventPlugin.DoesNotExist:
            raise ValidationError(detail=_("选择安装的插件不存在或不可用， 请重新确认"))

        if not validated_data.get("name"):
            # 没有名称内置一个
            validated_data["name"] = f"{self.event_plugin.plugin_display_name}({int(time.time())})"

        if not validated_data.get("ingest_config"):
            validated_data["ingest_config"] = self.event_plugin.ingest_config

        self.format_normalization_config(validated_data)
        return validated_data

    def perform_request(self, validated_request_data):
        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            instance = EventPluginInstance.objects.create(**validated_request_data)
            manager = get_manager(instance)
            manager.access()
        return {"id": instance.id, "data_id": instance.data_id}


class UpdateEventPluginInstanceResource(EventPluginInstanceBaseResource):
    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(required=True, label="配置ID")
        name = serializers.CharField(required=False, label="配置别名")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        config_params = serializers.DictField(label="配置输入, kv格式")
        normalization_config = NormalizationConfig(many=True, label="字段清洗规则", required=False)

    def __init__(self, context=None):
        super(UpdateEventPluginInstanceResource, self).__init__(context)
        self.instance = None

    def validate_request_data(self, request_data):
        validated_data = super(UpdateEventPluginInstanceResource, self).validate_request_data(request_data)
        try:
            self.instance = EventPluginInstance.objects.get(
                id=validated_data["id"], bk_biz_id=validated_data["bk_biz_id"]
            )
        except EventPlugin.DoesNotExist:
            raise ValidationError(detail=_("修改的插件配置信息在当前业务下不存在， 请确认！"))

        self.event_plugin = self.instance.event_plugin
        self.format_normalization_config(validated_data)
        return validated_data

    def perform_request(self, validated_request_data):
        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            for attr, value in validated_request_data.items():
                setattr(self.instance, attr, value)
                self.instance.save()
            manager = get_manager(self.instance)
            manager.access()
        return {"id": self.instance.id, "data_id": self.instance.data_id}


class CollectorProxyHostInfo(ProxyHostInfo):
    """
    collector对应的管控区域列表
    """

    DEFAULT_PROXY_PORT = 4318

    def get_listen_port(self):
        """
        监听端口修改
        """
        return ProxyHostInfo.DEFAULT_PROXY_PORT


class GetEventPluginInstanceResource(Resource):
    """
    获取插件在当前业务下的告警实例
    """

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(required=True, label="插件ID")
        version = serializers.CharField(required=True, label="版本号")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        plugin_info = GetEventPluginResource().perform_request(validated_request_data)
        instances = EventPluginInstance.objects.filter(
            plugin_id=validated_request_data["plugin_id"],
            bk_biz_id__in=[0, validated_request_data["bk_biz_id"]],
        )
        if not instances:
            plugin_info.update({"instances": [], "is_installed": False})
            return plugin_info

        manager = get_manager(instances[0])
        inst_serializer = manager.get_serializer_class()
        serializer_data = inst_serializer(instance=instances, many=True).data
        ingest_config = plugin_info["ingest_config"]
        collect_host = settings.INGESTER_HOST
        ingest_config["ingest_host"] = collect_host
        collect_url = f"{collect_host}/event/{plugin_info['plugin_id']}/"
        # 取一个代表
        instance = instances[0]
        if instances[0].bk_biz_id:
            # 不是全局的，需要单独配置
            collect_url = urllib.parse.urljoin(collect_host, f"/event/{instance.plugin_id}_{instance.data_id}/")
        alert_sources = ingest_config.get("alert_sources", [])
        if ingest_config.get("collect_type") == CollectType.BK_COLLECTOR:
            collect_host = (
                settings.OUTER_COLLOCTOR_HOST if ingest_config.get("is_external") else settings.INNER_COLLOCTOR_HOST
            )
            collect_url = urllib.parse.urljoin(collect_host, "/fta/v1/event/?token={{token}}")
            if alert_sources:
                # 有区分告警推送来源
                collect_url = collect_url + "&source={{source}}"

        ingest_config.update({"ingest_host": collect_host, "push_url": collect_url})
        instances_data = [
            {
                "id": inst_data["id"],
                "params_schema": inst_data["params_schema"],
                "updatable": inst_data["version"] != plugin_info["version"],
                "push_url": collect_url,
                "alert_sources": alert_sources,
            }
            for inst_data in serializer_data
        ]
        plugin_info.update(
            {
                "instances": instances_data,
                "alert_config": AlertConfigSerializer(instances[0].list_alert_config(), many=True).data,
                "normalization_config": serializer_data[0]["normalization_config"],
                "is_installed": True,
            }
        )

        return plugin_info


class GetEventPluginTokenResource(Resource):
    """
    获取事件插件token
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="安装插件配置ID")

    def perform_request(self, validated_data):
        instance = EventPluginInstance.objects.get(id=validated_data["id"])
        if not instance.data_id:
            raise DataIDNotSetError()

        if not instance.token:
            if instance.ingest_config.get("collect_type") != CollectType.BK_COLLECTOR:
                data_info = api.metadata.get_data_id(bk_data_id=instance.data_id)
                instance.token = data_info.get("token", "")
            else:
                instance.token = transform_data_id_to_token(
                    instance.data_id, bk_biz_id=instance.bk_biz_id, app_name=instance.plugin_id
                )
            instance.save()
        return {"token": instance.token}


class TailEventPluginDataResource(Resource):
    """
    获取事件插件上报的最新数据
    """

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(label="安装插件配置ID")
        bk_biz_id = serializers.CharField(label="业务ID")
        count = serializers.IntegerField(default=10, label="消息数量", max_value=100)
        data_type = serializers.ChoiceField(default="raw", choices=["raw", "cleaned"])

    def perform_request(self, validated_data):
        instance = EventPluginInstance.objects.filter(
            plugin_id=validated_data["plugin_id"], bk_biz_id__in=[0, validated_data["bk_biz_id"]]
        ).first()
        if not instance:
            # 没有安装，表示没有数据
            return []
        if not instance.data_id:
            raise DataIDNotSetError()

        data_id_info = api.metadata.get_data_id(bk_data_id=instance.data_id)

        try:
            # 需确定是获取清洗前还是清洗后的数据
            if not validated_data["data_type"] == "cleaned":
                kafka_config = data_id_info["mq_config"]
            else:
                kafka_config = data_id_info["result_table_list"][0]["shipper_list"][0]
        except Exception as e:
            raise GetKafkaConfigError({"msg": e})

        params = {
            "server": settings.BKAPP_KAFKA_DOMAIN or kafka_config["cluster_config"]["domain_name"],
            "port": kafka_config["cluster_config"]["port"],
            "topic": kafka_config["storage_config"]["topic"],
            "username": kafka_config["auth_info"]["username"],
            "password": kafka_config["auth_info"]["password"],
        }

        if isinstance(params["server"], list):
            params["server"] = params["server"][0]

        manager = KafkaManager(**params)
        events = manager.fetch_latest_messages(count=validated_data["count"])
        return events


class DisablePluginCollectResource(Resource):
    """
    停止数据采集
    """

    class RequestSerializer(serializers.Serializer):
        ids = serializers.CharField(label="卸载插件配置ID")

    def perform_request(self, validated_data):
        instances = EventPluginInstance.objects.get(id=validated_data["id"])
        disabled_ids = []
        for instance in instances:
            if not instance.data_id:
                # 没有dataid, 无法操作
                continue
            manager = get_manager(instance)
            manager.switch(False)
            disabled_ids.append(instance.id)
        return {"disabled_ids": disabled_ids}
