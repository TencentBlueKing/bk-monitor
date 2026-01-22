"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

from django.utils.translation import gettext as _
from rest_framework import serializers

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.request import get_request
from bkmonitor.utils.serializers import (
    MetricJsonBaseSerializer,
    MetricJsonSerializer,
    StrictCharField,
    TenantIdField,
)
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    OperatorSystem,
)
from monitor_web.plugin.constant import PARAM_MODE_CHOICES, SCRIPT_TYPE_CHOICES


class CollectorPluginMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorPluginMeta
        fields = "__all__"


class CollectorPluginInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorPluginInfo
        fields = "__all__"


class CollectorPluginConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorPluginConfig
        fields = "__all__"


class CollectorPluginMixin(MetricJsonBaseSerializer):
    class ConfigJsonSeriliazer(serializers.Serializer):
        default = serializers.JSONField(required=True, allow_null=True, label="默认值")
        file_base64 = serializers.CharField(required=False, label="文件Base64")
        mode = serializers.ChoiceField(required=True, choices=PARAM_MODE_CHOICES, label="模式")
        type = serializers.ChoiceField(
            required=True,
            choices=["text", "password", "switch", "file", "encrypt", "host", "service", "code", "list", "custom"],
            label="类型",
        )
        name = serializers.CharField(required=True, label="名称")
        alias = serializers.CharField(required=False, allow_blank=True, default="", label="别名")
        description = StrictCharField(required=True, allow_blank=True, label="描述")
        visible = serializers.BooleanField(required=False, label="是否可见")
        auth_json = serializers.ListField(required=False, label="认证信息")
        key = serializers.CharField(required=False, label="名称")
        required = serializers.BooleanField(required=False, label="是否必填", default=False)
        election = serializers.ListField(required=False, label="列表选项")
        options = serializers.DictField(required=False, label="选项")

    config_json = ConfigJsonSeriliazer(required=False, many=True, default=[], label="采集配置")
    plugin_display_name = StrictCharField(required=True, allow_blank=True, label="插件别名")
    description_md = StrictCharField(required=True, allow_blank=True, trim_whitespace=False, label="描述文件md")
    logo = serializers.CharField(required=True, allow_blank=True, label="logo")
    config_version = serializers.IntegerField(required=False, default=1, label="采集器版本")
    info_version = serializers.IntegerField(required=False, default=1, label="插件信息版本")
    signature = serializers.CharField(required=False, allow_blank=True, label="插件签名")
    is_support_remote = serializers.BooleanField(required=False, label="是否支持远程采集")
    version_log = StrictCharField(required=False, allow_blank=True, label="插件版本日志")

    def validate(self, attrs):
        for config in attrs.get("config_json", []):
            if config["type"] == "switch":
                if config["default"] not in ["true", "false"]:
                    raise ValueError(_("开关必须传布尔型"))
            if config["type"] == "file" and not config.get("file_base64"):
                raise ValueError(_("文件参数必须传base64"))
        return attrs


class CollectorMetaSerializer(serializers.ModelSerializer, CollectorPluginMixin):
    COLLECTOR_PLUGIN_META_FIELDS = ["plugin_id", "plugin_type", "bk_biz_id", "bk_supplier_id", "tag", "label"]

    bk_tenant_id = TenantIdField(label="租户ID")
    plugin_id = serializers.RegexField(required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=30, label="插件ID")
    data_label = serializers.CharField(required=False, default="", label="数据标签", allow_blank=True)
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    bk_supplier_id = serializers.IntegerField(required=False, default=0, label="供应商ID")
    plugin_type = serializers.ChoiceField(
        required=True, choices=[choice[0] for choice in CollectorPluginMeta.PLUGIN_TYPE_CHOICES], label="插件类型"
    )
    tag = StrictCharField(required=False, default="", allow_blank=True, label="标签", allow_null=True)
    label = StrictCharField(required=True, label="二级标签")
    import_plugin_metric_json = MetricJsonSerializer(required=False, many=True, default=[], label="导入插件的指标数据")

    def create(self, validated_data):
        create_data = {
            key: validated_data.get(key) for key in self.COLLECTOR_PLUGIN_META_FIELDS if validated_data.get(key)
        }
        plugin = CollectorPluginMeta.objects.create(bk_tenant_id=validated_data["bk_tenant_id"], **create_data)
        return plugin

    def update(self, instance, validated_data):
        immutable_fields = [
            "plugin_id",
            "config_json",
            "plugin_display_name",
            "metric_json",
            "description_md",
            "logo",
            "config_version",
            "info_version",
        ]
        for field in immutable_fields:
            validated_data.pop(field, None)

        new_label = validated_data.get("label")
        if instance.label != new_label and instance.current_version.stage == "release":
            PluginDataAccessor(instance.current_version, get_request().user.username).modify_label(new_label)

        for attr, value in list(validated_data.items()):
            setattr(instance, attr, value)
        instance.save()

        return instance

    class Meta:
        model = CollectorPluginMeta
        fields = "__all__"
        # 去除插件ID+租户ID的唯一性校验，后续在保存时通过数据库约束进行校验
        validators = []


