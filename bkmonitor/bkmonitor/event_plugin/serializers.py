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
import base64
import datetime
import time

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.action.serializers import HttpCallBackConfigSlz
from bkmonitor.event_plugin.constant import EVENT_NORMAL_FIELDS
from bkmonitor.models import AlertConfig, EventPluginInstance, EventPluginV2
from bkmonitor.models.fta.constant import PluginSourceFormat
from bkmonitor.utils.template import jinja_render
from bkmonitor.utils.user import get_global_user


# ===================== #
# Base                  #
# ===================== #
class RuleSerializer(serializers.Serializer):
    key = serializers.CharField(label="匹配字段")
    value = serializers.ListField(label="匹配值", child=serializers.CharField())
    method = serializers.ChoiceField(label="匹配方法", choices=["eq", "neq", "reg"])
    condition = serializers.ChoiceField(label="复合条件", choices=["and", "or", ""], default="")


class AlertConfigSerializer(serializers.Serializer):
    rules = RuleSerializer(many=True, label="规则参数", default=[])
    name = serializers.CharField(label="告警名称")


class NormalizationConfig(serializers.Serializer):
    field = serializers.CharField(label="映射字段")
    expr = serializers.CharField(label="表达式", allow_blank=True)
    option = serializers.DictField(label="选项", required=False, default={})


class CleanConfigSerializer(serializers.Serializer):
    rules = RuleSerializer(many=True, label="规则参数", default=[])
    alert_config = AlertConfigSerializer(many=True, label="告警名称清洗规则", default=[])
    normalization_config = NormalizationConfig(many=True, label="字段清洗规则")


class ConfigParamSerializer(serializers.Serializer):
    field = serializers.CharField(label="字段key", required=True)
    name = serializers.CharField(label="字段显示名", required=True)
    desc = serializers.CharField(label="字段描述", required=False, allow_blank=True)
    value = serializers.CharField(label="字段值", required=False, allow_blank=True)
    default_value = serializers.CharField(label="字段默认值", required=False, allow_blank=True)
    is_required = serializers.BooleanField(label="是否必填", required=False, default=False)
    is_hidden = serializers.BooleanField(label="是否必填", required=False, default=False)
    is_sensitive = serializers.BooleanField(label="是否必填", required=False, default=False)


class EventPluginBaseSerializer(serializers.ModelSerializer):
    plugin_id = serializers.RegexField(required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=64, label="插件ID")
    version = serializers.CharField(required=False, default="", allow_blank=True, label="插件版本号")
    config_params = ConfigParamSerializer(many=True, required=False, label="配置参数内容")
    ingest_config = serializers.DictField(label="接入配置")
    normalization_config = NormalizationConfig(many=True, label="字段清洗规则")
    alert_config = AlertConfigSerializer(many=True, write_only=True, required=False)
    bk_biz_id = serializers.CharField(required=False, default=0, allow_blank=True, label="业务ID")
    clean_configs = CleanConfigSerializer(many=True, required=False)

    @staticmethod
    def render_ingest_config(data):
        """
        通过填写的参数进行渲染
        :param data:插件配置参数
        :return:
        """
        params_schema = []
        config_context = {}
        for param in data["config_params"]:
            required = bool(param.get("is_required"))
            if not param.get("is_hidden"):
                # 不隐藏的参数，才显示在前端
                params_schema.append(
                    {
                        "formItemProps": {
                            "label": param["name"],
                            "required": required,
                            "sensitive": param["is_sensitive"],
                            "property": param["field"],
                            "help_text": param.get("desc", ""),
                        },
                        "type": "input",
                        "key": param["field"],
                        "value": param["value"] or param["default_value"],
                        "formChildProps": {"placeholder": _("请填写对应的参数")},
                        "rules": [{"message": _("必填项不可为空"), "required": True, "trigger": "blur"}] if required else [],
                    }
                )
            config_context.update({param["field"]: param["value"] or param["default_value"]})

        data["ingest_config"] = jinja_render(data["ingest_config"], config_context)
        data["params_schema"] = params_schema

    @staticmethod
    def translate_normalization_config(data):
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
        data["normalization_config"] = fields

    def to_representation(self, instance):
        data = super(EventPluginBaseSerializer, self).to_representation(instance)
        self.translate_normalization_config(data)
        self.render_ingest_config(data)
        return data