class ExporterSerializer(CollectorMetaSerializer):
    class CollectorJsonSerializer(serializers.Serializer):
        file_id = serializers.IntegerField(required=True, label="file_id")
        file_name = serializers.CharField(required=True, label="文件名")
        md5 = serializers.CharField(required=True, label="文件内容对应MD5")

    collector_json = serializers.DictField(
        required=True, child=CollectorJsonSerializer(required=False, allow_null=True), label="采集器配置"
    )

    def validate_collector_json(self, value):
        operate_systems = OperatorSystem.objects.values_list("os_type")
        collector_config = {_os[0]: value[_os[0]] for _os in operate_systems if value.get(_os[0])}
        if not collector_config:
            raise serializers.ValidationError(_("collector_json不合法，至少添加一项操作系统相关内容"))
        return collector_config


class JmxSerializer(CollectorMetaSerializer):
    class JmxCollectorJsonSerializer(serializers.Serializer):
        config_yaml = StrictCharField(
            required=True,
        )

    collector_json = JmxCollectorJsonSerializer(required=True, label="采集器配置")


class SNMPSerializer(CollectorMetaSerializer):
    class CollectorJsonSerializer(serializers.Serializer):
        snmp_version = serializers.ChoiceField(required=True, choices=("1", "2", "3"), label="SNMP插件版本")
        filename = serializers.CharField(required=True, label="Yaml配置文件名")
        config_yaml = StrictCharField(
            required=True,
        )

        def validate_snmp_version(self, value):
            return re.findall(r"\d+", value)[0]

    collector_json = CollectorJsonSerializer(required=True, label="采集器配置")


class LogSerializer(CollectorMetaSerializer):
    rules = serializers.ListField(required=True, label="采集器配置")
    collector_json = serializers.DictField(required=False, default={}, label="采集器配置")


class SNMPTrapSerializer(CollectorMetaSerializer):
    yaml = serializers.DictField(required=False, default={}, label="yaml配置文件")
    snmp_trap = serializers.DictField(required=False, default={}, label="snmp trap 运行参数")
    collector_json = serializers.DictField(required=False, default={}, label="采集器配置")


class ProcessSerializer(CollectorMetaSerializer):
    collector_json = serializers.DictField(required=False, default={}, label="采集器配置")
    # match_type = serializers.ChoiceField(required=True, label="进程匹配类型", choices=PROCESS_MATCH_TYPE_CHOICES)
    # pid_path = serializers.CharField(required=False, label="pid文件路径")
    # process_name = serializers.CharField(required=False, label="进程名称，空默认为二进制名称")
    # match_pattern = serializers.CharField(required=False, label="进程匹配关键字")
    # exclude_pattern = serializers.CharField(required=False, label="进程排除正则")
    # port_detect = serializers.BooleanField(required=False, label="是否端口检测", default=True)
    # labels = serializers.DictField(required=False, default={}, label="自定义标签")


class K8sSerializer(CollectorMetaSerializer):
    class CollectorJsonSerializer(serializers.Serializer):
        template = serializers.CharField(label="模板文件")
        values = serializers.JSONField(label="默认配置", default=dict)

    collector_json = CollectorJsonSerializer(required=True, label="采集器配置")


class DataDogSerializer(CollectorMetaSerializer):
    class CollectorJsonSerializer(serializers.Serializer):
        class OsSerializer(serializers.Serializer):
            file_id = serializers.IntegerField(required=True, label="file_id")
            file_name = serializers.CharField(required=True, label="文件名")
            md5 = serializers.CharField(required=True, label="文件内容对应MD5")

        datadog_check_name = serializers.CharField(required=True, label="校验名")
        config_yaml = serializers.CharField(required=True, label="配置内容")
        windows = OsSerializer(required=False, label="{}配置".format("windows"))
        linux = OsSerializer(required=False, label="{}配置".format("linux"))
        aix = OsSerializer(required=False, label="{}配置".format("aix"))

    collector_json = CollectorJsonSerializer(required=True, label="采集器配置")

    def validate_collector_json(self, value):
        operate_systems = OperatorSystem.objects.values_list("os_type")
        collector_config = {_os[0]: value[_os[0]] for _os in operate_systems if value.get(_os[0])}
        if not collector_config:
            raise serializers.ValidationError(_("collector_json不合法，至少添加一项操作系统相关内容"))
        return value


class ScriptSerializer(CollectorMetaSerializer):
    class CollectorJsonSerializer(serializers.Serializer):
        filename = serializers.CharField(required=True, label="脚本文件名")
        type = serializers.ChoiceField(required=True, label="脚本类型", choices=SCRIPT_TYPE_CHOICES)
        script_content_base64 = serializers.CharField(required=True, label="脚本内容")

    collector_json = serializers.DictField(required=True, child=CollectorJsonSerializer(), label="采集器配置")

    def validate_collector_json(self, value):
        operate_systems = OperatorSystem.objects.values_list("os_type")
        for i in operate_systems:
            if value.get(i[0]):
                return value
        raise serializers.ValidationError(_("collector_json不合法，至少添加一项操作系统相关内容"))


class PushgatewaySerializer(CollectorMetaSerializer):
    collector_json = serializers.DictField(default=None, allow_null=True, label="采集器配置")


class PluginRegisterRequestSerializer(serializers.Serializer):
    plugin_id = serializers.CharField(required=True, label="插件ID")
    config_version = serializers.IntegerField(required=True, label="采集器版本")
    info_version = serializers.IntegerField(required=True, label="采集器信息版本")


class ReleaseSerializer(serializers.Serializer):
    config_version = serializers.IntegerField(required=True, label="采集器版本")
    info_version = serializers.IntegerField(required=True, label="采集器信息版本")
    token = serializers.ListField(required=True, label="凭据")


class StartDebugSerializer(serializers.Serializer):
    class TargetNodesSerializer(serializers.Serializer):
        """
        远程采集目标主机（目前仅snmp在使用，为手动输入，因此不使用bk_host_id）
        """

        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID", default=0)
        ip = serializers.CharField(required=True, label="ip地址")

    class HostInfoSerializer(serializers.Serializer):
        """
        debug下发主机
        """

        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
        bk_supplier_id = serializers.IntegerField(default=0, label="服务商ID")
        ip = serializers.CharField(required=False, label="ip地址")

        bk_host_id = serializers.IntegerField(required=False, label="主机ID")

        def validate(self, attrs):
            if not attrs.get("bk_host_id") and not attrs.get("ip"):
                raise serializers.ValidationError(_("bk_host_id和ip不能同时为空"))
            return attrs

    class ParamSerializer(serializers.Serializer):
        class CollectorParamSerializer(serializers.Serializer):
            host = serializers.CharField(default="127.0.0.1", label="采集域名")
            port = serializers.CharField(required=False, label="采集端口")
            period = serializers.CharField(required=True, label="采集周期(秒)")
            metrics_url = serializers.CharField(required=False, label="采集URL", allow_blank=True)
            username = serializers.CharField(required=False, label="用户名", allow_blank=True)
            password = serializers.CharField(required=False, label="密码", allow_blank=True)

        collector = CollectorParamSerializer(required=False, allow_null=True)
        plugin = serializers.DictField(default={}, label="插件调试参数")

    config_version = serializers.CharField(required=True, label="config版本")
    info_version = serializers.CharField(required=True, label="info版本")
    param = ParamSerializer(required=False, label="调试参数")
    host_info = HostInfoSerializer(required=True, label="目标主机")
    target_nodes = TargetNodesSerializer(required=False, many=True, label="远程采集目标节点")
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def validate(self, attrs):
        attrs["host_info"]["bk_biz_id"] = validate_bk_biz_id(attrs.pop("bk_biz_id"))
        return attrs


class TaskIdSerializer(serializers.Serializer):
    task_id = serializers.CharField(required=True, label="任务ID")