class EventPluginSerializer(EventPluginBaseSerializer):
    logo = serializers.CharField(required=False, default="", allow_blank=True, label="logo")
    tags = serializers.ListField(child=serializers.CharField(), label="标签", default=[])

    def to_internal_value(self, data):
        internal_data = super(EventPluginSerializer, self).to_internal_value(data)
        if not internal_data.get("version"):
            internal_data["version"] = "{}.{}".format(datetime.datetime.now().strftime("%Y.%m.%d"), int(time.time()))
        internal_data["is_latest"] = True
        return internal_data

    def create_alert_configs(self, validated_data):
        if validated_data.get("alert_config") is None:
            return
        AlertConfig.objects.filter(plugin_id=validated_data["plugin_id"]).delete()
        alert_configs = [
            AlertConfig(
                plugin_id=validated_data["plugin_id"],
                name=alert_config["name"],
                rules=alert_config["rules"],
                order=order,
            )
            for order, alert_config in enumerate(validated_data["alert_config"])
        ]
        AlertConfig.objects.bulk_create(alert_configs)

    def save_logo_file(self, instance, logo_base64):
        logo_base64 = logo_base64.split(",")[-1]
        img = ContentFile(base64.b64decode(logo_base64))
        instance.logo.save(instance.plugin_id + ".png", img)

    def create(self, validated_data):
        validated_data["create_user"] = get_global_user() or "system"

        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            self.create_alert_configs(validated_data)
            validated_data.pop("alert_config", None)
            logo = validated_data.pop("logo", None)
            instance = EventPluginV2.objects.create(**validated_data)
            if logo:
                self.save_logo_file(instance, logo)
            #  修改历史最新版本属性
            EventPluginV2.objects.filter(plugin_id=instance.plugin_id).exclude(id=instance.id).update(is_latest=False)
            return instance

    def update(self, instance, validated_data):
        for field in self.Meta.write_once_fields:
            validated_data.pop(field, None)
        with transaction.atomic(settings.BACKEND_DATABASE_NAME):
            if "alert_config" in validated_data:
                validated_data["plugin_id"] = instance.plugin_id
                self.create_alert_configs(validated_data)
                validated_data.pop("alert_config", None)

            logo = validated_data.pop("logo", None)
            if logo:
                self.save_logo_file(instance, logo)

            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()
            return instance

    class Meta:
        model = EventPluginV2

        # 只读字段
        read_only_fields = [
            "popularity",
            "status",
            "create_time",
            "create_user",
            "update_time",
            "update_user",
            "package_dir",
        ]

        # 创建后只读字段
        write_once_fields = [
            "plugin_id",
            "version",
            "plugin_type",
            "bk_biz_id",
        ]

        fields = (
            [
                "author",
                "plugin_display_name",
                "scenario",
                "summary",
                "description",
                "tutorial",
                "logo",
                "tags",
                "ingest_config",
                "normalization_config",
                "clean_configs",
                "alert_config",
                "config_params",
            ]
            + read_only_fields
            + write_once_fields
        )


# ===================== #
# HTTP Push             #
# ===================== #
class IngestConfigSerializer(serializers.Serializer):
    source_format = serializers.ChoiceField(
        label="源数据格式", choices=PluginSourceFormat.to_choice(), default=PluginSourceFormat.JSON
    )
    multiple_events = serializers.BooleanField(label="是否需要拆分事件", default=False)
    events_path = serializers.CharField(label="事件所在路径", default="", allow_blank=True)
    collect_type = serializers.CharField(label="接收类型", default="bk-ingestor", allow_blank=False)
    is_external = serializers.BooleanField(label="是否依赖外网服务", default=False)
    alert_sources = serializers.ListField(label="告警来源", default=list)


class HttpPushPluginSerializer(EventPluginSerializer):
    """
    插件
    """

    ingest_config = IngestConfigSerializer(label="接入配置")


class HttpPushPluginInstSerializer(EventPluginBaseSerializer):
    """
    实例， 不需要logo信息
    """

    ingest_config = IngestConfigSerializer(label="接入配置")

    class Meta:
        model = EventPluginInstance
        fields = (
            "id",
            "plugin_id",
            "version",
            "ingest_config",
            "normalization_config",
            "clean_configs",
            "config_params",
            "data_id",
            "bk_biz_id",
        )


# ===================== #
# HTTP Pull             #
# ===================== #
class PaginationOptionSerializer(serializers.Serializer):
    max_size = serializers.IntegerField(label="最大拉取数量", default=0)
    page_size = serializers.IntegerField(label="单次拉取数量", min_value=1)
    total_path = serializers.CharField(label="总条目数量字段路径")


class PaginationSerializer(serializers.Serializer):
    type = serializers.ChoiceField(label="分页方式", choices=["page_number", "limit_offset"])
    option = PaginationOptionSerializer(required=False)


class HttpPullOptionSerializer(HttpCallBackConfigSlz, IngestConfigSerializer):
    url = serializers.CharField(required=True)
    method = serializers.CharField(required=False, default="GET")
    # 请求调度
    interval = serializers.CharField(label="请求周期", default="60")
    overlap = serializers.CharField(label="重叠时间", default="0")
    timeout = serializers.CharField(label="请求超时", default="60")
    time_format = serializers.CharField(label="时间格式", default="", allow_blank=True)

    pagination = PaginationSerializer(label="分页配置", required=False)


class HttpPullInstOptionSerializer(HttpCallBackConfigSlz, IngestConfigSerializer):
    # 事件解析
    url = serializers.URLField(required=True)
    # 请求调度
    interval = serializers.IntegerField(label="请求周期", min_value=10, default=60)
    overlap = serializers.IntegerField(label="重叠时间", min_value=0, default=0)
    timeout = serializers.IntegerField(label="请求超时", min_value=0, default=60)
    time_format = serializers.CharField(label="时间格式", default="", allow_blank=True)

    pagination = PaginationSerializer(label="分页配置", required=False)


class HttpPullPluginSerializer(EventPluginSerializer):
    ingest_config = HttpPullOptionSerializer(label="接入配置")


class HttpPullPluginInstSerializer(EventPluginBaseSerializer):
    ingest_config = HttpPullInstOptionSerializer(label="接入配置")

    class Meta:
        model = EventPluginInstance
        fields = (
            "id",
            "plugin_id",
            "version",
            "ingest_config",
            "normalization_config",
            "clean_configs",
            "config_params",
            "data_id",
            "bk_biz_id",
        )
